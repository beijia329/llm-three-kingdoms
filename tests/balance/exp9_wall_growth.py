#!/usr/bin/env python3
"""实验 9：城墙「越修越硬」机制的单变量对照（决定战争能否决定胜负）。

实验 8 已证明放宽进攻门槛能让战斗翻倍（+120%），但**存活势力仍 11~12/12**，
没有任何一方被灭统一。追查发现根因在 `game/systems/city_system.py:140-148`
的 military 发展：

    elif develop_type == "military":
        wall_increase = MILITARY_WALL_REPAIR          # = 200
        city.wall_hp     = min(wall_hp + 200, wall_max_hp + 200)
        city.wall_max_hp += 200# ←⚠️ 上限被永久抬高，永不回落

即「发展军事」不是修复城墙，而是**每回合永久抬高城墙上限 200 点**。
实测许昌 40 回合内wall_max_hp 从 3200 涨到 7400（+131%），
而 `WALL_DAMAGE_BASE` 每回合只有 400 且需先打完巷战 → 城墙永远打不破。

本脚本对照三种规则（单变量，只改这一处语义）：
  base:  现状（wall_max_hp 永久 +200）
  cap:   修复墙到满血，但**上限不永久增长**（wall_max_hp 不变）← 推荐
  hard:  进一步把墙做成真壁垒（每回合伤害提高 2 倍，模拟"血更厚"）

运行：
    python tests/balance/exp9_wall_growth.py --games 5 --turns 96
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
import game.systems.city_system as CS  # noqa: E402
import game.constants as C              # noqa: E402

# 变体 -> (military 发展是否永久抬高 wall_max_hp, 攻城伤害倍率)
VARIANTS: Dict[str, tuple] = {
    "base": (True, 1.0),    # 现状
    "cap":  (False, 1.0),   # 只修墙不涨上限（推荐）
    "hard": (False, 2.0),   # 不涨上限 + 攻城伤害×2
}

_ORIG_DEVELOP = CS.CitySystem.develop


def make_develop(grow_max: bool):
    """按变体重写 military 发展分支；其余（economy/culture/校验/扣钱）完全不动。"""

    def develop(self, city, develop_type):
        if develop_type != "military":
            return _ORIG_DEVELOP(self, city, develop_type)
        # 复制原始校验：无效类型 + 金钱门槛（成本由 _calculate_develop_cost 决定）
        from game.systems.city_system import DevelopResult
        if develop_type not in ("economy", "military", "culture"):
            return DevelopResult(success=False, develop_type=develop_type,
                                 description=f"无效的发展类型: {develop_type}")
        gold_cost = self._calculate_develop_cost(city)
        if city.gold < gold_cost:
            return DevelopResult(
                success=False, develop_type=develop_type, gold_cost=gold_cost,
                description=f"金钱不足: 需要{gold_cost}, 当前{city.gold}",
            )
        city.gold -= gold_cost
        inc = CS.MILITARY_WALL_REPAIR
        if grow_max:
            # 现状：上限也永久 +200（越修越硬）
            city.wall_hp = min(city.wall_hp + inc, city.wall_max_hp + inc)
            city.wall_max_hp += inc
        else:
            # 修复版：只把当前耐久修到上限，上限不增长
            city.wall_hp = min(city.wall_hp + inc, city.wall_max_hp)
        return DevelopResult(success=True, develop_type=develop_type, gold_cost=gold_cost,
                             description="军事发展", effect_value=inc)

    return develop


def run_one(seed: int, speed: int, max_turns: int, variant: str) -> Dict[str, Any]:
    from game.engine import GameEngine
    from game.data_loader import load_game_data
    from exp8_decision_cap import make_get   # 复用决策层「weak」修复
    from players.cli_player import CLIPlayer
    from exp4_terrain import apply_variant, restore

    grow_max, dmg_mult = VARIANTS[variant]
    P.set_march_speed(speed)
    apply_variant("nopeak")                # 共同前提：PEAK 可通行
    CLIPlayer.get_commands = make_get(8, 1.3, 0.6)   # 共同前提：放宽进攻门槛
    CS.CitySystem.develop = make_develop(grow_max)
    C.WALL_DAMAGE_BASE = int(400 * dmg_mult)
    try:
        engine = GameEngine(seed=seed)
        engine.init_game(load_game_data())
        engine.max_turns = max_turns
        players = P.make_players(seed)
        battles = atk_ok = 0
        wall_ratio_samples: List[float] = []
        while not engine.game_over:
            for f in P.FACTION_KEYS:
                for cmd in players[f].get_commands(engine.get_observation(f)):
                    if type(cmd).__name__ == "AttackCommand":
                        atk_ok += int(engine.execute_command(cmd).success)
                    else:
                        engine.execute_command(cmd)
            battles += int(engine.process_turn().get("battles_fought", 0) or 0)
            if engine.turn % 12 == 0 and engine.cities:
                ratios = [c.wall_hp / c.wall_max_hp for c in engine.cities.values()
                          if c.wall_max_hp > 0]
                wall_ratio_samples.append(sum(ratios) / max(1, len(ratios)))
            if engine.turn > 400:
                break
        counts = Counter(c.faction for c in engine.cities.values())
        active = {f: n for f, n in counts.items() if f != "neutral"}
        tot = sum(active.values()) or 1
        walls = [c.wall_hp / c.wall_max_hp for c in engine.cities.values() if c.wall_max_hp > 0]
        return {
            "seed": seed, "variant": variant, "speed": speed, "max_turns": max_turns,
            "end_turn": engine.turn, "winner": engine.winner,
            "surviving": len(active),
            "battles": battles, "attacks_ok": atk_ok,
            "battles_per_turn": round(battles / max(1, engine.turn), 3),
            "cities_taken": tot,
            "top_share": round(max(active.values()) / tot, 3),
            "hhi": round(sum((n / tot) ** 2 for n in active.values()), 4),
            "neutral_left": counts.get("neutral", 0),
            "mean_wall_ratio": round(sum(walls) / max(1, len(walls)), 3),
            "median_wall_max": int(statistics.median(
                [c.wall_max_hp for c in engine.cities.values()])) if engine.cities else 0,
        }
    finally:
        CS.CitySystem.develop = _ORIG_DEVELOP
        C.WALL_DAMAGE_BASE = 400
        restore()


def _worker(p):
    return run_one(*p)


def main() -> int:
    P.ensure_reproducible()  # 🔴 可复现性守卫（固定 PYTHONHASHSEED=0）
    ap = argparse.ArgumentParser(description="实验9：城墙增长机制对照")
    ap.add_argument("--speed", type=int, default=4)
    ap.add_argument("--turns", type=int, default=96)
    ap.add_argument("--games", type=int, default=5)
    ap.add_argument("--seed-base", type=int, default=98001)
    ap.add_argument("--variants", nargs="+", default=list(VARIANTS.keys()))
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--baseline", action="store_true",
                    help="把 P0 相关属性锁定为修复前取值（对抗并发修改，保证对照有效）")
    ap.add_argument("--out", type=str, default="")
    args = ap.parse_args()
    if args.baseline:  # 对抗并发修改：把 P0 属性锁回"修复前"
        _ok = P.use_pristine_baseline(True)
        print("  [基线锁定] " + ("已还原为修复前取值" if _ok else "失败（继续用工作区）"))

    seeds = [args.seed_base + i for i in range(args.games)]
    print("=" * 104)
    print("  实验 9：城墙「越修越硬」机制对照（speed={} turns={} games={}）".format(
        args.speed, args.turns, args.games))
    print("=" * 104)
    print("  共同前提（已各自验证）：PEAK可通行 + 放宽进攻门槛(0.6×)")
    print("  变体: base=(上限永久+200, 伤害×1) cap=(上限不增长, ×1) hard=(上限不增长, ×2)")
    print("=" * 104)

    rows: List[Dict[str, Any]] = []
    t0 = time.time()
    for v in args.variants:
        got: List[Dict[str, Any]] = []
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            for r in ex.map(_worker, [(s, args.speed, args.turns, v) for s in seeds]):
                got.append(r)
        got.sort(key=lambda r: r["seed"])
        for r in got:
            print(f"  {v:>6} seed={r['seed']} 战斗={r['battles']:>3} 存活={r['surviving']:>2}"
                  f" 最大占比={r['top_share']:.2f} HHI={r['hhi']:.3f}"
                  f" 城墙完好率={r['mean_wall_ratio']:.2f} 剩中立={r['neutral_left']:>2}"
                  f" winner={r['winner']}")
        rows.extend(got)

    print("\n" + "=" * 104)
    print("  城墙机制对照总表（中位数，N={} 局/组）".format(args.games))
    print("=" * 104)
    print(f"    {'variant':>8}{'战斗/局':>10}{'存活势力':>10}{'最大占比':>10}{'HHI':>8}"
          f"{'城墙完好率':>12}{'剩中立城':>10}{'统一局数':>10}")
    med = statistics.median
    for v in args.variants:
        rs = [r for r in rows if r["variant"] == v]
        if not rs:
            continue
        print(f"    {v:>8}{med([r['battles'] for r in rs]):>10.0f}"
              f"{med([r['surviving'] for r in rs]):>10.0f}"
              f"{med([r['top_share'] for r in rs]):>10.3f}"
              f"{med([r['hhi'] for r in rs]):>8.3f}"
              f"{med([r['mean_wall_ratio'] for r in rs]):>12.3f}"
              f"{med([r['neutral_left'] for r in rs]):>10.0f}"
              f"{sum(1 for r in rs if r['surviving']==1):>10}")
    print("=" * 104)
    print(f"  总耗时 {time.time()-t0:.1f}s")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"config": vars(args), "rows": rows}, fh, ensure_ascii=False, indent=2)
        print(f"  [已写出 JSON: {args.out}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
