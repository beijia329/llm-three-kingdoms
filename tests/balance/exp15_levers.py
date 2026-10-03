#!/usr/bin/env python3
"""实验 15-b：灭国压力【单变量对照】——哪根杠杆真的能让「12 方」走向统一？

⚠️⚠️ 已失效（历史脚本，保留备查，请勿用于新结论）⚠️⚠️
本脚本的 `_patch_cli` 断言基于**改前**源码字符串
（`troops >= tgt_garrison * 1.0` / `city.garrison < 3000`）。
A 门槛比（ATTACK_FORCE_RATIO 0.9）与征兵涨价曾在 48abdbb~002558f 落地，
虽已回退，但本脚本仍应改用 exp16_attribution.py 做杠杆实验：
exp16 独立实现与当前源码对齐的进程内注入（改 `cp.ATTACK_FORCE_RATIO` /
`cs.RECRUIT_COST_*` 模块绑定，而非源码字符串替换），并补了「归一化 top_share ×
surviving」这一正确判据。本文件**不删除**，仅用于保留历史与可复现轨迹。
详见 tests/balance/exp16_attribution.py。

【只读研究】不改 game/ 或 web/。所有杠杆均为**进程内注入**，每档跑完即还原。

== 杠杆一览 ==
A 攻城门槛比   CLI 内 `troops >= tgt_garrison * ratio`（默认 1.0）
               源码字符串替换后 exec 回填 CLIPlayer.get_commands（不改磁盘文件）
B 守军恢复     city_system.GARRISON_CAP_PER_LEVEL（默认 1000/级）
               + RECRUIT_COST_GOLD/FOOD（默认 1 / 2）
C 占领稳固期   新占城池 N 回合内拒绝敌方反攻（包装 _execute_attack + 记录夺城回合）
D 灭国机制     势力失去全部城池后，其在外军队解散、将领退出（包装每回合巡检）
E 出征保留兵   CLI `garrison - 100` 的 100 保留量（默认 100）

== 核心指标（判断"是否更接近统一"）==
surviving_factions  终局仍有城的势力数（12=纹丝不动，1=统一）
hhi                 城市集中度（0.083=完全均分，1.0=统一）
top_share           最大势力城市占比（碾压预警）
first_zero_turn     首个势力被灭的回合（None=从未灭国）
flips_total         全图易主总次数（越高=越动荡）
freeze_turn         最后一个易主事件发生的回合（之后地图冻结）

运行：
    export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONHASHSEED=0
    ./venv/bin/python tests/balance/exp15_levers.py --arms base,A_r090,C_imm3 --games 5 --turns 60
"""

from __future__ import annotations

import argparse
import inspect
import json
import os
import statistics
import sys
import textwrap
from collections import Counter
from typing import Any, Callable, Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import pacing_lib as P                                       # noqa: E402
import players.cli_player as cp                              # noqa: E402
import game.systems.city_system as cs                        # noqa: E402
import game.engine as ge                                     # noqa: E402
from game.data_loader import load_game_data                  # noqa: E402
from game.engine import GameEngine                           # noqa: E402

F = P.FACTION_KEYS

# ============================================================
# 杠杆定义
# ============================================================
_ORIG_GET_COMMANDS = cp.CLIPlayer.get_commands
_ORIG_FIND_GEN = cp.CLIPlayer.__dict__["_find_general_in_city"]   # staticmethod 描述符
_ORIG_CAP = cs.GARRISON_CAP_PER_LEVEL
_ORIG_CAP_ENGINE = ge.GARRISON_CAP_PER_LEVEL
_ORIG_COST_GOLD = cs.RECRUIT_COST_GOLD
_ORIG_COST_FOOD = cs.RECRUIT_COST_FOOD

