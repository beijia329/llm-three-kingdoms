#!/usr/bin/env python3
"""实验 20：`GameEngine.load_state_snapshot` 可用性实测（结论：不可用，已改为显式抛错）

背景
----
quality-lead 的审计（`docs/qa/2026-10-quality-audit.md`）指出
`game/engine.py` 的 `load_state_snapshot` 是「只写不读」：
`get_state_snapshot()` 在 `api/game_manager.py` 被调用（喂 `/api/state`），
而 `load_state_snapshot()` **全仓零调用者**。

两种可能，必须区分：
  A. **功能完整、只是没接线** → 补个 save/load 入口即可用；
  B. **实现不完整** → 直接接线会得到一个坏掉的对局。

本实验的实测结论是 **B**，而且更糟：它会**静默降级**。
实测（`--turns 12`，seed=42）：

    原引擎：turn=13  hex_map=已建  season=WINTER  外交关系=69 条
    恢复后：turn=13  hex_map=None  season=SPRING  外交关系=None
    继续推进 12 回合 → 表面"成功"（turn=25）
    但后台抛 AttributeError: 'NoneType' object has no attribute 'set_status'
    （被引擎的命令级 try/except 吞掉，外表看不出来）

根因不是"接线漏了"，而是**存档格式缺字段**（2026-10-03 实读 + 实跑）。
`GameState` 快照只有 11 个字段：

    turn / max_turns / year / seed / game_over / winner /
    cities / armies / generals / messages / turn_logs

两样关键东西都不在：
  1. **无地图/地块/领地字段** → `hex_map` 依赖原始地图数据构建，造不出来；
  2. **无外交关系字段** → 恢复后外交全丢。
     ⚠️ 易混点：`faction_relations` 属于 **`GameObservation`**（喂给 AI 的观察），
     **不是** `GameState`（存档快照）。第一版判断把它当成了快照字段、
     写成"字段存在但生产端没填"，被实跑纠正。

处置（2026-10-03）：`load_state_snapshot` 改为**显式抛 `NotImplementedError`**，
原实现移入 `_load_state_snapshot_legacy` 留档。理由：按本项目
「拒绝静默兜底」的原则，宁可显式不可用，也不留一个会造出降级引擎的陷阱。

本脚本因此承担两件事：
  1. 验证公开入口确实**显式拒绝**（不再静默降级）
  2. 用留档旧实现**重放证据**，证明当初为什么不能保留它

运行：
    PYTHONHASHSEED=0 ./venv/bin/python tests/balance/exp20_snapshot_restore.py --turns 12
"""

from __future__ import annotations

import argparse
import os
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


def _advance(engine: GameEngine, turns: int) -> None:
    """用启发式玩家推进若干回合。"""
    players = P.make_players(engine.seed)
    for _ in range(turns):
        if engine.game_over:
            break
        for f in P.FACTION_KEYS:
            obs = engine.get_observation(f)
            for cmd in players[f].get_commands(obs):
                engine.execute_command(cmd)
        engine.process_turn()


def _state_report(engine: GameEngine) -> Dict[str, Any]:
    """采集「恢复后应当还在」的关键状态。"""
    rels = None
    if engine._diplomacy_relation_system is not None:
        rels = len(engine._diplomacy_relation_system.get_all_relations())
    return {
        "turn": engine.turn,
        "hex_map_is_none": engine.hex_map is None,
        "season": getattr(engine, "season", None),
        "n_cities": len(engine.cities),
        "n_armies": len(engine.armies),
        "n_generals": len(engine.generals),
        "diplomacy_relations": rels,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="存档恢复可用性实测")
    ap.add_argument("--turns", type=int, default=12)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    P.ensure_reproducible()

    print("=" * 78)
    print("实验 20：load_state_snapshot 可用性（结论已确认为 B：实现不完整）")
    print(f"seed={args.seed}  turns={args.turns}")
    print("=" * 78)

    engine = GameEngine(seed=args.seed)
    engine.init_game(load_game_data())
    engine.max_turns = 192
    _advance(engine, args.turns)
    before = _state_report(engine)
    snapshot = engine.get_state_snapshot()

    # ---- 1. 公开入口必须显式拒绝 ----
    print("\n[1] 公开入口 load_state_snapshot 的行为（应显式抛错，不静默降级）")
    fresh = GameEngine(seed=args.seed)
    try:
        fresh.load_state_snapshot(snapshot)
        print("    ❌ 竟然没有抛异常 —— 静默降级的陷阱又回来了")
        return 1
    except NotImplementedError as exc:
        print(f"    ✅ 已显式拒绝: NotImplementedError")
        print(f"       {str(exc)[:150]}...")
    except Exception as exc:  # noqa: BLE001
        print(f"    ⚠️ 抛的不是 NotImplementedError，而是 {type(exc).__name__}: {exc!r}")
        return 1

    # ---- 2. 用留档旧实现重放证据（证明当初为何不能保留它）----
    print("\n[2] 用留档旧实现 _load_state_snapshot_legacy 重放证据")
    legacy = GameEngine(seed=args.seed)
    legacy._load_state_snapshot_legacy(snapshot)  # noqa: SLF001 —— 本实验就是要重放它
    after = _state_report(legacy)

    print(f"\n  原引擎状态（取快照前）:")
    for k, v in before.items():
        print(f"      {k:22s} = {v}")
    print(f"\n  旧实现恢复后:")
    for k in before:
        b, a = before[k], after[k]
        flag = "✅" if b == a else "⚠️"
        print(f"      {flag} {k:22s} 原={b!r}  恢复后={a!r}")

    lost: List[str] = [k for k in before if before[k] != after[k]]
    print(f"\n  不一致项: {lost if lost else '（无）'}")

    # ---- 3. 旧实现能否续跑（历史上它"看起来能"）----
    print(f"\n[3] 旧实现恢复后继续推进 {args.turns} 回合")
    try:
        _advance(legacy, args.turns)
        print(f"    ⚠️ 表面续跑成功，turn={legacy.turn} —— 这正是危险之处：")
        print("       它不报错，但 hex_map/外交 都已是 None，后台静默降级。")
    except Exception as exc:  # noqa: BLE001
        print(f"    抛异常: {exc!r}")

    # ---- 判定 ----
    print("\n" + "=" * 78)
    print("判定")
    print("=" * 78)
    if lost:
        print(f"  ✅ 结论 B 复现成功：旧实现恢复后丢失/未重建 {lost}，")
        print("     而公开入口已改为显式拒绝 → 陷阱已封。")
    else:
        print("  ⚠️ 未复现出状态丢失 —— 结论需要重新评估。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
