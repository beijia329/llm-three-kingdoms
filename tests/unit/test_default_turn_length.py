"""默认对局长度契约测试（v4.1）

背景
----
v4.1 决策「默认对局 = 48 回合」，依据是**实测**：192 回合里第 49 回合起零战斗，
turn 48/96/144/192 的 12 方城分布逐字节相同 → 后 144 回合完全空转，成本 4 倍。
该决策当时**只落了文档、没落代码**，验收时页面仍显示「第 N/192 回合」才暴露。

本文件把「默认值」与「硬上限」这对**容易被混为一谈**的口径钉死：

| 概念 | 值 | 位置 | 语义 |
|------|----|------|------|
| 默认对局长度 | 48 | GameConfig.max_turns / main.py --max-turns / run_web.py --max-turns | 不传参数时跑多少回合 |
| 硬上限 | 192 | game.constants.MAX_TURNS（及 GameEngine 默认） | 允许的最大回合数，不再默认使用 |

🔴 两个数都不许悄悄改：改小 48 会让默认对局缩水；改 192 会破坏
prompt_builder 的兜底与上限相关断言。
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest  # noqa: E402

from api.game_manager import GameConfig, GameManager  # noqa: E402
from game.constants import MAX_TURNS  # noqa: E402


# 上层口径：默认对局 = 48

class TestDefaultTurnLengthIs48:
    """默认对局长度必须是 48（未显式传 max_turns 时）。"""

    def test_gameconfig_default_is_48(self):
        assert GameConfig().max_turns == 48

    def test_manager_default_config_engine_is_48(self):
        """GameManager(GameConfig(seed=1))（不传 max_turns）→ engine.max_turns == 48

        这是验收时「页面显示 192」的直接修复点：默认配置必须落到 48。
        """
        gm = GameManager(GameConfig(seed=1))
        assert gm.engine is not None
        assert gm.engine.max_turns == 48


# 显式指定仍可覆盖（默认值 ≠ 上限）

class TestExplicitMaxTurnsOverride:
    """显式传 max_turns 时以其为准 —— 默认值不得约束调用方。"""

    def test_gameconfig_explicit_192_preserved(self):
        assert GameConfig(max_turns=192).max_turns == 192

    def test_manager_explicit_192_engine_preserved(self):
        """显式 192（长线观察档）→ engine.max_turns == 192，未被默认值破坏。"""
        gm = GameManager(GameConfig(seed=1, max_turns=192))
        assert gm.engine.max_turns == 192

    def test_manager_explicit_small_override(self):
        gm = GameManager(GameConfig(seed=1, max_turns=6))
        assert gm.engine.max_turns == 6


# 硬上限：MAX_TURNS 常量保持 192（它是「上限」，不是「默认」）

class TestUpperBoundConstantUnchanged:
    """MAX_TURNS 的语义是**上限**，值必须保持 192，不随默认对局下调。"""

    def test_max_turns_constant_is_192(self):
        assert MAX_TURNS == 192

    def test_engine_default_follows_upper_bound(self):
        """裸 GameEngine（不经 GameConfig）沿用常量上限 192。

        语义区分：engine 的**默认**是上限常量，对局的**默认**是 48，
        由 GameConfig 在 _init_engine 里显式覆盖。
        """
        from game.engine import GameEngine

        engine = GameEngine(seed=42)
        assert engine.max_turns == 192


# CLI 入口默认值（main.py / run_web.py）

class TestCliDefaults:
    """两处 CLI 的 --max-turns 默认值都必须同步为 48。"""

    def test_main_py_default(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["main.py"])
        import main

        assert main.parse_args().max_turns == 48

    def test_run_web_py_default(self, monkeypatch):
        """run_web.py 的默认值尤其关键：它把 GAME_MAX_TURNS 注入后端进程，
        若此处仍为 192，则默认启动 Web 后 /api/state 仍是 192（验收失败）。
        """
        monkeypatch.setattr(sys, "argv", ["run_web.py"])
        import run_web

        assert run_web.parse_args().max_turns == 48


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