ARMS: Dict[str, Dict[str, Any]] = {
    "base":          {},
    "A_r090":        {"ratio": 0.90},
    "A_r080":        {"ratio": 0.80},
    "A_r130":        {"ratio": 1.30},
    "B_cap500":      {"cap": 500},
    "B_cap2000":     {"cap": 2000},
    "B_cost":        {"recruit_gold": 3, "recruit_food": 6},
    "C_imm3":        {"immune": 3},
    "C_imm5":        {"immune": 5},
    "D_elim":        {"eliminate": True},
    "E_reserve0":    {"reserve": 0},
    # G：允许「从任一己方城市指派将领」出征（解铃还须系铃人——修复无将城市永久瘫痪）
    "G_anygen":      {"any_general": True},
    "F_A_G":         {"ratio": 0.90, "any_general": True},
    "F_A_C_G":       {"ratio": 0.90, "immune": 5, "any_general": True},
    "F_A_B_G":       {"ratio": 0.90, "cap": 2000, "any_general": True},
    "F_full":        {"ratio": 0.90, "cap": 2000, "immune": 5, "any_general": True,
                      "recruit_gold": 3, "recruit_food": 6},
    # 推荐候选：G + A(0.9) + 征兵涨价（不含会放大雪球的占领稳固期 C）
    "F_A_cost":      {"ratio": 0.90, "any_general": True, "recruit_gold": 3, "recruit_food": 6},
    "F_A_cost_cap500": {"ratio": 0.90, "any_general": True, "cap": 500,
                        "recruit_gold": 3, "recruit_food": 6},
    # 【落地版对标】G 收紧为「同一将领一回合只领一路 + 只能在己方城池中的空闲将领里挑」
    # 用于量化"实验版 G（可复用同一将）"与"落地版 G"的强度差（team-lead 要求）
    "G_1gen":        {"one_general": True},
    "F_landed":      {"ratio": 0.90, "one_general": True, "recruit_gold": 3, "recruit_food": 6},
}

# 落地版 G 的「一将一回合一路」登记表（按 (turn, general_id) 记）
_USED_GEN: set = set()


def _install_one_general_finder() -> None:
    """安装「一将一回合只领一路 + 只用己方城池中的空闲将领」的取将逻辑。

    与 any_general 的差别：
      - any_general（实验版）：每次直接取快照上的第一个将领，同一回合可被多路复用；
      - one_general（落地版）：本地驻将优先；否则从「未带兵（location 不是军队 id）」
        且本回合未被派出的己方将领中取统帅最高者，并登记占用。
    两者都要求引擎侧把该将领调往出发城（见 run_one 的 wrapped_attack）。
    """
    def finder(city_id, obs):
        # 1) 本地驻将优先（与生产逻辑一致）
        for g in obs.own_generals:
            if g.location == city_id and not g.is_captured and (obs.turn, g.id) not in _USED_GEN:
                _USED_GEN.add((obs.turn, g.id))
                return g
        # 2) 空闲将领兜底：未带兵 + 本回合未被派
        busy = {a.id for a in obs.own_armies}
        for g in sorted(obs.own_generals, key=lambda x: (-x.command, x.id)):
            if g.is_captured or g.location in busy:
                continue
            if (obs.turn, g.id) in _USED_GEN:
                continue
            _USED_GEN.add((obs.turn, g.id))
            return g
        return None

    cp.CLIPlayer._find_general_in_city = staticmethod(finder)   # type: ignore[assignment]


def _patch_cli(ratio: Optional[float], reserve: Optional[int],
               recruit_ceiling: Optional[int]) -> None:
    """通过源码字符串替换 + exec，注入 CLI 决策参数（不写磁盘）。"""
    if ratio is None and reserve is None and recruit_ceiling is None:
        return
    src = textwrap.dedent(inspect.getsource(_ORIG_GET_COMMANDS))
    if ratio is not None:
        assert "troops >= tgt_garrison * 1.0" in src
        src = src.replace("troops >= tgt_garrison * 1.0",
                          f"troops >= tgt_garrison * {ratio}")
    if reserve is not None:
        assert "troops = min(city.garrison - 100, desired)" in src
        src = src.replace("troops = min(city.garrison - 100, desired)",
                          f"troops = min(city.garrison - {reserve}, desired)")
    if recruit_ceiling is not None:
        assert "city.garrison < 3000" in src
        src = src.replace("city.garrison < 3000",
                          f"city.garrison < {recruit_ceiling}")
    ns = dict(cp.__dict__)
    exec(compile(src, "<patched-cli>", "exec"), ns)          # noqa: S102
    cp.CLIPlayer.get_commands = ns["get_commands"]           # type: ignore[assignment]


def _reset_all() -> None:
    cp.CLIPlayer.get_commands = _ORIG_GET_COMMANDS           # type: ignore[assignment]
    cp.CLIPlayer._find_general_in_city = _ORIG_FIND_GEN      # type: ignore[assignment]
    cs.GARRISON_CAP_PER_LEVEL = _ORIG_CAP
    ge.GARRISON_CAP_PER_LEVEL = _ORIG_CAP_ENGINE
    cs.RECRUIT_COST_GOLD = _ORIG_COST_GOLD
    cs.RECRUIT_COST_FOOD = _ORIG_COST_FOOD


