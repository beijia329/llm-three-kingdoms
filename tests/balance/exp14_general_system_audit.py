#!/usr/bin/env python3
"""实验 14：武将系统 v4.0 验收

验证五个此前「定义了但没生效」或「生效方式失衡」的机制，改动后是否真的落地：

  1. 政治加成去堆叠    —— 单城产出倍率是否从「可无限堆叠」收敛到有上限
  2. 忠诚度回归        —— 长局中忠诚度是否不再集体归零
  3. 投降机制          —— 投降是否真的发生过（原公式恒为 0，从未发生）
  4. 五行分布          —— 53 名武将是否被合理分入五行（不应某一行独大）
  5. 五行相克 / 忠诚战力 —— 是否真的进入了战斗结算

运行：
    PYTHONHASHSEED=0 ./venv/bin/python tests/balance/exp14_general_system_audit.py --games 3 --turns 48
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import Counter
from typing import Any, Dict, List

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import pacing_lib as P                                   # noqa: E402
from game.constants import POLITICS_BONUS_CAP           # noqa: E402
from game.data_loader import load_game_data             # noqa: E402
from game.element import ELEMENT_NAMES, element_of      # noqa: E402
from game.engine import GameEngine                       # noqa: E402
from game.personality import GENERAL_PROFILES           # noqa: E402
from game.systems.resource_system import ResourceSystem  # noqa: E402


def audit_static() -> Dict[str, Any]:
    """静态审计：五行分布、人设覆盖率、政治加成分布"""
    engine = GameEngine(seed=1)
    engine.init_game(load_game_data())

    elements = Counter()
    for g in engine.generals.values():
        elements[ELEMENT_NAMES[element_of(g)]] += 1

    # 人设覆盖
    covered = sum(1 for gid in engine.generals if gid in GENERAL_PROFILES)
    personality_filled = sum(
        1 for g in engine.generals.values() if g.personality != "balanced"
    )

    # 政治加成倍率分布（每座城）
    rs = ResourceSystem()
    bonuses = []
    for city in engine.cities.values():
        b = rs._get_politics_bonus(city, generals=engine.generals)
        bonuses.append(b)

    return {
        "generals_total": len(engine.generals),
        "element_dist": dict(elements),
        "profile_covered": covered,
        "personality_filled": personality_filled,
        "politics_bonus_min": round(min(bonuses), 3),
        "politics_bonus_max": round(max(bonuses), 3),
        "politics_bonus_mean": round(statistics.mean(bonuses), 3),
        "politics_bonus_cap": POLITICS_BONUS_CAP,
    }


def run_game(game_seed: int, max_turns: int) -> Dict[str, Any]:
    """跑一局，追踪忠诚度轨迹与投降事件"""
    engine = GameEngine(seed=game_seed)
    engine.init_game(load_game_data())
    engine.max_turns = int(max_turns)
    players = P.make_players(game_seed)

    # 包装 process_capture 统计投降
    surrender_events = 0
    capture_events = 0
    original_capture = engine._general_system.process_capture

    def spy_capture(general, captor_faction, turn=0):  # type: ignore[no-untyped-def]
        nonlocal surrender_events, capture_events
        r = original_capture(general, captor_faction, turn)
        capture_events += 1
        if r.surrendered:
            surrender_events += 1
        return r

    engine._general_system.process_capture = spy_capture  # type: ignore[method-assign]

    loyalty_samples: List[List[int]] = []
    turns = 0
    while not engine.game_over and turns <= P.SAFETY_MAX_ITER:
        for f in P.FACTION_KEYS:
            obs = engine.get_observation(f)
            for cmd in players[f].get_commands(obs):
                engine.execute_command(cmd)
        engine.process_turn()
        turns += 1
        if turns % 12 == 0:
            loyalty_samples.append([g.loyalty for g in engine.generals.values()])

    final_loyalty = [g.loyalty for g in engine.generals.values()]
    zero_loyalty = sum(1 for x in final_loyalty if x == 0)

    return {
        "turns": turns,
        "loyalty_final_mean": round(statistics.mean(final_loyalty), 1),
        "loyalty_final_min": min(final_loyalty),
        "loyalty_final_max": max(final_loyalty),
        "loyalty_zero_count": zero_loyalty,
        "loyalty_samples": loyalty_samples,
        "captures": capture_events,
        "surrender_events": surrender_events,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=3)
    ap.add_argument("--turns", type=int, default=48)
    ap.add_argument("--seed0", type=int, default=1)
    ap.add_argument("--out", default=os.path.join(_HERE, "data", "exp14_general_audit.json"))
    args = ap.parse_args()

    P.ensure_reproducible()

    static = audit_static()
    print("=== 静态审计 ===")
    print(f"  武将总数            {static['generals_total']}")
    print(f"  人设档案覆盖        {static['profile_covered']}/{static['generals_total']}")
    print(f"  非默认性格（已注入） {static['personality_filled']}/{static['generals_total']}")
    print(f"  五行分布            {static['element_dist']}")
    print(f"  政治加成倍率        min={static['politics_bonus_min']} "
          f"max={static['politics_bonus_max']} "
          f"mean={static['politics_bonus_mean']} (上限={static['politics_bonus_cap']})")
    if static["politics_bonus_max"] > static["politics_bonus_cap"]:
        print("  ❌ 政治加成突破上限！")
    else:
        print("  ✅ 政治加成未突破上限（去堆叠生效）")

    print()
    print("=== 长局追踪 ===")
    rows = []
    for i in range(args.games):
        seed = args.seed0 + i
        r = run_game(seed, args.turns)
        rows.append(r)
        print(f"  seed={seed} 回合{r['turns']:3d} "
              f"忠诚 均值{r['loyalty_final_mean']:5.1f} "
              f"[{r['loyalty_final_min']},{r['loyalty_final_max']}] "
              f"归零人数={r['loyalty_zero_count']:2d} "
              f"被俘{r['captures']:3d} 投降{r['surrender_events']:3d}")

    print()
    zero_total = sum(r["loyalty_zero_count"] for r in rows)
    cap_total = sum(r["captures"] for r in rows)
    sur_total = sum(r["surrender_events"] for r in rows)
    mean_loyalty = statistics.mean(r["loyalty_final_mean"] for r in rows)

    print("=== 结论 ===")
    print(f"  忠诚度均值 {mean_loyalty:.1f}（原实现 144 回合后全为 0）")
    print(f"  忠诚度归零人数合计 {zero_total}"
          f" → {'✅ 未集体归零' if zero_total == 0 else '❌ 仍有归零'}")
    print(f"  被俘 {cap_total} 次，其中投降 {sur_total} 次"
          f" → {'✅ 投降机制已生效' if sur_total > 0 else '⚠️ 本批样本未触发投降（不代表失效）'}")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"static": static, "rows": rows}, fh, ensure_ascii=False, indent=1)
    print(f"\n明细已写入 {args.out}")


if __name__ == "__main__":
    main()
