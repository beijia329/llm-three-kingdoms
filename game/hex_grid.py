"""六角格坐标系统

采用轴向坐标（axial coordinates）表示六角格位置。
每个格子用 (q, r) 表示，第三维 s = -q - r 隐式推导。

参考: https://www.redblobgames.com/grids/hexagons/
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple


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
