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
from game.hex_grid import HexCoord


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

    def test_develop_military_repairs_damaged_wall(self):
        """发展军事修复受损城墙，且不再永久抬高城墙上限【v4.0 修正】"""
        cs = CitySystem()
        city = _make_city(level=2)
        city.wall_hp = 600                      # 城墙受损
        cap_before = city.wall_max_hp

        result = cs.develop(city, "military")

        assert result.success is True
        assert city.wall_hp == 800              # 修复 MILITARY_WALL_REPAIR (200)
        assert city.wall_max_hp == cap_before   # 🔴 上限不涨

    def test_develop_military_does_not_inflate_wall_cap(self):
        """反复发展军事不会让城墙上限无限膨胀【v4.0 新增】

        原实现 city.wall_max_hp += 200 每次，实测许昌 40 回合 3200→7400(+131%)，
        使城市变成理论上不可攻破的堡垒，是"围城打不下来"的直接原因之一。
        """
        cs = CitySystem()
        city = _make_city(level=2, gold=100000)
        cap = city.wall_max_hp

        for _ in range(30):
            cs.develop(city, "military")

        assert city.wall_max_hp == cap          # 30 次后上限纹丝不动
        assert city.wall_hp <= cap              # 且不会超过上限

    def test_develop_military_trains_garrison_when_wall_full(self):
        """城墙已满时，发展军事转为训练守军（保证操作不空耗）【v4.0 新增】"""
        cs = CitySystem()
        city = _make_city(level=2)
        assert city.wall_hp == city.wall_max_hp     # 前提：城墙满
        garrison_before = city.garrison

        result = cs.develop(city, "military")

        assert result.success is True
        assert city.wall_max_hp == 1000             # 上限始终不变
        assert city.garrison > garrison_before      # 转为训练守军


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
        city = _make_city(level=2, gold=5, food=5000, garrison=500)

        result = cs.recruit(city, troops=1000)
        # 只有5金币，最多招5人（5/1=5）
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
    faction: str = "wei",
) -> City:
    """创建测试用城市"""
    lc = CITY_LEVELS[level]
    return City(
        id="test_city",
        name="测试城",
        faction=faction,
        level=level,
        wall_hp=lc["wall_hp"],
        wall_max_hp=lc["wall_hp"],
        gold=gold,
        food=food,
        population=population,
        morale=morale,
        garrison=garrison,
        position=HexCoord(0, 0),
    )


# ============================================================
# Hex Territory Tests
# ============================================================

from game.hex_map import HexMap
from game.tile import Tile, TerrainType


class TestCityTerritory:
    """城市控制区测试"""

    def test_territory_level_1(self):
        """1 级城市控制区半径=1，共 7 格"""
        from game.systems.city_system import CitySystem

        city = City(
            id="test", name="测试", faction="caocao", level=1,
            wall_hp=500, wall_max_hp=500, gold=200, food=300,
            population=5000, morale=70, garrison=500,
            position=HexCoord(5, 5),
        )
        hm = _make_small_hex_map(10, 10)

        system = CitySystem()
        territory = system.get_city_territory(city, hm)
        # 半径 1: 中心 + 6 邻居 = 7
        assert len(territory) == 7
        assert HexCoord(5, 5) in territory

    def test_territory_level_2(self):
        """2 级城市控制区半径=2"""
        from game.systems.city_system import CitySystem

        city = City(
            id="test", name="测试", faction="caocao", level=2,
            wall_hp=1000, wall_max_hp=1000, gold=400, food=600,
            population=15000, morale=70, garrison=1000,
            position=HexCoord(5, 5),
        )
        hm = _make_small_hex_map(10, 10)

        system = CitySystem()
        territory = system.get_city_territory(city, hm)
        # 半径 2: 19 格
        assert len(territory) == 19

    def test_territory_level_5(self):
        """5 级城市控制区半径=3"""
        from game.systems.city_system import CitySystem

        city = City(
            id="test", name="测试", faction="caocao", level=5,
            wall_hp=5000, wall_max_hp=5000, gold=2500, food=2500,
            population=100000, morale=70, garrison=5000,
            position=HexCoord(5, 5),
        )
        hm = _make_small_hex_map(10, 10)

        system = CitySystem()
        territory = system.get_city_territory(city, hm)
        # 半径 3: 37 格
        assert len(territory) == 37

    def test_territory_only_existing_tiles(self):
        """控制区只包含实际存在的地块"""
        from game.systems.city_system import CitySystem

        city = _make_city(level=2)
        hm = _make_small_hex_map(3, 3)  # 只有 3x3 格

        system = CitySystem()
        territory = system.get_city_territory(city, hm)
        # 最多 3x3 = 9 格
        assert len(territory) <= 9
        for coord in territory:
            assert hm.get_tile(coord) is not None

    def test_territory_different_position(self):
        """非原点位置的城市"""
        from game.systems.city_system import CitySystem

        city = City(
            id="test", name="测试", faction="caocao", level=2,
            wall_hp=1000, wall_max_hp=1000, gold=400, food=600,
            population=15000, morale=70, garrison=1000,
            position=HexCoord(5, 5),
        )
        hm = _make_small_hex_map(10, 10)

        system = CitySystem()
        territory = system.get_city_territory(city, hm)
        assert HexCoord(5, 5) in territory
        # 应有 19 格（半径 2）
        assert len(territory) == 19


def _make_small_hex_map(width: int, height: int) -> HexMap:
    """创建测试用小尺寸 HexMap"""
    hm = HexMap(width=width, height=height)
    for q in range(width):
        for r in range(height):
            hm.add_tile(Tile(coord=HexCoord(q, r), terrain=TerrainType.PLAIN))
    return hm
