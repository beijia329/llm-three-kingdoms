"""六角格地图主类

管理所有 Tile，提供坐标查询、邻居查询、范围查询和 A* 路径计算。
"""

from __future__ import annotations

import heapq
from typing import Dict, Iterator, List, Optional, Tuple

from game.hex_grid import HexCoord, hex_distance, hex_neighbors
from game.tile import Tile, TerrainType


class HexMap:
    """六角格地图

    管理所有地块，提供坐标查询、路径计算、范围查询等功能。

    Attributes:
        width: 地图宽度（格子数）
        height: 地图高度（格子数）
    """

    def __init__(self, width: int, height: int) -> None:
        """初始化地图

        Args:
            width: 地图宽度（格子数）
            height: 地图高度（格子数）
        """
        self.width = width
        self.height = height
        self._tiles: Dict[Tuple[int, int], Tile] = {}

    def add_tile(self, tile: Tile) -> None:
        """添加或覆盖一个地块

        Args:
            tile: 地块对象
        """
        self._tiles[tile.coord.to_tuple()] = tile

    def get_tile(self, coord: HexCoord) -> Optional[Tile]:
        """获取指定坐标的地块

        Args:
            coord: 六角格坐标

        Returns:
            地块对象，不存在时返回 None
        """
        return self._tiles.get(coord.to_tuple())

    def get_neighbors(self, coord: HexCoord) -> List[Tile]:
        """获取相邻且存在的地块

        Args:
            coord: 中心坐标

        Returns:
            相邻且已添加的地块列表
        """
        result: List[Tile] = []
        for n in hex_neighbors(coord):
            tile = self.get_tile(n)
            if tile is not None:
                result.append(tile)
        return result

    def iter_tiles(self) -> Iterator[Tile]:
        """迭代所有地块

        Returns:
            地块迭代器
        """
        return iter(self._tiles.values())

    @staticmethod
    def terrain_move_cost(terrain: TerrainType) -> float:
        """获取地形移动消耗

        Args:
            terrain: 地形类型

        Returns:
            移动消耗值（inf 表示不可通行）
        """
        costs: Dict[TerrainType, float] = {
            TerrainType.PLAIN: 1.0,
            TerrainType.FOREST: 1.5,
            TerrainType.HILL: 2.0,
            TerrainType.RIVER: 2.0,
            TerrainType.DESERT: 1.5,
            TerrainType.MOUNTAIN: float("inf"),
        }
        return costs.get(terrain, 1.0)

    def find_path(
        self,
        start: HexCoord,
        goal: HexCoord,
    ) -> List[HexCoord]:
        """A* 寻路算法

        在六角格地图上计算从起点到终点的最短路径，
        考虑地形移动消耗和可通行性。

        Args:
            start: 起点坐标
            goal: 终点坐标

        Returns:
            路径坐标列表（含起点和终点），无路径时返回空列表
        """
        if self.get_tile(start) is None or self.get_tile(goal) is None:
            return []

        if start == goal:
            return [start]

        # A* 优先队列: (f_score, counter, coord)
        open_set: List[Tuple[float, int, HexCoord]] = [(0.0, 0, start)]
        came_from: Dict[HexCoord, HexCoord] = {}
        g_score: Dict[HexCoord, float] = {start: 0.0}
        counter = 0

        while open_set:
            _, _, current = heapq.heappop(open_set)

            if current == goal:
                return self._reconstruct_path(came_from, current)

            for neighbor in hex_neighbors(current):
                tile = self.get_tile(neighbor)
                if tile is None or not tile.is_passable():
                    continue
                cost = self.terrain_move_cost(tile.terrain)
                tentative = g_score[current] + cost
                if neighbor not in g_score or tentative < g_score[neighbor]:
                    counter += 1
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative
                    f = tentative + hex_distance(neighbor, goal)
                    heapq.heappush(open_set, (f, counter, neighbor))

        return []

    @staticmethod
    def _reconstruct_path(
        came_from: Dict[HexCoord, HexCoord],
        current: HexCoord,
    ) -> List[HexCoord]:
        """从 came_from 字典重建路径

        Args:
            came_from: 前驱字典
            current: 当前（终点）坐标

        Returns:
            从起点到终点的完整路径
        """
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        return list(reversed(path))
