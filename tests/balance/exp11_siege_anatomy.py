#!/usr/bin/env python3
"""实验 11：攻城战解剖——63% 攻方伤亡到底产生在哪一环。

【为什么要做】quality-lead 的 exp5/exp6 给出结论"28 场围城全 siege、攻方伤亡
63.2%、无一攻下"，但**没有拆开战斗内部过程**。本脚本在 BattleResolver.resolve_battle
外层加钩子，逐场记录：
  - 攻守初始兵力比（判断攻方是否本就兵力不足）
  - 战斗结果分布（WIN / DEFENDER_WIN / DRAW / RETREAT）
  - 是否进入过巷战（STREET）
  - 城墙 max/current（判断 B-8 城墙永久变厚的影响）
  - 围城阶段耗了几回合、巷战耗了几回合

单变量：无（纯观测）。跑完输出聚合表 + 落 JSON。

运行：
    PYTHONHASHSEED=0 ./venv/bin/python tests/balance/exp11_siege_anatomy.py --games 5 --turns 48
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from typing import Any, Dict, List

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import pacing_lib as P           # noqa: E402
from game.battle.battle_resolver import BattleResolver   # noqa: E402
from game.data_loader import load_game_data              # noqa: E402
from game.engine import GameEngine                       # noqa: E402
from game.models import BattlePhase                      # noqa: E402

_FACTION_KEYS = list(P.FACTION_KEYS)


def run_game_capture(game_seed: int, max_turns: int) -> Dict[str, Any]:
    """跑一局，捕获全部战斗明细。"""
    records: List[Dict[str, Any]] = []

    original = BattleResolver.resolve_battle

    def patched(self, ctx):  # type: ignore[no-untyped-def]
        # 记录进入战斗前后的状态
        atk_initial = ctx.attacker_total_soldiers
        dfd_initial = ctx.defender_total_soldiers
        wall_max = ctx.wall_max_hp
        wall_cur = ctx.wall_hp

        # 逐回合阶段轨迹：通过包装 process_round 记录
        phase_trace: List[str] = []
        orig_round = self.process_round

        def round_spy(c):  # type: ignore[no-untyped-def]
            phase_trace.append(c.battle_phase.value)
            return orig_round(c)

        self.process_round = round_spy  # type: ignore[method-assign]
        try:
            result = original(self, ctx)
        finally:
            self.process_round = orig_round  # type: ignore[method-assign]

        records.append({
            "turn": ctx.turn,
            "attacker": ctx.attacker_faction,
            "defender": ctx.defender_faction,
            "city": ctx.defender_city,
            "atk_initial": atk_initial,
            "dfd_initial": dfd_initial,
            "atk_remaining": ctx.attacker_total_soldiers,
            "dfd_remaining": ctx.defender_total_soldiers,
            "atk_casualties": result.attacker_casualties,
            "dfd_casualties": result.defender_casualties,
            "result": result.result.value,
            "wall_max_at_entry": wall_max,
            "wall_hp_at_entry": wall_cur,
            "wall_hp_at_exit": ctx.wall_hp,
            "rounds": ctx.round_count,
            "phases": phase_trace,
            "entered_street": BattlePhase.STREET.value in phase_trace,
        })
        return result

    BattleResolver.resolve_battle = patched  # type: ignore[assignment]
    try:
        engine = GameEngine(seed=game_seed)
        engine.init_game(load_game_data())
        engine.max_turns = int(max_turns)
        players = P.make_players(game_seed)
        turns = 0
        while not engine.game_over and turns <= P.SAFETY_MAX_ITER:
            for f in _FACTION_KEYS:
                obs = engine.get_observation(f)
                for cmd in players[f].get_commands(obs):
                    engine.execute_command(cmd)
            engine.process_turn()
            turns += 1
    finally:
        BattleResolver.resolve_battle = original  # type: ignore[assignment]

    return {"seed": game_seed, "records": records, "turns": turns}


def analyze(all_records: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not all_records:
        return {}

    n = len(all_records)
    out: Dict[str, Any] = {"battles": n}

    out["result_dist"] = dict(Counter(r["result"] for r in all_records))
    out["street_share"] = sum(1 for r in all_records if r["entered_street"]) / n

    # 攻守兵力比 → 结果
    ratio_buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in all_records:
        d = max(r["dfd_initial"], 1)
        ratio = r["atk_initial"] / d
        if ratio < 0.75:
            b = "<0.75"
        elif ratio < 1.25:
            b = "0.75-1.25"
        elif ratio < 2.0:
            b = "1.25-2.0"
        else:
            b = ">=2.0"
        ratio_buckets[b].append(r)

    out["by_force_ratio"] = {}
    for b in ("<0.75", "0.75-1.25", "1.25-2.0", ">=2.0"):
        g = ratio_buckets.get(b, [])
        if not g:
            continue
        wins = sum(1 for r in g if r["result"] == "attacker_win")
        out["by_force_ratio"][b] = {
            "n": len(g),
            "attacker_win_rate": round(wins / len(g), 3),
            "mean_atk_loss_pct": round(
                statistics.mean(
                    r["atk_casualties"] / max(r["atk_initial"], 1) for r in g
                ) * 100, 1),
            "mean_dfd_loss_pct": round(
                statistics.mean(
                    r["dfd_casualties"] / max(r["dfd_initial"], 1) for r in g
                ) * 100, 1),
        }

    out["mean_wall_max"] = round(statistics.mean(r["wall_max_at_entry"] for r in all_records), 1)
    out["median_wall_max"] = statistics.median(r["wall_max_at_entry"] for r in all_records)
    out["max_wall_max"] = max(r["wall_max_at_entry"] for r in all_records)
    out["mean_rounds"] = round(statistics.mean(r["rounds"] for r in all_records), 1)

    # 撤退/平局时的剩余回合
    draws = [r for r in all_records if r["result"] == "draw"]
    if draws:
        out["draw_mean_rounds"] = round(statistics.mean(r["rounds"] for r in draws), 1)
        out["draw_wall_remaining"] = round(
            statistics.mean(r["wall_hp_at_exit"] for r in draws), 1)
        out["draw_entered_street"] = sum(1 for r in draws if r["entered_street"]) / len(draws)

    rets = [r for r in all_records if r["result"] == "retreat"]
    if rets:
        out["retreat_mean_rounds"] = round(statistics.mean(r["rounds"] for r in rets), 1)

    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=5)
    ap.add_argument("--turns", type=int, default=48)
    ap.add_argument("--seed0", type=int, default=1)
    ap.add_argument("--out", default=os.path.join(_HERE, "data", "exp11_siege_anatomy.json"))
    args = ap.parse_args()

    P.ensure_reproducible()
    print(P.__doc__ and "")

    all_records: List[Dict[str, Any]] = []
    for i in range(args.games):
        seed = args.seed0 + i
        res = run_game_capture(seed, args.turns)
        all_records.extend(res["records"])
        print(f"  seed={seed} battles={len(res['records'])}")

    summary = analyze(all_records)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"summary": summary, "records": all_records}, fh,
                  ensure_ascii=False, indent=1)

    print("\n=== 战斗结果分布 ===")
    for k, v in sorted(summary["result_dist"].items(), key=lambda x: -x[1]):
        print(f"  {k:16s} {v:4d}  ({v/summary['battles']*100:.1f}%)")
    print(f"\n进入过巷战的比例: {summary['street_share']*100:.1f}%")
    print(f"平均战斗回合数: {summary['mean_rounds']}")

    print("\n=== 按攻守兵力比分组 ===")
    print("  兵力比      场次   攻方胜率   攻方伤亡%   守方伤亡%")
    for b in ("<0.75", "0.75-1.25", "1.25-2.0", ">=2.0"):
        g = summary["by_force_ratio"].get(b)
        if g:
            print(f"  {b:10s} {g['n']:4d}   {g['attacker_win_rate']*100:6.1f}%   "
                  f"{g['mean_atk_loss_pct']:7.1f}%   {g['mean_dfd_loss_pct']:7.1f}%")

    print("\n=== 城墙 ===")
    print(f"  入场时 wall_max 均值 {summary['mean_wall_max']} / 中位 {summary['median_wall_max']}"
          f" / 最大 {summary['max_wall_max']}")

    if "draw_mean_rounds" in summary:
        print("\n=== 平局（DRAW）拆解 ===")
        print(f"  平均打到第 {summary['draw_mean_rounds']} 回合")
        print(f"  退场时城墙剩余均值 {summary['draw_wall_remaining']}")
        print(f"  已进巷战比例 {summary['draw_entered_street']*100:.1f}%")
    if "retreat_mean_rounds" in summary:
        print(f"\n=== 撤退（RETREAT）平均第 {summary['retreat_mean_rounds']} 回合 ===")

    print(f"\n明细已写入 {args.out}")


if __name__ == "__main__":
    main()
