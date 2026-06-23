"""数据加载器单元测试"""

import os

import pytest

from game.data_loader import load_hex_map_data, DATA_DIR


def test_load_hex_map_data():
    """加载六角格地图数据"""
    data = load_hex_map_data()
    assert "width" in data
    assert "height" in data
    assert "city_positions" in data
    assert "terrain" in data
    assert "rivers" in data


def test_load_hex_map_data_with_default_path():
    """使用默认路径加载"""
    data = load_hex_map_data()
    assert data["width"] == 120
    assert data["height"] == 90
    assert data["hex_size"] == 32


def test_load_hex_map_data_city_positions():
    """验证城市位置数据"""
    data = load_hex_map_data()
    positions = data["city_positions"]
    # 应有 15 个城市
    assert len(positions) == 15
    # 验证几个关键城市
    assert "luoyang" in positions
    assert "chengdu" in positions
    assert "jianye" in positions
    # 每个位置应有 q, r
    for city_id, pos in positions.items():
        assert "q" in pos
        assert "r" in pos
        assert isinstance(pos["q"], int)
        assert isinstance(pos["r"], int)


def test_load_hex_map_data_with_explicit_path():
    """使用显式路径加载"""
    path = os.path.join(DATA_DIR, "hex_map.json")
    data = load_hex_map_data(path)
    assert data["width"] == 120
