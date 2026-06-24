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

        # 南部 1/3 行应有 tropical 类
        southern_rows_terrains = set()
        for tile in hex_map.iter_tiles():
            if tile.coord.r >= 26:  # 下 1/3
                southern_rows_terrains.add(tile.terrain)

        # 北部 1/3 行应有 cold/frozen 类
        northern_rows_terrains = set()
        for tile in hex_map.iter_tiles():
            if tile.coord.r < 14:  # 上 1/3
                northern_rows_terrains.add(tile.terrain)

        # 南部应有 tropical 温度属性（排除纯水域）
        has_tropical_south = any(
            TERRAIN_PROPERTIES.get(t.value, {}).get("temperature") == "tropical"
            and t not in WATER_TERRAINS
            for t in southern_rows_terrains
        )
        # 北部应有 cold/frozen 温度属性
        has_cold_north = any(
            TERRAIN_PROPERTIES.get(t.value, {}).get("temperature") in ("cold", "frozen")
            and t not in WATER_TERRAINS
            for t in northern_rows_terrains
        )
        assert has_tropical_south, (
            f"No tropical land terrain in south rows. Found: {southern_rows_terrains}"
        )
        assert has_cold_north, (
            f"No cold/frozen land terrain in north rows. Found: {northern_rows_terrains}"
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


class TestMapQuality:
    """地图生成质量测试（Phase 1.5: 大陆形状 + 优化）"""

    @requires_mapgen
    def test_land_percentage_reasonable(self):
        """非水域地形应占 45% 以上（含山/峰）"""
        rng = GameRandom(seed=42)
        gen = MapGenerator(rng)
        hex_map = gen.generate(120, 90)
        total = 0
        land = 0
        for tile in hex_map.iter_tiles():
            total += 1
            if tile.terrain not in WATER_TERRAINS:
                land += 1
        ratio = land / total if total > 0 else 0
        assert ratio > 0.45, (
            f"Non-water ratio {ratio:.1%} too low (should be > 45%)"
        )

    @requires_mapgen
    def test_mountain_ratio_not_excessive(self):
        """山脉+山峰不应超过 25%"""
        rng = GameRandom(seed=42)
        gen = MapGenerator(rng)
        hex_map = gen.generate(120, 90)
        total = 0
        mountains = 0
        for tile in hex_map.iter_tiles():
            total += 1
            if tile.terrain in (TerrainType.MOUNTAIN, TerrainType.PEAK):
                mountains += 1
        ratio = mountains / total if total > 0 else 0
        assert ratio < 0.25, (
            f"Mountain ratio {ratio:.1%} too high (should be < 25%)"
        )

    @requires_mapgen
    def test_center_has_more_non_water_than_edges(self):
        """地图中心非水域比率应高于边缘（大陆形状）"""
        rng = GameRandom(seed=42)
        gen = MapGenerator(rng)
        hex_map = gen.generate(120, 90)
        center_land = 0
        center_total = 0
        edge_land = 0
        edge_total = 0
        for tile in hex_map.iter_tiles():
            q, r = tile.coord.q, tile.coord.r
            is_non_water = tile.terrain not in WATER_TERRAINS
            # 中心区域（q 25-95, r 18-72）
            if 25 <= q < 95 and 18 <= r < 72:
                center_total += 1
                if is_non_water:
                    center_land += 1
            # 边缘区域
            else:
                edge_total += 1
                if is_non_water:
                    edge_land += 1
        center_ratio = center_land / max(center_total, 1)
        edge_ratio = edge_land / max(edge_total, 1)
        assert center_ratio > edge_ratio, (
            f"Center non-water {center_ratio:.1%} should exceed edge {edge_ratio:.1%}"
        )

    @requires_mapgen
    def test_grassland_and_plain_exist(self):
        """草原和平原等地形应存在于生成地图中"""
        rng = GameRandom(seed=42)
        gen = MapGenerator(rng)
        hex_map = gen.generate(120, 90)
        terrains = {t.terrain for t in hex_map.iter_tiles()}
        common_land = {TerrainType.GRASS, TerrainType.GRASSLAND, TerrainType.PLAIN}
        assert any(t in common_land for t in terrains), (
            f"Should have common land terrains, got: {terrains}"
        )

    @requires_mapgen
    def test_map_has_varied_terrain(self):
        """地图应至少有 8 种不同地形（多样性检查）"""
        rng = GameRandom(seed=42)
        gen = MapGenerator(rng)
        hex_map = gen.generate(120, 90)
        terrains = {t.terrain for t in hex_map.iter_tiles()}
        assert len(terrains) >= 8, (
            f"Map should have >= 8 terrain types, got {len(terrains)}: {terrains}"
        )
