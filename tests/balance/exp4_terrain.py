#!/usr/bin/env python3
"""实验 4：地形阻断单变量对照（修正版—— 阻断点在 Tile.is_passable，不在 cost表）。

【关键修正】实验 4 初版改 `TERRAIN_MOVE_COST['deep_water']` 完全无效，实测发现真正
的阻断来自 `game.tile.Tile.is_passable()` 里**硬编码**的不可通行集合：
    MOUNTAIN / PEAK / WATER / DEEP_WATER
即改 cost 表不会让水域可通行，必须改 is_passable。本脚本改为对 is_passable 做
单变量对照，并新增「陆地连通分量」分析（回答：这地图到底是几块大陆？）。

运行：
    python tests/balance/exp4_terrain.py --games 5 --speed 8
    python tests/balance/exp4_terrain.py --variants none water --games 5
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Dict, List

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import pacing_lib as P                    # noqa: E402
import game.constants as C# noqa: E402
from game.tile import Tile, TerrainType  # noqa: E402

IMPASSABLE = (TerrainType.MOUNTAIN, TerrainType.PEAK, TerrainType.WATER, TerrainType.DEEP_WATER)
# 🔴 必须在模块加载时捕获「未被任何人打过补丁」的原始方法。
# 若在 apply_variant 内部再取 Tile.is_passable，第二次调用会拿到上一次
#  install 的 patched 闭包 → 变体叠加污染（实测 base 与 nopeak 表现完全相同）。
_ORIG_PASSABLE = Tile.is_passable

# 变体名 -> 额外允许通行的地形
VARIANTS: Dict[str, tuple] = {
    "base": (),                                    # 现状：与 is_passable 默认完全一致
    "water": (TerrainType.WATER, TerrainType.DEEP_WATER),         # 仅水域可通行
    "nomountain": (TerrainType.MOUNTAIN,),                        # 仅山脉可通行
    "nopeak": (TerrainType.PEAK,),                                # 仅山峰可通行
    "nomtn": (TerrainType.MOUNTAIN, TerrainType.PEAK),           # 山脉+山峰可通行
    "all": (TerrainType.WATER, TerrainType.DEEP_WATER,
            TerrainType.MOUNTAIN, TerrainType.PEAK),               # 全地形（绝对上界）
}


def apply_variant(name: str) -> None:
    """打补丁：让指定额外地形可通行。**幂等**——每次都从原始方法重建，
    绝不叠加上一轮的 patched 闭包（否则 base 会继承 nopeak 的效果）。

    🔴 若`P.use_pristine_baseline()` 已锁定基线，则"不可通行集合"以基线
    （含 PEAK）为准，避免 baseline 锁被本函数覆盖。"""
    import pacing_lib as _P
    if _P._BASELINE_SNAPSHOT:
        # 基线锁定中：不可通行集合必须用基线版（含 PEAK）
        import game.tile as _TT
        _TT.Tile.is_passable = lambda self: self.terrain not in IMPASSABLE
        return
    Tile.is_passable = _ORIG_PASSABLE
    extra = VARIANTS[name]
    if not extra:
        return

    def patched(self) -> bool:
        if self.terrain in extra:
            return True
        return _ORIG_PASSABLE(self)

    Tile.is_passable = patched


def restore() -> None:
    Tile.is_passable = _ORIG_PASSABLE


def _hex_neighbors(q: int, r: int):
    return ((q + 1, r), (q + 1, r - 1), (q, r - 1), (q - 1, r), (q - 1, r + 1), (q, r + 1))


def landmass_components(variant: str) -> Dict[str, Any]:
    """统计可通行陆地的连通分量（回答：地图被切成几块？各势力在中立几号块？）"""
    from game.engine import GameEngine
    from game.data_loader import load_game_data
    from game.hex_map import HexCoord

    apply_variant(variant)
    try:
        eng = GameEngine(seed=1)
        eng.init_game(load_game_data())
        hm = eng.hex_map
        tiles = getattr(hm, "_tiles")
        passable = set()
        for key, t in tiles.items():
            # key 可能是 HexCoord，也可能是 (q, r) 元组
            if t.is_passable():
                if hasattr(key, "q"):
                    passable.add((key.q, key.r))
                else:
                    passable.add((key[0], key[1]))

        # 连通分量
        comp: Dict[tuple, int] = {}
        n_comp = 0
        comp_size: Dict[int, int] = {}
        for start in passable:
            if start in comp:
                continue
            n_comp += 1
            size = 0
            dq = deque([start])
            comp[start] = n_comp
            while dq:
                q, r = dq.popleft()
                size += 1
                for nq, nr in _hex_neighbors(q, r):
                    if (nq, nr) in passable and (nq, nr) not in comp:
                        comp[(nq, nr)] = n_comp
                        dq.append((nq, nr))
            comp_size[n_comp] = size

        # 城市归属分量
        city_comp: Dict[str, int] = {}
        for cid, c in eng.cities.items():
            p = c.position
            city_comp[cid] = comp.get((p.q, p.r), -1)

        main = max(comp_size, key=lambda k: comp_size[k]) if comp_size else 0
        return {
            "variant": variant,
            "n_passable_tiles": len(passable),
            "n_tiles_total": len(tiles),
            "passable_pct": round(len(passable) / len(tiles) * 100, 1),
            "n_components": n_comp,
            "main_component": main,
            "main_size": comp_size.get(main, 0),
            "components_ge50": sum(1 for v in comp_size.values() if v >= 50),
            "comp_size_top10": sorted(comp_size.values(), reverse=True)[:10],
        }
    finally:
        restore()


def connectivity_snapshot(variant: str) -> Dict[str, Any]:
    """给定可通行变体，统计城对可达性。"""
    from game.engine import GameEngine
    from game.data_loader import load_game_data

    apply_variant(variant)
    try:
        eng = GameEngine(seed=1)
        eng.init_game(load_game_data())
        hm, cities = eng.hex_map, eng.cities
        ids = sorted(cities.keys())
        unreachable, dists = 0, []
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                p = hm.find_path(cities[a].position, cities[b].position)
                if p:
                    dists.append(len(p) - 1)
                else:
                    unreachable += 1
        dists.sort()
        n = len(dists)
        fac_homes: Dict[str, str] = {}
        for cid in ids:
            f = cities[cid].faction
            if f != "neutral":
                fac_homes.setdefault(f, cid)
        neutral_ids = [c for c in ids if cities[c].faction == "neutral"]
        fac_reach = {f: sum(1 for nid in neutral_ids
                            if hm.find_path(cities[h].position, cities[nid].position))
                     for f, h in fac_homes.items()}
        orphan = [nid for nid in neutral_ids
                  if not any(hm.find_path(cities[h].position, cities[nid].position)
                             for h in fac_homes.values())]
        total = len(ids) * (len(ids) - 1) // 2
        return {
            "variant": variant,
            "total_pairs": total,
            "unreachable": unreachable,
            "unreachable_pct": round(unreachable / total * 100, 2),
            "median": dists[n // 2] if n else 0,
            "mean": round(sum(dists) / n, 2) if n else 0,
            "max": dists[-1] if n else 0,
            "cut_off_factions": [f for f, k in fac_reach.items() if k == 0],
            "orphan_neutral_cities": orphan,
        }
    finally:
        restore()


def _worker(payload):
    speed, seed, max_turns, variant = payload
    P.set_march_speed(speed)
    apply_variant(variant)
    row = P.run_one_game(seed, max_turns)
    row["march_speed"] = speed
    row["variant"] = variant
    return row


def main() -> int:
    P.ensure_reproducible()  # 🔴 可复现性守卫（固定 PYTHONHASHSEED=0）
    ap = argparse.ArgumentParser(description="实验4：地形可通行性单变量对照（修正版）")
    ap.add_argument("--speed", type=int, default=8)
    ap.add_argument("--games", type=int, default=5)
    ap.add_argument("--seed-base", type=int, default=93001)
    ap.add_argument("--max-turns", type=int, default=192)
    ap.add_argument("--variants", nargs="+", default=["base", "water"],
                    choices=list(VARIANTS.keys()))
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--baseline", action="store_true",
                    help="把 P0 相关属性锁定为修复前取值（对抗并发修改，保证对照有效）")
    ap.add_argument("--out", type=str, default="")
    args = ap.parse_args()
    if args.baseline:  # 对抗并发修改：把 P0 属性锁回"修复前"
        _ok = P.use_pristine_baseline(True)
        print("  [基线锁定] " + ("已还原为修复前取值" if _ok else "失败（继续用工作区）"))

    seeds = [args.seed_base + i for i in range(args.games)]
    print("=" * 100)
    print("  实验 4：地形可通行性单变量对照（headless / CLIPlayer / 无 LLM）")
    print("=" * 100)
    print(f"  固定项: 行军速度={args.speed}, max_turns={args.max_turns}, seeds={seeds}")
    print(f"  变量  : Tile.is_passable 变体 ∈ {args.variants}")
    print(f"  变体说明: base=现状  water=水域可通行  all=连山地也可行走(上界对照)")
    print("=" * 100)

    print("\n  [A] 陆地连通分量（这地图到底是几块大陆？）")
    comps = []
    for v in args.variants:
        cm = landmass_components(v)
        comps.append(cm)
        print(f"    {v:>7}: 可通行 tile {cm['n_passable_tiles']:>6}/{cm['n_tiles_total']}"
              f" ({cm['passable_pct']:>4}%) | 连通分量={cm['n_components']:>5}"
              f" | 主大陆={cm['main_size']:>6} 格 | ≥50格的分量={cm['components_ge50']:>4}"
              f" | 最大10分量={cm['comp_size_top10']}")

    print("\n  [B] 城对可达性对照（静态，零随机）")
    snaps = []
    print(f"    {'variant':>8}{'不可达对':>10}{'占比':>8}{'中位距':>9}{'均值':>8}{'最大距':>9}"
          f"{'被切断势力':>24}{'孤立中立城':>18}")
    for v in args.variants:
        s = connectivity_snapshot(v)
        snaps.append(s)
        print(f"    {v:>8}{s['unreachable']:>10}{s['unreachable_pct']:>7.1f}%"
              f"{s['median']:>9}{s['mean']:>8.1f}{s['max']:>9}"
              f"{str(s['cut_off_factions']):>24}{str(s['orphan_neutral_cities']):>18}")

    print(f"\n  [C] 对战节奏对照（每档 {args.games} 局）")
    summaries: Dict[str, Dict[str, Any]] = {}
    all_rows: List[Dict[str, Any]] = []
    order: List[str] = []
    t0 = time.time()
    for v in args.variants:
        P.print_config_header(args.speed, args.max_turns, seeds)
        payloads = [(args.speed, s, args.max_turns, v) for s in seeds]
        rows: List[Dict[str, Any]] = []
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            for row in ex.map(_worker, payloads):
                rows.append(row)
        rows.sort(key=lambda r: r["seed"])
        for r in rows:
            print(f"    seed={r['seed']} turns={r['turns']:>3} battles={r['battles']:>3} "
                  f"first_battle={str(r['first_battle_turn']):>4} neutral={r['neutral_taken']:>2} "
                  f"survivors={r['surviving_factions']:>2} top={r['top_faction_share']:.2f} "
                  f"winner={r['winner']}")
        s = P.summarize(rows)
        s["variant"] = v
        summaries[v] = s
        order.append(v)
        all_rows.extend(rows)
        print()

    print("=" * 100)
    print("  地形可通行性对照总表（行军速度固定）")
    print("=" * 100)
    print(f"{'variant':>8}{'局数':>5}{'战斗场次':>16}{'首战回合':>14}{'结束回合':>12}"
          f"{'存活势力':>12}{'最大占比':>12}{'中立城':>12}")
    print("-" * 100)
    for v in order:
        s = summaries[v]

        def cell(st):
            if st["max"] == 0 and st["min"] == 0:
                return f"{'-':>12}"
            return f"{P._numfmt(st['median']):>6}[{P._numfmt(st['min'])}~{P._numfmt(st['max'])}]"

        print(f"{v:>8}{s['completed']:>5}{cell(s['battles']):>16}{cell(s['first_battle_turn']):>14}"
              f"{cell(s['turns']):>12}{cell(s['surviving_factions']):>12}"
              f"{cell(s['top_faction_share']):>12}{cell(s['neutral_taken']):>12}")
    print("=" * 100)
    for v in order:
        s = summaries[v]
        top = sorted(s["win_rate"].items(), key=lambda kv: -kv[1])[:4]
        print(f"    {v:>8}: " + ", ".join(f"{k}={v2*100:.0f}%" for k, v2 in top)
              + f" | 0胜={len(s['zero_win_factions'])}方"
              + (f" | 🔴OP: {s['op_suspects']}" if s["op_suspects"] else " | 无OP嫌疑"))
    print(f"\n  总耗时: {time.time() - t0:.1f}s")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"config": {"speed": args.speed, "games": args.games, "seeds": seeds,
                                  "max_turns": args.max_turns, "variants": args.variants},
                       "components": comps, "connectivity": snaps,
                       "summaries": summaries, "raw_rows": all_rows},
                      fh, ensure_ascii=False, indent=2)
        print(f"  [已写出 JSON: {args.out}]")
        csv_path = os.path.splitext(args.out)[0] + ".csv"
        cols = ["variant", "march_speed", "seed", "turns", "battles", "first_battle_turn",
                "armies_launched", "neutral_taken", "first_neutral_turn",
                "surviving_factions", "top_faction_share", "hhi", "winner", "crashed"]
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for r in all_rows:
                w.writerow(r)
        print(f"  [已写出 CSV: {csv_path}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
