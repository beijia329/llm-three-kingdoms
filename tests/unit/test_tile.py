"""Tile 地块数据模型单元测试"""

import pytest

from game.hex_grid import HexCoord
from game.tile import Tile, TerrainType


def test_tile_creation():
    """测试 Tile 基本创建"""
    tile = Tile(coord=HexCoord(0, 0), terrain=TerrainType.PLAIN)
    assert tile.coord == HexCoord(0, 0)
    assert tile.terrain == TerrainType.PLAIN
    assert tile.faction is None


def test_tile_yields_default():
    """新创建地块产出默认为 0"""
    tile = Tile(coord=HexCoord(0, 0), terrain=TerrainType.PLAIN)
    assert tile.gold_yield >= 0
    assert tile.food_yield >= 0
    assert tile.pop_yield >= 0


def test_tile_default_morale():
    """默认民心为 50"""
    tile = Tile(coord=HexCoord(0, 0), terrain=TerrainType.PLAIN)
    assert tile.morale == 50


def test_tile_default_influence():
    """默认影响力为空字典"""
    tile = Tile(coord=HexCoord(0, 0), terrain=TerrainType.PLAIN)
    assert tile.influence == {}
    assert isinstance(tile.influence, dict)


def test_tile_faction_assignment():
    """测试 faction 赋值"""
    tile = Tile(coord=HexCoord(0, 0), terrain=TerrainType.PLAIN, faction="wei")
    assert tile.faction == "wei"


def test_tile_owner_city():
    """测试 owner_city_id"""
    tile = Tile(
        coord=HexCoord(0, 0),
        terrain=TerrainType.PLAIN,
        owner_city_id="xuchang",
    )
    assert tile.owner_city_id == "xuchang"


def test_tile_is_passable():
    """测试可通行判定"""
    plain = Tile(coord=HexCoord(0, 0), terrain=TerrainType.PLAIN)
    assert plain.is_passable() is True

    mountain = Tile(coord=HexCoord(1, 1), terrain=TerrainType.MOUNTAIN)
    assert mountain.is_passable() is False

    river = Tile(coord=HexCoord(2, 2), terrain=TerrainType.RIVER)
    assert river.is_passable() is True


def test_tile_terrain_types():
    """所有地形类型应有定义"""
    terrains = list(TerrainType)
    assert TerrainType.PLAIN in terrains
    assert TerrainType.FOREST in terrains
    assert TerrainType.HILL in terrains
    assert TerrainType.MOUNTAIN in terrains
    assert TerrainType.RIVER in terrains
    assert TerrainType.DESERT in terrains


class TestFifteenTerrainTypes:
    """15 种地形类型扩展测试（Phase 1 地图生成器）"""

    ALL_15_TERRAINS = [
        "grass", "grassland", "plain", "forest", "dense_forest",
        "hill", "mountain", "peak", "desert", "marsh",
        "tundra", "snow", "water", "deep_water", "river",
    ]

    def test_all_15_terrains_exist_in_enum(self):
        """全部 15 种地形枚举值应存在且字符串值一致"""
        for name in self.ALL_15_TERRAINS:
            member = getattr(TerrainType, name.upper(), None)
            assert member is not None, f"TerrainType.{name.upper()} missing"
            assert member.value == name, (
                f"TerrainType.{name.upper()}.value should be '{name}', "
                f"got '{member.value}'"
            )

    def test_terrain_type_count(self):
        """枚举成员数应为 15"""
        assert len(list(TerrainType)) == 15

    def test_grass_variants(self):
        """grassy 类地形应有区分"""
        assert TerrainType.GRASS.value == "grass"
        assert TerrainType.GRASSLAND.value == "grassland"
        assert TerrainType.PLAIN.value == "plain"
        assert TerrainType.GRASS != TerrainType.GRASSLAND

    def test_forest_variants(self):
        """森林类地形应有区分"""
        assert TerrainType.FOREST.value == "forest"
        assert TerrainType.DENSE_FOREST.value == "dense_forest"
        assert TerrainType.FOREST != TerrainType.DENSE_FOREST

    def test_elevation_variants(self):
        """海拔类地形应有完整梯度"""
        assert TerrainType.HILL.value == "hill"
        assert TerrainType.MOUNTAIN.value == "mountain"
        assert TerrainType.PEAK.value == "peak"

    def test_cold_variants(self):
        """寒冷类地形应有区分"""
        assert TerrainType.TUNDRA.value == "tundra"
        assert TerrainType.SNOW.value == "snow"

    def test_water_variants(self):
        """水域地形应有区分"""
        assert TerrainType.WATER.value == "water"
        assert TerrainType.DEEP_WATER.value == "deep_water"
        assert TerrainType.RIVER.value == "river"


class TestIsPassable:
    """is_passable() 15 种地形通行规则测试"""

    def _tile_with(self, terrain: TerrainType) -> Tile:
        return Tile(coord=HexCoord(0, 0), terrain=terrain)

    def test_plain_traversable(self):
        """草地/平原/草原均可通行"""
        for t in (TerrainType.GRASS, TerrainType.GRASSLAND, TerrainType.PLAIN):
            assert self._tile_with(t).is_passable() is True, (
                f"{t.value} should be passable"
            )

    def test_forest_traversable(self):
        """森林均可通行（但移动消耗高）"""
        for t in (TerrainType.FOREST, TerrainType.DENSE_FOREST):
            assert self._tile_with(t).is_passable() is True, (
                f"{t.value} should be passable"
            )

    def test_hill_traversable(self):
        """丘陵可通行"""
        assert self._tile_with(TerrainType.HILL).is_passable() is True

    def test_mountain_impassable(self):
        """山脉不可通行"""
        assert self._tile_with(TerrainType.MOUNTAIN).is_passable() is False

    def test_peak_impassable(self):
        """山峰不可通行"""
        assert self._tile_with(TerrainType.PEAK).is_passable() is False

    def test_water_impassable(self):
        """水域不可通行（陆地行军视角）"""
        assert self._tile_with(TerrainType.WATER).is_passable() is False

    def test_deep_water_impassable(self):
        """深海不可通行"""
        assert self._tile_with(TerrainType.DEEP_WATER).is_passable() is False

    def test_river_passable(self):
        """河流可通行但减速"""
        assert self._tile_with(TerrainType.RIVER).is_passable() is True

    def test_desert_passable(self):
        """沙漠可通行"""
        assert self._tile_with(TerrainType.DESERT).is_passable() is True

    def test_marsh_passable(self):
        """沼泽可通行"""
        assert self._tile_with(TerrainType.MARSH).is_passable() is True

    def test_tundra_passable(self):
        """冻土可通行"""
        assert self._tile_with(TerrainType.TUNDRA).is_passable() is True

    def test_snow_passable(self):
        """雪地可通行"""
        assert self._tile_with(TerrainType.SNOW).is_passable() is True


def test_tile_elevation_default():
    """海拔默认为 0"""
    tile = Tile(coord=HexCoord(0, 0), terrain=TerrainType.PLAIN)
    assert tile.elevation == 0


def test_tile_with_elevation():
    """可设置海拔"""
    tile = Tile(coord=HexCoord(0, 0), terrain=TerrainType.HILL, elevation=3)
    assert tile.elevation == 3
