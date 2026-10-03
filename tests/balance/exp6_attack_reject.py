#!/usr/bin/env python3
"""实验 6：进攻被拒原因分解（定位 87% 出征失败的真正原因）。

实验 5 发现：CLIPlayer 每局下达 ~290 次AttackCommand，但引擎只成功 ~13%。
本脚本按 `GameEngine._execute_attack` 的校验链逐条打标，统计每个失败原因占比，
把「战斗稀少」从现象归因到具体代码分支。

校验链顺序（engine.py:_execute_attack）：
  1 出发城市不存在/不属于己方
  2 目标城市不存在
  3 兵力不足 (troops > garrison)
  4 将领不存在
  5 将领不在出发城               ← 高度可疑：CLIPlayer 用 obs.own_generals[0] 兜底
  6 map.get_distance <= 0（邻接关系）
  7 外交禁止can_attack=False      ← 高度可疑：默认外交关系可能禁止进攻
  8 hex_map.find_path 为空（无可行路径）← PEAK 阻断

运行：
    python tests/balance/exp6_attack_reject.py --games 3 --turns 40
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Dict, List

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import pacing_lib as P                # noqa: E402
from game.models import AttackCommand  # noqa: E402
from game.engine import GameEngine     # noqa: E402
from game.data_loader import load_game_data  # noqa: E402
from exp4_terrain import apply_variant, VARIANTS  # noqa: E402


def classify(desc: str) -> str:
    """把引擎返回的中文失败原因归类成稳定的英文标签。"""
    d = desc or ""
    if "出发城市" in d and "不存在" in d:
        return "from_city_missing"
    if "不属于" in d:
        return "from_city_not_owned"
    if "目标城市" in d and "不存在" in d:
        return "to_city_missing"
    if "兵力不足" in d:
        return "insufficient_troops"
    if "将领" in d and "不存在" in d:
        return "general_missing"
    if "不在" in d:
        return "general_not_in_city"
    if "无法到达" in d:
        return "unreachable_by_map_distance"
    if "处于" in d and "状态" in d:
        return "diplomacy_forbids"
    if "无可行路径" in d:
        return "no_hex_path"
    if "已在此城" in d or "已经在此" in d:
        return "already_there"
    return "other:" + d[:40]


def diagnose(seed: int, speed: int, max_turns: int, variant: str,
             full_baseline: bool = False) -> Dict[str, Any]:
    """跑一局并归因进攻失败。

    full_baseline=True 时**完整还原 P0 修复前状态**（地形 + 将领跨城兜底），
    与 exp10 的 before 组口径一致；False 时只按 variant 切换地形。
    """
    P.set_march_speed(speed)
    if full_baseline:
        # 完整基线：地形 PEAK 阻断 + CLIPlayer 恢复跨城兜底将领
        from exp10_p0_before_after import set_peak_passable, set_general_fallback
        set_peak_passable(False)
        set_general_fallback(True)
    else:
        apply_variant(variant)
    engine = GameEngine(seed=seed)
    engine.init_game(load_game_data())
    engine.max_turns = max_turns
    players = P.make_players(seed)

    reasons: Counter = Counter()
    total = 0
    ok = 0
    # 分势力记录被拒原因（定位是否某一方特别吃亏）
    by_faction: Dict[str, Counter] = {f: Counter() for f in P.FACTION_KEYS}

    while not engine.game_over:
        for f in P.FACTION_KEYS:
            obs = engine.get_observation(f)
            for cmd in players[f].get_commands(obs):
                if not isinstance(cmd, AttackCommand):
                    engine.execute_command(cmd)
                    continue
                total += 1
                res = engine.execute_command(cmd)
                if res.success:
                    ok += 1
                    reasons["SUCCESS"] += 1
                else:
                    tag = classify(res.description)
                    reasons[tag] += 1
                    by_faction[f][tag] += 1
        engine.process_turn()
        if engine.turn > 400:
            break

    from exp4_terrain import restore
    restore()
    if full_baseline:
        from exp10_p0_before_after import set_peak_passable, set_general_fallback
        set_peak_passable(True)          # 恢复工作区的 PEAK 可通行
        set_general_fallback(False)      # 恢复工作区的"不跨城兜底"

    return {
        "seed": seed, "speed": speed, "max_turns": max_turns, "variant": variant,
        "full_baseline": full_baseline,
        "end_turn": engine.turn,
        "attack_total": total, "attack_ok": ok,
        "reasons": dict(reasons),
        "by_faction": {f: dict(c) for f, c in by_faction.items() if c},
    }


def _worker(p):
    return diagnose(*p)


def main() -> int:
    P.ensure_reproducible()  # 🔴 可复现性守卫（固定 PYTHONHASHSEED=0）
    ap = argparse.ArgumentParser(description="实验6：进攻被拒原因分解")
    ap.add_argument("--speed", type=int, default=4)
    ap.add_argument("--games", type=int, default=3)
    ap.add_argument("--turns", type=int, default=40)
    ap.add_argument("--seed-base", type=int, default=95001)
    ap.add_argument("--variant", default="base", choices=list(VARIANTS.keys()))
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--baseline", action="store_true",
                    help="把 P0 相关属性锁定为修复前取值（对抗并发修改，保证对照有效）")
    ap.add_argument("--out", type=str, default="")
    args = ap.parse_args()
    if args.baseline:  # 对抗并发修改：把 P0 属性锁回"修复前"
        _ok = P.use_pristine_baseline(True)
        print("  [基线锁定] " + ("已还原为修复前取值" if _ok else "失败（继续用工作区）"))

    seeds = [args.seed_base + i for i in range(args.games)]
    print("=" * 100)
    print("  实验 6：进攻被拒原因分解（speed={} turns={} variant={}）".format(
        args.speed, args.turns, args.variant))
    print("=" * 100)

    rows: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for r in ex.map(_worker, [(s, args.speed, args.turns, args.variant, args.baseline) for s in seeds]):
            rows.append(r)

    agg: Counter = Counter()
    tot = ok = 0
    fac_agg: Dict[str, Counter] = {}
    for r in rows:
        agg.update(r["reasons"])
        tot += r["attack_total"]
        ok += r["attack_ok"]
        for f, c in r["by_faction"].items():
            fac_agg.setdefault(f, Counter()).update(c)

    print(f"\n  合计出征 {tot} 次，成功 {ok} 次（成功率 {ok/max(1,tot)*100:.1f}%）\n")
    print(f"    {'失败原因':>32}{'次数':>8}{'占全部出征':>12}")
    print("    " + "-" * 52)
    for tag, n in agg.most_common():
        mark = "" if tag == "SUCCESS" else""
        print(f"    {tag:>32}{n:>8}{n/max(1,tot)*100:>11.1f}%{mark}")

    fail_total = tot - ok
    if fail_total:
        print(f"\n  仅看失败（{fail_total} 次）的归因:")
        for tag, n in agg.most_common():
            if tag == "SUCCESS":
                continue
            print(f"    {tag:>32}{n:>8}{n/fail_total*100:>11.1f}%")

    print(f"\n  各势力被拒次数（谁吃亏最多）:")
    for f, c in sorted(fac_agg.items(), key=lambda kv: -sum(kv[1].values())):
        top = ", ".join(f"{k}={v}" for k, v in c.most_common(3))
        print(f"    {f:<14} 拒{sum(c.values()):>4}次: {top}")

    print("\n  结论依据:")
    if agg.get("general_not_in_city", 0) > fail_total * 0.3:
        print("    🔴 主因= 将领不在出发城（CLIPlayer 用 obs.own_generals[0] 兜底，"
              "该将领其实在别的城）→ 大量进攻在第5道校验就被拒")
    if agg.get("diplomacy_forbids", 0) > fail_total * 0.3:
        print("    🔴 主因= 外交状态禁止进攻（默认非战争关系下 can_attack=False）")
    if agg.get("no_hex_path", 0) > fail_total * 0.3:
        print("    🔴 主因= PEAK 地形阻断导致无路径（见实验0c/4）")
    if agg.get("insufficient_troops", 0) > fail_total * 0.3:
        print("    🔴 主因= 兵力不足")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"config": vars(args), "rows": rows, "agg": dict(agg),
                       "total": tot, "ok": ok}, fh, ensure_ascii=False, indent=2)
        print(f"\n  [已写出 JSON: {args.out}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
