"""影响力系统单元测试"""

import pytest

from game.hex_grid import HexCoord
from game.hex_map import HexMap
from game.influence_system import InfluenceSystem
from game.models import City
from game.tile import Tile, TerrainType


def _make_test_city(
    faction: str = "wei",
    level: int = 2,
    morale: int = 80,
    position_q: int = 5,
    position_r: int = 5,
) -> City:
    """创建测试用城市"""
    return City(
        id=f"city_{faction}",
        name=f"Test {faction}",
        faction=faction,
        level=level,
        wall_hp=1000,
        wall_max_hp=1000,
        gold=1000,
        food=1000,
        population=15000,
        morale=morale,
        garrison=1000,
        position=HexCoord(position_q, position_r),
    )


def _make_test_hex_map(width: int = 10, height: int = 10) -> HexMap:
    """创建测试用 HexMap"""
    hm = HexMap(width=width, height=height)
    for q in range(width):
        for r in range(height):
            hm.add_tile(Tile(coord=HexCoord(q, r), terrain=TerrainType.PLAIN))
    return hm


class TestInfluenceSpread:
    """影响力扩散测试"""

    def test_influence_spreads_from_city(self):
        """影响力从城市向外扩散"""
        hm = _make_test_hex_map()
        city = _make_test_city(faction="wei", morale=80, level=2)
        sys = InfluenceSystem()
        sys.spread_influence([city], hm)
        tile = hm.get_tile(HexCoord(5, 5))
        assert tile is not None
        assert tile.influence.get("wei", 0) > 0

    def test_influence_decays_with_distance(self):
        """影响力随距离衰减"""
        hm = _make_test_hex_map(20, 20)
        city = _make_test_city(faction="wei", morale=80, level=2)
        sys = InfluenceSystem()
        sys.spread_influence([city], hm)

        center = hm.get_tile(HexCoord(5, 5))
        assert center is not None
        near = hm.get_tile(HexCoord(6, 5))
        assert near is not None
        far = hm.get_tile(HexCoord(8, 5))
        assert far is not None

        center_inf = center.influence.get("wei", 0)
        near_inf = near.influence.get("wei", 0)
        far_inf = far.influence.get("wei", 0)

        assert center_inf > near_inf > far_inf

    def test_influence_multiple_factions(self):
        """多势力影响力竞争"""
        hm = _make_test_hex_map(20, 20)
        city_wei = _make_test_city(faction="wei", morale=80, level=3, position_q=5, position_r=8)
        city_shu = _make_test_city(faction="shu", morale=80, level=3, position_q=10, position_r=8)
        sys = InfluenceSystem()
        sys.spread_influence([city_wei, city_shu], hm)

        # 中间点应该有两个势力的影响力
        mid = hm.get_tile(HexCoord(7, 8))
        assert mid is not None
        assert "wei" in mid.influence
        assert "shu" in mid.influence

    def test_spread_clears_previous(self):
        """每次扩散前清空旧影响力"""
        hm = _make_test_hex_map()
        city = _make_test_city()
        sys = InfluenceSystem()
        sys.spread_influence([city], hm)

        # 第一次扩散
        tile = hm.get_tile(HexCoord(5, 5))
        assert tile is not None
        first_val = tile.influence.get("wei", 0)

        # 第二次扩散（城市等级不变，值应相同）
        sys.spread_influence([city], hm)
        second_val = tile.influence.get("wei", 0)
        assert abs(first_val - second_val) < 0.01


class TestInfluenceModifiers:
    """影响力 Buff/Debuff 计算测试"""

    def test_own_influence_buff(self):
        """己方高影响力提供产出加成"""
        tile = Tile(coord=HexCoord(0, 0), terrain=TerrainType.PLAIN,
                    faction="wei", influence={"wei": 100.0})
        mods = InfluenceSystem.get_tile_modifiers(tile, "wei")
        assert mods["production"] > 0
        assert mods["defense"] > 0

    def test_enemy_influence_debuff(self):
        """敌方高影响力提供产出减成"""
        tile = Tile(coord=HexCoord(0, 0), terrain=TerrainType.PLAIN,
                    faction="wei", influence={"wei": 10.0, "shu": 50.0})
        mods = InfluenceSystem.get_tile_modifiers(tile, "wei")
        assert mods["production"] < 0
        assert mods["defense"] < 0
        assert mods["movement"] < 0

    def test_no_influence_no_modifiers(self):
        """无影响力时无修正"""
        tile = Tile(coord=HexCoord(0, 0), terrain=TerrainType.PLAIN,
                    faction="wei", influence={})
        mods = InfluenceSystem.get_tile_modifiers(tile, "wei")
        assert mods["production"] == 0.0
        assert mods["defense"] == 0.0
        assert mods["movement"] == 0.0

    def test_enemy_not_dominant_no_debuff(self):
        """敌方影响力未达到支配地位时不触发 debuff，但己方也不占优"""
        tile = Tile(coord=HexCoord(0, 0), terrain=TerrainType.PLAIN,
                    faction="wei", influence={"wei": 50.0, "shu": 60.0})
        mods = InfluenceSystem.get_tile_modifiers(tile, "wei")
        # 60 < 50 * 2 = 100, 所以 shu 未达到支配，无 debuff
        # 但 wei (50) < shu (60)，wei 不是最高，所以也没有 own buff
        assert mods["production"] == 0.0
        assert mods["defense"] == 0.0
        assert mods["movement"] == 0.0
