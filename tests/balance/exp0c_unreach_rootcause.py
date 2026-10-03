#!/usr/bin/env python3
"""实验 0c：A* 不可达根因定位——是「地形阻断」还是「地图有空洞」。

实验 0b 发现 114/465 城对不可达，甚至几何距离 2 的 beihai<->linzi 都走不通。
本脚本区分两种成因：
  A. 地图空洞：两城之间根本没有 tile 数据（tile is None）→ 寻路必然失败
  B. 地形阻断：tile 存在但 cost=inf（deep_water 等）→ 路径被cost 挡住
同时检查：
  - hex_map 的 tile 总数与覆盖范围（是否覆盖整张中国地图）
  - 城市落点周边 6 邻格是否存在（出征第一步有没有路）
  - A* 实现是否用了不可采纳的启发式（导致「有路也判不可达」）

运行：
    python tests/balance/exp0c_unreach_rootcause.py
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pacing_lib as P                # noqa: E402
from game.hex_map import HexMap       # noqa: E402


def main() -> int:
    P.ensure_reproducible()  # 🔴 可复现性守卫（固定 PYTHONHASHSEED=0）
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=str, default="")
    args = ap.parse_args()

    from game.engine import GameEngine
    from game.data_loader import load_game_data

    print("=" * 78)
    print("  实验 0c：A* 不可达根因定位")
    print("=" * 78)

    eng = GameEngine(seed=1)
    eng.init_game(load_game_data())
    hm: HexMap = eng.hex_map
    cities = eng.cities
    ids = sorted(cities.keys())

    # --- tile 覆盖情况 ---
    tiles = getattr(hm, "tiles", None)
    print("\n  [1] hex_map tile 覆盖")
    print(f"    tiles容器类型: {type(tiles).__name__}  元素数: {len(tiles) if tiles is not None else 'N/A'}")
    if isinstance(tiles, dict):
        qs = [t.q for t in tiles.values()]
        rs = [t.r for t in tiles.values()]
        print(f"    q范围: {min(qs)}~{max(qs)}   r范围: {min(rs)}~{max(rs)}")
        terr = Counter(str(getattr(t.terrain, 'value', t.terrain)) for t in tiles.values())
        print(f"    地形分布: {dict(terr)}")
    city_qs = [cities[c].position.q for c in ids]
    city_rs = [cities[c].position.r for c in ids]
    print(f"    城市 q范围: {min(city_qs)}~{max(city_qs)}  r范围: {min(city_qs)}~{max(city_rs)}")

    # --- 城市落点6 邻格是否存在 ---
    print("\n  [2] 每座城市落点 + 其 6 邻格是否有 tile（出征第一步）")
    no_neighbor = []
    on_hole = []
    for cid in ids:
        pos = cities[cid].position
        t0 = hm.get_tile(pos)
        if t0 is None:
            on_hole.append(cid)
        neigh_missing = 0
        neigh_blocked = 0
        for dq, dr in ((1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)):
            tt = hm.get_tile(type(pos)(pos.q + dq, pos.r + dr))
            if tt is None:
                neigh_missing += 1
            elif HexMap.terrain_move_cost(tt.terrain) == float("inf"):
                neigh_blocked += 1
        if neigh_missing:
            no_neighbor.append((cid, neigh_missing))
        if neigh_missing == 6:
            print(f"    🔴 {cid:<12} 落点周围 6 格全部无 tile（孤岛）")
    print(f"    落点本身无tile 的城市: {on_hole if on_hole else '无'}")
    print(f"    至少有 1 个邻格缺 tile 的城市: {len(no_neighbor)} 座")
    for cid, k in no_neighbor:
        print(f"      {cid:<12} 缺 {k}/6 邻格")

    # --- 不可达城对分类：空洞 vs 阻断 ---
    print("\n  [3] 不可达城对分类")
    hole_pairs = 0     # 找不到任何 tile 的中间点
    blocked_pairs = 0  # 有 tile 但全被 inf 挡住
    examples = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            pa, pb = cities[a].position, cities[b].position
            if hm.find_path(pa, pb):
                continue
            # 用「只看 tile 是否存在、不看 cost」做 BFS
            if bfs_exists(hm, pa, pb):
                blocked_pairs += 1
            else:
                hole_pairs += 1
                if len(examples) < 12:
                    examples.append((a, b))
    print(f"    因「地图空洞」不可达（无 tile 路径）: {hole_pairs} 对")
    print(f"    因「地形阻断」不可达（有 tile 但 cost=inf）: {blocked_pairs} 对")
    print(f"    示例空洞对: {examples}")

    # --- A* 启发式检查 ---
    print("\n  [4] A* 与 BFS 交叉验证（find_path 失败返回 [] 而非 None）")
    mismatches = 0
    checked = 0
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            path = hm.find_path(cities[a].position, cities[b].position)
            bfs = bfs_cost(hm, cities[a].position, cities[b].position)
            checked += 1
            # 注意：find_path 无路时返回 []（falsy），不是 None
            a_failed = not path
            b_failed = bfs is None
            if a_failed != b_failed:
                mismatches += 1
                if mismatches <= 8:
                    print(f"    ⚠️ {a}<->{b}: A*={'None' if a_failed else len(path)-1} "
                          f"BFS={'None' if b_failed else bfs}")
    print(f"    共核对 {checked} 对，不一致 {mismatches} 对"
          f" → {'A* 实现有BUG' if mismatches else 'A* 与 BFS 完全一致 ⇒问题在地图地形数据，不在寻路算法'}")

    print("\n  [5] 案例诊断：A* 失败但tile 连续（证明是 cost=inf 阻断，不是空洞）")
    for a, b in (("beihai", "linzi"), ("chengdu", "ji"), ("bai_di", "beihai")):
        pa, pb = cities[a].position, cities[b].position
        ta, tb = hm.get_tile(pa), hm.get_tile(pb)
        print(f"    {a}(q={pa.q},r={pa.r}) {getattr(ta.terrain,'value',None)} "
              f"-> {b}(q={pb.q},r={pb.r}) {getattr(tb.terrain,'value',None)}")
        print(f"      A*路径: {'无' if not hm.find_path(pa,pb) else len(hm.find_path(pa,pb))-1}"
              f" | 仅看tile存在性的BFS: {'连通' if bfs_exists(hm, pa, pb) else '不连通'}"
              f" | 考虑cost的BFS: {bfs_cost(hm, pa, pb)}")
        print(f"      → 结论: {'地形阻断（tile连续但不可通行）' if bfs_exists(hm,pa,pb) and bfs_cost(hm,pa,pb) is None else '需进一步检查'}")

    if args.out:
        import json
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"hole_pairs": hole_pairs, "blocked_pairs": blocked_pairs,
                       "astar_bfs_mismatch": mismatches}, fh, ensure_ascii=False, indent=2)
        print(f"\n  [已写出 JSON: {args.out}]")
    print("=" * 78)
    return 0


def bfs_exists(hm, start, goal) -> bool:
    """只考虑 tile 是否存在（忽略 cost=inf）的连通性 BFS。"""
    from collections import deque
    pos_t = type(start)
    seen = {(start.q, start.r)}
    dq = deque([(start.q, start.r)])
    while dq:
        q, r = dq.popleft()
        if (q, r) == (goal.q, goal.r):
            return True
        for dq_, dr_ in ((1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)):
            n = (q + dq_, r + dr_)
            if n in seen:
                continue
            if hm.get_tile(pos_t(*n)) is None:
                continue
            seen.add(n)
            dq.append(n)
    return False


def bfs_cost(hm, start, goal):
    """考虑 cost=inf 的真实最短路 BFS（对照 A*）。"""
    from collections import deque
    pos_t = type(start)
    dist = {(start.q, start.r): 0}
    dq = deque([(start.q, start.r)])
    while dq:
        q, r = dq.popleft()
        d = dist[(q, r)]
        if (q, r) == (goal.q, goal.r):
            return d
        for dq_, dr_ in ((1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)):
            n = (q + dq_, r + dr_)
            if n in dist:
                continue
            t = hm.get_tile(pos_t(*n))
            if t is None:
                continue
            c = HexMap.terrain_move_cost(t.terrain)
            if c == float("inf"):
                continue
            dist[n] = d + c
            dq.append(n)
    return None


if __name__ == "__main__":
    sys.exit(main())
