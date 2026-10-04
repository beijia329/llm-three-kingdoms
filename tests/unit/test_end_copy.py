"""终局文案单一真源契约测试（v4.3.0 D1 · H1 判定口径统一）

对应 `game/end_copy.py` 与 docs/design/2026-10-04-胜负条件与对局长度.md §1.1。

🔴 硬约束：任何 `end_reason != "unification"` 的标题**不得**含「一统天下」；
且后端事件文案与 `/api/state` 的 `end_title`/`end_subtitle` 必须同源一致。
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest  # noqa: E402

from game.end_copy import format_end_copy, format_end_event  # noqa: E402


class TestFormatEndCopyFourOutcomes:
    """四种结局全覆盖（unification / timeout / stalemate / winner 为空）。"""

    def test_unification(self):
        title, sub = format_end_copy("unification", "sunjian", 30, 192, 6)
        assert title == "孙坚 一统天下"
        assert sub == "第 30 回合 · 廓清寰宇"

    def test_timeout(self):
        title, sub = format_end_copy("timeout", "sunjian", 48, 48, 6)
        assert title == "孙坚 领先胜出"
        assert sub == "第 48 / 48 回合 · 时限已到，天下未定"
        assert "统一" not in title

    def test_stalemate(self):
        title, sub = format_end_copy("stalemate", "sunjian", 55, 192, 6)
        assert title == "孙坚 领先胜出"
        assert sub == "连续 6 回合无战事 · 僵局收束，天下未定"
        assert "统一" not in title

    def test_no_winner_tie(self):
        title, sub = format_end_copy("timeout", None, 48, 48, 6)
        assert title == "天下未定 · 并列"
        assert "统一" not in title
        assert sub == "第 48 / 48 回合 · 时限已到，天下未定"

    def test_no_winner_stalemate(self):
        title, sub = format_end_copy("stalemate", None, 55, 192, 6)
        assert title == "天下未定 · 并列"
        assert sub == "连续 6 回合无战事 · 僵局收束，天下未定"

    def test_unknown_reason_never_says_unification(self):
        """旧档 end_reason=None → 按 timeout 口径，绝不臆造「一统天下」。"""
        title, _ = format_end_copy(None, "sunjian", 48, 48, 6)
        assert title == "孙坚 领先胜出"
        assert "统一" not in title

    def test_stalemate_turns_parameter_used(self):
        _, sub = format_end_copy("stalemate", "han", 40, 192, 3)
        assert "连续 3 回合" in sub


class TestFormatEndEventSharesSource:
    """事件文案与标题同源（format_end_copy）。"""

    def test_event_contains_title(self):
        title, _ = format_end_copy("timeout", "sunjian", 48, 48, 6)
        assert title in format_end_event("timeout", "sunjian", 48, 48, 6)

    def test_event_unification_has_trophy_wording(self):
        ev = format_end_event("unification", "sunjian", 30, 192, 6)
        assert "一统天下" in ev

    def test_event_non_unification_no_unification_word(self):
        for reason in ("timeout", "stalemate", None):
            ev = format_end_event(reason, "sunjian", 48, 48, 6)
            assert "统一" not in ev


class TestApiStateEndCopyContract:
    """`/api/state` 顶层必须带 end_title / end_subtitle，且与真源一致。"""

    def test_fields_present_even_before_end(self):
        from api.game_manager import GameConfig, GameManager

        gm = GameManager(GameConfig(seed=1, max_turns=3, game_mode="standard"))
        state = gm.get_state()
        assert "end_title" in state and "end_subtitle" in state
        assert state["end_title"] == "" and state["end_subtitle"] == ""

    def test_timeout_state_fields_match_source(self):
        from api.game_manager import GameConfig, GameManager

        gm = GameManager(GameConfig(seed=1, max_turns=1, game_mode="standard"))
        gm.process_turn()
        assert gm.engine.game_over and gm.engine.end_reason == "timeout"
        state = gm.get_state()
        exp_title, exp_sub = format_end_copy(
            "timeout", gm.engine.winner, gm.engine.turn, gm.engine.max_turns,
            gm.config.stalemate_turns,
        )
        assert state["end_title"] == exp_title
        assert state["end_subtitle"] == exp_sub
        # 🔴 H1：非统一结局，标题不得出现「统一」
        assert "统一" not in state["end_title"]

    def test_unification_state_fields(self):
        from api.game_manager import GameConfig, GameManager

        gm = GameManager(GameConfig(seed=1, game_mode="infinite"))
        for city in gm.engine.cities.values():
            city.faction = "sunjian"
        gm.process_turn()
        assert gm.engine.end_reason == "unification"
        state = gm.get_state()
        assert state["end_title"] == "孙坚 一统天下"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
