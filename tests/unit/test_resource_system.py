"""资源系统单元测试"""

import pytest

from game.models import City
from game.hex_grid import HexCoord
from game.systems.resource_system import ResourceSystem
from game.constants import (
    GOLD_PER_POPULATION,
    FOOD_PER_POPULATION,
    CITY_LEVELS,
)


class TestResourceProduction:
    """资源产出计算测试"""

    def test_gold_production_basic(self):
        """基础金钱产出"""
        rs = ResourceSystem()
        city = _make_test_city(level=3, population=30000, morale=70)

        gold = rs.calculate_gold_production(city)
        # base_gold + population * GOLD_PER_POPULATION
        # = 200 + 30000 * 0.01 = 200 + 300 = 500
        # morale 70 is within normal range (50-80), no penalty
        assert gold == pytest.approx(500, rel=0.01)

    def test_food_production_basic(self):
        """基础粮草产出"""
        rs = ResourceSystem()
        city = _make_test_city(level=3, population=30000, morale=70)

        food = rs.calculate_food_production(city)
        # base_food + population * FOOD_PER_POPULATION
        # = 250 + 30000 * 0.015 = 250 + 450 = 700
        assert food == pytest.approx(700, rel=0.01)

    def test_production_scales_with_level(self):
        """不同等级城市产出不同"""
        rs = ResourceSystem()
        city_low = _make_test_city(level=1, population=5000, morale=70)
        city_high = _make_test_city(level=5, population=100000, morale=70)

        gold_low = rs.calculate_gold_production(city_low)
        gold_high = rs.calculate_gold_production(city_high)

        assert gold_low < gold_high

    def test_production_scales_with_population(self):
        """人口越多产出越高"""
        rs = ResourceSystem()
        city_small = _make_test_city(level=2, population=5000, morale=70)
        city_large = _make_test_city(level=2, population=25000, morale=70)

        gold_small = rs.calculate_gold_production(city_small)
        gold_large = rs.calculate_gold_production(city_large)

        assert gold_small < gold_large

    def test_zero_population(self):
        """人口为0时只有基础产出"""
        rs = ResourceSystem()
        city = _make_test_city(level=1, population=0, morale=70)

        gold = rs.calculate_gold_production(city)
        # 只有基础产出
        assert gold == CITY_LEVELS[1]["base_gold"]


class TestMoraleEffect:
    """民心对产出的影响测试"""

    def test_morale_boost_above_80(self):
        """民心>80时获得产出加成"""
        rs = ResourceSystem()
        city_high = _make_test_city(level=2, population=15000, morale=90)
        city_normal = _make_test_city(level=2, population=15000, morale=70)

        gold_high = rs.calculate_gold_production(city_high)
        gold_normal = rs.calculate_gold_production(city_normal)

        assert gold_high > gold_normal

    def test_morale_penalty_below_50(self):
        """民心<50时产出减少"""
        rs = ResourceSystem()
        city_low = _make_test_city(level=2, population=15000, morale=30)
        city_normal = _make_test_city(level=2, population=15000, morale=70)

        gold_low = rs.calculate_gold_production(city_low)
        gold_normal = rs.calculate_gold_production(city_normal)

        assert gold_low < gold_normal

    def test_morale_below_10_no_production(self):
        """民心<10时产出为0（死亡螺旋）"""
        rs = ResourceSystem()
        city = _make_test_city(level=3, population=30000, morale=5)

        gold = rs.calculate_gold_production(city)
        food = rs.calculate_food_production(city)

        assert gold == 0
        assert food == 0

    def test_morale_at_10_has_production(self):
        """民心=10时仍可产出"""
        rs = ResourceSystem()
        city = _make_test_city(level=2, population=15000, morale=10)

        gold = rs.calculate_gold_production(city)
        assert gold > 0

    def test_morale_at_100_max_boost(self):
        """民心=100时获得最大加成"""
        rs = ResourceSystem()
        city = _make_test_city(level=2, population=15000, morale=100)

        gold = rs.calculate_gold_production(city)
        food = rs.calculate_food_production(city)

        assert gold > 0
        assert food > 0


