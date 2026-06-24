"""六角格坐标系统单元测试"""

import math

import pytest

from game.hex_grid import (
    HexCoord,
    Direction,
    hex_distance,
    hex_neighbors,
    get_direction,
    direction_opposite,
    axial_to_pixel,
    pixel_to_axial,
)


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


class TestDirection:
    """Direction 六方向枚举 + get_direction 测试（Wesnoth 精华提取）"""

    def test_direction_enum_has_six_members(self):
        """应有 6 个方向成员"""
        members = list(Direction)
        assert len(members) == 6

    def test_direction_names(self):
        """方向名称应与 Wesnoth 一致"""
        names = {d.name for d in Direction}
        expected = {"N", "NE", "SE", "S", "SW", "NW"}
        assert names == expected

    def test_get_direction_zero_steps(self):
        """steps=0 返回零向量"""
        for d in Direction:
            v = get_direction(d, steps=0)
            assert v == HexCoord(0, 0)

    def test_get_direction_single_step(self):
        """单步方向向量应为单位向量"""
        for d in Direction:
            v = get_direction(d, steps=1)
            assert hex_distance(HexCoord(0, 0), v) == 1, (
                f"Direction {d.name} should be 1 step away"
            )

    def test_get_direction_multi_step(self):
        """多步方向向量距离应等于步数"""
        for d in Direction:
            for steps in (1, 2, 3, 5):
                v = get_direction(d, steps=steps)
                dist = hex_distance(HexCoord(0, 0), v)
                assert dist == steps, (
                    f"{d.name} × {steps} should be {steps} away, got {dist}"
                )

    def test_get_direction_consistency(self):
        """同一方向连续 steps 次单步 = 一次多步"""
        for d in Direction:
            single = HexCoord(0, 0)
            vec = get_direction(d, steps=1)
            for _ in range(4):
                single = single + vec
            multi = get_direction(d, steps=4)
            assert single == multi, (
                f"{d.name}: 4×1step ({single}) != 1×4steps ({multi})"
            )

    def test_direction_opposite(self):
        """相反方向应抵消"""
        for d in Direction:
            opp = direction_opposite(d)
            v1 = get_direction(d, steps=1)
            v2 = get_direction(opp, steps=1)
            assert v1.q + v2.q == 0
            assert v1.r + v2.r == 0

    def test_direction_opposite_is_involutive(self):
        """相反方向的相反方向 = 原方向"""
        for d in Direction:
            assert direction_opposite(direction_opposite(d)) == d

    def test_direction_opposite_all_unique(self):
        """所有相反方向均不同"""
        opposites = {direction_opposite(d) for d in Direction}
        assert len(opposites) == 6

    def test_move_and_back(self):
        """走 steps 再反向走 steps 应回到原点"""
        origin = HexCoord(5, 5)
        for d in Direction:
            for steps in (1, 3):
                fwd = get_direction(d, steps=steps)
                rev = get_direction(direction_opposite(d), steps=steps)
                assert origin + fwd + rev == origin, (
                    f"{d.name}: origin + fwd + rev != origin"
                )

    def test_all_directions_sum_to_zero(self):
        """所有 6 方向单步向量之和应为零向量"""
        total = HexCoord(0, 0)
        for d in Direction:
            total = total + get_direction(d, steps=1)
        assert total == HexCoord(0, 0), f"Sum of all directions = {total}"

    def test_get_direction_negative_steps(self):
        """负步数应等于相反方向正步数"""
        for d in Direction:
            v_neg = get_direction(d, steps=-3)
            v_pos = get_direction(direction_opposite(d), steps=3)
            assert v_neg == v_pos, (
                f"{d.name}: -3 steps should equal opposite × 3"
            )
