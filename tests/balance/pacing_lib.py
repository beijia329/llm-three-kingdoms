"""行军节奏 / 战斗频率实验的共享探针库（headless，无渲染、无 LLM）。

设计约束：
- 绝不import pygame / renderer / players.llm；只走 engine + players.cli_player。
- 单变量注入：`game.constants.ARMY_MARCH_SPEED` 在 `_process_hex_movement` 里是
  **函数内 import**（每次调用重新读模块属性），因此可在运行时直接改写模块属性实现
  单变量对照，**无需改源码**、不污染其他实验。
- 完全确定性：引擎 seed + 每势力派生 seed（stable_hash，不受 PYTHONHASHSEED 影响），
  同一配置重复运行结果逐位一致。

每个脚本都可 `python tests/balance/xxx.py` 直接运行。
"""

from __future__ import annotations

import os
import statistics
import sys
import time
import traceback
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ============================================================
# 🔴 可复现性守卫（必须在任何业务 import 之前执行）
# ============================================================
# 实测教训：即使固定引擎 seed 与各势力派生 seed，同一 seed 在不同进程仍会
# 得到不同结果（exp6 两次复跑：271 次 vs 245 次出征）。根因是**引擎内部存在
# 依赖 set/dict 迭代顺序的逻辑**（如`GameEngine._spread_influence` 用
# `assigned: set` + 对 `self.cities.values()` 的遍历顺序决定影响力扩散方向），
# 而 Python 的 `str`/`tuple` 哈希默认按进程随机化（PYTHONHASHSEED=random）→
# set 迭代顺序逐进程变化 → 随机数消耗序列变化 → 结果漂移。
#
# 对策：强制 PYTHONHASHSEED=0，使 str/tuple 哈希确定化。
# 注意：本守卫**必须在进程启动时**生效，故在脚本入口调用 `ensure_reproducible()`；
# 对已运行的进程无效，因此每个实验脚本都在 `if __name__ == "__main__"` 之前调用。
REPRODUCIBLE = True

# ============================================================
# 🔴 外交消息投递开关（2026-10-03 新增，默认 True）
# ============================================================
# 此前本库**不投递** `receive_message`，而 `CLIPlayer` 只能靠该回调得知
# 「有人提议结盟」（`players/cli_player.py:71-77` 在里面设 `_pending_alliance`）。
# 后果：本库驱动的**全部平衡实验**都在一个「启发式玩家不可能结盟」的世界里运行
# ——外交消息照发（实测 560 条/5 局），但结盟提议 0 次、同盟 0 对、停战 0 对。
#
# 而产品路径是投递的：`main.py:134-136`。三条路径对比：
#     main.py CLI ai-vs-ai        ✅ 投递
#     api/game_manager.py（Web）   ❌ 不投递
#     tests/balance/pacing_lib.py ❌ 不投递（本开关改动前）
#
# 两变体实测（`tests/balance/exp19_diplomacy_reachability.py`，5 局 × 48 回合）：
#     不投递：外交消息 560｜结盟提议 0 次｜同盟 0 对
#     投递：  外交消息 521｜结盟提议 92 次｜同盟 47 对
# 阳性对照双变体均命中（战争对 175/175）。
#
# 故默认改为 **True**，使实验台与产品路径一致。
# ⚠️ 这会改变此前所有平衡实验的数字口径（战斗场次 / 存活势力 / 集中度等），
#    凡涉及外交的旧结论需按新口径重测，不要与新数字混用。
#    需要复现旧口径做对照时，显式传 `deliver_messages=False`。
DELIVER_MESSAGES = True


def _deliver_message(
    players: Dict[str, Any],
    sender: str,
    cmd: Any,
    result: Any,
) -> None:
    """按 `main.py:134-136` 的做法把外交消息投递给目标玩家对象。

    只处理 `message` 命令且执行成功的情况，与产品路径等价。
    """
    if not DELIVER_MESSAGES:
        return
    if getattr(cmd, "type", None) != "message":
        return
    if not getattr(result, "success", False):
        return
    target = players.get(getattr(cmd, "to", None))
    if target is not None:
        target.receive_message(sender, str(getattr(cmd, "content", "")))


