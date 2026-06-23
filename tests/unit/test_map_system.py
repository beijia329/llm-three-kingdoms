"""地图系统单元测试"""

import pytest

from game.models import City
from game.systems.map_system import MapSystem


class TestMapSystem:
    """地图系统基础功能测试"""

    def test_empty_map(self):
        """空地图应正常工作"""
        ms = MapSystem()
        assert ms.get_city_count() == 0
        assert ms.get_neighbors("nonexistent") == []

    def test_add_city(self):
        """添加单个城市"""
        ms = MapSystem()
        city = City(
            id="chengdu", name="成都", faction="shu", level=3,
            wall_hp=2000, wall_max_hp=2000, gold=800, food=1000,
            population=30000, morale=70, garrison=2000,
            position=(100, 200), neighbors=["hanzhong"],
        )
        ms.add_city(city)
        assert ms.get_city_count() == 1
        assert ms.get_city("chengdu") is not None
        assert ms.get_city("chengdu").name == "成都"

    def test_add_multiple_cities(self):
        """添加多个城市并建立连接"""
        ms = MapSystem()

        cities = [
            City(id="a", name="A", faction="wei", level=1,
                 wall_hp=500, wall_max_hp=500, gold=200, food=300,
                 population=5000, morale=70, garrison=500,
                 position=(0, 0), neighbors=["b"]),
            City(id="b", name="B", faction="wei", level=1,
                 wall_hp=500, wall_max_hp=500, gold=200, food=300,
                 population=5000, morale=70, garrison=500,
                 position=(100, 0), neighbors=["a", "c"]),
            City(id="c", name="C", faction="shu", level=1,
                 wall_hp=500, wall_max_hp=500, gold=200, food=300,
                 population=5000, morale=70, garrison=500,
                 position=(200, 0), neighbors=["b"]),
        ]
        for c in cities:
            ms.add_city(c)

        assert ms.get_city_count() == 3
        assert ms.are_adjacent("a", "b") is True
        assert ms.are_adjacent("b", "c") is True
        assert ms.are_adjacent("a", "c") is False  # 不相邻

    def test_get_neighbors(self):
        """获取相邻城市"""
        ms = MapSystem()
        _add_chain_cities(ms, 4)  # a-b-c-d

        neighbors = ms.get_neighbors("b")
        assert set(neighbors) == {"a", "c"}

        # 端点的邻居
        assert ms.get_neighbors("a") == ["b"]
        assert ms.get_neighbors("d") == ["c"]

    def test_get_neighbors_nonexistent(self):
        """不存在的城市返回空列表"""
        ms = MapSystem()
        assert ms.get_neighbors("ghost") == []

    def test_get_faction_cities(self):
        """按势力获取城市列表"""
        ms = MapSystem()

        cities = [
            _make_city("a", "wei", ["b"]),
            _make_city("b", "wei", ["a", "c"]),
            _make_city("c", "shu", ["b", "d"]),
            _make_city("d", "wu", ["c"]),
        ]
        for c in cities:
            ms.add_city(c)

        assert set(ms.get_faction_cities("wei")) == {"a", "b"}
        assert set(ms.get_faction_cities("shu")) == {"c"}
        assert set(ms.get_faction_cities("wu")) == {"d"}
        assert ms.get_faction_cities("neutral") == []


class TestMapDistance:
    """地图距离计算测试"""

    def test_distance_adjacent(self):
        """相邻城市距离为1"""
        ms = MapSystem()
        _add_chain_cities(ms, 3)
        assert ms.get_distance("a", "b") == 1

    def test_distance_two_steps(self):
        """隔一个城市距离为2"""
        ms = MapSystem()
        _add_chain_cities(ms, 3)
        assert ms.get_distance("a", "c") == 2

    def test_distance_same_city(self):
        """同一城市距离为0"""
        ms = MapSystem()
        _add_chain_cities(ms, 2)
        assert ms.get_distance("a", "a") == 0

    def test_distance_nonexistent(self):
        """不存在的城市距离为-1"""
        ms = MapSystem()
        _add_chain_cities(ms, 2)
        assert ms.get_distance("a", "ghost") == -1

    def test_distance_unreachable(self):
        """不连通的城市距离为-1"""
        ms = MapSystem()
        cities = [
            _make_city("a", "wei", ["b"]),
            _make_city("b", "wei", ["a"]),
            _make_city("c", "shu", ["d"]),  # 独立图
            _make_city("d", "shu", ["c"]),
        ]
        for c in cities:
            ms.add_city(c)
        assert ms.get_distance("a", "c") == -1

    def test_distance_complex_graph(self):
        """复杂图距离计算"""
        ms = MapSystem()
        # a-b-c-d-e, 且 b-f-g
        cities = [
            _make_city("a", "wei", ["b"]),
            _make_city("b", "wei", ["a", "c", "f"]),
            _make_city("c", "shu", ["b", "d"]),
            _make_city("d", "shu", ["c", "e"]),
            _make_city("e", "wu", ["d"]),
            _make_city("f", "wei", ["b", "g"]),
            _make_city("g", "wei", ["f"]),
        ]
        for c in cities:
            ms.add_city(c)

        assert ms.get_distance("a", "g") == 3  # a-b-f-g (3 edges)
        assert ms.get_distance("a", "e") == 4  # a-b-c-d-e
        assert ms.get_distance("g", "e") == 5  # g-f-b-c-d-e