class TestPopulationGrowth:
    """人口增长计算测试"""

    def test_population_growth_normal(self):
        """正常人口增长"""
        rs = ResourceSystem()
        city = _make_test_city(level=3, population=30000, morale=70)

        growth = rs.calculate_population_growth(city)
        assert growth > 0

    def test_population_growth_high_morale(self):
        """高民心时人口增长更快"""
        rs = ResourceSystem()
        city_high = _make_test_city(level=2, population=15000, morale=90)
        city_low = _make_test_city(level=2, population=15000, morale=50)

        growth_high = rs.calculate_population_growth(city_high)
        growth_low = rs.calculate_population_growth(city_low)

        assert growth_high > growth_low

    def test_population_growth_zero_morale(self):
        """民心为0时人口减少（负增长）"""
        rs = ResourceSystem()
        city = _make_test_city(level=3, population=30000, morale=0)

        growth = rs.calculate_population_growth(city)
        assert growth <= 0

    def test_population_growth_cap(self):
        """增长不超过上限"""
        rs = ResourceSystem()
        city = _make_test_city(level=1, population=1000, morale=100)

        growth = rs.calculate_population_growth(city)
        # 不应超过 MAX_POPULATION_GROWTH_RATE * population
        max_growth = int(0.05 * city.population)
        assert growth <= max_growth

    def test_population_growth_max_population(self):
        """达到最大人口后不再增长"""
        rs = ResourceSystem()
        max_pop = CITY_LEVELS[1]["max_population"]
        city = _make_test_city(level=1, population=max_pop, morale=70)

        growth = rs.calculate_population_growth(city)
        assert growth == 0

    def test_zero_population_no_growth(self):
        """人口为0时无增长"""
        rs = ResourceSystem()
        city = _make_test_city(level=1, population=0, morale=70)

        growth = rs.calculate_population_growth(city)
        assert growth == 0


class TestFoodConsumption:
    """粮草消耗计算测试"""

    def test_garrison_food_consumption(self):
        """守军消耗粮草"""
        rs = ResourceSystem()
        city = _make_test_city(level=3, population=30000, morale=70, garrison=2000)

        consumption = rs.calculate_food_consumption(city)
        # 2000 * 0.1 = 200
        assert consumption == 200

    def test_no_garrison_no_consumption(self):
        """无守军时无消耗"""
        rs = ResourceSystem()
        city = _make_test_city(level=2, population=15000, morale=70, garrison=0)

        consumption = rs.calculate_food_consumption(city)
        assert consumption == 0


class TestCityResourceUpdate:
    """城市资源更新综合测试"""

    def test_full_resource_update(self):
        """完整资源更新流程"""
        rs = ResourceSystem()
        city = _make_test_city(level=3, population=30000, morale=70, garrison=2000)

        result = rs.update_city_resources(city)

        # 验证返回字段
        assert "gold_change" in result
        assert "food_change" in result
        assert "population_change" in result

        # 金库增加
        assert result["gold_change"] > 0
        # 粮草变化 = 产出 - 消耗
        assert result["food_change"] is not None

    def test_resource_update_zero_population(self):
        """人口为0时的资源更新"""
        rs = ResourceSystem()
        city = _make_test_city(level=1, population=0, morale=70)

        result = rs.update_city_resources(city)
        assert result["gold_change"] == CITY_LEVELS[1]["base_gold"]
        assert result["population_change"] == 0


# ============================================================
# 辅助函数
# ============================================================

def _make_test_city(
    level: int,
    population: int,
    morale: int,
    garrison: int = 0,
) -> City:
    """创建测试用城市"""
    level_config = CITY_LEVELS[level]
    return City(
        id="test_city",
        name="测试城",
        faction="wei",
        level=level,
        wall_hp=level_config["wall_hp"],
        wall_max_hp=level_config["wall_hp"],
        gold=1000,
        food=1000,
        population=population,
        morale=morale,
        garrison=garrison,
        position=HexCoord(0, 0),
    )
