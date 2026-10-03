#!/usr/bin/env python3
"""实验 8：战斗频率的真正上限在哪——CLIPlayer 决策层单变量对照。

实验 1/6/7 的结论链：
  - 行军速度 4→10：战斗不增（26→22）→ 速度不是瓶颈
  - 修general_not_in_city：成功率 13%→65%，战斗不变（31→32）
  - 修 PEAK 阻断：成功率→100%，战斗不变（27→27）
  ⇒ 瓶颈不在「允许打」而在「决定打」：CLIPlayer 主动压低了进攻频率。

CLIPlayer 里的三重压制（本脚本逐项放开做单变量对照）：
  A. `commands[:8]`  —— 每方每回合命令数硬上限，进攻排在前面，超出的被截断
  B. 进攻信心门槛   —— `troops >= tgt_garrison * 1.0`（兵力需≥守军）才敢打
  C. 出手概率       —— `rng.random() < aggression * 1.3` 每回合掷骰

另测 D：放宽「中立城无需兵力优势」的既有逻辑（C 只对中立城放宽）。

运行：
    python tests/balance/exp8_decision_cap.py --games 5 --turns 48
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

import pacing_lib as P                              # noqa: E402
from players.cli_player import CLIPlayer            # noqa: E402
from game.personality import FACTION_PERSONALITY    # noqa: E402

# 变体 -> (命令数上限, 攻击倾向系数, 是否降低敌城兵力门槛)
VARIANTS: Dict[str, tuple] = {
    "base":   (8, 1.3, 1.0),   # 现状
    "cap16":  (16, 1.3, 1.0),  # 仅放开命令数上限
    "agg2":   (8, 2.5, 1.0),   # 仅放开出手概率
    "weak":   (8, 1.3, 0.6),   # 仅降低敌城兵力门槛到 0.6×
    "cap16_agg2": (16, 2.5, 1.0),
    "all":    (16, 2.5, 0.6),  # 三项全放开（上界对照）
}

_ORIG_GET = CLIPlayer.get_commands


def make_get(cmd_cap: int, agg_mult: float, weak_ratio: float):
    """按变体参数复刻 CLIPlayer.get_commands 的决策逻辑。

    为保证「除目标变量外其余完全一致」，这里逐行对照 players/cli_player.py 原文，
    只替换 commands[:cap]、aggression*agg_mult、tgt_garrison*weak_ratio 三处。
    """

    def get_commands(self, observation):
        from game.models import (
            DeclareWarCommand, DevelopCommand, ProposeAllianceCommand,
            RecruitCommand, AttackCommand, MessageCommand, DiplomaticStatus,
        )
        commands = []
        turn = observation.turn
        self._msg_sent = False
        enemy_ids = {c.id for c in observation.known_cities}
        enemy_factions = list({c.faction for c in observation.known_cities
                               if c.faction != self.faction})

        if self._pending_alliance and self._diplomacy > 0.3 and not self._msg_sent:
            commands.append(ProposeAllianceCommand(faction=self.faction, turn=turn,
                                                   to=self._pending_alliance))
            self._msg_sent = True
            self._pending_alliance = None

        has_allies = False
        if observation.faction_relations:
            for rel in observation.faction_relations:
                other = rel.faction_b if rel.faction_a == self.faction else rel.faction_a
                if rel.status == DiplomaticStatus.WAR:
                    enemy_factions.append(other)
                elif rel.status == DiplomaticStatus.ALLIANCE:
                    has_allies = True

        if (self._aggression > 0.6 and not has_allies
                and not self._msg_sent and enemy_factions and turn % 5 == 1):
            target = self._rng.choice(enemy_factions)
            already = any(
                rel.status == DiplomaticStatus.WAR
                for rel in (observation.faction_relations or [])
                if (rel.faction_a == self.faction and rel.faction_b == target)
                or (rel.faction_b == self.faction and rel.faction_a == target)
            )
            if not already:
                commands.append(DeclareWarCommand(faction=self.faction, turn=turn,
                                                  to=target, reason="扩张领土"))
                self._msg_sent = True

        diplo_interval = 2 if self._diplomacy > 0.4 else 3
        if (self._diplomacy > 0.25 and not self._msg_sent
                and enemy_factions and turn % diplo_interval == 0):
            target = self._rng.choice(enemy_factions)
            commands.append(MessageCommand(
                faction=self.faction, turn=turn, to=target,
                content=self._rng.choice(["提议结盟共抗强敌", "互不侵犯如何？", "你我合兵一处，天下可定"]),
            ))
            self._msg_sent = True

        attack_garrison = int(1200 - self._aggression * 800)
        attack_gold = int(400 - self._aggression * 300)
        recruit_gold = int(300 - self._aggression * 150)
        generals_in_city = {g.location for g in observation.own_generals}

        for city in observation.own_cities:
            border = any(nid in enemy_ids for nid in city.neighbors)
            if not border:
                continue
            if (city.garrison >= attack_garrison
                    and city.gold >= attack_gold
                    and self._rng.random() < min(1.0, self._aggression * agg_mult)):
                target = CLIPlayer._find_attack_target(city, enemy_ids, observation)
                if target:
                    tgt_garrison = 0
                    tgt_is_neutral = False
                    for kc in observation.known_cities:
                        if kc.id == target:
                            tgt_garrison = getattr(kc, "garrison", 0) or 0
                            tgt_is_neutral = kc.faction not in FACTION_PERSONALITY
                            break
                    desired = int(3000 * max(0.4, self._aggression))
                    if tgt_garrison:
                        desired = max(desired, int(tgt_garrison * 1.3) + 200)
                    troops = min(city.garrison - 100, desired)
                    if tgt_is_neutral:
                        confident = troops >= 200
                    else:
                        # weak_ratio <1 → 放宽「兵力需≥守军」的门槛
                        confident = (troops >= 200) and (
                            tgt_garrison == 0 or troops >= tgt_garrison * weak_ratio
                        )
                    if confident:
                        # 关键修复：只在本城有将领时才出征（否则必被引擎拒）
                        gen = next((g for g in observation.own_generals
                                    if g.location == city.id), None)
                        general_id = gen.id if gen else ""
                        if general_id:
                            commands.append(AttackCommand(
                                faction=self.faction, turn=turn,
                                from_city=city.id, to_city=target,
                                troops=troops, general=general_id,
                            ))
                            continue
            if city.gold >= recruit_gold and city.garrison < 3000:
                commands.append(RecruitCommand(
                    faction=self.faction, turn=turn,
                    city=city.id, troops=min(1000, city.gold // 1),
                ))

        max_cmds = int(4 + self._expand * 4)
        for city in observation.own_cities:
            if len(commands) >= max_cmds:
                break
            dev_gold = int(500 - self._expand * 200)
            if city.gold >= dev_gold:
                if self._expand > self._aggression and self._expand > 0.3:
                    dev_type = "economy"
                elif self._aggression > 0.6:
                    dev_type = "military"
                else:
                    dev_type = ["economy", "military", "culture"][(turn + len(commands)) % 3]
                commands.append(DevelopCommand(
                    faction=self.faction, turn=turn, city=city.id, develop_type=dev_type,
                ))

        return commands[:cmd_cap]

    return get_commands


def run_one(seed: int, speed: int, max_turns: int, variant: str) -> Dict[str, Any]:
    from game.engine import GameEngine
    from game.data_loader import load_game_data
    from exp4_terrain import apply_variant as av, restore, VARIANTS as TV

    cap, agg, weak = VARIANTS[variant]
    P.set_march_speed(speed)
    av("nopeak")            # 地形修复作为共同基线（已验证是必要前提）
    CLIPlayer.get_commands = make_get(cap, agg, weak)
    try:
        engine = GameEngine(seed=seed)
        engine.init_game(load_game_data())
        engine.max_turns = max_turns
        players = P.make_players(seed)
        atk = atk_ok = battles = 0
        cmd_counts: Counter = Counter()
        while not engine.game_over:
            for f in P.FACTION_KEYS:
                obs = engine.get_observation(f)
                cmds = players[f].get_commands(obs)
                cmd_counts[len(cmds)] += 1
                for cmd in cmds:
                    from game.models import AttackCommand
                    if isinstance(cmd, AttackCommand):
                        atk += 1
                        if engine.execute_command(cmd).success:
                            atk_ok += 1
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
        return {
            "seed": seed, "variant": variant, "speed": speed, "max_turns": max_turns,
            "end_turn": engine.turn, "winner": engine.winner,
            "attacks": atk, "attacks_ok": atk_ok,
            "ok_rate": round(atk_ok / atk, 3) if atk else 0.0,
            "battles": battles, "battles_per_turn": round(battles / max(1, engine.turn), 3),
            "surviving": len(active),
            "top_share": round(max(active.values()) / tot, 3),
            "hhi": round(sum((n / tot) ** 2 for n in active.values()), 4),
            "neutral_left": sum(1 for c in engine.cities.values() if c.faction == "neutral"),
            "cmd_count_dist": dict(cmd_counts),
        }
    finally:
        CLIPlayer.get_commands = _ORIG_GET
        restore()


def _worker(p):
    return run_one(*p)


def main() -> int:
    P.ensure_reproducible()  # 🔴 可复现性守卫（固定 PYTHONHASHSEED=0）
    ap = argparse.ArgumentParser(description="实验8：CLIPlayer 决策层单变量对照")
    ap.add_argument("--speed", type=int, default=4)
    ap.add_argument("--turns", type=int, default=48)
    ap.add_argument("--games", type=int, default=5)
    ap.add_argument("--seed-base", type=int, default=97001)
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
    print("  实验 8：CLIPlayer 决策层单变量对照（speed={} turns={} games={}共同基线=nopeak）".format(
        args.speed, args.turns, args.games))
    print("=" * 104)
    print("  变体说明: base=(cap8,agg1.3,敌城门槛1.0) cap16=(16,1.3,1.0) agg2=(8,2.5,1.0)")
    print("           weak=(8,1.3,0.6) cap16_agg2=(16,2.5,1.0) all=(16,2.5,0.6)")
    print("  注：本实验所有变体均已包含「将领归属修复」+「PEAK 可通行」两个前提修复")
    print("=" * 104)

    rows: List[Dict[str, Any]] = []
    t0 = time.time()
    for v in args.variants:
        cap, agg, weak = VARIANTS[v]
        got: List[Dict[str, Any]] = []
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            for r in ex.map(_worker, [(s, args.speed, args.turns, v) for s in seeds]):
                got.append(r)
        got.sort(key=lambda r: r["seed"])
        for r in got:
            print(f"  {v:>11} seed={r['seed']} 战斗={r['battles']:>3}"
                  f"({r['battles_per_turn']:.2f}/回合) 出征={r['attacks']:>4}"
                  f"(成功{r['attacks_ok']:>4}) 存活={r['surviving']:>2}"
                  f" top={r['top_share']:.2f} 剩中立={r['neutral_left']:>2} winner={r['winner']}")
        rows.extend(got)

    print("\n" + "=" * 104)
    print("  决策层对照总表（中位数，N={}局/组，同 seed 配对）".format(args.games))
    print("=" * 104)
    print(f"    {'variant':>12}{'参数':>18}{'战斗/局':>10}{'战斗/回合':>11}{'成功出征':>10}"
          f"{'存活势力':>10}{'最大占比':>10}{'HHI':>8}{'剩中立城':>10}")
    med = statistics.median
    for v in args.variants:
        rs = [r for r in rows if r["variant"] == v]
        if not rs:
            continue
        cap, agg, weak = VARIANTS[v]
        print(f"    {v:>12}{f'({cap},{agg},{weak})':>18}"
              f"{med([r['battles'] for r in rs]):>10.0f}"
              f"{med([r['battles_per_turn'] for r in rs]):>11.3f}"
              f"{med([r['attacks_ok'] for r in rs]):>10.0f}"
              f"{med([r['surviving'] for r in rs]):>10.0f}"
              f"{med([r['top_share'] for r in rs]):>10.3f}"
              f"{med([r['hhi'] for r in rs]):>8.3f}"
              f"{med([r['neutral_left'] for r in rs]):>10.0f}")
    print("=" * 104)

    print("\n  结论: 战斗频率对哪个变量最敏感")
    base = [r for r in rows if r["variant"] == "base"]
    if base:
        b = med([r["battles"] for r in base])
        for v in args.variants:
            if v == "base":
                continue
            rs = [r for r in rows if r["variant"] == v]
            if not rs:
                continue
            m = med([r["battles"] for r in rs])
            delta = (m - b) / b * 100 if b else 0
            flag = "🔴 显著提升" if delta >= 30 else ("🟡 小幅" if delta > 5 else "⚪ 无变化")
            print(f"    {v:>12}: 战斗 {b:.0f} → {m:.0f} ({delta:+.0f}%){flag}")

    print(f"\n  总耗时 {time.time()-t0:.1f}s")
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"config": vars(args), "rows": rows}, fh, ensure_ascii=False, indent=2)
        print(f"  [已写出 JSON: {args.out}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
