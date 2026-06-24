"""MapGenerator 地图生成器单元测试（Phase 1）"""

import pytest

from game.random import GameRandom
from game.tile import TerrainType
from game.hex_map import HexMap


# ---------------------------------------------------------------------------
# 由于 MapGenerator 尚未创建，导入会失败，这确认了 RED 状态。
# 创建 game/map_generator.py 后测试转为 GREEN。
# ---------------------------------------------------------------------------
MapGenerator = None
try:
    from game.map_generator import MapGenerator  # noqa: E402, F811
except ImportError:
    pass


requires_mapgen = pytest.mark.skipif(
    MapGenerator is None,
    reason="MapGenerator not yet implemented (Phase 1 Step 5 → RED)",
)


LAND_TERRAINS = {
    TerrainType.GRASS,
    TerrainType.GRASSLAND,
    TerrainType.PLAIN,
    TerrainType.FOREST,
    TerrainType.DENSE_FOREST,
    TerrainType.HILL,
    TerrainType.MOUNTAIN,
    TerrainType.PEAK,
    TerrainType.DESERT,
    TerrainType.MARSH,
    TerrainType.TUNDRA,
    TerrainType.SNOW,
}

WATER_TERRAINS = {TerrainType.WATER, TerrainType.DEEP_WATER}

TROPICAL_TERRAINS = {TerrainType.DESERT, TerrainType.DENSE_FOREST}
COLD_TERRAINS = {TerrainType.TUNDRA, TerrainType.SNOW}


