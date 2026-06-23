"""常量配置单元测试"""

import pytest
from game.constants import (
    MAX_TURNS,
    NUM_FACTIONS,
    STARTING_CITIES_PER_FACTION,
    CITY_LEVELS,
    FACTIONS,
    FACTION_COLORS,
    GOLD_PER_POPULATION,
    FOOD_PER_POPULATION,
    RECRUIT_COST_GOLD,
    RECRUIT_COST_FOOD,
    WALL_DAMAGE_BASE,
    LOYALTY_DECAY_PER_TURN,
    MORALE_BREAK_THRESHOLD,
    GENERAL_ATTRIBUTE_MIN,
    GENERAL_ATTRIBUTE_MAX,
)


class TestGameConstants:
    """游戏规则常量测试"""

    def test_game_rules(self):
        """测试基本游戏规则"""
        assert MAX_TURNS == 24
        assert NUM_FACTIONS == 3
        assert STARTING_CITIES_PER_FACTION == 5

    def test_factions(self):
        """测试势力定义"""
        assert len(FACTIONS) == 3
        assert "wei" in FACTIONS
        assert "shu" in FACTIONS
        assert "wu" in FACTIONS
        assert FACTIONS["wei"] == "魏国"

    def test_faction_colors(self):
        """测试势力颜色"""
        assert len(FACTION_COLORS) == 4  # 3 factions + neutral
        assert FACTION_COLORS["neutral"] == "#888888"
        # 颜色应该是有效的十六进制颜色码
        for color in FACTION_COLORS.values():
            assert color.startswith("#")
            assert len(color) == 7


class TestCityLevels:
    """城市等级配置测试"""

    def test_city_level_count(self):
        """应有5个城市等级"""
        assert len(CITY_LEVELS) == 5

    def test_city_level_keys(self):
        """每个等级应有完整配置字段"""
        required_keys = [
            "name", "base_gold", "base_food", "max_population",
            "wall_hp", "initial_gold", "initial_food",
            "initial_population", "initial_morale", "initial_garrison",
        ]
        for level, config in CITY_LEVELS.items():
            for key in required_keys:
                assert key in config, f"Level {level} missing key: {key}"

    def test_city_level_values(self):
        """城市等级数值应递增"""
        for level in range(2, 6):
            prev = CITY_LEVELS[level - 1]
            curr = CITY_LEVELS[level]
            assert curr["base_gold"] > prev["base_gold"], (
                f"Level {level} base_gold should be > level {level - 1}"
            )
            assert curr["max_population"] > prev["max_population"], (
                f"Level {level} max_population should be > level {level - 1}"
            )
            assert curr["wall_hp"] > prev["wall_hp"], (
                f"Level {level} wall_hp should be > level {level - 1}"
            )

    def test_city_level_ranges(self):
        """各数值应在合理范围内"""
        for level, config in CITY_LEVELS.items():
            assert config["initial_morale"] == 70
            assert config["initial_morale"] <= 100
            assert config["initial_morale"] >= 0
            assert config["initial_garrison"] > 0
            assert config["max_population"] > 0

    def test_city_level_names(self):
        """城市等级名称"""
        assert CITY_LEVELS[1]["name"] == "小城"
        assert CITY_LEVELS[3]["name"] == "大城"
        assert CITY_LEVELS[5]["name"] == "都城"


class TestEconomyConstants:
    """经济系统参数测试"""

    def test_production_rates(self):
        """产出系数应在合理范围"""
        assert 0 < GOLD_PER_POPULATION < 1
        assert 0 < FOOD_PER_POPULATION < 1
        assert GOLD_PER_POPULATION < FOOD_PER_POPULATION  # 产粮 > 产金

    def test_recruit_costs(self):
        """征兵消耗应为正数"""
        assert RECRUIT_COST_GOLD > 0
        assert RECRUIT_COST_FOOD > 0


class TestBattleConstants:
    """战斗系统参数测试"""

    def test_wall_damage(self):
        """城墙伤害应为正数"""
        assert WALL_DAMAGE_BASE > 0

    def test_morale_thresholds(self):
        """士气阈值应在合理范围"""
        assert 0 < MORALE_BREAK_THRESHOLD < 100


class TestGeneralConstants:
    """将领系统参数测试"""

    def test_loyalty_decay(self):
        """忠诚度衰减应为正数"""
        assert LOYALTY_DECAY_PER_TURN > 0

    def test_attribute_range(self):
        """属性范围应合理"""
        assert GENERAL_ATTRIBUTE_MIN == 1
        assert GENERAL_ATTRIBUTE_MAX == 100
        assert GENERAL_ATTRIBUTE_MIN < GENERAL_ATTRIBUTE_MAX
