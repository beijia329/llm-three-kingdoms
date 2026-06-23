"""HexMap 六角格地图单元测试"""

import pytest

from game.hex_grid import HexCoord
from game.hex_map import HexMap
from game.tile import Tile, TerrainType


def test_hex_map_create_and_get():
    """基本创建和获取地块"""
    hm = HexMap(width=5, height=5)
    tile = Tile(coord=HexCoord(0, 0), terrain=TerrainType.PLAIN)
    hm.add_tile(tile)
    result = hm.get_tile(HexCoord(0, 0))
    assert result is not None
    assert result.terrain == TerrainType.PLAIN


def test_hex_map_out_of_bounds():
    """超出范围返回 None"""
    hm = HexMap(width=3, height=3)
    assert hm.get_tile(HexCoord(10, 10)) is None


def test_hex_map_find_path_straight():
    """A* 直线路径"""
    hm = HexMap(width=10, height=10)
    for q in range(10):
        for r in range(10):
            hm.add_tile(Tile(coord=HexCoord(q, r), terrain=TerrainType.PLAIN))

    path = hm.find_path(HexCoord(0, 0), HexCoord(2, 0))
    assert len(path) >= 1
    assert path[0] == HexCoord(0, 0)
    assert path[-1] == HexCoord(2, 0)


def test_hex_map_find_path_unreachable():
    """无法到达时返回空列表"""
    hm = HexMap(width=10, height=10)
    # 只有起点和终点，中间没有格子
    hm.add_tile(Tile(coord=HexCoord(0, 0), terrain=TerrainType.PLAIN))
    hm.add_tile(Tile(coord=HexCoord(5, 5), terrain=TerrainType.PLAIN))
    path = hm.find_path(HexCoord(0, 0), HexCoord(5, 5))
    assert path == []


def test_hex_map_find_path_mountain_blocked():
    """山脉阻挡不可通行"""
    hm = HexMap(width=10, height=10)
    for q in range(10):
        for r in range(10):
            terrain = TerrainType.MOUNTAIN if (q == 3) else TerrainType.PLAIN
            hm.add_tile(Tile(coord=HexCoord(q, r), terrain=terrain))

    # 横向山脉列阻挡
    path = hm.find_path(HexCoord(0, 0), HexCoord(5, 0))
    # 应该能找到绕过山脉的路径或无法到达
    if path:
        # 路径中不应包含山脉格
        for coord in path:
            tile = hm.get_tile(coord)
            assert tile is not None
            assert tile.terrain != TerrainType.MOUNTAIN


def test_hex_map_terrain_move_cost():
    """地形移动消耗"""
    assert HexMap.terrain_move_cost(TerrainType.PLAIN) == 1.0
    assert HexMap.terrain_move_cost(TerrainType.FOREST) == 1.5
    assert HexMap.terrain_move_cost(TerrainType.HILL) == 2.0
    assert HexMap.terrain_move_cost(TerrainType.RIVER) == 2.0
    assert HexMap.terrain_move_cost(TerrainType.DESERT) == 1.5
    assert HexMap.terrain_move_cost(TerrainType.MOUNTAIN) == float("inf")


def test_hex_map_get_neighbors():
    """获取相邻地块"""
    hm = HexMap(width=10, height=10)
    for q in range(10):
        for r in range(10):
            hm.add_tile(Tile(coord=HexCoord(q, r), terrain=TerrainType.PLAIN))

    neighbors = hm.get_neighbors(HexCoord(5, 5))
    assert len(neighbors) == 6


def test_hex_map_get_neighbors_edge():
    """边缘格子的相邻数量可能少于 6"""
    hm = HexMap(width=5, height=5)
    for q in range(5):
        for r in range(5):
            hm.add_tile(Tile(coord=HexCoord(q, r), terrain=TerrainType.PLAIN))

    neighbors = hm.get_neighbors(HexCoord(0, 0))
    assert len(neighbors) <= 6


def test_hex_map_iter_tiles():
    """迭代所有地块"""
    hm = HexMap(width=3, height=3)
    for q in range(3):
        for r in range(3):
            hm.add_tile(Tile(coord=HexCoord(q, r), terrain=TerrainType.PLAIN))

    tiles = list(hm.iter_tiles())
    assert len(tiles) == 9


def test_hex_map_find_path_same():
    """起点等于终点"""
    hm = HexMap(width=10, height=10)
    hm.add_tile(Tile(coord=HexCoord(0, 0), terrain=TerrainType.PLAIN))
    path = hm.find_path(HexCoord(0, 0), HexCoord(0, 0))
    assert path == [HexCoord(0, 0)]


def test_hex_map_find_path_start_or_goal_none():
    """起点或终点不存在"""
    hm = HexMap(width=10, height=10)
    hm.add_tile(Tile(coord=HexCoord(0, 0), terrain=TerrainType.PLAIN))
    # 终点不存在
    path = hm.find_path(HexCoord(0, 0), HexCoord(99, 99))
    assert path == []

    # 起点不存在
    path = hm.find_path(HexCoord(99, 99), HexCoord(0, 0))
    assert path == []