def apply_arm(cfg: Dict[str, Any]) -> None:
    """把一档配置注入到进程内（每次运行前调用）。"""
    _reset_all()
    _patch_cli(cfg.get("ratio"), cfg.get("reserve"), cfg.get("recruit_ceiling"))
    if cfg.get("any_general"):
        # 还原 v3.1 之前被删掉的「跨城派将」兜底：找不到本地将领时改用己方任一将领
        # （引擎侧配合把该将领调往出发城，见 run_one 的 wrapped_attack）
        cp.CLIPlayer._find_general_in_city = staticmethod(   # type: ignore[assignment]
            lambda city_id, obs: next(iter(obs.own_generals), None)
        )
    if cfg.get("one_general"):
        _USED_GEN.clear()
        _install_one_general_finder()
    if "cap" in cfg:
        cs.GARRISON_CAP_PER_LEVEL = int(cfg["cap"])
        ge.GARRISON_CAP_PER_LEVEL = int(cfg["cap"])
    if "recruit_gold" in cfg:
        cs.RECRUIT_COST_GOLD = int(cfg["recruit_gold"])
    if "recruit_food" in cfg:
        cs.RECRUIT_COST_FOOD = int(cfg["recruit_food"])


# ============================================================
# 单局运行 + 指标
# ============================================================

def run_one(seed: int, max_turns: int, cfg: Dict[str, Any]) -> Dict[str, Any]:
    apply_arm(cfg)

    engine = GameEngine(seed=seed)
    engine.init_game(load_game_data())
    engine.max_turns = int(max_turns)
    players = P.make_players(seed)

    immune = int(cfg.get("immune", 0) or 0)
    eliminate = bool(cfg.get("eliminate", False))
    any_general = bool(cfg.get("any_general", False) or cfg.get("one_general", False))
    recent_capture: Dict[str, int] = {}
    captures: List[Dict[str, Any]] = []
    battles_by_result: Counter = Counter()
    prev_owner = {cid: c.faction for cid, c in engine.cities.items()}
    flips: Counter = Counter()
    min_counts: Dict[str, int] = {f: 99 for f in F}
    first_zero: Dict[str, Optional[int]] = {f: None for f in F}

    # --- 夺城记录（供 C 稳固期 / 统计） ---
    orig_apply = engine._apply_battle_result

    def wrapped_apply(ctx, result):
        if result.result.value == "attacker_win" and ctx.defender_city:
            recent_capture[ctx.defender_city] = engine.turn
        battles_by_result[result.result.value] += 1
        orig_apply(ctx, result)

    engine._apply_battle_result = wrapped_apply                 # type: ignore[assignment]

    # --- C：占领稳固期 —— 拒绝反攻；G：跨城派将 —— 把将领调往出发城 ---
    orig_attack = engine._execute_attack

    def wrapped_attack(cmd):
        if immune > 0 and cmd.to_city in recent_capture:
            since = engine.turn - recent_capture[cmd.to_city]
            if 0 <= since < immune:
                from game.engine import CommandResult
                return CommandResult(success=False, command_type="attack",
                                     description=f"目标 {cmd.to_city} 处于占领稳固期（{since}/{immune}）")
        if any_general:
            g = engine.generals.get(cmd.general)
            if (g is not None and g.faction == cmd.faction
                    and not g.is_captured and g.location != cmd.from_city):
                g.location = cmd.from_city           # 指派：将领赴任出发城
        return orig_attack(cmd)

    engine._execute_attack = wrapped_attack                     # type: ignore[assignment]

    # --- D：灭国——无城势力清场 ---
    def apply_elimination():
        if not eliminate:
            return
        cityless = [f for f in F if not any(c.faction == f for c in engine.cities.values())]
        for f in cityless:
            for aid in [a.id for a in engine.armies.values() if a.faction == f]:
                engine.armies.pop(aid, None)
            for g in engine.generals.values():
                if g.faction == f:
                    g.is_captured = True
                    g.captor_faction = None

    turns = 0
    while not engine.game_over and turns <= P.SAFETY_MAX_ITER:
        for f in F:
            obs = engine.get_observation(f)
            for cmd in players[f].get_commands(obs):
                engine.execute_command(cmd)
        engine.process_turn()
        turns += 1
        apply_elimination()

        cnt = Counter(c.faction for c in engine.cities.values() if c.faction in F)
        for f in F:
            v = cnt.get(f, 0)
            if v < min_counts[f]:
                min_counts[f] = v
            if v == 0 and first_zero[f] is None:
                first_zero[f] = engine.turn

        for cid, c in engine.cities.items():
            if c.faction != prev_owner[cid]:
                flips[cid] += 1
                captures.append({"turn": engine.turn, "city": cid,
                                 "from": prev_owner[cid], "to": c.faction})
                prev_owner[cid] = c.faction

    final_counts = Counter(c.faction for c in engine.cities.values() if c.faction in F)
    total = sum(final_counts.values())
    hhi = sum((v / total) ** 2 for v in final_counts.values()) if total else 0.0
    top_share = (max(final_counts.values()) / total) if total else 0.0
    zero_turns = [t for t in first_zero.values() if t is not None]

    return {
        "seed": seed,
        "turns": engine.turn,
        "game_over": bool(engine.game_over),
        "winner": engine.winner,
        "final_counts": dict(final_counts),
        "surviving_factions": sum(1 for v in final_counts.values() if v > 0),
        "hhi": round(hhi, 4),
        "top_share": round(top_share, 3),
        "n_battles": sum(battles_by_result.values()),
        "battle_results": dict(battles_by_result),
        "flips_total": sum(flips.values()),
        "flip_cities": dict(flips.most_common(8)),
        "freeze_turn": (captures[-1]["turn"] if captures else 0),
        "min_counts": min_counts,
        "first_zero_turn": first_zero,
        "first_elim_turn": (min(zero_turns) if zero_turns else None),
        "captures": captures,
    }


