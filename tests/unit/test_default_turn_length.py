"""默认对局长度与结束语义契约测试（v4.3.0 方案 A′）

背景
----
- v4.1 决策「默认对局 = 48 回合」，依据是实测 192 回合里第 49 回合起零战斗、
  后 144 回合空转。该顾虑成立，但「局限在回合」本身被玩家否决。
- v4.3.0 改为**方案 A′**：默认 `game_mode="infinite"` + 僵局熔断
  （连续 `stalemate_turns` 回合零战斗 → 收束为「领先胜出」），并保留
  `max_turns=192` 作为无限模式的**软上限/兜底**（防极端死循环）。

本文件把三层口径钉死（它们**都容易被混为一谈**）：

| 概念 | 值 | 位置 | 语义 |
|------|----|------|------|
| 默认游戏模式 | infinite | GameConfig.game_mode | 有战事就打到统一，零战事 N 回合熔断 |
| 默认 max_turns | 192 | GameConfig.max_turns / main.py / run_web.py | 无限模式下=软上限兜底；standard 下=硬时限 |
| 硬上限常量 | 192 | game.constants.MAX_TURNS | 允许的最大回合数 |
| 僵局熔断阈值 | 6 | GameConfig.stalemate_turns / constants.STALEMATE_TURNS | 连续零战斗回合阈值 |
| 快档 | 48 | 显式传参（--max-turns 48 / GAME_MAX_TURNS=48） | 短场/压测档，**不删**；其结束文案同为「领先」 |

🔴 三个数都不许悄悄改：改 max_turns 会动默认对局长度；改 MAX_TURNS 会破坏
prompt_builder 的兜底与上限断言；改 stalemate_turns 会动对局节奏。
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest  # noqa: E402

from api.game_manager import GameConfig, GameManager  # noqa: E402
from game.constants import MAX_TURNS, STALEMATE_TURNS  # noqa: E402


# 上层口径：默认 = 无限模式 + max_turns 192（软上限）+ 熔断 6

class TestDefaultMatchLengthIs192:
    """默认配置：infinite 模式、max_turns=192（软上限）、stalemate_turns=6。"""

    def test_gameconfig_default_max_turns_is_192(self):
        assert GameConfig().max_turns == 192

    def test_gameconfig_default_mode_is_infinite(self):
        assert GameConfig().game_mode == "infinite"

    def test_gameconfig_default_stalemate_turns_is_6(self):
        assert GameConfig().stalemate_turns == 6

    def test_manager_default_config_engine_is_infinite_192(self):
        """GameManager(GameConfig(seed=1))（不传 max_turns）→
        engine.max_turns == 192 且 engine.game_mode == INFINITE。

        这是「默认对局 = 无限 + 192 兜底」的落地点：infinite 不再把
        max_turns 顶到 9999（否则兜底失效）。
        """
        from game.game_mode import GameMode

        gm = GameManager(GameConfig(seed=1))
        assert gm.engine is not None
        assert gm.engine.max_turns == 192
        assert gm.engine.game_mode == GameMode.INFINITE
        assert gm.engine.stalemate_turns == 6


# 显式指定仍可覆盖（默认值 ≠ 上限，≠ 强制）

class TestExplicitOverride:
    """显式传参时以其为准 —— 默认值不得约束调用方（含 48 快档）。"""

    def test_gameconfig_explicit_192_preserved(self):
        assert GameConfig(max_turns=192).max_turns == 192

    def test_gameconfig_explicit_48_fastlane_preserved(self):
        """48 快档仍可显式选择（不删）。"""
        cfg = GameConfig(max_turns=48, game_mode="standard")
        assert cfg.max_turns == 48
        assert cfg.game_mode == "standard"

    def test_manager_explicit_standard_mode_preserved(self):
        from game.game_mode import GameMode

        gm = GameManager(GameConfig(seed=1, max_turns=48, game_mode="standard"))
        assert gm.engine.max_turns == 48
        assert gm.engine.game_mode == GameMode.STANDARD

    def test_manager_explicit_stalemate_override(self):
        gm = GameManager(GameConfig(seed=1, stalemate_turns=3))
        assert gm.engine.stalemate_turns == 3


# 硬上限：MAX_TURNS 常量保持 192（它是「上限」，不是「默认」）

class TestUpperBoundConstantUnchanged:
    """MAX_TURNS 的语义是**上限**，值必须保持 192。"""

    def test_max_turns_constant_is_192(self):
        assert MAX_TURNS == 192

    def test_stalemate_turns_constant_is_6(self):
        assert STALEMATE_TURNS == 6

    def test_engine_default_follows_upper_bound(self):
        """裸 GameEngine（不经 GameConfig）沿用常量上限 192。"""
        from game.engine import GameEngine

        engine = GameEngine(seed=42)
        assert engine.max_turns == 192


# CLI 入口默认值（main.py / run_web.py）

class TestCliDefaults:
    """两处 CLI 的默认值都必须同步为 v4.3.0 口径。"""

    def test_main_py_default_max_turns(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["main.py"])
        import main

        assert main.parse_args().max_turns == 192

    def test_run_web_py_default_max_turns(self, monkeypatch):
        """run_web.py 把 GAME_MAX_TURNS 注入后端进程；默认必须是 192。"""
        monkeypatch.setattr(sys, "argv", ["run_web.py"])
        import run_web

        assert run_web.parse_args().max_turns == 192

    def test_run_web_py_default_mode_is_infinite(self, monkeypatch):
        """run_web.py 的 --mode 默认必须是 infinite（方案 A′ 的上线默认）。"""
        monkeypatch.setattr(sys, "argv", ["run_web.py"])
        import run_web

        assert run_web.parse_args().mode == "infinite"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
