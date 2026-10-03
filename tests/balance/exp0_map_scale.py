#!/usr/bin/env python3
"""实验 0：地图尺度 × 行军速度的静态匹配分析（零随机性，纯几何对照组）。

目的：
  1. 独立复算 31 城两两 hex 距离分布，作为 team-lead 实测数字的**对照**；
  2. 量化「行军速度 vs 地图尺度」的错配程度：各速度档下打遍全国需要多少回合；
  3. 给出「首次交战回合」的理论下界，供实验 1/2 的实跑数据校验。

运行：
    python tests/balance/exp0_map_scale.py
    python tests/balance/exp0_map_scale.py --speeds 4 6 8 10 --out tests/balance/data/exp0_map_scale.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import pacing_lib as P  # noqa: E402


def main() -> int:
    P.ensure_reproducible()  # 🔴 可复现性守卫（固定 PYTHONHASHSEED=0）
    ap = argparse.ArgumentParser(description="实验0：地图尺度与行军速度匹配分析")
    ap.add_argument("--speeds", type=int, nargs="+", default=[4, 6, 8, 10],
                    help="要评估的行军速度档（默认 4 6 8 10）")
    ap.add_argument("--out", type=str, default="", help="可选：写出 JSON")
    args = ap.parse_args()

    print("=" * 78)
    print("  实验 0：地图尺度 × 行军速度静态匹配分析（headless / 无 LLM / 零随机）")
    print("=" * 78)

    scale = P.measure_map_scale()
    dists = scale.pop("all")

    print(f"\n  城市数        : {scale['n_cities']}")
    print(f"  城对数        : {scale['n_pairs']}   不可达: {scale['unreachable_pairs']}")
    print(f"  距离分布(hex 步数): min={scale['min']}  p25={scale['p25']}  "
          f"中位={scale['median']}  均值={scale['mean']}  p75={scale['p75']}  max={scale['max']}")

    # 直方图
    print("\n  距离直方图（按 5 步分桶）:")
    buckets = Counter((d // 5) * 5 for d in dists)
    for lo in sorted(buckets):
        hi = lo + 4
        n = buckets[lo]
        bar = "#" * int(round(n / max(buckets.values()) * 46))
        print(f"    {lo:>2}-{hi:<2} 步 | {bar:<46} {n:>3} 对 ({n/len(dists)*100:>5.1f}%)")

    # 各速度档下的交战回合
    print("\n  各行军速度档的「打到邻居 / 打到中位 / 打到最远」所需回合:")
    print(f"    {'speed':>6}{'邻居(p25=%.0f)' % scale['p25']:>16}{'中位':>10}{'p75':>10}{'最远':>10}{'全国均(回合)':>16}")
    speed_rows = {}
    for sp in args.speeds:
        row = {
            "neighbor_p25": round(P.turns_to_engage(scale["p25"], sp), 2),
            "median": round(P.turns_to_engage(scale["median"], sp), 2),
            "p75": round(P.turns_to_engage(scale["p75"], sp), 2),
            "max": round(P.turns_to_engage(scale["max"], sp), 2),
            "mean": round(P.turns_to_engage(scale["mean"], sp), 2),
        }
        speed_rows[sp] = row
        print(f"    {sp:>6}{row['neighbor_p25']:>16}{row['median']:>10}"
              f"{row['p75']:>10}{row['max']:>10}{row['mean']:>16}")

    # 错配诊断
    print("\n  错配诊断（对照 max_turns 候选 24/36/48）:")
    for mt in (24, 36, 48):
        print(f"    max_turns={mt}:")
        for sp in args.speeds:
            reach = sp * mt  # 期内最大可达步数
            cover = sum(1 for d in dists if d <= reach) / len(dists) * 100
            print(f"      speed={sp:>2}: 期内可达 {reach:>3} 步 → 可触达 {cover:>5.1f}% 的城市对"
                  f"  | 中位距离需 {P.turns_to_engage(scale['median'], sp):>5.1f} 回合"
                  f" → {'可达' if P.turns_to_engage(scale['median'], sp) <= mt else '不可达'}")

    out = {"scale": scale, "speed_rows": {str(k): v for k, v in speed_rows.items()}}
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)
        print(f"\n  [已写出JSON: {args.out}]")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
