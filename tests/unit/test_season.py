"""季节与游戏模式单元测试"""

from game.season import Season
from game.game_mode import GameMode


class TestSeason:
    """季节枚举测试"""

    def test_season_from_turn_spring(self):
        assert Season.from_turn(1) == Season.SPRING
        assert Season.from_turn(5) == Season.SPRING
        assert Season.from_turn(9) == Season.SPRING

    def test_season_from_turn_summer(self):
        assert Season.from_turn(2) == Season.SUMMER
        assert Season.from_turn(6) == Season.SUMMER
        assert Season.from_turn(10) == Season.SUMMER

    def test_season_from_turn_autumn(self):
        assert Season.from_turn(3) == Season.AUTUMN
        assert Season.from_turn(7) == Season.AUTUMN
        assert Season.from_turn(11) == Season.AUTUMN

    def test_season_from_turn_winter(self):
        assert Season.from_turn(4) == Season.WINTER
        assert Season.from_turn(8) == Season.WINTER
        assert Season.from_turn(12) == Season.WINTER

    def test_season_full_cycle(self):
        """完整年份循环（每 4 回合 = 1 年）"""
        assert Season.from_turn(1) == Season.SPRING
        assert Season.from_turn(2) == Season.SUMMER
        assert Season.from_turn(3) == Season.AUTUMN
        assert Season.from_turn(4) == Season.WINTER
        assert Season.from_turn(5) == Season.SPRING  # 第二年春
        assert Season.from_turn(8) == Season.WINTER  # 第二年冬

    def test_season_names_zh(self):
        names = Season.season_names_zh()
        assert names["spring"] == "春"
        assert names["summer"] == "夏"
        assert names["autumn"] == "秋"
        assert names["winter"] == "冬"


class TestGameMode:
    """游戏模式枚举测试"""

    def test_game_mode_values(self):
        assert GameMode.STANDARD.value == "standard"
        assert GameMode.INFINITE.value == "infinite"

    def test_game_mode_count(self):
        assert len(GameMode) == 2
