#!/usr/bin/env python3
"""实验 10：P0 修复前/后 终局对照（在同一进程口径下完成，抵抗并发修改）。

【为什么需要本脚本】2026-10-03 11:15 前后，其他 agent 依据本报告的 P0 建议
并发修改了工作区（game/tile.py、game/constants.py、players/cli_player.py），
导致「跑 base」已经不再是"修复前"。本脚本把两侧强制放在**同一份代码**上对比：

  组 A「修复前」：进程内把 P0 属性锁回修复前取值
      - TERRAIN_MOVE_COST['peak'] = inf
      - Tile.is_passable 恢复含 PEAK 的原实现
      - CLIPlayer 恢复带 own_generals[0] 兜底的原实现（模拟旧逻辑）
  组 B「修复后」：P0 全部生效
      - peak 可通行（is_passable + 权表）
      - CLIPlayer 只派有本地将领的城
  组 C「修复后 + 补全_find_general_in_city 兜底」：
      验证另一 agent 的修复**不完整**——`_find_general_in_city` 仍会跨城返回
      兜底将领，导致 `general_not_in_city` 拒绝率居高不下。本组把该兜底也去掉，
      给出「补全后」的收益上界。

三组共用同一批 seed（配对设计），单变量只有 P0 修复本身。

运行：
    python tests/balance/exp10_p0_before_after.py --games 6 --turns 96
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Dict, List

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import pacing_lib as P# noqa: E402
import game.constants as C                # noqa: E402
from game.tile import Tile, TerrainType# noqa: E402
from game.models import AttackCommand     # noqa: E402
from players.cli_player import CLIPlayer  # noqa: E402

_IMPASSABLE_WITH_PEAK = (
    TerrainType.MOUNTAIN, TerrainType.PEAK, TerrainType.WATER, TerrainType.DEEP_WATER
)
_IMPASSABLE_NO_PEAK = (
    TerrainType.MOUNTAIN, TerrainType.WATER, TerrainType.DEEP_WATER
)

GROUPS = ("before", "after", "after_full")


def set_peak_passable(allow: bool) -> None:
    """切换 PEAK 可通行性（同时改is_passable 与 A* 权表，两处必须同步）。"""
    if allow:
        Tile.is_passable = lambda self: self.terrain not in _IMPASSABLE_NO_PEAK
        C.TERRAIN_MOVE_COST["peak"] = 3.0
    else:
        Tile.is_passable = lambda self: self.terrain not in _IMPASSABLE_WITH_PEAK
        C.TERRAIN_MOVE_COST["peak"] = float("inf")


def set_general_fallback(allow: bool) -> None:
    """控制 CLIPlayer 是否允许跨城兜底将领。

    allow=True  → 旧逻辑：_find_general_in_city 找不到本城将领时返回 own_generals[0]
    allow=False → 修复后：找不到本城将领就返回 None（该城不出征）
    """
    def make(allow_fb: bool):
        @staticmethod
        def _find(city_id: str, obs):
            for g in obs.own_generals:
                if g.location == city_id:
                    return g
            if allow_fb:
                return obs.own_generals[0] if obs.own_generals else None
            return None
        return _find

    CLIPlayer._find_general_in_city = make(allow)


def run_one(seed: int, speed: int, max_turns: int, group: str) -> Dict[str, Any]:
    from game.engine import GameEngine
    from game.data_loader import load_game_data

    # 三组设置
    set_peak_passable(group != "before")
    # before  : 旧逻辑(跨城兜底)   after / after_full : 不跨城兜底
    set_general_fallback(group == "before")

    engine = GameEngine(seed=seed)
    engine.init_game(load_game_data())
    engine.max_turns = max_turns
    players = P.make_players(seed)

    atk = atk_ok = battles = 0
    reasons: Counter = Counter()
    while not engine.game_over:
        for f in P.FACTION_KEYS:
            for cmd in players[f].get_commands(engine.get_observation(f)):
                if isinstance(cmd, AttackCommand):
                    atk += 1
                    r = engine.execute_command(cmd)
                    if r.success:
                        atk_ok += 1
                        reasons["SUCCESS"] += 1
                    else:
                        d = r.description
                        if "不在" in d:
                            reasons["general_not_in_city"] += 1
                        elif "无可行路径" in d:
                            reasons["no_hex_path"] += 1
                        else:
                            reasons[d[:30]] += 1
                else:
                    engine.execute_command(cmd)
        battles += int(engine.process_turn().get("battles_fought", 0) or 0)
        if engine.turn > 400:
            break

    counts = Counter(c.faction for c in engine.cities.values())
    active = {f: n for f, n in counts.items() if f != "neutral"}
    tot = sum(active.values()) or 1
    return {
        "seed": seed, "group": group, "speed": speed, "max_turns": max_turns,
        "end_turn": engine.turn, "winner": engine.winner,
        "attacks": atk, "attacks_ok": atk_ok,
        "ok_rate": round(atk_ok / atk, 3) if atk else 0.0,
        "battles": battles, "battles_per_turn": round(battles / max(1, engine.turn), 3),
        "surviving": len(active),
        "top_share": round(max(active.values()) / tot, 3),
        "hhi": round(sum((n / tot) ** 2 for n in active.values()), 4),
        "neutral_left": counts.get("neutral", 0),
        "reasons": dict(reasons),
    }


def _worker(p):
    return run_one(*p)


def main() -> int:
    ap = argparse.ArgumentParser(description="实验10：P0 修复前/后终局对照")
    ap.add_argument("--speed", type=int, default=4)
    ap.add_argument("--turns", type=int, default=96)
    ap.add_argument("--games", type=int, default=6)
    ap.add_argument("--seed-base", type=int, default=99001)
    ap.add_argument("--groups", nargs="+", default=list(GROUPS), choices=list(GROUPS))
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", type=str, default="")
    args = ap.parse_args()

    P.ensure_reproducible()
    args = ap.parse_args()
    seeds = [args.seed_base + i for i in range(args.games)]

    print("=" * 104)
    print("  实验 10：P0 修复前/ 后 终局对照（speed={} turns={} games={}）".format(
        args.speed, args.turns, args.games))
    print("=" * 104)
    print("  before     : PEAK 不可通行 + 跨城兜底将领（= 修复前）")
    print("  after      : PEAK 可通行 + 不跨城兜底（= 当前工作区已实施）")
    print("  after_full : after + 补全_find_general_in_city 的跨城兜底（修复补全）")
    print(f"  seeds={seeds}（三组共用，配对设计）")
    print("=" * 104)

    rows: List[Dict[str, Any]] = []
    t0 = time.time()
    for g in args.groups:
        got: List[Dict[str, Any]] = []
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            for r in ex.map(_worker, [(s, args.speed, args.turns, g) for s in seeds]):
                got.append(r)
        got.sort(key=lambda r: r["seed"])
        for r in got:
            print(f"  {g:>11} seed={r['seed']} 出征={r['attacks']:>4}(成功{r['attacks_ok']:>4},"
                  f"{r['ok_rate']*100:>5.1f}%) 战斗={r['battles']:>3} 存活={r['surviving']:>2}"
                  f" top={r['top_share']:.2f} 剩中立={r['neutral_left']:>2} winner={r['winner']}")
        rows.extend(got)

    print("\n" + "=" * 104)
    print("  P0 修复前/后对照总表（中位数，N={} 局/组）".format(args.games))
    print("=" * 104)
    print(f"    {'group':>12}{'出征':>9}{'成功率':>10}{'战斗/局':>10}{'战斗/回合':>11}"
          f"{'存活势力':>10}{'最大占比':>10}{'HHI':>8}{'剩中立城':>10}")
    med = statistics.median
    for g in args.groups:
        rs = [r for r in rows if r["group"] == g]
        if not rs:
            continue
        print(f"    {g:>12}{med([r['attacks'] for r in rs]):>9.0f}"
              f"{med([r['ok_rate'] for r in rs])*100:>9.1f}%"
              f"{med([r['battles'] for r in rs]):>10.0f}"
              f"{med([r['battles_per_turn'] for r in rs]):>11.3f}"
              f"{med([r['surviving'] for r in rs]):>10.0f}"
              f"{med([r['top_share'] for r in rs]):>10.3f}"
              f"{med([r['hhi'] for r in rs]):>8.3f}"
              f"{med([r['neutral_left'] for r in rs]):>10.0f}")
    print("=" * 104)

    print("\n  失败原因构成对比:")
    for g in args.groups:
        rs = [r for r in rows if r["group"] == g]
        if not rs:
            continue
        agg: Counter = Counter()
        for r in rs:
            agg.update(r["reasons"])
        fail = sum(v for k, v in agg.items() if k != "SUCCESS")
        if not fail:
            print(f"    {g:>12}: 无失败")
            continue
        parts = [f"{k}={v}({v/fail*100:.0f}%)" for k, v in agg.most_common(3) if k != "SUCCESS"]
        print(f"    {g:>12}: 失败 {fail} 次 → " + ", ".join(parts))

    b = [r for r in rows if r["group"] == "before"]
    if b:
        base_b = med([r["battles"] for r in b])
        base_ok = med([r["ok_rate"] for r in b])
        print("\n  相对修复前的增益:")
        for g in args.groups:
            if g == "before":
                continue
            rs = [r for r in rows if r["group"] == g]
            if not rs:
                continue
            m = med([r["battles"] for r in rs])
            o = med([r["ok_rate"] for r in rs])
            print(f"    {g:>12}: 战斗 {base_b:.0f}→{m:.0f} ({(m-base_b)/base_b*100:+.0f}%)"
                  f" | 成功率 {base_ok*100:.0f}%→{o*100:.0f}%"
                  f" | 存活势力 {med([r['surviving'] for r in b]):.0f}→"
                  f"{med([r['surviving'] for r in rs]):.0f}")

    print(f"\n  总耗时 {time.time()-t0:.1f}s")
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"config": vars(args), "rows": rows}, fh, ensure_ascii=False, indent=2)
        print(f"  [已写出 JSON: {args.out}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
