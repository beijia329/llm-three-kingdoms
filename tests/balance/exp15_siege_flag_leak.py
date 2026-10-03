#!/usr/bin/env python3
"""实验 15：围城标记泄漏（stale is_besieged / besieging_armies）发生率实测

疑点
----
`City.is_besieged` / `City.besieging_armies` 的**唯一**清理点在
`game/engine.py:1170`，且只在「该城发生并被结算了一场战斗」时执行：

    if defender_city is not None:
        defender_city.is_besieged = False
        defender_city.besieging_armies = []

但标记的**写入点**是 `game/battle/army_movement.py:364`（军队抵达敌城时），
它在**行军相位**执行，早于战斗结算。两条路径之间若存在「设了标记但不会走到
结算」的分支，标记就会永久残留：

  A. `battle_scheduler._create_battle_context` 在
     `attacker_faction == defender_faction` 时（`battle_scheduler.py:177-184`）
     把军队转 GARRISONED、`soldiers=0` 并 **return None** —— 该城不会产生战斗，
     于是 `_apply_battle_result` 的清理语句永不执行。
  B. 围城军队在未触发该城战斗的情况下消失（战死至 0 / 撤退改道 /
     被 `_redirect_army_home` 送回 / 被 `_sweep_stranded_armies` 清理）。

而 `is_besieged` 在全局**只有一个游戏效果**：`game/systems/city_system.py:376`
每回合 `-3 民心`（民心下限 0，不可逆）。

方法（含阳性对照）
------------------
本项目纪律：**空输出不等于不存在**，必须证明探针有能力观察到现象。
故本探针在**两个相位**分别采样（用相位钩子，同时顺带验证钩子确实可用）：

  1. `AFTER_MOVEMENT`（标记刚写完、战斗尚未结算）→ **阳性对照**：
     这里若恒为 0，说明探针无效，不能据此说"无泄漏"。
  2. `TURN_END`（战斗结算完毕后）→ **泄漏检测**：
     此处仍为 True 的城，就是跨回合残留的泄漏。

另外独立统计 `besieging_armies` 中的**幽灵 id**（指向已不存在的军队）。

运行：
    PYTHONHASHSEED=0 ./venv/bin/python tests/balance/exp15_siege_flag_leak.py --games 5 --turns 48
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
from typing import Any, Dict, List

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import pacing_lib as P  # noqa: E402
from game.data_loader import load_game_data  # noqa: E402
from game.engine import GameEngine  # noqa: E402
from game.models import ArmyStatus  # noqa: E402
from game.turn_phase import TurnPhase, clear_phase_hooks, register_phase_hook  # noqa: E402


class Probe:
    """相位采样式探针。"""

    def __init__(self) -> None:
        # 阳性对照：AFTER_MOVEMENT 相位
        self.mv_flagged: List[int] = []
        self.mv_flagged_with_live: List[int] = []
        # 泄漏检测：TURN_END 相位
        self.end_flagged: List[int] = []
        self.end_leaked: List[int] = []
        # 幽灵 id 统计
        self.ghost_id_city_turns: int = 0
        # 泄漏明细（城市名 -> 首次泄漏回合）
        self.leak_detail: Dict[str, int] = {}
        # 采样相位对应的回合号
        self._turn_of_sample: int = 0

    # ---- 工具 ----
    @staticmethod
    def _live_besiegers(engine: GameEngine, city) -> List[str]:
        """该城中「活着的围城军队」id（仍在 armies 里且状态 == BESIEGING）。"""
        out: List[str] = []
        for aid in city.besieging_armies:
            army = engine.armies.get(aid)
            if army is not None and army.status == ArmyStatus.BESIEGING:
                out.append(aid)
        return out

    @staticmethod
    def _ghost_ids(engine: GameEngine, city) -> List[str]:
        """该城 besieging_armies 中已不存在的军队 id。"""
        return [aid for aid in city.besieging_armies if aid not in engine.armies]

    # ---- 钩子 ----
    def hook_after_movement(self, engine: GameEngine, result: Dict[str, Any]) -> None:
        flagged = [c for c in engine.cities.values() if c.is_besieged]
        self.mv_flagged.append(len(flagged))
        self.mv_flagged_with_live.append(
            sum(1 for c in flagged if self._live_besiegers(engine, c))
        )

    def hook_turn_end(self, engine: GameEngine, result: Dict[str, Any]) -> None:
        flagged = [c for c in engine.cities.values() if c.is_besieged]
        leaked = [c for c in flagged if not self._live_besiegers(engine, c)]
        self.end_flagged.append(len(flagged))
        self.end_leaked.append(len(leaked))
        for c in leaked:
            self.leak_detail.setdefault(c.name, engine.turn)
        for c in engine.cities.values():
            if self._ghost_ids(engine, c):
                self.ghost_id_city_turns += 1


def run_probe(game_seed: int, max_turns: int) -> Dict[str, Any]:
    """跑一局，统计围城标记泄漏。"""
    clear_phase_hooks()
    probe = Probe()
    register_phase_hook(
        TurnPhase.AFTER_MOVEMENT, probe.hook_after_movement,
        priority=900, name="probe_after_movement",
    )
    register_phase_hook(
        TurnPhase.TURN_END, probe.hook_turn_end,
        priority=900, name="probe_turn_end",
    )

    engine = GameEngine(seed=game_seed)
    engine.init_game(load_game_data())
    engine.max_turns = int(max_turns)
    players = P.make_players(game_seed)

    crashed = None
    try:
        while not engine.game_over:
            for f in P.FACTION_KEYS:
                obs = engine.get_observation(f)
                for cmd in players[f].get_commands(obs):
                    engine.execute_command(cmd)
            engine.process_turn()
    except Exception as exc:
        crashed = repr(exc)

    clear_phase_hooks()

    return {
        "seed": game_seed,
        "turns": engine.turn,
        "crashed": crashed,
        # 阳性对照
        "mv_turns_with_flag": sum(1 for n in probe.mv_flagged if n > 0),
        "mv_peak": max(probe.mv_flagged) if probe.mv_flagged else 0,
        "mv_total": sum(probe.mv_flagged),
        "mv_peak_with_live": max(probe.mv_flagged_with_live) if probe.mv_flagged_with_live else 0,
        # 泄漏
        "end_turns_with_flag": sum(1 for n in probe.end_flagged if n > 0),
        "end_peak": max(probe.end_flagged) if probe.end_flagged else 0,
        "end_total": sum(probe.end_flagged),
        "end_peak_leaked": max(probe.end_leaked) if probe.end_leaked else 0,
        "leak_detail": dict(probe.leak_detail),
        "ghost_id_city_turns": probe.ghost_id_city_turns,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="围城标记泄漏发生率实测")
    ap.add_argument("--games", type=int, default=5)
    ap.add_argument("--turns", type=int, default=48)
    ap.add_argument("--seed0", type=int, default=42)
    args = ap.parse_args()

    P.ensure_reproducible()

    print("=" * 78)
    print("实验 15：围城标记泄漏（stale is_besieged）发生率实测")
    print(f"games={args.games}  turns={args.turns}  seed0={args.seed0}")
    print("=" * 78)

    rows = []
    for i in range(args.games):
        seed = args.seed0 + i
        r = run_probe(seed, args.turns)
        rows.append(r)
        crash = f"  ⚠️ {r['crashed']}" if r["crashed"] else ""
        print(f"\n--- seed={seed} ---{crash}")
        print(
            f"  [阳性对照 AFTER_MOVEMENT] 有标记的回合 {r['mv_turns_with_flag']}/{r['turns']}"
            f"  峰值 {r['mv_peak']} 城（其中同时有活围城军的峰值 {r['mv_peak_with_live']}）"
            f"  累计 {r['mv_total']} 城·回合"
        )
        print(
            f"  [泄漏检测 TURN_END]   仍有标记的回合 {r['end_turns_with_flag']}/{r['turns']}"
            f"  峰值 {r['end_peak']} 城"
            f"  其中无活围城军的峰值 {r['end_peak_leaked']}"
        )
        print(f"  [幽灵 id] 含不存在军队 id 的城市·回合数 = {r['ghost_id_city_turns']}")
        if r["leak_detail"]:
            print(f"  ✗ 跨回合残留: {r['leak_detail']}")

    print("\n" + "=" * 78)
    print("汇总")
    print("=" * 78)

    # 先判探针有效性
    valid = [r for r in rows if r["mv_turns_with_flag"] > 0]
    print(f"\n【探针有效性】阳性对照命中的对局: {len(valid)}/{len(rows)}")
    if not valid:
        print("  🔴 阳性对照未命中 —— 本轮数据**不能**用于判定「无泄漏」，先修探针。")
        return 2
    print(
        f"  阳性对照：有标记的回合数 "
        f"{[r['mv_turns_with_flag'] for r in rows]}（共 {sum(r['mv_turns_with_flag'] for r in rows)} 个回合观察到围城标记）"
    )

    print("\n【泄漏检测】")
    print(f"  终局相位仍有标记的回合数: {[r['end_turns_with_flag'] for r in rows]}")
    print(f"  终局相位标记峰值城数:     {[r['end_peak'] for r in rows]}")
    print(f"  其中无活围城军的峰值:     {[r['end_peak_leaked'] for r in rows]}")
    print(f"  幽灵 id 城市·回合数:      {[r['ghost_id_city_turns'] for r in rows]}")

    total_leak = sum(r["end_peak_leaked"] for r in rows)
    total_ghost = sum(r["ghost_id_city_turns"] for r in rows)
    print(f"\n  合计：跨回合残留城（峰值口径）= {total_leak}；幽灵 id 城市·回合 = {total_ghost}")
    if total_leak == 0 and total_ghost == 0:
        print("  ✅ 在阳性对照有效的前提下，未观察到标记泄漏。")
    else:
        print("  🔴 观察到标记泄漏，见上方明细。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