def ensure_reproducible() -> None:
    """若尚未固定 PYTHONHASHSEED 则强制重啟（子进程场景由父进程 env 传入）。"""
    if os.environ.get("PYTHONHASHSEED") != "0":
        os.environ["PYTHONHASHSEED"] = "0"
        if REPRODUCIBLE:
            os.execv(sys.executable, [sys.executable] + sys.argv)


# ============================================================
# 🔴 基线锁定（对抗并发修改）—— 纯进程内属性还原，不写工作区文件
# ============================================================
# 背景：2026-10-03 11:15 前后，其他 agent 依据本报告的 P0 建议并发修改了
#   game/tile.py（PEAK 可通行）、game/constants.py（peak: inf→3.0）、
#   players/cli_player.py（去掉 own_generals[0] 兜底）。
# 这会让「修复前 vs 修复后」对照随时失效（同一命令两次跑出不同结论）。
#
# 🔴 设计约束：**绝不写回工作区文件**（多人/多 agent 并行时会把别人的改动抹掉）。
# 改为在进程内把「已改的那几个属性」还原成修复前的值：
#   - TERRAIN_MOVE_COST['peak'] = inf        （A* 真正使用的权表）
#   - Tile.is_passable 恢复含 PEAK 的原实现   （与上一条双保险）
#   - CLIPlayer 决策层由 exp7/exp8 的补丁接管，不依赖其工作区版本
# 这样「base 档」在任何时刻都稳定代表"修复前"，且不碰别人的文件。
_BASELINE_SNAPSHOT: Dict[str, Any] = {}


def use_pristine_baseline(enable: bool = True) -> bool:
    """把 P0 相关属性在**进程内**还原为修复前取值（不写任何文件）。

    Returns True 表示基线已生效。
    """
    global _BASELINE_SNAPSHOT
    if not enable:
        return False
    if _BASELINE_SNAPSHOT:
        return True
    try:
        import game.constants as _C
        from game.tile import Tile as _Tile
    except Exception:
        return False

    # 1) A* 权表：peak 恢复为不可通行
    tmc = _C.TERRAIN_MOVE_COST
    _BASELINE_SNAPSHOT["peak_cost"] = tmc.get("peak", None)
    tmc["peak"] = float("inf")

    # 2) is_passable 恢复为「PEAK 也不可通行」
    from exp4_terrain import IMPASSABLE, _ORIG_PASSABLE
    _BASELINE_SNAPSHOT["is_passable"] = _Tile.is_passable
    _Tile.is_passable = lambda self: self.terrain not in IMPASSABLE
    return True


def restore_working_tree() -> None:
    """撤销 use_pristine_baseline 的进程内改动。"""
    global _BASELINE_SNAPSHOT
    if not _BASELINE_SNAPSHOT:
        return
    try:
        import game.constants as _C
        from game.tile import Tile as _Tile
        snap = _BASELINE_SNAPSHOT
        if "peak_cost" in snap:
            if snap["peak_cost"] is None:
                _C.TERRAIN_MOVE_COST.pop("peak", None)
            else:
                _C.TERRAIN_MOVE_COST["peak"] = snap["peak_cost"]
        if "is_passable" in snap:
            _Tile.is_passable = snap["is_passable"]
    except Exception:
        pass
    _BASELINE_SNAPSHOT = {}


