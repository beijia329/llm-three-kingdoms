"""游戏数据加载器

从 JSON 文件加载城市、将领、地图拓扑等初始数据。
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def load_game_data(data_dir: str = DATA_DIR) -> Dict[str, Any]:
    """从 data 目录加载所有游戏初始数据

    Args:
        data_dir: 数据目录路径

    Returns:
        包含 cities, generals, map_topology 的字典
    """
    cities_path = os.path.join(data_dir, "cities.json")
    generals_path = os.path.join(data_dir, "generals.json")
    provinces_path = os.path.join(data_dir, "provinces.json")

    cities: List[Dict[str, Any]] = []
    if os.path.exists(cities_path):
        with open(cities_path, "r", encoding="utf-8") as f:
            cities = json.load(f)
        logger.info("加载 %d 个城市数据", len(cities))
    else:
        logger.warning("城市数据文件不存在: %s", cities_path)

    generals: List[Dict[str, Any]] = []
    if os.path.exists(generals_path):
        with open(generals_path, "r", encoding="utf-8") as f:
            generals = json.load(f)
        logger.info("加载 %d 个将领数据", len(generals))
    else:
        logger.warning("将领数据文件不存在: %s", generals_path)

    provinces: List[Dict[str, Any]] = []
    if os.path.exists(provinces_path):
        with open(provinces_path, "r", encoding="utf-8") as f:
            provinces = json.load(f)
        logger.info("加载 %d 个州数据", len(provinces))
    else:
        logger.warning("州数据文件不存在: %s", provinces_path)

    # 构建地图拓扑
    #
    # 🔴 v4.1：这里做**对称化**，把 cities.json 里的单向邻接补成双向。
    #
    # 起因（主理人数据审计，2026-10-03）：实扫发现 cities.json 的 neighbors 有
    # **25 处单向关系**（如「邺城→洛阳」成立但「洛阳→邺城」不成立）。
    # 危害不在引擎（MapSystem.add_city 会为寻路补全双向），而在**玩家侧**：
    # `players/cli_player.py:148` 用 `city.neighbors` 判断"是否边境城"、
    # `:296` 用它枚举可攻目标 —— 这两处**直接读 City.neighbors，不经过 MapSystem**。
    # 单向邻接会让 AI 漏看邻国：既可能漏守边境，也可能漏掉可攻击目标。
    #
    # 修在数据加载层而不是逐条改 cities.json，理由有二：
    #   1. 一处收口 —— 所有消费方（引擎/玩家/前端）拿到的是同一份对称拓扑；
    #   2. `cities.json` 是手工维护的历史数据（含 neutral 城与省界），
    #      逐条修容易再引入新的不对称，且无法防住将来新增城市时的同样问题。
    # 数据侧仍建议后续补全（规范化），但不应成为正确性的前提。
    _raw_neighbors: Dict[str, List[str]] = {}
    for city in cities:
        city_id = city.get("id", "")
        if city_id:
            _raw_neighbors[city_id] = list(city.get("neighbors") or [])

    map_topology: Dict[str, List[str]] = {cid: set() for cid in _raw_neighbors}
    for city_id, neighbors in _raw_neighbors.items():
        for nb in neighbors:
            if nb not in _raw_neighbors:
                # 悬空引用（指向不存在的城）保留原样，交由调用方感知
                map_topology[city_id].add(nb)
                continue
            map_topology[city_id].add(nb)
            map_topology[nb].add(city_id)  # ← 反向补齐

    map_topology = {
        cid: sorted(nbs) for cid, nbs in map_topology.items()
    }
    # sorted() 保证确定性：引擎有「同 seed 可复现」的硬要求，
    # 集合迭代顺序不稳定会让同一份数据在不同进程产生不同邻接顺序。

    return {
        "cities": cities,
        "generals": generals,
        "provinces": provinces,
        "map_topology": map_topology,
    }


def load_hex_map_data(path: str = "") -> Dict[str, Any]:
    """加载六角格地图数据

    Args:
        path: 地图数据文件路径，为空时使用默认路径 data/hex_map.json

    Returns:
        包含 width, height, terrain, rivers, city_positions 等的字典
    """
    if not path:
        path = os.path.join(DATA_DIR, "hex_map.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_city_positions(path: str = "") -> Dict[str, Dict[str, int]]:
    """加载城市六角格坐标

    Args:
        path: 坐标文件路径，为空时使用默认路径 data/city_positions.json

    Returns:
        城市ID到 {"q": int, "r": int} 的映射
    """
    if not path:
        path = os.path.join(DATA_DIR, "city_positions.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_china_geojson(path: str = "") -> Dict[str, Any]:
    """加载中国行政区划 GeoJSON 数据

    Args:
        path: GeoJSON 文件路径，为空时使用默认路径 data/china_provinces.json

    Returns:
        GeoJSON FeatureCollection，包含各省边界坐标
    """
    if not path:
        path = os.path.join(DATA_DIR, "china_provinces.json")
    if not os.path.exists(path):
        logger.warning("中国地图数据文件不存在: %s", path)
        return {"type": "FeatureCollection", "features": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
