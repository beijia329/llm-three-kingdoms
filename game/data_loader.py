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
    map_topology: Dict[str, List[str]] = {}
    for city in cities:
        neighbors = city.get("neighbors", [])
        city_id = city.get("id", "")
        if city_id:
            map_topology[city_id] = list(neighbors)

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
