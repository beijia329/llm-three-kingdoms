"""交战国对下发契约测试（v4.3.0 D3 · 地图「交战前线」红线数据）

地图要在「双方 at_war」时画 L4 红线（见 docs/art/2026-10-04-战棋视觉元素规范.md §4.2）。
本测试守卫后端 `get_state()` 的 `at_war_pairs` 字段：只发 [a,b] 对数组，且严格只含
处于战争状态的对；无战争时为 []（前端据此不画红线，不臆造）。
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest  # noqa: E402

from api.game_manager import GameConfig, GameManager  # noqa: E402
from game.models import DiplomaticStatus  # noqa: E402


class TestAtWarPairsPayload:
    def test_empty_when_no_war(self):
        gm = GameManager(GameConfig(seed=1, max_turns=2, game_mode="standard"))
        state = gm.get_state()
        assert "at_war_pairs" in state
        assert state["at_war_pairs"] == []

    def test_declared_war_appears_as_pair(self):
        gm = GameManager(GameConfig(seed=1, max_turns=2, game_mode="standard"))
        rel = gm.engine._diplomacy_relation_system
        assert rel is not None
        rel.set_status("caocao", "liubei", DiplomaticStatus.WAR, turn=1)

        state = gm.get_state()
        pairs = {tuple(sorted(p)) for p in state["at_war_pairs"]}
        assert ("caocao", "liubei") in pairs

    def test_pairs_are_two_element_lists(self):
        gm = GameManager(GameConfig(seed=1, max_turns=2, game_mode="standard"))
        rel = gm.engine._diplomacy_relation_system
        rel.set_status("sunjian", "han", DiplomaticStatus.WAR, turn=1)
        state = gm.get_state()
        for p in state["at_war_pairs"]:
            assert isinstance(p, list) and len(p) == 2


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
