#!/usr/bin/env python3
"""实验 5：战斗稀少的根因诊断（为什么提高行军速度不增加战斗？）。

实验 1 的反直觉结果：ARMY_MARCH_SPEED 从 4 → 10（2.5 倍），战斗场次不升反降
（26 → 22 中位数）。这说明「行军速度」不是战斗频率的瓶颈。本脚本沿「出征→抵达→交战」
链路逐段量化，找出真正的堵点。

逐回合统计：
  - 出征命令数（AttackCommand 实际下达数）
  - 因兵力/资金/守军门槛被CLIPlayer 自己否决的次数（对比「想打」与「真打」）
  - 军队在途数（status=MARCHING）
  - 抵达数 / 抵达后并入守军（disbanded）数
  - 战斗结算数
  - 每回合各势力拥有的「可交战邻接对」数量（结构性上限）

关键判据：若「在途军队」长期为 0 而「战斗」也少 → 堵点在「决策/门槛」；
若「在途军队」很多但「战斗」少 → 堵点在「抵达后不交战（如双方守军差距过大被判定不可打）」。

运行：
    python tests/balance/exp5_bottleneck.py --speeds 4 10 --turns 40
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Dict, List

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import pacing_lib as P# noqa: E402
from game.models import ArmyStatus, AttackCommand      # noqa: E402
from exp4_terrain import apply_variant, VARIANTS      # noqa: E402


def diagnose_one(seed: int, speed: int, max_turns: int, variant: str = "base") -> Dict[str, Any]:
    """跑一局并逐段统计出征链路。"""
    from game.engine import GameEngine
    from game.data_loader import load_game_data

    P.set_march_speed(speed)
    apply_variant(variant)
    engine = GameEngine(seed=seed)
    engine.init_game(load_game_data())
    engine.max_turns = max_turns
    players = P.make_players(seed)

    attack_cmds = 0
    attack_ok = 0
    battle_total = 0
    in_flight_max = 0
    in_flight_sum = 0
    turn_samples: List[Dict[str, Any]] = []
    # 「想打但被门槛否决」：CLI 层观测到的边境城数 vs 实际下达的AttackCommand 数
    border_opportunities = 0
    attack_results = Counter()

    t0 = time.time()
    while not engine.game_over:
        turn_attacks = 0
        for f in P.FACTION_KEYS:
            obs = engine.get_observation(f)
            enemy_ids = {c.id for c in obs.known_cities}
            # 机会数：自家边境城（有敌方邻居）的数量
            border_opportunities += sum(
                1 for c in obs.own_cities if any(n in enemy_ids for n in c.neighbors)
            )
            cmds = players[f].get_commands(obs)
            for cmd in cmds:
                if isinstance(cmd, AttackCommand):
                    attack_cmds += 1
                    turn_attacks += 1
                res = engine.execute_command(cmd)
                if isinstance(cmd, AttackCommand):
                    # CommandResult 是 dataclass（.success），不是 dict
                    ok = bool(getattr(res, "success", False))
                    if ok:
                        attack_ok += 1
                    attack_results[ok] += 1
        before = len(engine.armies)
        res = engine.process_turn()
        nb = int(res.get("battles_fought", 0) or 0)
        battle_total += nb

        marching = sum(1 for a in engine.armies.values() if a.status == ArmyStatus.MARCHING)
        besieging = sum(1 for a in engine.armies.values() if a.status == ArmyStatus.BESIEGING)
        in_flight = marching + besieging
        in_flight_max = max(in_flight_max, in_flight)
        in_flight_sum += in_flight
        turn_samples.append({
            "turn": engine.turn, "attacks": turn_attacks, "battles": nb,
            "marching": marching, "besieging": besieging, "armies_total": len(engine.armies),
        })
        if engine.turn > 400:
            break

    from exp4_terrain import restore
    restore()

    # 在途军队的「平均存活回合」：出击后多久才落地/交战
    samples = turn_samples
    n = len(samples) or 1
    return {
        "seed": seed, "speed": speed, "max_turns": max_turns, "variant": variant,
        "end_turn": engine.turn,
        "attack_cmds": attack_cmds,
        "attack_ok": attack_ok,
        "border_opportunities": border_opportunities,
        "attack_success_rate": round(attack_ok / attack_cmds, 3) if attack_cmds else 0.0,
        "battles": battle_total,
        "in_flight_mean": round(in_flight_sum / n, 2),
        "in_flight_max": in_flight_max,
        "battles_per_100_turns": round(battle_total / n * 100, 1),
        "attacking_turns": sum(1 for s in samples if s["attacks"] > 0),
        "battle_turns": sum(1 for s in samples if s["battles"] > 0),
        "elapsed_s": round(time.time() - t0, 2),
        "samples_head": samples[:12],
    }


def _worker(payload):
    return diagnose_one(*payload)


def main() -> int:
    P.ensure_reproducible()  # 🔴 可复现性守卫（固定 PYTHONHASHSEED=0）
    ap = argparse.ArgumentParser(description="实验5：战斗稀少根因诊断")
    ap.add_argument("--speeds", type=int, nargs="+", default=[4, 10])
    ap.add_argument("--games", type=int, default=3)
    ap.add_argument("--turns", type=int, default=40)
    ap.add_argument("--seed-base", type=int, default=94001)
    ap.add_argument("--variant", default="base", choices=list(VARIANTS.keys()))
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", type=str, default="")
    args = ap.parse_args()

    seeds = [args.seed_base + i for i in range(args.games)]
    print("=" * 100)
    print("  实验 5：出征链路逐段诊断（找出战斗稀少的真正堵点）")
    print("=" * 100)
    print(f"  speed ∈ {args.speeds}, turns={args.turns}, games={args.games}, "
          f"variant={args.variant}, seeds={seeds}")
    print("=" * 100)

    rows: List[Dict[str, Any]] = []
    for sp in args.speeds:
        payloads = [(s, sp, args.turns, args.variant) for s in seeds]
        got: List[Dict[str, Any]] = []
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            for r in ex.map(_worker, payloads):
                got.append(r)
        got.sort(key=lambda r: r["seed"])
        for r in got:
            print(f"\n    --- speed={sp} seed={r['seed']} ---")
            print(f"      出征命令={r['attack_cmds']:>5}  成功={r['attack_ok']:>5}"
                  f" (成功率 {r['attack_success_rate']*100:.0f}%)")
            print(f"      边境机会={r['border_opportunities']:>5}"
                  f"  → 实际出征率={r['attack_cmds']/max(1,r['border_opportunities'])*100:.1f}%")
            print(f"      战斗={r['battles']:>4}  每百回合={r['battles_per_100_turns']:.1f}")
            print(f"      在途军队 均值={r['in_flight_mean']:.1f} 峰值={r['in_flight_max']}")
            print(f"      有出征的回合={r['attacking_turns']}  有战斗的回合={r['battle_turns']}"
                  f"  (共{r['end_turn']}回合)")
            print(f"      前12回合轨迹 (turn:攻击/战斗/在途行军/围城):")
            for s in r["samples_head"]:
                print(f"        t{s['turn']:>3}: atk={s['attacks']:>2} bat={s['battles']:>2} "
                      f"march={s['marching']:>2} besiege={s['besieging']:>2} armies={s['armies_total']:>3}")
        rows.extend(got)
        print()

    print("=" * 100)
    print("  汇总（每 speed 的中位数）")
    print("=" * 100)
    print(f"    {'speed':>6}{'出征命令':>10}{'成功率':>9}{'战斗':>7}{'每百回合战斗':>13}"
          f"{'在途均值':>10}{'在途峰值':>10}{'出征回合占比':>13}")
    import statistics
    for sp in args.speeds:
        rs = [r for r in rows if r["speed"] == sp]
        if not rs:
            continue
        med = statistics.median
        print(f"    {sp:>6}{med([r['attack_cmds'] for r in rs]):>10.0f}"
              f"{med([r['attack_success_rate'] for r in rs])*100:>8.0f}%"
              f"{med([r['battles'] for r in rs]):>7.0f}"
              f"{med([r['battles_per_100_turns'] for r in rs]):>13.1f}"
              f"{med([r['in_flight_mean'] for r in rs]):>10.1f}"
              f"{med([r['in_flight_max'] for r in rs]):>10.0f}"
              f"{med([r['attacking_turns']/max(1,r['end_turn']) for r in rs])*100:>12.0f}%")

    print("\n  判读:")
    print("    · 出征命令多、在途军队多、但战斗少 → 堵点在「抵达后不打/打了没赢」")
    print("    · 出征命令少、边境机会多         → 堵点在 CLIPlayer 决策门槛（不敢打）")
    print("    · 在途军队≈0 且战斗少            → 堵点在出征意愿，地图/速度不是瓶颈")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"config": vars(args), "rows": rows}, fh, ensure_ascii=False, indent=2)
        print(f"\n  [已写出 JSON: {args.out}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
