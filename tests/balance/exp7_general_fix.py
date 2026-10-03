#!/usr/bin/env python3
"""实验 7：CLIPlayer 将领归属修复的单变量对照（最高价值杠杆）。

实验 6 归因：74.6% 的进攻失败来自 `general_not_in_city`
（`players/cli_player.py:156` 的 `observation.own_generals[0]` 兜底：
 当出发城没有本地将领时，代码仍取「己方第一个将领」，而该将领在别的城，
 于是被 `engine._execute_attack` 第 5 道校验「将领不在出发城」拒掉）。

本脚本**不改源码**，在运行时给 CLIPlayer 打一个最小补丁：
  出发城没有本地将领 → 跳过该城的进攻（不再发非法命令），
再对照「修复后」的出征成功率 / 战斗场次 / 统一度。

这用于量化「修这个 bug 到底值多少」，供决策：是否值得改 players/cli_player.py。

运行：
    python tests/balance/exp7_general_fix.py --games 5 --turns 48
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

import pacing_lib as P                    # noqa: E402
from game.models import AttackCommand, Command  # noqa: E402
from players.cli_player import CLIPlayer  # noqa: E402
from exp4_terrain import apply_variant, restore, VARIANTS  # noqa: E402
from exp6_attack_reject import classify   # noqa: E402

_ORIG_GET = CLIPlayer.get_commands


def patched_get_commands(self, observation) -> List[Command]:
    """修复版：过滤掉「出发城无本地将领」的非法进攻命令。

    只做一件事——把 CLIPlayer 原本会发出的、必然被引擎拒绝的 AttackCommand 剔除，
    不改变任何其他决策逻辑（发展/征兵/外交/目标选择全部保持原样），
    因此是干净的单变量对照。
    """
    cmds = _ORIG_GET(self, observation)
    if not any(isinstance(c, AttackCommand) for c in cmds):
        return cmds
    generals_in_city = {g.location for g in observation.own_generals}
    return [
        c for c in cmds
        if not (isinstance(c, AttackCommand) and c.from_city not in generals_in_city)
    ]


def run_one(seed: int, speed: int, max_turns: int, variant: str, fix: bool) -> Dict[str, Any]:
    from game.engine import GameEngine
    from game.data_loader import load_game_data

    P.set_march_speed(speed)
    apply_variant(variant)
    CLIPlayer.get_commands = patched_get_commands if fix else _ORIG_GET
    try:
        engine = GameEngine(seed=seed)
        engine.init_game(load_game_data())
        engine.max_turns = max_turns
        players = P.make_players(seed)

        atk_total = atk_ok = battles = 0
        reasons: Counter = Counter()
        while not engine.game_over:
            for f in P.FACTION_KEYS:
                obs = engine.get_observation(f)
                for cmd in players[f].get_commands(obs):
                    if isinstance(cmd, AttackCommand):
                        atk_total += 1
                        r = engine.execute_command(cmd)
                        if r.success:
                            atk_ok += 1
                            reasons["SUCCESS"] += 1
                        else:
                            reasons[classify(r.description)] += 1
                    else:
                        engine.execute_command(cmd)
            battles += int(engine.process_turn().get("battles_fought", 0) or 0)
            if engine.turn > 400:
                break

        counts = {f: 0 for f in P.FACTION_KEYS}
        for c in engine.cities.values():
            if c.faction in counts:
                counts[c.faction] += 1
        active = {f: n for f, n in counts.items() if n > 0}
        tot = sum(active.values()) or 1
        neutral_left = sum(1 for c in engine.cities.values() if c.faction == "neutral")
        return {
            "seed": seed, "speed": speed, "max_turns": max_turns, "variant": variant,
            "fix": fix, "end_turn": engine.turn, "winner": engine.winner,
            "attack_total": atk_total, "attack_ok": atk_ok,
            "attack_ok_rate": round(atk_ok / atk_total, 3) if atk_total else 0.0,
            "battles": battles,
            "battles_per_turn": round(battles / max(1, engine.turn), 3),
            "neutral_left": neutral_left,
            "surviving_factions": len(active),
            "top_share": round(max(active.values()) / tot, 3),
            "hhi": round(sum((n / tot) ** 2 for n in active.values()), 4),
            "reasons": dict(reasons),
        }
    finally:
        CLIPlayer.get_commands = _ORIG_GET
        restore()


def _worker(p):
    return run_one(*p)


def main() -> int:
    P.ensure_reproducible()  # 🔴 可复现性守卫（固定 PYTHONHASHSEED=0）
    ap = argparse.ArgumentParser(description="实验7：将领归属修复对照")
    ap.add_argument("--speed", type=int, default=4)
    ap.add_argument("--turns", type=int, default=48)
    ap.add_argument("--games", type=int, default=6)
    ap.add_argument("--seed-base", type=int, default=96001)
    ap.add_argument("--variant", default="base", choices=list(VARIANTS.keys()))
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--baseline", action="store_true",
                    help="把 P0 相关属性锁定为修复前取值（对抗并发修改，保证对照有效）")
    ap.add_argument("--out", type=str, default="")
    args = ap.parse_args()
    if args.baseline:  # 对抗并发修改：把 P0 属性锁回"修复前"
        _ok = P.use_pristine_baseline(True)
        print("  [基线锁定] " + ("已还原为修复前取值" if _ok else "失败（继续用工作区）"))

    seeds = [args.seed_base + i for i in range(args.games)]
    print("=" * 100)
    print("  实验 7：CLIPlayer 将领归属修复对照（speed={} turns={} variant={}）".format(
        args.speed, args.turns, args.variant))
    print("=" * 100)

    rows: List[Dict[str, Any]] = []
    t0 = time.time()
    for fix in (False, True):
        label = "修复后(fix)" if fix else "现状(base)"
        print(f"\n  ---- {label} ----")
        payloads = [(s, args.speed, args.turns, args.variant, fix) for s in seeds]
        got: List[Dict[str, Any]] = []
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            for r in ex.map(_worker, payloads):
                got.append(r)
        got.sort(key=lambda r: r["seed"])
        for r in got:
            print(f"    seed={r['seed']} turns={r['end_turn']:>3} 出征={r['attack_total']:>4}"
                  f"(成功{r['attack_ok']:>3}, {r['attack_ok_rate']*100:>4.0f}%) 战斗={r['battles']:>3}"
                  f" 存活={r['surviving_factions']:>2} top={r['top_share']:.2f}"
                  f" 剩中立={r['neutral_left']:>2} winner={r['winner']}")
        rows.extend(got)

    print("\n" + "=" * 100)
    print("  修复前后对照（中位数，N={}局/组，同 seed 配对）".format(args.games))
    print("=" * 100)
    print(f"    {'组':>14}{'出征成功率':>12}{'战斗场次':>10}{'战斗/回合':>11}"
          f"{'存活势力':>10}{'最大占比':>10}{'HHI':>9}{'剩中立城':>10}")
    med = statistics.median
    base = [r for r in rows if not r["fix"]]
    fixd = [r for r in rows if r["fix"]]
    for label, rs in (("现状", base), ("修复后", fixd)):
        if not rs:
            continue
        print(f"    {label:>14}{med([r['attack_ok_rate'] for r in rs])*100:>11.0f}%"
              f"{med([r['battles'] for r in rs]):>10.0f}"
              f"{med([r['battles_per_turn'] for r in rs]):>11.3f}"
              f"{med([r['surviving_factions'] for r in rs]):>10.0f}"
              f"{med([r['top_share'] for r in rs]):>10.3f}"
              f"{med([r['hhi'] for r in rs]):>9.3f}"
              f"{med([r['neutral_left'] for r in rs]):>10.0f}")

    print("\n  被拒原因对比:")
    for label, rs in (("现状", base), ("修复后", fixd)):
        agg: Counter = Counter()
        for r in rs:
            agg.update(r["reasons"])
        fail = sum(v for k, v in agg.items() if k != "SUCCESS")
        if not fail:
            continue
        parts = [f"{k}={v}({v/fail*100:.0f}%)" for k, v in agg.most_common(4) if k != "SUCCESS"]
        print(f"    {label:>6} 失败{sum(r['attack_total']-r['attack_ok'] for r in rs):>4}次: "
              + ", ".join(parts))

    print(f"\n  总耗时 {time.time()-t0:.1f}s")
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"config": vars(args), "rows": rows}, fh, ensure_ascii=False, indent=2)
        print(f"  [已写出 JSON: {args.out}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
