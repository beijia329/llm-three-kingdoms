#!/usr/bin/env python3
"""实验 12：终局统一度 + 军队泄漏诊断（v4.0 战斗机制修复的验收实验）

【回答什么问题】
v4.0 修了三个战斗机制缺陷（撤退僵尸军队 / 城墙上限膨胀 / 巷战仍享城墙加成）
之后，对局是否真的能"打完"？兵力是否不再凭空消失？

【为什么需要它】exp11 只统计战斗场次与伤亡，**不含统一度**，
无法回答"12 方是否仍谁也打不完"这个 v3.1 遗留的核心问题。

【指标】
  - surviving_factions  终局仍有城的势力数（12 = 仍无统一，1 = 已统一）
  - hhi                 城市集中度（1/12≈0.083 完全均分，1.0 完全统一）
  - armies_leaked       终局仍在场的军队数（应为 0；>0 说明还有军队泄漏）
  - zombie_armies       状态为 RETREATING 但在场超过 5 回合的军队（僵尸指标）
  - troops_in_armies    终局困在军队里的兵力（占全图兵力比例）
  - freeze_turn         最后一次城池易主发生的回合（0 = 全程无易主；越早 = 地图越早冻结）
  - first_elim_turn     首个势力城市数归零的回合（None = 从未灭国）

🔴 2026-10-0X v4.0「灭国压力」修复：新增 freeze_turn / first_elim_turn 两项，
口径与 exp15_levers.py 对齐（同一 capture/prev_owner 口径），用于量化
「G 解将荒 + A 门槛比 0.9 + 征兵涨价」三件套对「地图冻结 / 从不灭国」的改善。

运行：
    PYTHONHASHSEED=0 ./venv/bin/python tests/balance/exp12_unification_check.py --games 5 --turns 48
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from typing import Any, Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import pacing_lib as P                              # noqa: E402
from game.data_loader import load_game_data         # noqa: E402
from game.engine import GameEngine                  # noqa: E402
from game.models import ArmyStatus                  # noqa: E402


def run_one(game_seed: int, max_turns: int) -> Dict[str, Any]:
    """跑一局并采集统一度 + 军队泄漏指标。"""
    engine = GameEngine(seed=game_seed)
    engine.init_game(load_game_data())
    engine.max_turns = int(max_turns)
    players = P.make_players(game_seed)

    # 记录每支 RETREATING 军队首次出现的回合，用于判定僵尸
    retreat_since: Dict[str, int] = {}
    max_zombie = 0
    leaked_samples: List[Dict[str, Any]] = []
    battles = 0

    # v4.0：易主 / 灭国追踪（口径与 exp15_levers 对齐）
    prev_owner = {cid: c.faction for cid, c in engine.cities.items()}
    initial_counts: Dict[str, int] = {}
    for c in engine.cities.values():
        if c.faction in P.FACTION_KEYS:
            initial_counts[c.faction] = initial_counts.get(c.faction, 0) + 1
    freeze_turn = 0                       # 末次城池易主的回合；0 = 全程无易主
    first_zero: Dict[str, Optional[int]] = {f: None for f in P.FACTION_KEYS}

    turns = 0
    while not engine.game_over and turns <= P.SAFETY_MAX_ITER:
        for f in P.FACTION_KEYS:
            obs = engine.get_observation(f)
            for cmd in players[f].get_commands(obs):
                engine.execute_command(cmd)
        res = engine.process_turn()
        battles += int(res.get("battles_fought", 0) or 0)
        turns += 1

        # 城池易主：任一城 faction 变化即记为本回合发生易主
        for cid, c in engine.cities.items():
            if c.faction != prev_owner[cid]:
                prev_owner[cid] = c.faction
                freeze_turn = engine.turn
        # 灭国：开局有城的势力首次城市数归零
        counts: Dict[str, int] = {}
        for c in engine.cities.values():
            if c.faction in first_zero:
                counts[c.faction] = counts.get(c.faction, 0) + 1
        for f in P.FACTION_KEYS:
            if (initial_counts.get(f, 0) > 0 and first_zero[f] is None
                    and counts.get(f, 0) == 0):
                first_zero[f] = engine.turn

        # 僵尸巡检：RETREATING 状态持续 > 5 回合
        alive = set(engine.armies.keys())
        for aid in list(retreat_since):
            if aid not in alive:
                del retreat_since[aid]
        for aid, army in engine.armies.items():
            if army.status == ArmyStatus.RETREATING:
                retreat_since.setdefault(aid, engine.turn)
        zombies = [a for a, t0 in retreat_since.items() if engine.turn - t0 > 5]
        max_zombie = max(max_zombie, len(zombies))

    # 终局统计
    city_counts: Dict[str, int] = {}
    for c in engine.cities.values():
        if c.faction != "neutral":
            city_counts[c.faction] = city_counts.get(c.faction, 0) + 1
    active = {f: n for f, n in city_counts.items() if n > 0}
    total = sum(active.values())
    hhi = sum((n / total) ** 2 for n in active.values()) if total else 0.0

    troops_in_armies = sum(a.soldiers for a in engine.armies.values())
    troops_in_cities = sum(c.garrison for c in engine.cities.values())
    total_troops = troops_in_armies + troops_in_cities

    for aid, army in engine.armies.items():
        leaked_samples.append({
            "id": aid, "faction": army.faction, "soldiers": army.soldiers,
            "status": army.status.value, "from": army.from_city, "to": army.to_city,
            "progress": round(army.progress, 3),
        })

    return {
        "seed": game_seed,
        "turns": engine.turn,
        "game_over": engine.game_over,
        "winner": engine.winner,
        "battles": battles,
        "surviving_factions": len(active),
        "hhi": round(hhi, 4),
        "top_share": round(max(active.values()) / total, 3) if total else 0.0,
        "armies_left": len(engine.armies),
        "zombie_armies_max": max_zombie,
        "troops_in_armies": troops_in_armies,
        "troops_in_cities": troops_in_cities,
        "troops_trapped_pct": round(troops_in_armies / total_troops * 100, 1) if total_troops else 0.0,
        "freeze_turn": freeze_turn,
        "first_elim_turn": min(
            (t for t in first_zero.values() if t is not None), default=None
        ),
        "eliminated": {f: t for f, t in first_zero.items() if t is not None},
        "leaked": leaked_samples,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=5)
    ap.add_argument("--turns", type=int, default=48)
    ap.add_argument("--seed0", type=int, default=1)
    ap.add_argument("--out", default=os.path.join(_HERE, "data", "exp12_unification.json"))
    args = ap.parse_args()

    P.ensure_reproducible()

    rows: List[Dict[str, Any]] = []
    for i in range(args.games):
        seed = args.seed0 + i
        r = run_one(seed, args.turns)
        rows.append(r)
        print(f"  seed={seed} turns={r['turns']:3d} battles={r['battles']:3d} "
              f"存活势力={r['surviving_factions']:2d} hhi={r['hhi']:.3f} "
              f"残留军队={r['armies_left']} 僵尸峰值={r['zombie_armies_max']} "
              f"冻结于={r['freeze_turn']:3d} 首灭={r['first_elim_turn']}")

    print()
    print("=== 汇总 ===")
    print(f"  平均战斗场次     {statistics.mean(r['battles'] for r in rows):.1f}")
    print(f"  平均存活势力数   {statistics.mean(r['surviving_factions'] for r in rows):.1f}"
          f"   (12=仍无统一, 1=已统一)")
    print(f"  平均 HHI         {statistics.mean(r['hhi'] for r in rows):.4f}"
          f"   (0.083=完全均分, 1.0=完全统一)")
    print(f"  平均 top_share   {statistics.mean(r['top_share'] for r in rows):.3f}"
          f"   (红线 ≤ 0.30)")
    print(f"  地图冻结回合     {statistics.mean(r['freeze_turn'] for r in rows):.1f}"
          f"   (末次城池易主的回合；越早=地图越早冻结)")
    elim_turns = [r["first_elim_turn"] for r in rows if r["first_elim_turn"] is not None]
    print(f"  出现灭国的局数   {len(elim_turns)}/{len(rows)}"
          + (f"   平均首灭回合 {statistics.mean(elim_turns):.1f}"
             if elim_turns else "   (从未灭国)"))
    print(f"  终局残留军队     {sum(r['armies_left'] for r in rows)} 支（合计）")
    print(f"  僵尸军队峰值     {max(r['zombie_armies_max'] for r in rows)} 支（最大）")
    print(f"  困在军队的兵力   {statistics.mean(r['troops_trapped_pct'] for r in rows):.1f}%"
          f"   (占全图总兵力)")

    leaked = [x for r in rows for x in r["leaked"]]
    if leaked:
        print()
        print(f"=== 终局仍在场的军队明细（共 {len(leaked)} 支）===")
        for x in leaked[:12]:
            print(f"  {x['id']:12s} {x['faction']:10s} 兵{x['soldiers']:5d} "
                  f"{x['status']:10s} {x['from']}→{x['to']} progress={x['progress']}")
    else:
        print()
        print("✅ 终局无残留军队（无军队泄漏）")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"rows": rows}, fh, ensure_ascii=False, indent=1)
    print(f"\n明细已写入 {args.out}")


if __name__ == "__main__":
    main()