# ---- 路径引导 ----
_HERE = os.path.dirname(os.path.abspath(__file__))          # tests/balance
_TESTS = os.path.dirname(_HERE)                             # tests
_ROOT = os.path.dirname(_TESTS)                             # project root
for _p in (_ROOT, _TESTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import game.constants as C                                     # noqa: E402
from game.engine import GameEngine                             # noqa: E402
from game.data_loader import load_game_data                    # noqa: E402
from game.random import GameRandom                             # noqa: E402
from players.cli_player import CLIPlayer                       # noqa: E402

FACTION_KEYS: List[str] = list(C.FACTIONS.keys())
NUM_FACTIONS = len(FACTION_KEYS)
FAIR_SHARE = 1.0 / NUM_FACTIONS
# 12方均匀公平份额 8.33%；OP 嫌疑阈值取 2× = 16.67%
OP_THRESHOLD = 2.0 * FAIR_SHARE

SAFETY_MAX_ITER = 400  # 引擎在turn>=max_turns 结束，这里再加一道保险


def stable_hash(text: str) -> int:
    """稳定字符串哈希（不受 PYTHONHASHSEED 影响），保证跨进程可复现。"""
    h = 0
    for ch in text:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h


def set_march_speed(speed: int) -> None:
    """单变量注入：改写行军速度。

    `_process_hex_movement` / `terrain_move_cost` 都是函数内 `from game.constants import X`，
    每次调用重新绑定，因此改模块属性立即生效，且不需重启进程。
    """
    C.ARMY_MARCH_SPEED = int(speed)


def make_players(game_seed: int) -> Dict[str, CLIPlayer]:
    """12 势力各一个 CLIPlayer，种子由 game_seed + 势力名确定性派生。"""
    return {
        f: CLIPlayer(
            faction=f,
            rng=GameRandom((game_seed * 1_000_003 + stable_hash(f)) % 2_000_000_000),
        )
        for f in FACTION_KEYS
    }


# ============================================================
# 单局运行 + 全量指标采集
# ============================================================

def run_one_game(game_seed: int, max_turns: int) -> Dict[str, Any]:
    """跑一局 headless ai-vs-ai，采集节奏/战斗/统一度指标。

    Returns:
        seed, turns, winner, crashed,error,
        battles                本局战斗总场次
        first_battle_turn      首次交战回合（None=全程无战斗）
        battle_turns           有战斗的回合列表
        armies_launched        本局累计出征军队数
        neutral_taken          中立城被占领数量
        first_neutral_turn     首座中立城被攻下的回合（None=无人碰）
        neutral_turns          每座中立城被攻下的回合（升序）
        final_counts           终局各势力城市数（不含 neutral）
        surviving_factions     终局仍有城的势力数
        top_faction_share      最大势力城市占比（碾压度指标）
        hhi                    城市集中度赫芬达尔指数（1=完全统一，1/12=完全均分）
        elapsed_s
    """
    engine = GameEngine(seed=game_seed)
    engine.init_game(load_game_data())
    engine.max_turns = int(max_turns)
    players = make_players(game_seed)

    # 开局中立城快照：只统计「这些城」被攻下的情况，
    # 否则会把21 座开局就属于某方的城误计为「中立城占领」。
    neutral_ids = {cid for cid, c in engine.cities.items() if c.faction == "neutral"}

    battles = 0
    battle_turns: List[int] = []
    first_battle_turn: Optional[int] = None
    armies_launched = 0
    neutral_taken = 0
    neutral_turns: List[int] = []
    seen_neutral = set()

    t0 = time.time()
    crashed: Optional[str] = None
    error: Optional[str] = None
    tb: Optional[str] = None
    turns = 0
    try:
        while not engine.game_over:
            for f in FACTION_KEYS:
                obs = engine.get_observation(f)
                for cmd in players[f].get_commands(obs):
                    armies_launched += 1
                    result = engine.execute_command(cmd)
                    _deliver_message(players, f, cmd, result)
            res = engine.process_turn()
            n = int(res.get("battles_fought", 0) or 0)
            if n > 0:
                battles += n
                battle_turns.append(engine.turn)
                if first_battle_turn is None:
                    first_battle_turn = engine.turn
            # 中立城易主检测：只跟踪开局中立城的快照集合
            for cid in neutral_ids:
                if cid not in seen_neutral and engine.cities[cid].faction != "neutral":
                    seen_neutral.add(cid)
                    neutral_turns.append(engine.turn)
                    neutral_taken += 1
            turns += 1
            if turns > SAFETY_MAX_ITER:
                crashed = "SAFETY_HIT_MAX_ITER"
                break
    except Exception as exc:
        crashed = "EXCEPTION"
        error = repr(exc)
        tb = traceback.format_exc()
    elapsed = time.time() - t0

    final_counts = {f: 0 for f in FACTION_KEYS}
    if not crashed:
        for c in engine.cities.values():
            if c.faction in final_counts:
                final_counts[c.faction] += 1

    active = {f: n for f, n in final_counts.items() if n > 0}
    total_active = sum(active.values())
    top_share = (max(active.values()) / total_active) if total_active else 0.0
    hhi = sum((n / total_active) ** 2 for n in active.values()) if total_active else 0.0

    neutral_turns.sort()
    return {
        "seed": game_seed,
        "turns": engine.turn if not crashed else turns,
        "max_turns": int(max_turns),
        "game_over": bool(engine.game_over),
        "winner": engine.winner,
        "crashed": crashed,
        "error": error,
        "traceback": tb,
        "battles": battles,
        "first_battle_turn": first_battle_turn,
        "battle_turns": battle_turns,
        "armies_launched": armies_launched,
        "neutral_taken": len(seen_neutral),
        "first_neutral_turn": neutral_turns[0] if neutral_turns else None,
        "neutral_turns": neutral_turns,
        "final_counts": final_counts,
        "surviving_factions": len(active),
        "top_faction_share": top_share,
        "hhi": hhi,
        "elapsed_s": round(elapsed, 3),
    }


# ============================================================
# 地图尺度静态测量（几何基线，不含随机性）
# ============================================================

def measure_map_scale() -> Dict[str, Any]:
    """测量 31 城两两 hex 最短路距离分布（对照组：验证行军速度与地图尺度是否匹配）。

    距离按 `HexMap.find_path` 的 A* 路径长度 - 1（步数）计算，
    与引擎 `_process_hex_movement` 沿path_hexes 推进的口径一致。
    """
    from game.hex_map import HexMap

    engine = GameEngine(seed=1)
    engine.init_game(load_game_data())
    hm = engine.hex_map
    assert isinstance(hm, HexMap)

    ids = sorted(engine.cities.keys())
    dists: List[int] = []
    unreachable = 0
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            path = hm.find_path(engine.cities[a].position, engine.cities[b].position)
            if not path:
                unreachable += 1
                continue
            dists.append(len(path) - 1)
    dists.sort()
    n = len(dists)

    def pct(p: float) -> int:
        return dists[min(n - 1, int(round(p * (n - 1))))]

    return {
        "n_cities": len(ids),
        "n_pairs": n,
        "unreachable_pairs": unreachable,
        "min": dists[0] if n else 0,
        "p25": pct(0.25),
        "median": pct(0.50),
        "mean": round(statistics.mean(dists), 2) if n else 0.0,
        "p75": pct(0.75),
        "max": dists[-1] if n else 0,
        "all": dists,
    }


def turns_to_engage(dist: int, speed: int) -> float:
    """按纯几何估算：走完 dist 步需要的回合数（不考虑地形消耗与季节）。"""
    return dist / float(speed) if speed else float("inf")


# ============================================================
# 批量运行 + 汇总统计
# ============================================================

def run_batch(
    march_speed: int,
    seeds: Sequence[int],
    max_turns: int,
    progress: bool = True,
) -> List[Dict[str, Any]]:
    """在一个配置下跑 N 局（seed 逐一不同），返回每局指标列表。"""
    set_march_speed(march_speed)
    rows: List[Dict[str, Any]] = []
    for i, seed in enumerate(seeds, 1):
        row = run_one_game(seed, max_turns)
        rows.append(row)
        if progress:
            print(
                f"    [{i}/{len(seeds)}] seed={seed} turns={row['turns']:>3} "
                f"battles={row['battles']:>3} first_battle={row['first_battle_turn']} "
                f"neutral={row['neutral_taken']:>2} winner={row['winner']} "
                f"({row['elapsed_s']}s)",
                flush=True,
            )
    return rows


def _num(vals: List[float]) -> Dict[str, float]:
    """一组数的集中趋势统计（min/median/mean/max）。"""
    vs = sorted(v for v in vals if v is not None)
    if not vs:
        return {"min": 0, "median": 0.0, "mean": 0.0, "max": 0}
    return {
        "min": vs[0],
        "median": round(statistics.median(vs), 2),
        "mean": round(statistics.mean(vs), 2),
        "max": vs[-1],
    }


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """把多局原始结果压成一组对照指标。"""
    ok = [r for r in rows if not r["crashed"]]
    wins = {f: 0 for f in FACTION_KEYS}
    for r in ok:
        w = r["winner"]
        if w in wins:
            wins[w] += 1
    denom = len(ok) or 1

    win_rates = {f: wins[f] / denom for f in FACTION_KEYS}
    op = [f for f in FACTION_KEYS if win_rates[f] > OP_THRESHOLD]
    zero = [f for f in FACTION_KEYS if wins[f] == 0]

    # 每个 seed 的胜者归属，用于算「集中度」
    return {
        "games": len(rows),
        "completed": len(ok),
        "crashes": [{"seed": r["seed"], "reason": r["crashed"], "error": r["error"]} for r in rows if r["crashed"]],
        "battles": _num([r["battles"] for r in ok]),
        "first_battle_turn": _num([r["first_battle_turn"] for r in ok]),
        "games_without_battle": sum(1 for r in ok if r["first_battle_turn"] is None),
        "armies_launched": _num([r["armies_launched"] for r in ok]),
        "neutral_taken": _num([r["neutral_taken"] for r in ok]),
        "first_neutral_turn": _num([r["first_neutral_turn"] for r in ok]),
        "turns": _num([r["turns"] for r in ok]),
        "surviving_factions": _num([r["surviving_factions"] for r in ok]),
        "top_faction_share": _num([r["top_faction_share"] for r in ok]),
        "hhi": _num([r["hhi"] for r in ok]),
        "wins": wins,
        "win_rate": win_rates,
        "op_suspects": op,
        "zero_win_factions": zero,
        "decided_games": sum(1 for r in ok if r["winner"] is not None),
        "avg_elapsed_s": round(statistics.mean([r["elapsed_s"] for r in ok]), 2) if ok else 0.0,
    }


def print_config_header(march_speed: int, max_turns: int, seeds: Sequence[int]) -> None:
    print("-" * 78)
    print(f"  配置: ARMY_MARCH_SPEED={march_speed}  max_turns={max_turns}  "
          f"games={len(seeds)}  seeds={list(seeds)}")
    print("-" * 78)


def print_summary_table(summaries: Dict[str, Dict[str, Any]], order: List[str]) -> None:
    """把多个配置并排打印成一张对照表。"""
    print()
    print("=" * 100)
    print("  行军速度 × 回合数 对照总表（每格 = N 局中位数 [min~max]）")
    print("=" * 100)
    print(f"{'speed':>6}{'turns':>7}{'局数':>5}{'战斗场次':>16}{'首战回合':>14}"
          f"{'结束回合':>12}{'存活势力':>12}{'最大占比':>12}{'中立城':>12}")
    print("-" * 100)
    for key in order:
        s = summaries.get(key)
        if not s:
            continue
        speed, mt = key.split("@")

        def cell(st: Dict[str, float]) -> str:
            if st["max"] == 0 and st["min"] == 0:
                return f"{'-':>16}"
            rng = f"{_numfmt(st['min'])}~{_numfmt(st['max'])}"
            return f"{_numfmt(st['median']):>7}[{rng:>7}]"

        print(f"{speed:>6}{mt:>7}{s['completed']:>5}"
              f"{cell(s['battles'])}{cell(s['first_battle_turn']):>14}"
              f"{cell(s['turns']):>12}{cell(s['surviving_factions']):>12}"
              f"{cell(s['top_faction_share']):>12}{cell(s['neutral_taken']):>12}")
    print("=" * 100)
    print("  说明：首战回合 '-' = 该配置全部对局 0 战斗；最大占比 = 终局最大势力城市占比(1.0=完全统一)")
    print("=" * 100)


def _numfmt(v: float) -> str:
    """紧凑数字格式：整数不带小数点，小数保留 2~3 位。"""
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.2f}"
