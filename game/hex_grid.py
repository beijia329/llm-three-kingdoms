"""六角格坐标系统

采用轴向坐标（axial coordinates）表示六角格位置。
每个格子用 (q, r) 表示，第三维 s = -q - r 隐式推导。

参考: https://www.redblobgames.com/grids/hexagons/
Wesnoth src/map/location.hpp — 方向枚举 / get_direction 设计
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Tuple


class Direction(Enum):
    """六角格六方向枚举（pointy-topped axial 坐标）

    参考 Wesnoth map_location::DIRECTION 和 Red Blob Games 轴向方向定义。
    """

    N = "N"
    NE = "NE"
    SE = "SE"
    S = "S"
    SW = "SW"
    NW = "NW"


@dataclass(frozen=True)
class HexCoord:
    """六角格轴向坐标

    Attributes:
        q: 轴向 q 坐标
        r: 轴向 r 坐标
        s: 隐式第三维坐标，s = -q - r
    """

    q: int
    r: int

    @property
    def s(self) -> int:
        """隐式第三维坐标"""
        return -self.q - self.r

    def __add__(self, other: HexCoord) -> HexCoord:
        """向量加法"""
        return HexCoord(self.q + other.q, self.r + other.r)

    def __sub__(self, other: HexCoord) -> HexCoord:
        """向量减法"""
        return HexCoord(self.q - other.q, self.r - other.r)

    def to_tuple(self) -> Tuple[int, int]:
        """返回 (q, r) 元组"""
        return (self.q, self.r)


# 方向到轴向偏移量的映射（pointy-topped 六角格）
_DIRECTION_VECTORS: Dict[Direction, HexCoord] = {
    Direction.N: HexCoord(0, -1),
    Direction.NE: HexCoord(1, -1),
    Direction.SE: HexCoord(1, 0),
    Direction.S: HexCoord(0, 1),
    Direction.SW: HexCoord(-1, 1),
    Direction.NW: HexCoord(-1, 0),
}

# 相反方向映射
_OPPOSITE_DIRECTION: Dict[Direction, Direction] = {
    Direction.N: Direction.S,
    Direction.NE: Direction.SW,
    Direction.SE: Direction.NW,
    Direction.S: Direction.N,
    Direction.SW: Direction.NE,
    Direction.NW: Direction.SE,
}


# 六角格 6 个方向向量
HEX_DIRECTIONS = [
    HexCoord(1, 0),
    HexCoord(1, -1),
    HexCoord(0, -1),
    HexCoord(-1, 0),
    HexCoord(-1, 1),
    HexCoord(0, 1),
]


def hex_distance(a: HexCoord, b: HexCoord) -> int:
    """计算两个六角格的曼哈顿距离

    Args:
        a: 第一个坐标
        b: 第二个坐标

    Returns:
        两个坐标之间的六角格距离（步数）
    """
    diff = a - b
    return max(abs(diff.q), abs(diff.r), abs(diff.s))


def hex_neighbors(center: HexCoord) -> List[HexCoord]:
    """获取某格子的 6 个相邻格子

    Args:
        center: 中心坐标

    Returns:
        相邻 6 个格子的坐标列表
    """
    return [center + d for d in HEX_DIRECTIONS]


def get_direction(direction: Direction, steps: int = 1) -> HexCoord:
    """获取某方向的偏移向量

    参考 Wesnoth map_location::get_direction() 设计。

    Args:
        direction: 六角格方向
        steps: 步数（默认为 1，负数为反向）

    Returns:
        偏移坐标向量

    Examples:
        >>> get_direction(Direction.N, 2)
        HexCoord(0, -2)
        >>> get_direction(Direction.SE, -1)
        HexCoord(-1, 0)
    """
    if steps == 0:
        return HexCoord(0, 0)
    if steps < 0:
        direction = direction_opposite(direction)
        steps = -steps
    v = _DIRECTION_VECTORS[direction]
    return HexCoord(v.q * steps, v.r * steps)


def direction_opposite(direction: Direction) -> Direction:
    """获取相反方向

    Args:
        direction: 当前方向

    Returns:
        相反方向
    """
    return _OPPOSITE_DIRECTION[direction]


def axial_to_pixel(coord: HexCoord, size: float) -> Tuple[float, float]:
    """轴向坐标转屏幕像素坐标（pointy-topped 六角格）

    Args:
        coord: 轴向坐标
        size: 六角格外接圆半径（像素）

    Returns:
        (x, y) 屏幕像素坐标
    """
    x = size * (math.sqrt(3) * coord.q + math.sqrt(3) / 2 * coord.r)
    y = size * (3.0 / 2 * coord.r)
    return (x, y)


def pixel_to_axial(x: float, y: float, size: float) -> HexCoord:
    """屏幕像素坐标转轴向坐标

    Args:
        x: 屏幕 x 坐标
        y: 屏幕 y 坐标
        size: 六角格外接圆半径（像素）

    Returns:
        最近的 HexCoord
    """
    q = (math.sqrt(3) / 3 * x - 1.0 / 3 * y) / size
    r = (2.0 / 3 * y) / size
    return _hex_round(q, r)


def _hex_round(q: float, r: float) -> HexCoord:
    """浮点六角坐标取整到最近的整数格

    Args:
        q: 浮点 q 坐标
        r: 浮点 r 坐标

    Returns:
        最近的整数 HexCoord
    """
    s = -q - r
    rq, rr, rs = round(q), round(r), round(s)
    dq, dr, ds = abs(rq - q), abs(rr - r), abs(rs - s)
    # 修正取整误差：将误差最大的分量用另外两个分量重新计算
    if dq > dr and dq > ds:
        rq = -rr - rs
    elif dr > ds:
        rr = -rq - rs
    return HexCoord(int(rq), int(rr))
