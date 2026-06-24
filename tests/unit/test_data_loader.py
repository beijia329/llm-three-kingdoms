"""数据加载器单元测试"""

import os

import pytest

from game.data_loader import load_hex_map_data, load_city_positions, DATA_DIR


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
    assert len(positions) >= 20
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


class TestLoadCityPositions:
    """load_city_positions 测试"""

    def test_load_city_positions_returns_dict(self):
        """加载城市坐标返回字典"""
        positions = load_city_positions()
        assert isinstance(positions, dict)
        assert len(positions) >= 30

    def test_load_city_positions_has_key_cities(self):
        """应包含关键城市"""
        positions = load_city_positions()
        assert "luoyang" in positions
        assert "chengdu" in positions
        assert "jianye" in positions
        assert "xuchang" in positions
        assert "changan" in positions

    def test_load_city_positions_valid_coords(self):
        """所有坐标应为有效 int 且在合理范围"""
        positions = load_city_positions()
        for city_id, pos in positions.items():
            assert "q" in pos, f"{city_id} missing q"
            assert "r" in pos, f"{city_id} missing r"
            assert isinstance(pos["q"], int)
            assert isinstance(pos["r"], int)
            assert 0 <= pos["q"] < 200, f"{city_id} q={pos['q']} out of range"
            assert 0 <= pos["r"] < 120, f"{city_id} r={pos['r']} out of range"

    def test_load_city_positions_file_size(self):
        """city_positions.json 应远小于 hex_map.json"""
        import os
        cp_size = os.path.getsize(os.path.join(DATA_DIR, "city_positions.json"))
        hm_size = os.path.getsize(os.path.join(DATA_DIR, "hex_map.json"))
        assert cp_size < 2000, f"city_positions.json should be small, got {cp_size} bytes"
        assert hm_size > cp_size * 100, "hex_map.json should be much larger"
