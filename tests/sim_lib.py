"""共享的无渲染（headless）对局运行库。

设计约束（来自质量门任务）：
- 绝不 import pygame / renderer；只走 engine + players.cli_player。
- 确定性：用稳定的字符串哈希替代 Python 内置 hash()（后者受 PYTHONHASHSEED
  影响，无法跨进程复现），保证「相同输入 → 相同输出」。
- 每个脚本都可 `python tests/.../xxx.py` 直接运行。

只被 tests/ 下的脚本使用；运行方式见各脚本顶部。
"""

from __future__ import annotations

import os
import sys
import traceback

# 把项目根目录加入 sys.path，使 `game` / `players` 可被导入。
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))  # .../tests
_PROJECT_ROOT = os.path.dirname(_THIS_DIR)              # .../llm-sanguo-project
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from game.engine import GameEngine                       # noqa: E402
from game.data_loader import load_game_data              # noqa: E402
from game.constants import FACTIONS                      # noqa: E402
from game.random import GameRandom                       # noqa: E402
from players.cli_player import CLIPlayer                 # noqa: E402

MAX_TURNS = 192
FACTION_KEYS = list(FACTIONS.keys())
NUM_FACTIONS = len(FACTION_KEYS)

# 安全上限：引擎保证在 turn>=max_turns 时结束，这里再加一道保险以防极端死循环。
SAFETY_MAX_ITER = 500


def stable_hash(text: str) -> int:
    """稳定的字符串哈希（不受 PYTHONHASHSEED 影响）。

    用于为每个势力派生确定性的随机种子，使整套模拟可跨进程复现。
    """
    h = 0
    for ch in text:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return h


def make_players(game_seed: int) -> dict:
    """为 12 个势力各创建一个 CLIPlayer，种子由 game_seed + 势力名确定派生。"""
    players = {}
    for f in FACTION_KEYS:
        faction_seed = (game_seed * 1_000_003 + stable_hash(f)) % 2_000_000_000
        players[f] = CLIPlayer(faction=f, rng=GameRandom(faction_seed))
    return players


def run_one_game(game_seed: int, max_turns: int = MAX_TURNS) -> dict:
    """运行一局完整的 headless ai-vs-ai 对局。

    返回字典包含：
        seed, turns, game_over, winner, crashed, error, traceback,
        city_counts(12方城市数), elapsed_s
    winner 可能为 None（平局 / 仅剩中立城）。
    """
    import time
    engine = GameEngine(seed=game_seed)
    data = load_game_data()
    engine.init_game(data)
    engine.max_turns = max_turns
    players = make_players(game_seed)

    t0 = time.time()
    crashed = None
    error = None
    tb = None
    turns = 0
    try:
        while not engine.game_over:
            for f in FACTION_KEYS:
                obs = engine.get_observation(f)
                for cmd in players[f].get_commands(obs):
                    engine.execute_command(cmd)
            engine.process_turn()
            turns += 1
            if turns > SAFETY_MAX_ITER:
                crashed = "SAFETY_HIT_MAX_ITER"
                break
    except Exception as exc:  # 捕获任何崩溃
        crashed = "EXCEPTION"
        error = repr(exc)
        tb = traceback.format_exc()
    elapsed = time.time() - t0

    result = {
        "seed": game_seed,
        "turns": engine.turn if not crashed else turns,
        "max_turns": max_turns,
        "game_over": bool(engine.game_over),
        "winner": engine.winner,
        "crashed": crashed,
        "error": error,
        "traceback": tb,
        "elapsed_s": round(elapsed, 3),
    }
    if not crashed:
        result["city_counts"] = {
            f: len(engine.map.get_faction_cities(f)) for f in FACTION_KEYS
        }
    else:
        result["city_counts"] = {}
    return result
