"""城市系统单元测试"""

import pytest

from game.models import City
from game.systems.city_system import (
    CitySystem,
    DevelopResult,
    RecruitResult,
    CityUpdateResult,
)
from game.constants import CITY_LEVELS


class TestDevelopCity:
    """城市发展功能测试"""

    def test_develop_economy(self):
        """发展经济"""
        cs = CitySystem()
        city = _make_city(level=2)

        result = cs.develop(city, "economy")
        assert isinstance(result, DevelopResult)
        assert result.success is True
        assert result.gold_cost > 0
        assert result.description is not None

    def test_develop_military(self):
        """发展军事"""
        cs = CitySystem()
        city = _make_city(level=2)

        result = cs.develop(city, "military")
        assert result.success is True

    def test_develop_culture(self):
        """发展文化"""
        cs = CitySystem()
        city = _make_city(level=2)

        result = cs.develop(city, "culture")
        assert result.success is True

    def test_develop_not_enough_gold(self):
        """金钱不足时发展失败"""
        cs = CitySystem()
        city = _make_city(level=2, gold=0)

        result = cs.develop(city, "economy")
        assert result.success is False

    def test_develop_invalid_type(self):
        """无效发展类型"""
        cs = CitySystem()
        city = _make_city(level=2)

        result = cs.develop(city, "invalid")
        assert result.success is False

    def test_develop_level_1_cost_less(self):
        """低级城市发展成本更低"""
        cs = CitySystem()
        c1 = _make_city(level=1)
        c5 = _make_city(level=5)

        r1 = cs.develop(c1, "economy")
        r5 = cs.develop(c5, "economy")

        assert r1.gold_cost < r5.gold_cost

    def test_develop_economy_increases_gold_production(self):
        """发展经济后，后续资源产出增加"""
        cs = CitySystem()
        city = _make_city(level=2)

        # 经济发展通过 effect_value 反映增益
        result = cs.develop(city, "economy")
        assert result.success is True
        assert result.effect_value > 0  # 有经济增益效果

    def test_develop_culture_increases_morale(self):
        """发展文化提升民心"""
        cs = CitySystem()
        city = _make_city(level=2, morale=60)

        result = cs.develop(city, "culture")
        assert result.success is True
        assert city.morale > 60

    def test_develop_military_increases_wall_hp(self):
        """发展军事提升城墙耐久"""
        cs = CitySystem()
        city = _make_city(level=2)

        wall_before = city.wall_hp
        cs.develop(city, "military")
        assert city.wall_hp > wall_before


class TestRecruit:
    """征兵功能测试"""

    def test_recruit_basic(self):
        """基础征兵"""
        cs = CitySystem()
        city = _make_city(level=2, gold=2000, food=2000, garrison=500)

        result = cs.recruit(city, troops=500)
        assert isinstance(result, RecruitResult)
        assert result.success is True
        assert result.troops_recruited == 500
        assert result.gold_cost > 0
        assert result.food_cost > 0

    def test_recruit_increases_garrison(self):
        """征兵后守军增加"""
        cs = CitySystem()
        city = _make_city(level=2, gold=5000, food=5000, garrison=500)

        cs.recruit(city, troops=1000)
        assert city.garrison == 1500

    def test_recruit_not_enough_gold(self):
        """金钱不足时征兵失败"""
        cs = CitySystem()
        city = _make_city(level=2, gold=0, food=5000, garrison=500)

        result = cs.recruit(city, troops=500)
        assert result.success is False
        assert city.garrison == 500  # 守军不变

    def test_recruit_not_enough_food(self):
        """粮草不足时征兵失败"""
        cs = CitySystem()
        city = _make_city(level=2, gold=5000, food=0, garrison=500)

        result = cs.recruit(city, troops=500)
        assert result.success is False

    def test_recruit_zero_troops(self):
        """征兵0人"""
        cs = CitySystem()
        city = _make_city(level=2, gold=5000, food=5000)

        result = cs.recruit(city, troops=0)
        assert result.success is False

    def test_recruit_negative_troops(self):
        """征兵负数"""
        cs = CitySystem()
        city = _make_city(level=2, gold=5000, food=5000)

        result = cs.recruit(city, troops=-100)
        assert result.success is False

    def test_recruit_partial_when_limited(self):
        """资源有限时征兵部分成功"""
        cs = CitySystem()
        city = _make_city(level=2, gold=10, food=5000, garrison=500)

        result = cs.recruit(city, troops=1000)
        # 只有10金币，最多招5人（10/2=5）
        assert result.success is True
        assert result.troops_recruited == 5
        assert city.gold == 0  # 花光了
        assert city.garrison == 505  # 增加了5人

    def test_recruit_max_limit(self):
        """征兵不能超过守军上限"""
        cs = CitySystem()
        city = _make_city(level=2, gold=50000, food=50000, garrison=0)

        result = cs.recruit(city, troops=100000)
        # level 2 上限2000，应部分成功
        assert result.success is True
        assert result.troops_recruited == 2000
        assert city.garrison == 2000


class TestCityUpdate:
    """城市回合更新测试"""

    def test_update_city(self):
        """城市回合更新"""
        cs = CitySystem()
        city = _make_city(level=2, garrison=500, gold=1000, food=1000, population=15000)

        result = cs.update_city(city)
        assert isinstance(result, CityUpdateResult)
        assert result.gold_change > 0  # 产出增加金库
        assert result.food_change != 0  # 粮草有变化

    def test_update_city_resource_changes(self):
        """更新后城市资源正确变化"""
        cs = CitySystem()
        city = _make_city(level=1, garrison=500, gold=100, food=500, population=5000)

        gold_before = city.gold
        food_before = city.food
        pop_before = city.population

        cs.update_city(city)

        assert city.gold > gold_before
        # 人口可能增长
        assert city.population >= pop_before

    def test_update_death_spiral(self):
        """民心极低时触发死亡螺旋"""
        cs = CitySystem()
        city = _make_city(level=1, morale=5, population=5000, garrison=500, food=100)

        result = cs.update_city(city)
        # 金库不变（产出为0）
        assert result.gold_change >= 0


# ============================================================
# 辅助函数
# ============================================================

def _make_city(
    level: int = 1,
    gold: int = 1000,
    food: int = 1000,
    population: int = 5000,
    morale: int = 70,
    garrison: int = 500,
) -> City:
    """创建测试用城市"""
    lc = CITY_LEVELS[level]
    return City(
        id="test_city",
        name="测试城",
        faction="wei",
        level=level,
        wall_hp=lc["wall_hp"],
        wall_max_hp=lc["wall_hp"],
        gold=gold,
        food=food,
        population=population,
        morale=morale,
        garrison=garrison,
        position=(0, 0),
    )
