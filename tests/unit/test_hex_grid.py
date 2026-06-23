"""六角格坐标系统单元测试"""

import math

import pytest

from game.hex_grid import HexCoord, hex_distance, hex_neighbors, axial_to_pixel, pixel_to_axial


def test_hex_coord_creation():
    """测试 HexCoord 创建和 s 属性自动计算"""
    coord = HexCoord(q=2, r=-1)
    assert coord.q == 2
    assert coord.r == -1
    assert coord.s == -1  # s = -q - r = -2 - (-1) = -1


def test_hex_coord_addition():
    """测试 HexCoord 加法"""
    a = HexCoord(1, 2)
    b = HexCoord(3, -1)
    result = a + b
    assert result.q == 4
    assert result.r == 1


def test_hex_coord_subtraction():
    """测试 HexCoord 减法"""
    a = HexCoord(5, 3)
    b = HexCoord(2, 1)
    result = a - b
    assert result.q == 3
    assert result.r == 2


def test_hex_distance():
    """测试六角格距离计算"""
    a = HexCoord(0, 0)
    b = HexCoord(3, -2)
    # d = max(|3-0|, |(-2)-0|, |(-1)-0|) = max(3, 2, 1) = 3
    assert hex_distance(a, b) == 3

    # 同格距离为 0
    assert hex_distance(HexCoord(0, 0), HexCoord(0, 0)) == 0

    # 邻格距离为 1
    assert hex_distance(HexCoord(0, 0), HexCoord(1, 0)) == 1
    assert hex_distance(HexCoord(0, 0), HexCoord(0, 1)) == 1


def test_hex_neighbors():
    """测试邻居计算"""
    center = HexCoord(1, 1)
    neighbors = hex_neighbors(center)
    assert len(neighbors) == 6
    assert HexCoord(2, 1) in neighbors    # (1, 0) dir
    assert HexCoord(2, 0) in neighbors    # (1, -1) dir
    assert HexCoord(1, 0) in neighbors    # (0, -1) dir
    assert HexCoord(0, 1) in neighbors    # (-1, 0) dir
    assert HexCoord(0, 2) in neighbors    # (-1, 1) dir
    assert HexCoord(1, 2) in neighbors    # (0, 1) dir


def test_axial_to_pixel():
    """测试轴向坐标转像素坐标"""
    size = 32.0
    coord = HexCoord(1, 1)
    x, y = axial_to_pixel(coord, size)
    expected_x = size * (math.sqrt(3) * 1 + math.sqrt(3) / 2 * 1)
    expected_y = size * (3.0 / 2 * 1)
    assert x == pytest.approx(expected_x)
    assert y == pytest.approx(expected_y)


def test_pixel_to_axial_roundtrip():
    """测试像素坐标与轴向坐标的往返转换"""
    size = 32.0
    original = HexCoord(10, 5)
    x, y = axial_to_pixel(original, size)
    result = pixel_to_axial(x, y, size)
    assert result == original


def test_hex_coord_to_tuple():
    """测试 to_tuple 方法"""
    coord = HexCoord(3, -2)
    t = coord.to_tuple()
    assert t == (3, -2)


def test_hex_coord_frozen():
    """HexCoord 应该不可变"""
    coord = HexCoord(1, 1)
    with pytest.raises(Exception):
        coord.q = 5  # type: ignore