class TestMapPathFinding:
    """路径查找测试"""

    def test_find_path_simple(self):
        """简单路径"""
        ms = MapSystem()
        _add_chain_cities(ms, 4)  # a-b-c-d
        path = ms.find_path("a", "d")
        assert path == ["a", "b", "c", "d"]

    def test_find_path_no_path(self):
        """无路径返回空"""
        ms = MapSystem()
        cities = [
            _make_city("a", "wei", []),
            _make_city("b", "wei", []),
        ]
        for c in cities:
            ms.add_city(c)
        assert ms.find_path("a", "b") == []

    def test_find_path_same_city(self):
        """起点终点相同"""
        ms = MapSystem()
        _add_chain_cities(ms, 3)
        assert ms.find_path("a", "a") == ["a"]

    def test_find_path_multiple_routes(self):
        """多路径时返回最短路径"""
        ms = MapSystem()
        # a-b-c-d (3步), a-e-d (2步), 应返回最短
        cities = [
            _make_city("a", "wei", ["b", "e"]),
            _make_city("b", "wei", ["a", "c"]),
            _make_city("c", "shu", ["b", "d"]),
            _make_city("d", "shu", ["c", "e"]),
            _make_city("e", "shu", ["a", "d"]),
        ]
        for c in cities:
            ms.add_city(c)
        path = ms.find_path("a", "d")
        assert len(path) == 3  # a-e-d
        assert path[0] == "a"
        assert path[-1] == "d"

    def test_find_path_with_obstacle(self):
        """绕路路径"""
        ms = MapSystem()
        # a-b-c-d, a-e-d (e不可达) -> 走长路
        cities = [
            _make_city("a", "wei", ["b"]),
            _make_city("b", "wei", ["a", "c"]),
            _make_city("c", "shu", ["b", "d"]),
            _make_city("d", "shu", ["c"]),
        ]
        for c in cities:
            ms.add_city(c)
        path = ms.find_path("a", "d")
        assert path == ["a", "b", "c", "d"]

    def test_find_path_nonexistent(self):
        """不存在的城市返回空"""
        ms = MapSystem()
        _add_chain_cities(ms, 3)
        assert ms.find_path("a", "ghost") == []
        assert ms.find_path("ghost", "a") == []


class TestMapAllCities:
    """完整地图功能测试"""

    def test_get_all_cities(self):
        """获取所有城市ID"""
        ms = MapSystem()
        _add_chain_cities(ms, 5)
        all_cities = ms.get_all_city_ids()
        assert set(all_cities) == {"a", "b", "c", "d", "e"}

    def test_get_all_cities_empty(self):
        """空地图"""
        ms = MapSystem()
        assert ms.get_all_city_ids() == []

    def test_get_cities_by_faction_counts(self):
        """三方城市统计"""
        ms = MapSystem()
        cities = [
            _make_city("a", "wei", ["b"]),
            _make_city("b", "wei", ["a", "c"]),
            _make_city("c", "shu", ["b"]),
        ]
        for c in cities:
            ms.add_city(c)

        counts = ms.get_faction_city_counts()
        assert counts["wei"] == 2
        assert counts["shu"] == 1
        assert counts.get("wu", 0) == 0


# ============================================================
# 测试辅助函数
# ============================================================

def _make_city(city_id: str, faction: str, neighbors: list) -> City:
    """快速创建测试用城市"""
    return City(
        id=city_id,
        name=f"City-{city_id}",
        faction=faction,
        level=1,
        wall_hp=500,
        wall_max_hp=500,
        gold=200,
        food=300,
        population=5000,
        morale=70,
        garrison=500,
        position=(0, 0),
        neighbors=neighbors,
    )


def _add_chain_cities(ms: MapSystem, n: int) -> None:
    """创建链状城市图 a-b-c-..."""
    ids = [chr(ord("a") + i) for i in range(n)]
    for i, city_id in enumerate(ids):
        neighbors = []
        if i > 0:
            neighbors.append(ids[i - 1])
        if i < n - 1:
            neighbors.append(ids[i + 1])
        ms.add_city(_make_city(city_id, "wei" if i % 2 == 0 else "shu", neighbors))
