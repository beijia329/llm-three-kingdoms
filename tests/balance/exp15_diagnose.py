#!/usr/bin/env python3
"""实验 15-a：灭国压力【根因定位】——为什么 12 势力一个也灭不掉？

【只读研究】不修改 game/ 或 web/。所有探针均为**进程内 monkeypatch**：
  - execute_command         → 记录发出的 AttackCommand（谁、从哪、打哪、多少兵）
  - _apply_battle_result    → 记录每场战斗双方兵力/结果/是否夺城
  - 每回合快照              → 各势力城数/守军/金粮、边境城市数与「结构性可攻数量」

【回答的问题】
1. 势力是否曾被打到 1 城 / 0 城？（灭国是否真的发生过）
2. 城池反复易主的规模有多大？（翻手次数 / 重夺次数）
3. 攻方为何在打下城后守不住？（夺城后守军 vs 下一回合反攻兵力）
4. 「结构性可攻机会」是否长期存在？（还是双方守军都顶到上限 → 谁都打不动）

运行：
    export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONHASHSEED=0
    ./venv/bin/python tests/balance/exp15_diagnose.py --games 5 --turns 60
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from typing import Any, Dict, List

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import pacing_lib as P                              # noqa: E402
from game.data_loader import load_game_data         # noqa: E402
from game.engine import GameEngine                  # noqa: E402

F = P.FACTION_KEYS


def run_one(seed: int, max_turns: int) -> Dict[str, Any]:
    engine = GameEngine(seed=seed)
    engine.init_game(load_game_data())
    engine.max_turns = int(max_turns)
    players = P.make_players(seed)

    battles: List[Dict[str, Any]] = []
    attacks: List[Dict[str, Any]] = []
    flips: Counter = Counter()
    captures: List[Dict[str, Any]] = []
    timeline: List[Dict[str, Any]] = []
    prev_owner = {cid: c.faction for cid, c in engine.cities.items()}

    # ---- 探针 1：战斗结果 ----
    orig_apply = engine._apply_battle_result

    def wrapped_apply(ctx, result):
        battles.append({
            "turn": engine.turn,
            "attacker": ctx.attacker_faction,
            "defender": ctx.defender_faction,
            "city": ctx.defender_city,
            "atk": int(ctx.attacker_initial_soldiers),
            "dfd": int(ctx.defender_initial_soldiers),
            "result": result.result.value,
            "atk_cas": int(result.attacker_casualties),
            "dfd_cas": int(result.defender_casualties),
        })
        orig_apply(ctx, result)

    engine._apply_battle_result = wrapped_apply  # type: ignore[assignment]

    # ---- 探针 2：发出的进攻命令 ----
    orig_exec = engine.execute_command

    def wrapped_exec(cmd):
        if cmd.type == "attack":
            attacks.append({
                "turn": engine.turn, "faction": cmd.faction,
                "from": cmd.from_city, "to": cmd.to_city, "troops": int(cmd.troops),
            })
        return orig_exec(cmd)

    engine.execute_command = wrapped_exec  # type: ignore[assignment]

    turns = 0
    while not engine.game_over and turns <= P.SAFETY_MAX_ITER:
        for f in F:
            obs = engine.get_observation(f)
            for cmd in players[f].get_commands(obs):
                engine.execute_command(cmd)
        engine.process_turn()
        turns += 1

        # 每回合快照
        counts: Counter = Counter()
        gar_by_f: Counter = Counter()
        gold_by_f: Counter = Counter()
        food_by_f: Counter = Counter()
        border_by_f: Counter = Counter()
        adv_by_f: Counter = Counter()          # 结构性可攻：garrison-100 >= 最优邻城守军
        for c in engine.cities.values():
            if c.faction not in F:
                continue
            counts[c.faction] += 1
            gar_by_f[c.faction] += c.garrison
            gold_by_f[c.faction] += c.gold
            food_by_f[c.faction] += c.food
            enemy_neigh = [engine.cities[n] for n in c.neighbors
                           if n in engine.cities and engine.cities[n].faction != c.faction]
            if enemy_neigh:
                border_by_f[c.faction] += 1
                weakest = min(x.garrison for x in enemy_neigh)
                if c.garrison - 100 >= weakest:
                    adv_by_f[c.faction] += 1

        timeline.append({
            "turn": engine.turn,
            "counts": dict(counts),
            "garrison": dict(gar_by_f),
            "gold": dict(gold_by_f),
            "food": dict(food_by_f),
            "border": dict(border_by_f),
            "attackable": dict(adv_by_f),
        })

        for cid, c in engine.cities.items():
            if c.faction != prev_owner[cid]:
                flips[cid] += 1
                captures.append({"turn": engine.turn, "city": cid,
                                 "from": prev_owner[cid], "to": c.faction})
                prev_owner[cid] = c.faction

    # 终局
    final_counts = Counter(c.faction for c in engine.cities.values() if c.faction in F)
    min_counts = {f: min((t["counts"].get(f, 0) for t in timeline), default=0) for f in F}
    eliminations = {f: next((t["turn"] for t in timeline if t["counts"].get(f, 0) == 0), None)
                    for f in F}

    # 终局快照：满员城市 / 无驻将城市 / 结构性可攻（含与不含"须有本地将领"）
    own_cities = [c for c in engine.cities.values() if c.faction in F]
    gen_locs = {g.location for g in engine.generals.values() if not g.is_captured}
    at_cap = sum(1 for c in own_cities if c.garrison >= c.level * 1000)
    no_gen = sum(1 for c in own_cities if c.id not in gen_locs)
    struct = with_gen = 0
    for c in own_cities:
        en = [engine.cities[n] for n in c.neighbors
              if n in engine.cities and engine.cities[n].faction != c.faction]
        if en and c.garrison - 100 >= min(e.garrison for e in en):
            struct += 1
            if c.id in gen_locs:
                with_gen += 1

    return {
        "seed": seed,
        "turns": engine.turn,
        "game_over": engine.game_over,
        "winner": engine.winner,
        "final_counts": dict(final_counts),
        "min_counts": min_counts,
        "first_zero_turn": eliminations,
        "own_cities": len(own_cities),
        "at_cap_cities": at_cap,
        "no_general_cities": no_gen,
        "struct_attackable": struct,
        "attackable_with_general": with_gen,
        "n_battles": len(battles),
        "battle_results": dict(Counter(b["result"] for b in battles)),
        "n_attacks": len(attacks),
        "flips_total": sum(flips.values()),
        "flip_cities": dict(flips.most_common()),
        "captures": captures,
        "timeline": timeline,
        "battles": battles,
        "attacks": attacks,
    }


def analyze(rows: List[Dict[str, Any]]) -> None:
    print("\n" + "=" * 92)
    print("  根因定位汇总（每局为一个样本）")
    print("=" * 92)
    print(f"{'seed':>5}{'局终回合':>9}{'战斗':>6}{'出征':>6}{'易主次数':>9}"
          f"{'终局城数(min-max)':>18}{'存活势力':>9}{'最惨势力(城)':>14}")
    print("-" * 92)
    for r in rows:
        fc = r["final_counts"]
        surv = sum(1 for v in fc.values() if v > 0)
        minc = min(r["min_counts"].values())
        worst = min(r["min_counts"], key=lambda k: r["min_counts"][k])
        print(f"{r['seed']:>5}{r['turns']:>9}{r['n_battles']:>6}{r['n_attacks']:>6}"
              f"{r['flips_total']:>9}{f'{min(fc.values())}-{max(fc.values())}':>18}"
              f"{surv:>9}{f'{worst}:{minc}':>14}")

    print()
    # 势力曾被压到的最低城数（关键：有没有势力接近过灭国）
    print("  各势力「历史最低城数」（0 = 曾被灭国）—— 合并 5 局取最小值：")
    agg_min = defaultdict(list)
    for r in rows:
        for f, v in r["min_counts"].items():
            agg_min[f].append(v)
    for f in F:
        vals = agg_min[f]
        print(f"    {f:>11}: min={min(vals)}  各局={vals}")

    print()
    br = Counter()
    for r in rows:
        br.update(r["battle_results"])
    print(f"  战斗结果分布（{sum(br.values())} 场）: {dict(br)}")

    # 终局快照聚合（RC1 / RC3 的核心证据）
    tc = sum(r["own_cities"] for r in rows)
    ac = sum(r["at_cap_cities"] for r in rows)
    ng = sum(r["no_general_cities"] for r in rows)
    st = sum(r["struct_attackable"] for r in rows)
    wg = sum(r["attackable_with_general"] for r in rows)
    print()
    print("  终局快照聚合（5 局合计）—— RC1/RC3 核心证据：")
    print(f"    城市数 {tc}  |  满员(守军=等级×1000) {ac}  = {100*ac/tc:.0f}%")
    print(f"    无驻将城市 {ng}  = {100*ng/tc:.0f}%")
    print(f"    结构性可攻机会 {st}  →  加「须有本地将领」后 {wg}  "
          f"（损失 {100*(1-wg/max(1,st)):.0f}%）")

    flips = Counter()
    for r in rows:
        flips.update(r["flip_cities"])
    print()
    print("  易主最频繁的城池 Top10（5 局合计）：")
    for cid, n in flips.most_common(10):
        print(f"    {cid:>12}: {n} 次")

    # 结构性可攻机会：随时间变化
    print()
    print("  「结构性可攻边境城市数」随回合变化（5 局均值，衡量进攻窗口是否枯竭）：")
    max_t = max(len(r["timeline"]) for r in rows)
    for t in range(0, max_t, max(1, max_t // 10)):
        vals = []
        for r in rows:
            if t < len(r["timeline"]):
                vals.append(sum(r["timeline"][t]["attackable"].values()))
        if vals:
            print(f"    turn {t+1:>3}: 可攻 {statistics.mean(vals):.1f} / "
                  f"边境 {statistics.mean([sum(r['timeline'][t]['border'].values()) for r in rows if t < len(r['timeline'])]):.1f}")

    # 夺城后守军 vs 反攻兵力
    print()
    print("  夺城事件分析（攻下后该城守军 = 攻方残部）：")
    all_battles = [b for r in rows for b in r["battles"]]
    wins = [b for b in all_battles if b["result"] == "attacker_win"]
    if wins:
        surv_ratio = [ (b["atk"] - b["atk_cas"]) / max(b["atk"], 1) for b in wins ]
        print(f"    攻方胜 {len(wins)} 场，攻方幸存比例 中位={statistics.median(surv_ratio):.2f}")
    lose_l = [b for b in all_battles if b["result"] != "attacker_win"]
    print(f"    非攻方胜 {len(lose_l)} 场（守胜/平/退）："
          f"{dict(Counter(b['result'] for b in lose_l))}")
    # 兵力比 vs 结果
    print()
    print("  战斗「攻/守兵力比」与结果的关系：")
    buckets = defaultdict(Counter)
    for b in all_battles:
        ratio = b["atk"] / max(b["dfd"], 1)
        lo = min(2.0, round(ratio * 4) / 4)  # 0.25 粒度
        buckets[lo][b["result"]] += 1
    for lo in sorted(buckets):
        c = buckets[lo]
        tot = sum(c.values())
        print(f"    ratio≈{lo:.2f}  n={tot:>4}  " +
              "  ".join(f"{k}:{v}" for k, v in c.most_common()))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=5)
    ap.add_argument("--turns", type=int, default=60)
    ap.add_argument("--seed0", type=int, default=1)
    ap.add_argument("--out", default=os.path.join(_HERE, "data", "exp15_diagnose.json"))
    args = ap.parse_args()

    P.ensure_reproducible()

    rows = []
    for i in range(args.games):
        seed = args.seed0 + i
        r = run_one(seed, args.turns)
        rows.append(r)
        print(f"  seed={seed} turns={r['turns']:>3} battles={r['n_battles']:>3} "
              f"attacks={r['n_attacks']:>3} flips={r['flips_total']:>3} "
              f"final_surv={sum(1 for v in r['final_counts'].values() if v>0)}", flush=True)

    analyze(rows)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"rows": rows}, fh, ensure_ascii=False, indent=1)
    print(f"\n明细已写入 {args.out}")


if __name__ == "__main__":
    main()
