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
