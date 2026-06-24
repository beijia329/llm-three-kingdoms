"""地图系统

管理游戏地图的拓扑结构：城市节点和道路连接。
使用邻接表存储，支持：
- 查询相邻城市
- 计算两城市距离（BFS最短路径）
- 路径查找
- 按势力查询城市
"""

from __future__ import annotations

from collections import deque
from typing import Dict, List, Optional

from game.models import City, Province


class MapSystem:
    """地图系统

    使用邻接表存储城市间的连接关系。
    城市通过 neighbors 字段定义相邻关系。

    Attributes:
        _cities: 城市ID到City对象的映射
        _provinces: 州ID到Province对象的映射
        _adjacency: 邻接表，city_id -> 相邻city_id列表
    """

    def __init__(self) -> None:
        self._cities: Dict[str, City] = {}
        self._provinces: Dict[str, Province] = {}
        self._adjacency: Dict[str, List[str]] = {}

    # ============================================================
    # 城市管理
    # ============================================================

    def add_city(self, city: City) -> None:
        """添加一个城市到地图

        根据 city.neighbors 建立双向连接。

        Args:
            city: 要添加的城市对象
        """
        self._cities[city.id] = city
        self._adjacency[city.id] = list(city.neighbors)

        # 确保双向连接：如果邻居已经存在，确保自己也出现在邻居的邻接表中
        for neighbor_id in city.neighbors:
            if neighbor_id in self._adjacency:
                if city.id not in self._adjacency[neighbor_id]:
                    self._adjacency[neighbor_id].append(city.id)
            else:
                self._adjacency[neighbor_id] = [city.id]

    def get_city(self, city_id: str) -> Optional[City]:
        """获取城市对象

        Args:
            city_id: 城市ID

        Returns:
            城市对象，不存在返回 None
        """
        return self._cities.get(city_id)

    def get_city_count(self) -> int:
        """获取城市总数

        Returns:
            地图上的城市数量
        """
        return len(self._cities)

    def get_all_city_ids(self) -> List[str]:
        """获取所有城市ID

        Returns:
            所有城市ID列表
        """
        return list(self._cities.keys())

    # ============================================================
    # 邻接查询
    # ============================================================

    def get_neighbors(self, city_id: str) -> List[str]:
        """获取指定城市的相邻城市列表

        Args:
            city_id: 城市ID

        Returns:
            相邻城市ID列表，城市不存在返回空列表
        """
        return list(self._adjacency.get(city_id, []))

    def are_adjacent(self, city_a: str, city_b: str) -> bool:
        """判断两个城市是否相邻

        Args:
            city_a: 城市A的ID
            city_b: 城市B的ID

        Returns:
            相邻返回 True，否则返回 False
        """
        return city_b in self._adjacency.get(city_a, [])

    # ============================================================
    # 距离计算（BFS）
    # ============================================================

    def get_distance(self, from_city: str, to_city: str) -> int:
        """计算两个城市间的最短距离（边数）

        使用 BFS 算法计算最短路径长度。

        Args:
            from_city: 起始城市ID
            to_city: 目标城市ID

        Returns:
            最短距离（边数），起点终点相同返回0，
            城市不存在或不可达返回-1
        """
        if from_city not in self._adjacency:
            return -1
        if to_city not in self._adjacency:
            return -1
        if from_city == to_city:
            return 0

        visited = {from_city}
        queue = deque([(from_city, 0)])

        while queue:
            current, distance = queue.popleft()
            for neighbor in self._adjacency.get(current, []):
                if neighbor == to_city:
                    return distance + 1
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, distance + 1))

        return -1  # 不可达

    # ============================================================
    # 路径查找（BFS最短路径）
    # ============================================================

    def find_path(self, from_city: str, to_city: str) -> List[str]:
        """查找两个城市间的最短路径

        使用 BFS 算法，返回经过的城市ID列表（含起点和终点）。

        Args:
            from_city: 起始城市ID
            to_city: 目标城市ID

        Returns:
            最短路径上的城市ID列表，从起点到终点。
            不可达或城市不存在返回空列表。
            起点终点相同时返回 [from_city]。
        """
        if from_city not in self._adjacency:
            return []
        if to_city not in self._adjacency:
            return []
        if from_city == to_city:
            return [from_city]

        visited = {from_city}
        queue = deque([from_city])
        predecessor: Dict[str, Optional[str]] = {from_city: None}

        while queue:
            current = queue.popleft()
            for neighbor in self._adjacency.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    predecessor[neighbor] = current
                    queue.append(neighbor)
                    if neighbor == to_city:
                        # 重建路径
                        path = []
                        node = to_city
                        while node is not None:
                            path.append(node)
                            node = predecessor[node]
                        path.reverse()
                        return path

        return []  # 不可达

    # ============================================================
    # 势力查询
    # ============================================================

    def get_faction_cities(self, faction: str) -> List[str]:
        """获取指定势力的所有城市ID

        Args:
            faction: 势力名称

        Returns:
            该势力拥有的城市ID列表
        """
        return [
            city_id
            for city_id, city in self._cities.items()
            if city.faction == faction
        ]

    def get_faction_city_counts(self) -> Dict[str, int]:
        """获取各势力的城市数量统计

        Returns:
            势力名称到城市数量的映射
        """
        counts: Dict[str, int] = {}
        for city in self._cities.values():
            counts[city.faction] = counts.get(city.faction, 0) + 1
        return counts

    # ============================================================
    # 州郡管理
    # ============================================================

    def add_province(self, province: Province) -> None:
        """添加一个州到地图系统

        Args:
            province: 州对象
        """
        self._provinces[province.id] = province

    def get_province(self, province_id: str) -> Optional[Province]:
        """获取州对象

        Args:
            province_id: 州ID

        Returns:
            州对象，不存在返回 None
        """
        return self._provinces.get(province_id)

    def get_all_provinces(self) -> Dict[str, Province]:
        """获取所有州

        Returns:
            州ID到州对象的映射
        """
        return dict(self._provinces)

    def get_province_cities(self, province_id: str) -> List[str]:
        """获取指定州的所有城市ID

        Args:
            province_id: 州ID

        Returns:
            该州下辖的城市ID列表
        """
        province = self._provinces.get(province_id)
        if province:
            return list(province.cities)
        return []

    def get_city_province(self, city_id: str) -> Optional[str]:
        """获取城市所属州ID

        Args:
            city_id: 城市ID

        Returns:
            州ID，城市不存在或未分配州则返回 None
        """
        city = self._cities.get(city_id)
        if city:
            return city.province_id
        return None
