#!/usr/bin/env python3
"""实验 3：回合数上限对照（24 / 36 / 48），行军速度固定为选定值。

在实验 1+2 选定的行军速度下，对比不同 max_turns 的结束时间与统一度。
单变量：只有 max_turns 变化（行军速度用 --speed 固定为常量）。

运行：
    # 先用实验1 的结论决定 --speed（默认 8）
    python tests/balance/exp3_turn_count.py --speed 8 --games 8
    python tests/balance/exp3_turn_count.py --speed 8 --games 8 --speeds 4 8   # 顺带做速度×回合交叉
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Dict, List

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import pacing_lib as P  # noqa: E402
from exp1_march_speed import _worker  # noqa: E402

TURN_CAPS = [24, 36, 48]


def main() -> int:
    P.ensure_reproducible()  # 🔴 可复现性守卫（固定 PYTHONHASHSEED=0）
    ap = argparse.ArgumentParser(description="实验3：回合数上限对照")
    ap.add_argument("--speed", type=int, default=8, help="固定行军速度（默认 8）")
    ap.add_argument("--speeds", type=int, nargs="+", default=[],
                    help="若给出，则对每个速度都跑一遍回合数对照（速度×回合交叉表）")
    ap.add_argument("--turn-caps", type=int, nargs="+", default=TURN_CAPS)
    ap.add_argument("--games", type=int, default=8, help="每配置局数（默认 8）")
    ap.add_argument("--seed-base", type=int, default=92001)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--out", type=str, default="")
    args = ap.parse_args()

    speeds = args.speeds if args.speeds else [args.speed]
    seeds = [args.seed_base + i for i in range(args.games)]

    print("=" * 96)
    print("  实验 3：max_turns 单变量对照（headless / CLIPlayer / 无 LLM）")
    print("=" * 96)
    print(f"  固定项: 行军速度={speeds}, seeds={seeds}（各配置共用，配对设计）")
    print(f"  变量  : max_turns ∈ {args.turn_caps}    每配置 {args.games} 局")
    print("=" * 96)

    summaries: Dict[str, Dict[str, Any]] = {}
    all_rows: List[Dict[str, Any]] = []
    order: List[str] = []
    t0 = time.time()

    for sp in speeds:
        for mt in args.turn_caps:
            P.print_config_header(sp, mt, seeds)
            payloads = [(sp, s, mt) for s in seeds]
            rows: List[Dict[str, Any]] = []
            with ProcessPoolExecutor(max_workers=args.workers) as ex:
                for row in ex.map(_worker, payloads):
                    rows.append(row)
            rows.sort(key=lambda r: r["seed"])
            for r in rows:
                print(f"    seed={r['seed']} turns={r['turns']:>3} battles={r['battles']:>3} "
                      f"first_battle={str(r['first_battle_turn']):>4} neutral={r['neutral_taken']:>2} "
                      f"survivors={r['surviving_factions']:>2} top={r['top_faction_share']:.2f} "
                      f"hhi={r['hhi']:.3f} winner={r['winner']}")
            key = f"{sp}@{mt}"
            summaries[key] = P.summarize(rows)
            summaries[key]["march_speed"] = sp
            order.append(key)
            all_rows.extend(rows)
            print()

    P.print_summary_table(summaries, order)

    print("\n  统一度与「是否分出胜负」对照:")
    print(f"    {'speed':>6}{'turns':>7}{'打满回合率':>12}{'明确胜者率':>12}"
          f"{'存活势力':>10}{'HHI':>9}{'最大占比':>10}{'战斗/回合':>11}")
    for key in order:
        s = summaries[key]
        sp, mt = key.split("@")
        filled = sum(1 for r in all_rows
                     if r["march_speed"] == int(sp) and r["max_turns"] == int(mt)
                     and r["turns"] >= int(mt))
        fill_rate = filled / max(1, s["completed"])
        decided = s["decided_games"] / max(1, s["completed"])
        per_turn = s["battles"]["mean"] / max(1e-9, s["turns"]["mean"])
        print(f"    {sp:>6}{mt:>7}{fill_rate*100:>11.0f}%{decided*100:>11.0f}%"
              f"{s['surviving_factions']['median']:>10.1f}{s['hhi']['median']:>9.3f}"
              f"{s['top_faction_share']['median']:>10.3f}{per_turn:>11.3f}")

    print("\n  胜率分布（碾压检测）:")
    for key in order:
        s = summaries[key]
        sp, mt = key.split("@")
        top = sorted(s["win_rate"].items(), key=lambda kv: -kv[1])[:4]
        print(f"    speed={sp:>2} turns={mt:>2}: "
              + ", ".join(f"{k}={v*100:.0f}%" for k, v in top)
              + f" | 0胜={len(s['zero_win_factions'])}方"
              + (f" | 🔴OP: {s['op_suspects']}" if s["op_suspects"] else " | 无OP嫌疑"))

    print(f"\n  总耗时: {time.time() - t0:.1f}s")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"config": {"speeds": speeds, "turn_caps": args.turn_caps,
                                  "games": args.games, "seeds": seeds, "llm": False},
                       "summaries": summaries, "raw_rows": all_rows},
                      fh, ensure_ascii=False, indent=2)
        print(f"  [已写出 JSON: {args.out}]")
        csv_path = os.path.splitext(args.out)[0] + ".csv"
        cols = ["march_speed", "max_turns", "seed", "turns", "battles", "first_battle_turn",
                "armies_launched", "neutral_taken", "first_neutral_turn",
                "surviving_factions", "top_faction_share", "hhi", "winner", "crashed", "elapsed_s"]
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for r in all_rows:
                w.writerow(r)
        print(f"  [已写出 CSV: {csv_path}]")
    print("=" * 96)
    return 0


if __name__ == "__main__":
    sys.exit(main())
