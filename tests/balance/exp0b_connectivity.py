#!/usr/bin/env python3
"""实验 0b：地图连通性体检（零随机性）。

实验 0 意外发现：351/465 城对 A* 不可达（114 对，24.5%）。若属实，这比行军速度
更可能是「9 座中立城无人碰 / 6 回合只1 场战斗」的结构性根因。本脚本定位成因。

排查项：
  1. 不可达城对的具体分布（是否集中在某一地区/某势力）
  2. 地形移动消耗表：哪些地形 cost=inf（不可通行）
  3. 城市落点是否落在不可通行格子上（起始就出不来）
  4. 势力连通性：每方起始城市在本方扩张下能否连成一片
  5. 用「忽略地形」的距离做对照，区分「距离远」与「路不通」

运行：
    python tests/balance/exp0b_connectivity.py
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter, defaultdict

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pacing_lib as P  # noqa: E402
from game.hex_map import HexMap                # noqa: E402


def cube_dist(a: tuple, b: tuple) -> int:
    """忽略地形的纯 hex 立方坐标距离（对照口径）。"""
    return int((abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])) / 2)


def main() -> int:
    P.ensure_reproducible()  # 🔴 可复现性守卫（固定 PYTHONHASHSEED=0）
    ap = argparse.ArgumentParser(description="实验0b：地图连通性体检")
    ap.add_argument("--out", type=str, default="")
    args = ap.parse_args()

    from game.engine import GameEngine
    from game.data_loader import load_game_data
    from game.constants import TERRAIN_MOVE_COST

    print("=" * 78)
    print("  实验 0b：地图连通性体检（headless / 零随机）")
    print("=" * 78)

    eng = GameEngine(seed=1)
    eng.init_game(load_game_data())
    hm: HexMap = eng.hex_map
    cities = eng.cities
    ids = sorted(cities.keys())

    # --- 1. 地形移动消耗表 ---
    print("\n  [1] 地形移动消耗表（TERRAIN_MOVE_COST）")
    for terrain, cost in TERRAIN_MOVE_COST.items():
        flag = "  ← 不可通行" if cost == float("inf") else ""
        print(f"    {terrain:<12} cost={cost}{flag}")

    # --- 2. 城市落点地形 ---
    print("\n  [2] 31 座城市的落点地形")
    blocked = []
    terrain_ct = Counter()
    for cid in ids:
        tile = hm.get_tile(cities[cid].position)
        t = getattr(tile, "terrain", None)
        tv = getattr(t, "value", t)
        terrain_ct[str(tv)] += 1
        cost = HexMap.terrain_move_cost(t) if t is not None else None
        mark = ""
        if cost == float("inf"):
            blocked.append(cid)
            mark = "  ← 城市落在不可通行格!"
        print(f"    {cid:<12} {str(tv):<12} cost={cost}{mark}")
    print(f"\n    地形分布: {dict(terrain_ct)}")
    print(f"    落在不可通行格的城市: {blocked if blocked else '无'}")

    # --- 3. 不可达城对 ---
    print("\n  [3] A* 不可达城对")
    unreachable = []
    reach_dists = []
    geo_unreachable = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            path = hm.find_path(cities[a].position, cities[b].position)
            if path:
                reach_dists.append((len(path) - 1, a, b))
            else:
                ca, cb = cities[a].position, cities[b].position
                gd = cube_dist((ca.q, ca.r, -ca.q - ca.r), (cb.q, cb.r, -cb.q - cb.r))
                unreachable.append((a, b, gd))
                if gd <= 12:
                    geo_unreachable.append((a, b, gd))

    total_pairs = len(ids) * (len(ids) - 1) // 2
    print(f"    总城对{total_pairs}  A*可达 {len(reach_dists)}  A*不可达 {len(unreachable)}"
          f"  ({len(unreachable)/total_pairs*100:.1f}%)")

    reach_dists.sort()
    n = len(reach_dists)
    if n:
        print(f"    仅在可达子集内: min={reach_dists[0][0]}中位={reach_dists[n//2][0]} "
              f"p75={reach_dists[int(n*0.75)][0]} max={reach_dists[-1][0]}均值="
              f"{sum(d for d,_,_ in reach_dists)/n:.2f}")
    print(f"    不可达城对的「忽略地形几何距离」: min={min(g for _,_,g in unreachable) if unreachable else 0} "
          f"中位={sorted(g for _,_,g in unreachable)[len(unreachable)//2] if unreachable else 0} "
          f"max={max(g for _,_,g in unreachable) if unreachable else 0}")
    print(f"    其中几何距离 ≤12（物理上很近却走不通）: {len(geo_unreachable)} 对")
    for a, b, g in sorted(geo_unreachable, key=lambda x: x[2])[:15]:
        print(f"      {a} <-> {b}  几何距离={g}")

    # 按势力看中立城连通性
    print("\n  [4] 中立城能否从各势力首府走到（首批 5 座）")
    fac_homes = {}
    for cid in ids:
        f = cities[cid].faction
        if f != "neutral":
            fac_homes.setdefault(f, cid)
    neutral_ids = [c for c in ids if cities[c].faction == "neutral"]
    print(f"    中立城共{len(neutral_ids)} 座: {neutral_ids}")
    reach_cnt = Counter()
    for f, home in sorted(fac_homes.items()):
        n_reach = 0
        for nid in neutral_ids:
            if hm.find_path(cities[home].position, cities[nid].position):
                n_reach += 1
        reach_cnt[f] = n_reach
        print(f"    {f:<14}(首府 {home:<12}) 可达中立城 {n_reach}/{len(neutral_ids)}")
    orphan = [nid for nid in neutral_ids
              if not any(hm.find_path(cities[h].position, cities[nid].position) for h in fac_homes.values())]
    print(f"\n    🔴 任何势力都走不到的孤立中立城: {orphan if orphan else '无'}")

    # --- 5. 势力内部连通性 ---
    print("\n  [5] 各势力起始城市之间的连通性（扩张是否会被地形卡断）")
    for f, home in sorted(fac_homes.items()):
        own = [c for c in ids if cities[c].faction == f]
        pairs = 0
        bad = 0
        for i, a in enumerate(own):
            for b in own[i + 1:]:
                pairs += 1
                if not hm.find_path(cities[a].position, cities[b].position):
                    bad += 1
        if pairs:
            print(f"    {f:<14} 起始 {len(own)} 城, 内部不可达 {bad}/{pairs} 对")

    out = {
        "total_pairs": total_pairs,
        "a_star_reachable": len(reach_dists),
        "a_star_unreachable": len(unreachable),
        "unreachable_pct": round(len(unreachable) / total_pairs * 100, 2),
        "cities_on_blocked_tile": blocked,
        "orphan_neutral_cities": orphan,
        "terrain_cost": {k: (None if v == float("inf") else v) for k, v in TERRAIN_MOVE_COST.items()},
    }
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        import json
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)
        print(f"\n  [已写出 JSON: {args.out}]")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