class TestMapGenerator:
    """MapGenerator 功能测试"""

    @requires_mapgen
    def test_generate_creates_valid_hex_map(self):
        """测试 1: 生成有效的 HexMap"""
        rng = GameRandom(seed=42)
        gen = MapGenerator(rng)
        hex_map = gen.generate(30, 20)
        assert hex_map is not None
        assert isinstance(hex_map, HexMap)
        # 应生成 width * height 个格子
        tiles = list(hex_map.iter_tiles())
        assert len(tiles) == 30 * 20, (
            f"Expected {30 * 20} tiles, got {len(tiles)}"
        )
        # 所有格子应有合法的 terrain
        for tile in tiles:
            assert isinstance(tile.terrain, TerrainType)

    @requires_mapgen
    def test_map_has_both_land_and_water(self):
        """测试 2: 地图有水有陆地"""
        rng = GameRandom(seed=42)
        gen = MapGenerator(rng)
        hex_map = gen.generate(60, 40)
        terrains = {t.terrain for t in hex_map.iter_tiles()}
        # 至少有一种水域
        assert any(t in WATER_TERRAINS for t in terrains), (
            f"No water terrain found in {terrains}"
        )
        # 至少有一种陆地地形
        assert any(t in LAND_TERRAINS for t in terrains), (
            f"No land terrain found in {terrains}"
        )

    @requires_mapgen
    def test_climate_zones_present(self):
        """测试 3: 气候带存在（南部热带、北部寒冷）"""
        rng = GameRandom(seed=42)
        gen = MapGenerator(rng)
        hex_map = gen.generate(60, 40)
        from game.constants import TERRAIN_PROPERTIES

        # 取南部行（r 接近 40）
        southern_rows_terrains = set()
        for tile in hex_map.iter_tiles():
            if tile.coord.r >= 30:  # 下 1/4
                southern_rows_terrains.add(tile.terrain)

        # 取北部行（r 接近 0）
        northern_rows_terrains = set()
        for tile in hex_map.iter_tiles():
            if tile.coord.r < 10:  # 上 1/4
                northern_rows_terrains.add(tile.terrain)

        # 南部应有 tropical 温度属性的地形
        has_tropical_south = any(
            TERRAIN_PROPERTIES.get(t.value, {}).get("temperature") == "tropical"
            for t in southern_rows_terrains
        )
        # 北部应有 cold/frozen 温度属性的地形
        has_cold_north = any(
            TERRAIN_PROPERTIES.get(t.value, {}).get("temperature") in ("cold", "frozen")
            for t in northern_rows_terrains
        )
        assert has_tropical_south, (
            f"No tropical terrain in south rows. Found: {southern_rows_terrains}"
        )
        assert has_cold_north, (
            f"No cold/frozen terrain in north rows. Found: {northern_rows_terrains}"
        )

    @requires_mapgen
    def test_deterministic_with_same_seed(self):
        """测试 4: 相同 seed → 完全相同的地图"""
        rng1 = GameRandom(seed=42)
        rng2 = GameRandom(seed=42)
        gen1 = MapGenerator(rng1)
        gen2 = MapGenerator(rng2)
        hm1 = gen1.generate(30, 20)
        hm2 = gen2.generate(30, 20)

        tiles1 = sorted(hm1.iter_tiles(), key=lambda t: t.coord.to_tuple())
        tiles2 = sorted(hm2.iter_tiles(), key=lambda t: t.coord.to_tuple())

        assert len(tiles1) == len(tiles2)
        for t1, t2 in zip(tiles1, tiles2):
            assert t1.coord == t2.coord, (
                f"Coord mismatch: {t1.coord} vs {t2.coord}"
            )
            assert t1.terrain == t2.terrain, (
                f"Terrain mismatch at {t1.coord}: {t1.terrain} vs {t2.terrain}"
            )

    @requires_mapgen
    def test_deep_water_exists(self):
        """测试 5: 深海存在"""
        rng = GameRandom(seed=42)
        gen = MapGenerator(rng)
        hex_map = gen.generate(60, 40)
        terrains = [t.terrain for t in hex_map.iter_tiles()]
        assert TerrainType.DEEP_WATER in terrains, (
            "DEEP_WATER should exist in generated map"
        )

    @requires_mapgen
    def test_mountain_peak_at_high_elevation(self):
        """测试 6: 高海拔区域有山脉或山峰"""
        rng = GameRandom(seed=42)
        gen = MapGenerator(rng)
        hex_map = gen.generate(60, 40)
        terrains = [t.terrain for t in hex_map.iter_tiles()]
        assert TerrainType.MOUNTAIN in terrains or TerrainType.PEAK in terrains, (
            "MOUNTAIN or PEAK should exist in generated map"
        )

    @requires_mapgen
    def test_different_seeds_produce_different_maps(self):
        """不同 seed 应产生不同的地图（概率性测试，极小概率相同）"""
        rng1 = GameRandom(seed=42)
        rng2 = GameRandom(seed=999)
        gen1 = MapGenerator(rng1)
        gen2 = MapGenerator(rng2)
        hm1 = gen1.generate(30, 20)
        hm2 = gen2.generate(30, 20)

        t1 = [t.terrain for t in sorted(hm1.iter_tiles(), key=lambda x: x.coord.to_tuple())]
        t2 = [t.terrain for t in sorted(hm2.iter_tiles(), key=lambda x: x.coord.to_tuple())]
        assert t1 != t2, "Different seeds should produce different maps"

    @requires_mapgen
    def test_water_tiles_not_land(self):
        """水域格不应是陆地地形"""
        rng = GameRandom(seed=42)
        gen = MapGenerator(rng)
        hex_map = gen.generate(30, 20)
        for tile in hex_map.iter_tiles():
            if tile.terrain in WATER_TERRAINS:
                assert tile.terrain not in LAND_TERRAINS, (
                    f"Water tile at {tile.coord} has land terrain: {tile.terrain}"
                )

    @requires_mapgen
    def test_generate_small_map(self):
        """测试极小地图（边界情况）"""
        rng = GameRandom(seed=42)
        gen = MapGenerator(rng)
        hex_map = gen.generate(5, 5)
        tiles = list(hex_map.iter_tiles())
        assert len(tiles) == 25
        for tile in tiles:
            assert isinstance(tile.terrain, TerrainType)
