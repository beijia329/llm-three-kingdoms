"""常量配置单元测试"""

import pytest
from game.constants import (
    MAX_TURNS,
    NUM_FACTIONS,
    TOTAL_CITIES,
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
        assert MAX_TURNS == 192
        assert NUM_FACTIONS == 12
        assert TOTAL_CITIES == 22

    def test_factions(self):
        """测试势力定义"""
        assert len(FACTIONS) == 12
        assert "caocao" in FACTIONS
        assert "liubei" in FACTIONS
        assert "sunjian" in FACTIONS
        assert FACTIONS["caocao"] == "曹操"

    def test_faction_colors(self):
        """测试势力颜色"""
        assert len(FACTION_COLORS) == 13  # 12 factions + neutral
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


class TestHexMapConstants:
    """六角格地图常量测试"""

    def test_hex_size(self):
        """六角格大小应为正数"""
        from game.constants import HEX_SIZE
        assert HEX_SIZE > 0

    def test_hex_map_dimensions(self):
        """地图尺寸应为正数"""
        from game.constants import HEX_MAP_WIDTH, HEX_MAP_HEIGHT
        assert HEX_MAP_WIDTH > 0
        assert HEX_MAP_HEIGHT > 0


class TestTerrainConstants:
    """地形常量测试"""

    def test_terrain_move_cost(self):
        """地形移动消耗应有定义"""
        from game.constants import TERRAIN_MOVE_COST
        assert TERRAIN_MOVE_COST["plain"] == 1.0
        assert TERRAIN_MOVE_COST["mountain"] == float("inf")
        for terrain in ["plain", "forest", "hill", "mountain", "river", "desert"]:
            assert terrain in TERRAIN_MOVE_COST

    def test_terrain_defense_bonus(self):
        """地形防御加成"""
        from game.constants import TERRAIN_DEFENSE_BONUS
        assert TERRAIN_DEFENSE_BONUS["plain"] == 0.0
        assert TERRAIN_DEFENSE_BONUS["mountain"] == 0.40
        assert TERRAIN_DEFENSE_BONUS["desert"] == -0.10

    def test_terrain_yields(self):
        """地形产出应有定义"""
        from game.constants import TERRAIN_YIELDS
        for terrain in ["plain", "forest", "hill", "mountain", "river", "desert"]:
            yields = TERRAIN_YIELDS[terrain]
            assert "gold" in yields
            assert "food" in yields
            assert "pop" in yields

    def test_city_territory_radius(self):
        """城市控制区半径"""
        from game.constants import CITY_TERRITORY_RADIUS
        assert len(CITY_TERRITORY_RADIUS) == 5
        assert CITY_TERRITORY_RADIUS[1] == 1
        assert CITY_TERRITORY_RADIUS[5] == 3


class TestSeasonConstants:
    """季节常量测试"""

    def test_season_food_bonus(self):
        """季节粮草加成"""
        from game.constants import SEASON_FOOD_BONUS
        assert "spring" in SEASON_FOOD_BONUS
        assert "summer" in SEASON_FOOD_BONUS
        assert "autumn" in SEASON_FOOD_BONUS
        assert "winter" in SEASON_FOOD_BONUS
        assert SEASON_FOOD_BONUS["autumn"] > 1.0  # 秋季丰收

    def test_season_movement_factor(self):
        """季节移动系数"""
        from game.constants import SEASON_MOVEMENT_FACTOR
        assert SEASON_MOVEMENT_FACTOR["winter"] < 1.0  # 冬季减速
        assert "winter" in SEASON_MOVEMENT_FACTOR


class TestInfluenceConstants:
    """影响力常量测试"""

    def test_influence_decay(self):
        """影响力衰减应在合理范围"""
        from game.constants import INFLUENCE_DECAY_PER_HEX
        assert 0 < INFLUENCE_DECAY_PER_HEX < 1

    def test_influence_buff_rates(self):
        """影响力 Buff/Debuff 比率"""
        from game.constants import INFLUENCE_OWN_BUFF_RATE, INFLUENCE_ENEMY_DEBUFF_RATE
        assert INFLUENCE_OWN_BUFF_RATE > 0
        assert INFLUENCE_ENEMY_DEBUFF_RATE > 0

    def test_influence_dominance_ratio(self):
        """敌方影响力优势阈值"""
        from game.constants import INFLUENCE_ENEMY_DOMINANCE_RATIO
        assert INFLUENCE_ENEMY_DOMINANCE_RATIO > 1.0
