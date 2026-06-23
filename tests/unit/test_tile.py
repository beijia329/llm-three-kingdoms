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


def test_tile_elevation_default():
    """海拔默认为 0"""
    tile = Tile(coord=HexCoord(0, 0), terrain=TerrainType.PLAIN)
    assert tile.elevation == 0


def test_tile_with_elevation():
    """可设置海拔"""
    tile = Tile(coord=HexCoord(0, 0), terrain=TerrainType.HILL, elevation=3)
    assert tile.elevation == 3