# ============================================================
# 主流程
# ============================================================

def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    ok = [r for r in rows if not r.get("crashed")]
    elim_turns = [r["first_elim_turn"] for r in ok if r["first_elim_turn"] is not None]
    return {
        "games": len(rows),
        "surviving": round(statistics.mean(r["surviving_factions"] for r in ok), 2),
        "hhi": round(statistics.mean(r["hhi"] for r in ok), 4),
        "top_share": round(statistics.mean(r["top_share"] for r in ok), 3),
        "battles": round(statistics.mean(r["n_battles"] for r in ok), 1),
        "flips": round(statistics.mean(r["flips_total"] for r in ok), 1),
        "freeze": round(statistics.mean(r["freeze_turn"] for r in ok), 1),
        "unified": sum(1 for r in ok if r["surviving_factions"] == 1),
        "elim_games": sum(1 for r in ok if r["surviving_factions"] < 12),
        "first_elim_turn": (round(statistics.mean(elim_turns), 1) if elim_turns else None),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="base,A_r090,B_cap500,C_imm3,D_elim")
    ap.add_argument("--games", type=int, default=5)
    ap.add_argument("--turns", type=int, default=60)
    ap.add_argument("--seed0", type=int, default=1)
    ap.add_argument("--out", default=os.path.join(_HERE, "data", "exp15_levers.json"))
    args = ap.parse_args()

    P.ensure_reproducible()

    arm_names = [a.strip() for a in args.arms.split(",") if a.strip()]
    results: Dict[str, Any] = {}
    for arm in arm_names:
        cfg = ARMS[arm]
        print(f"\n### 档位 [{arm}]  cfg={cfg} ###", flush=True)
        rows = []
        for i in range(args.games):
            seed = args.seed0 + i
            r = run_one(seed, args.turns, cfg)
            rows.append(r)
            print(f"   seed={seed} turns={r['turns']:>3} 存活={r['surviving_factions']:>2} "
                  f"hhi={r['hhi']:.3f} top={r['top_share']:.2f} 战斗={r['n_battles']:>3} "
                  f"易主={r['flips_total']:>3} 冻结于={r['freeze_turn']:>3}", flush=True)
        results[arm] = {"cfg": cfg, "summary": summarize(rows), "rows": rows}

    _reset_all()

    print("\n" + "=" * 104)
    print("  灭国压力 单变量对照总表（每档 5 局均值；surv=存活势力数，12=无统一，1=统一）")
    print("=" * 104)
    print(f"{'档位':>14}{'surv':>7}{'HHI':>8}{'top占比':>9}{'战斗/局':>9}"
          f"{'易主/局':>9}{'冻结回合':>9}{'首灭回合':>9}{'曾灭国局数':>11}{'统一局数':>9}")
    print("-" * 104)
    for arm in arm_names:
        s = results[arm]["summary"]
        fe = s["first_elim_turn"] if s["first_elim_turn"] is not None else "-"
        print(f"{arm:>14}{s['surviving']:>7}{s['hhi']:>8.3f}{s['top_share']:>9.2f}"
              f"{s['battles']:>9}{s['flips']:>9}{s['freeze']:>9}{str(fe):>9}"
              f"{s['elim_games']:>11}{s['unified']:>9}")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)
    print(f"\n明细已写入 {args.out}")


if __name__ == "__main__":
    main()
