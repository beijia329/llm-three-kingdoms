#!/usr/bin/env python3
"""实验 16：三件套【单变量归因】+ 悬念度 + 经济刹车响应曲线

== 背景 ==
v4.0「灭国压力」修复包含三根杠杆（均已落地进生产源码）：
  G   解将荒       —— 允许从「位于己方城市中的空闲将领」调人随军出征
                     （game/engine.py::_execute_attack 放宽校验 + 维护 city.generals；
                      players/cli_player.py::_find_dispatchable_general）
  A   攻城门槛比   —— players/cli_player.py::ATTACK_FORCE_RATIO 1.0 → 0.9
  涨价 征兵刹车     —— game/constants.py RECRUIT_COST_GOLD 1→3 / RECRUIT_COST_FOOD 2→6

团队决策（2026-10-0X）：0.493 才是真实游戏平衡，需回答三个问题：
  1. 雪球到底由哪根杠杆造成？（单变量归因）
  2. 局面是否仍有悬念？（leader_at_48 vs 终局冠军 → 翻盘率）
  3. 经济刹车的边际效果如何？（涨价响应曲线）

== 杠杆注入方式（进程内，绝不写工作区文件）==
本脚本按**当前生产源码**的标识注入，运行完即还原：
  G    cp.CLIPlayer._find_dispatchable_general ← 关档时替换为「恒返回 None」
       （等价于改前：出发城无本地驻将 → 不发起该次进攻。CLI 侧不派跨城将，
        引擎的放宽校验虽仍在，但永远不会被触发，结果与改前一致。）
  A    cp.ATTACK_FORCE_RATIO                     ← 1.0=关 / 0.9=开
  涨价  cs.RECRUIT_COST_GOLD / cs.RECRUIT_COST_FOOD ← 1/2=关 / 3/6=开
       （city_system 在模块级 `from game.constants import RECRUIT_COST_*`，
        故须改 city_system 模块命名空间内的绑定，改 constants 不生效。）

⚠️ 不复用 tests/balance/exp15_levers.py：该脚本的 `_patch_cli` 断言的是**改前**源码
   字符串（`troops >= tgt_garrison * 1.0` / `city.garrison < 3000`），A 与涨价的
   注入在源码落地后已失效；其 `base` 档现在等价于「三件套全开」。故本脚本独立实现
   与当前源码对齐的注入。

== 指标 ==
  top_share            终局最大势力城市占比（分母 = 仍有城势力城市总数）
  归一化               top_share × surviving_factions（= 最大势力相对均值的倍数）
  surviving_factions   终局仍有城的势力数（12=无统一，1=统一）
  battles              本局战斗总场次
  freeze_turn          末次城池易主发生的回合（0=全程无易主）
  leader_at_48         第 48 回合城最多的势力（并列按势力键字典序取最小）
  champion             终局冠军（engine.winner）
  翻盘                  leader_at_48 != champion

== 档位 ==
  pre   ：三件套全关（改前基线，用于验证 harness 复现改前数值）
  G     ：只上 G
  G+A   ：G + A(0.9)
  C     ：G + A(0.9) + 金3粮6       ← 应逐位复现 tests/balance/data/exp12_landed_after.json
  C5    ：G + A(0.9) + 金5粮10
  C8    ：G + A(0.9) + 金8粮16

运行：
    export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONHASHSEED=0
    ./venv/bin/python tests/balance/exp16_attribution.py \
        --arms pre,G,G+A,C,C5,C8 --games 5 --turns 96 \
        --out tests/balance/data/exp16_attribution.json
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from typing import Any, Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import pacing_lib as P                              # noqa: E402
from game.data_loader import load_game_data         # noqa: E402
from game.engine import GameEngine                  # noqa: E402

import players.cli_player as cp                     # noqa: E402
import game.systems.city_system as cs               # noqa: E402

F = P.FACTION_KEYS

# ---- 捕获生产原值，用于还原 ----
_ORIG_RATIO = cp.ATTACK_FORCE_RATIO
_ORIG_DISPATCH = cp.CLIPlayer._find_dispatchable_general
_ORIG_GOLD = cs.RECRUIT_COST_GOLD
_ORIG_FOOD = cs.RECRUIT_COST_FOOD

# ---- 档位定义 ----
# general_dispatch: G 杠杆（跨城调将）开关
# attack_ratio:     A 杠杆（1.0=关 / 0.9=开）
# recruit_gold/food: 涨价刹车（1/2=关）
ARMS: Dict[str, Dict[str, Any]] = {
    "pre":  {"general_dispatch": False, "attack_ratio": 1.0, "recruit_gold": 1, "recruit_food": 2},
    "G":    {"general_dispatch": True,  "attack_ratio": 1.0, "recruit_gold": 1, "recruit_food": 2},
    "G+A":  {"general_dispatch": True,  "attack_ratio": 0.9, "recruit_gold": 1, "recruit_food": 2},
    "C":    {"general_dispatch": True,  "attack_ratio": 0.9, "recruit_gold": 3, "recruit_food": 6},
    "C5":   {"general_dispatch": True,  "attack_ratio": 0.9, "recruit_gold": 5, "recruit_food": 10},
    "C8":   {"general_dispatch": True,  "attack_ratio": 0.9, "recruit_gold": 8, "recruit_food": 16},
}


def _no_dispatch(self, obs, assigned):               # noqa: ANN001
    """G 关档：出发城无本地驻将时直接放弃该次进攻（等价改前）。"""
    return None


def apply_levers(cfg: Dict[str, Any]) -> None:
    """把一档配置注入进程内（每次 run_one 前调用）。"""
    cp.ATTACK_FORCE_RATIO = float(cfg["attack_ratio"])
    cs.RECRUIT_COST_GOLD = int(cfg["recruit_gold"])
    cs.RECRUIT_COST_FOOD = int(cfg["recruit_food"])
    cp.CLIPlayer._find_dispatchable_general = (              # type: ignore[assignment]
        _ORIG_DISPATCH if cfg["general_dispatch"] else _no_dispatch
    )


def restore_levers() -> None:
    cp.ATTACK_FORCE_RATIO = _ORIG_RATIO                      # type: ignore[assignment]
    cs.RECRUIT_COST_GOLD = _ORIG_GOLD                        # type: ignore[assignment]
    cs.RECRUIT_COST_FOOD = _ORIG_FOOD                        # type: ignore[assignment]
    cp.CLIPlayer._find_dispatchable_general = _ORIG_DISPATCH  # type: ignore[assignment]


def _leader(counts: Dict[str, int]) -> Optional[str]:
    """城最多者；并列按势力键字典序取最小，保证确定性。"""
    mx = max(counts.values()) if counts else 0
    if mx <= 0:
        return None
    cand = [f for f in F if counts.get(f, 0) == mx]
    return sorted(cand)[0]


def run_one(seed: int, max_turns: int, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """跑一局并采集归因 / 悬念 / 集中度指标（口径与 exp12_unification_check 对齐）。"""
    apply_levers(cfg)

    engine = GameEngine(seed=seed)
    engine.init_game(load_game_data())
    engine.max_turns = int(max_turns)
    players = P.make_players(seed)

    prev_owner = {cid: c.faction for cid, c in engine.cities.items()}
    initial_counts: Dict[str, int] = {}
    for c in engine.cities.values():
        if c.faction in F:
            initial_counts[c.faction] = initial_counts.get(c.faction, 0) + 1
    freeze_turn = 0
    first_zero: Dict[str, Optional[int]] = {f: None for f in F}
    battles = 0
    leader_at_48: Optional[str] = None

    turns = 0
    while not engine.game_over and turns <= P.SAFETY_MAX_ITER:
        for f in F:
            obs = engine.get_observation(f)
            for cmd in players[f].get_commands(obs):
                engine.execute_command(cmd)
        res = engine.process_turn()
        battles += int(res.get("battles_fought", 0) or 0)
        turns += 1

        for cid, c in engine.cities.items():
            if c.faction != prev_owner[cid]:
                prev_owner[cid] = c.faction
                freeze_turn = engine.turn

        counts: Dict[str, int] = {}
        for c in engine.cities.values():
            if c.faction in first_zero:
                counts[c.faction] = counts.get(c.faction, 0) + 1
        for f in F:
            if (initial_counts.get(f, 0) > 0 and first_zero[f] is None
                    and counts.get(f, 0) == 0):
                first_zero[f] = engine.turn

        if leader_at_48 is None and engine.turn == 48:
            leader_at_48 = _leader(counts)

    city_counts: Dict[str, int] = {}
    for c in engine.cities.values():
        if c.faction != "neutral":
            city_counts[c.faction] = city_counts.get(c.faction, 0) + 1
    active = {f: n for f, n in city_counts.items() if n > 0}
    total = sum(active.values())
    hhi = sum((n / total) ** 2 for n in active.values()) if total else 0.0
    top_share = (max(active.values()) / total) if total else 0.0
    champion = engine.winner

    return {
        "seed": seed,
        "turns": engine.turn,
        "game_over": bool(engine.game_over),
        "champion": champion,
        "winner": champion,                      # 兼容 exp12 字段名
        "battles": battles,
        "surviving_factions": len(active),
        "hhi": round(hhi, 4),
        "top_share": round(top_share, 3),
        "normalized": round(top_share * len(active), 3),
        "freeze_turn": freeze_turn,
        "first_elim_turn": min(
            (t for t in first_zero.values() if t is not None), default=None
        ),
        "leader_at_48": leader_at_48,
        "flip": (leader_at_48 is not None and champion is not None
                 and leader_at_48 != champion),
    }


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(rows)
    flips = sum(1 for r in rows if r["flip"])
    decided = sum(1 for r in rows if r["leader_at_48"] is not None and r["champion"] is not None)
    return {
        "games": n,
        "top_share": round(statistics.mean(r["top_share"] for r in rows), 3),
        "normalized": round(statistics.mean(r["normalized"] for r in rows), 2),
        "surviving": round(statistics.mean(r["surviving_factions"] for r in rows), 2),
        "battles": round(statistics.mean(r["battles"] for r in rows), 1),
        "freeze": round(statistics.mean(r["freeze_turn"] for r in rows), 1),
        "first_elim_turn": (
            round(statistics.mean(r["first_elim_turn"] for r in rows
                                  if r["first_elim_turn"] is not None), 1)
            if any(r["first_elim_turn"] is not None for r in rows) else None
        ),
        "flips": flips,
        "decided_games": decided,
        "flip_rate": f"{flips}/{decided}" if decided else "n/a",
    }


def verify_reproduction(rows_c: List[Dict[str, Any]]) -> None:
    """C 档应逐位复现 tests/balance/data/exp12_landed_after.json。"""
    ref_path = os.path.join(_HERE, "data", "exp12_landed_after.json")
    if not os.path.exists(ref_path):
        print("  ⚠️ 未找到 exp12_landed_after.json，跳过复现校验")
        return
    with open(ref_path, encoding="utf-8") as fh:
        ref = {r["seed"]: r for r in json.load(fh)["rows"]}
    fields = ("winner", "battles", "surviving_factions", "hhi", "top_share",
              "freeze_turn", "first_elim_turn")
    bad = []
    for r in rows_c:
        ref_r = ref.get(r["seed"])
        if ref_r is None:
            continue
        for k in fields:
            if r[k] != ref_r[k]:
                bad.append(f"seed{r['seed']}.{k}: 本harness={r[k]} ref={ref_r[k]}")
    if bad:
        print("  🔴 C 档未能复现 exp12_landed_after：")
        for line in bad:
            print("     -", line)
    else:
        print("  ✅ C 档逐位复现 exp12_landed_after.json（winner/battles/surviving/"
              "hhi/top_share/freeze/first_elim 全一致）")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="pre,G,G+A,C,C5,C8")
    ap.add_argument("--games", type=int, default=5)
    ap.add_argument("--turns", type=int, default=96)
    ap.add_argument("--seed0", type=int, default=1)
    ap.add_argument("--out", default=os.path.join(_HERE, "data", "exp16_attribution.json"))
    args = ap.parse_args()

    P.ensure_reproducible()

    arm_names = [a.strip() for a in args.arms.split(",") if a.strip()]
    results: Dict[str, Any] = {}
    for arm in arm_names:
        cfg = ARMS[arm]
        print(f"\n### 档位 [{arm}]  cfg={cfg} ###", flush=True)
        rows: List[Dict[str, Any]] = []
        for i in range(args.games):
            seed = args.seed0 + i
            r = run_one(seed, args.turns, cfg)
            rows.append(r)
            print(f"   seed={seed} turn={r['turns']:>3} 存活={r['surviving_factions']:>2} "
                  f"top={r['top_share']:.3f} 归一化={r['normalized']:.2f} "
                  f"战斗={r['battles']:>3} 冻结={r['freeze_turn']:>3} "
                  f"48回合领先={r['leader_at_48']} 冠军={r['champion']} "
                  f"{'⤴翻盘' if r['flip'] else ''}", flush=True)
        results[arm] = {"cfg": cfg, "summary": summarize(rows), "rows": rows}
        if arm == "C":
            verify_reproduction(rows)

    restore_levers()

    print("\n" + "=" * 118)
    print("  实验16 单变量归因 + 悬念度 + 刹车曲线（每档 5 局均值，96 回合）")
    print("=" * 118)
    print(f"{'档位':>7}{'surv':>7}{'top占比':>9}{'归一化':>9}{'战斗/局':>9}"
          f"{'冻结回合':>9}{'首灭回合':>9}{'翻盘率':>9}")
    print("-" * 118)
    for arm in arm_names:
        s = results[arm]["summary"]
        fe = s["first_elim_turn"] if s["first_elim_turn"] is not None else "-"
        print(f"{arm:>7}{s['surviving']:>7}{s['top_share']:>9.3f}{s['normalized']:>9.2f}"
              f"{s['battles']:>9}{s['freeze']:>9}{str(fe):>9}{s['flip_rate']:>9}")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)
    print(f"\n明细已写入 {args.out}")


if __name__ == "__main__":
    main()
