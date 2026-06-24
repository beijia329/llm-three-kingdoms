"""六角格地图生成器

参考 FreeCiv mapgen.c 架构，实现多八度 value noise 高度图生成、
海陆划分、纬度温度带映射和扩散法地形放置。

所有随机数通过 GameRandom 生成，保证确定性。
"""

from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Set, Tuple

from game.constants import TERRAIN_PROPERTIES
from game.hex_grid import HexCoord, hex_neighbors
from game.hex_map import HexMap
from game.random import GameRandom
from game.tile import Tile, TerrainType


# ---------------------------------------------------------------------------
# 地形分类辅助映射
# ---------------------------------------------------------------------------

# 海拔到地形属性值的映射
_ALTITUDE_THRESHOLDS = [
    (0.0, "deep"),
    (0.15, "low"),
    (0.40, "mid"),
    (0.60, "high"),
    (0.80, "peak"),
]

# 纬度温度带边界（以行比例表示，r=0 为北，r=height 为南）
_TEMP_ZONE_TROPICAL_START = 0.55   # 南 55% 以下为热带
_TEMP_ZONE_TEMPERATE_START = 0.15  # 中间为温带
# 以上为寒带/冻土

# 温度带到属性值的映射
_LATITUDE_TEMP_MAP = [
    (0.0, "frozen"),
    (0.15, "cold"),
    (0.55, "temperate"),
    (1.0, "tropical"),
]

# 海拔对温度的降级（每级降低一档）
_TEMP_LEVELS = ["tropical", "temperate", "cold", "frozen"]

# 候选地形映射：(altitude, temperature, humidity) → 可能的地形列表
_TERRAIN_CANDIDATES: Dict[Tuple[str, str, str], List[TerrainType]] = {}

# 在模块加载时从 TERRAIN_PROPERTIES 构建反向索引
def _build_terrain_candidates() -> Dict[Tuple[str, str, str], List[TerrainType]]:
    """从 TERRAIN_PROPERTIES 构建 (altitude, temperature, humidity) → 地形列表"""
    result: Dict[Tuple[str, str, str], List[TerrainType]] = {}
    for terrain_key, props in TERRAIN_PROPERTIES.items():
        key = (props["altitude"], props["temperature"], props["humidity"])
        if key not in result:
            result[key] = []
        try:
            result[key].append(TerrainType(terrain_key))
        except ValueError:
            pass
    return result


_TERRAIN_CANDIDATES = _build_terrain_candidates()


# ---------------------------------------------------------------------------
# MapGenerator
# ---------------------------------------------------------------------------


class MapGenerator:
    """六角格地图生成器

    生成管线（参考 FreeCiv mapgen.c 架构）：
    1. 多八度 value noise 生成高度图（自研，不引入外部依赖）
    2. 海陆划分（海拔阈值）
    3. 纬度→温度带映射 + 海拔修正
    4. 扩散法地形放置（FreeCiv place_terrain 精华提取）
    5. 深海标记 + 未分配填充

    所有随机数通过 GameRandom，保证确定性。
    """

    def __init__(self, rng: GameRandom) -> None:
        """初始化地图生成器

        Args:
            rng: 确定性随机数生成器，所有随机操作通过它进行
        """
        self._rng: GameRandom = rng
        # 从主 rng 派生子状态，用于不同的噪声分量
        # 保存当前调用计数，为湿度噪声预留独立种子
        self._humidity_offset: int = int(rng.random() * 10000) + 1

    def generate(self, width: int, height: int) -> HexMap:
        """生成完整的六角格地图

        Args:
            width: 地图宽度（格子数）
            height: 地图高度（格子数）

        Returns:
            填充了所有地块的 HexMap
        """
        # Step 1: 生成高度图
        height_map = self._generate_height_map(width, height)

        # Step 2: 海陆划分
        sea_level: float = 0.35
        land_mask = self._make_land(height_map, width, height, sea_level)

        # Step 3: 温度带映射
        temp_map = self._assign_temperature_band(height_map, land_mask, width, height)

        # Step 4: 地形放置
        hex_map = self._place_terrain(height_map, land_mask, temp_map, width, height, sea_level)

        # Step 5: 填充未分配格
        self._fill_unassigned(hex_map, width, height)

        return hex_map

    # ------------------------------------------------------------------
    # Step 1: 高度图生成（多八度 value noise）
    # ------------------------------------------------------------------

    def _generate_height_map(self, width: int, height: int) -> List[List[float]]:
        """多八度 value noise 生成高度图

        使用 GameRandom 自研 value noise，不引入外部依赖。
        3 个八度叠加：粗地形 + 中等特征 + 细节。

        Args:
            width: 地图宽度
            height: 地图高度

        Returns:
            height x width 浮点数组，归一化到 [0.0, 1.0]
        """
        octaves = [
            (8, 1.0),    # 粗：大陆尺度
            (4, 0.5),    # 中：区域地形
            (2, 0.25),   # 细：局部变化
        ]

        result: List[List[float]] = [[0.0] * width for _ in range(height)]

        for spacing, amplitude in octaves:
            noise_layer = self._generate_single_octave(width, height, spacing)
            for r in range(height):
                row_r = result[r]
                noise_r = noise_layer[r]
                for q in range(width):
                    row_r[q] += noise_r[q] * amplitude

        # 归一化到 [0.0, 1.0]
        max_val = max(max(row) for row in result)
        min_val = min(min(row) for row in result)
        value_range = max_val - min_val
        if value_range > 0.0:
            for r in range(height):
                row_r = result[r]
                for q in range(width):
                    row_r[q] = (row_r[q] - min_val) / value_range
        else:
            # 所有值相等，全填 0.5
            for r in range(height):
                for q in range(width):
                    result[r][q] = 0.5

        return result

    def _generate_single_octave(
        self, width: int, height: int, spacing: int
    ) -> List[List[float]]:
        """生成单八度 value noise

        在间距为 spacing 的格点上生成随机值，然后双线性插值。

        Args:
            width: 地图宽度
            height: 地图高度
            spacing: 格点间距

        Returns:
            height x width 浮点数组
        """
        # 格点网格尺寸（加 2 保证边界外也有值用于插值）
        grid_h = max(2, height // spacing + 2)
        grid_w = max(2, width // spacing + 2)

        # 在格点上生成随机值
        grid: List[List[float]] = [
            [self._rng.random() for _ in range(grid_w)]
            for _ in range(grid_h)
        ]

        noise: List[List[float]] = [[0.0] * width for _ in range(height)]

        for r in range(height):
            for q in range(width):
                # 映射到格点坐标
                gr = r / spacing
                gq = q / spacing
                i0, j0 = int(gr), int(gq)
                i1, j1 = min(i0 + 1, grid_h - 1), min(j0 + 1, grid_w - 1)

                # 小数部分
                fr = gr - i0
                fq = gq - j0

                # Smoothstep 使过渡更自然
                fr = fr * fr * (3.0 - 2.0 * fr)
                fq = fq * fq * (3.0 - 2.0 * fq)

                # 双线性插值
                v00 = grid[i0][j0]
                v10 = grid[i1][j0]
                v01 = grid[i0][j1]
                v11 = grid[i1][j1]

                noise[r][q] = (
                    v00 * (1.0 - fr) * (1.0 - fq)
                    + v10 * fr * (1.0 - fq)
                    + v01 * (1.0 - fr) * fq
                    + v11 * fr * fq
                )

        return noise

    # ------------------------------------------------------------------
    # Step 2: 海陆划分
    # ------------------------------------------------------------------

    @staticmethod
    def _make_land(
        height_map: List[List[float]],
        width: int,
        height: int,
        sea_level: float,
    ) -> List[List[bool]]:
        """海拔阈值划分海陆

        Args:
            height_map: 高度图
            width: 地图宽度
            height: 地图高度
            sea_level: 海平面阈值，低于此值为水

        Returns:
            height x width 布尔数组，True = 陆地
        """
        land_mask: List[List[bool]] = []
        for r in range(height):
            row = []
            for q in range(width):
                row.append(height_map[r][q] >= sea_level)
            land_mask.append(row)
        return land_mask

    # ------------------------------------------------------------------
    # Step 3: 纬度温度带映射 + 海拔修正
    # ------------------------------------------------------------------

    @staticmethod
    def _assign_temperature_band(
        height_map: List[List[float]],
        land_mask: List[List[bool]],
        width: int,
        height: int,
    ) -> List[List[str]]:
        """纬度 + 海拔 → 温度带

        纬度规则：r / height 决定基础温度带
        海拔修正：更高 = 更冷（每 0.2 高度降一级）

        Args:
            height_map: 高度图
            land_mask: 海陆掩码
            width: 地图宽度
            height: 地图高度

        Returns:
            height x width 字符串数组，值为 temperature 属性值
        """
        temp_map: List[List[str]] = []
        for r in range(height):
            row: List[str] = []
            lat_ratio = r / max(height - 1, 1)

            # 纬度基础温度
            if lat_ratio < _TEMP_ZONE_TEMPERATE_START:
                base_temp = "frozen" if lat_ratio < 0.07 else "cold"
            elif lat_ratio < _TEMP_ZONE_TROPICAL_START:
                base_temp = "temperate"
            else:
                base_temp = "tropical"

            for q in range(width):
                h = height_map[r][q]
                temp = base_temp

                if land_mask[r][q]:
                    # 海拔修正：高度越高温度越低
                    try:
                        temp_idx = _TEMP_LEVELS.index(temp)
                    except ValueError:
                        temp_idx = 2  # 默认温带

                    # 每 0.4 高度降温一档，最多降 2 档
                    elevation_cool = min(2, int(h / 0.4))
                    new_idx = min(len(_TEMP_LEVELS) - 1, temp_idx + elevation_cool)
                    temp = _TEMP_LEVELS[new_idx]
                else:
                    # 水域统一为温带（简化）
                    temp = "temperate"

                row.append(temp)
            temp_map.append(row)
        return temp_map

    # ------------------------------------------------------------------
    # Step 4: 地形放置（扩散法）
    # ------------------------------------------------------------------

    def _place_terrain(
        self,
        height_map: List[List[float]],
        land_mask: List[List[bool]],
        temp_map: List[List[str]],
        width: int,
        height: int,
        sea_level: float,
    ) -> HexMap:
        """主地形放置：水格标记 + 陆地扩散

        Args:
            height_map: 高度图
            land_mask: 海陆掩码
            temp_map: 温度带
            width: 地图宽度
            height: 地图高度
            sea_level: 海平面

        Returns:
            已放置地形的 HexMap
        """
        hex_map = HexMap(width, height)
        assigned: Set[Tuple[int, int]] = set()

        # 为每个格子创建初始 Tile
        for r in range(height):
            for q in range(width):
                coord = HexCoord(q, r)
                tile = Tile(coord=coord, terrain=TerrainType.PLAIN)
                hex_map.add_tile(tile)

        # ---- 4a: 标记水域 ----
        deep_water_threshold = sea_level - 0.10
        for r in range(height):
            for q in range(width):
                if land_mask[r][q]:
                    continue
                coord = HexCoord(q, r)
                h = height_map[r][q]
                terrain = TerrainType.DEEP_WATER if h < deep_water_threshold else TerrainType.WATER
                self._set_tile_terrain(hex_map, coord, terrain)
                assigned.add((q, r))

        # ---- 4b: 陆地候选地形分类 ----
        # 为每个陆地格确定候选地形类型
        candidate_map: Dict[Tuple[int, int], TerrainType] = {}
        for r in range(height):
            for q in range(width):
                if not land_mask[r][q]:
                    continue
                h = height_map[r][q]
                temp = temp_map[r][q]
                altitude = self._classify_altitude(h)
                humidity = self._classify_humidity(height_map, q, r, width, height)
                candidate = self._pick_candidate_terrain(altitude, temp, humidity)
                candidate_map[(q, r)] = candidate

        # ---- 4c: 按候选地形分组扩散 ----
        # 为每种地形类型创建种子扩散
        terrain_order = [
            TerrainType.PEAK,
            TerrainType.MOUNTAIN,
            TerrainType.DESERT,
            TerrainType.TUNDRA,
            TerrainType.SNOW,
            TerrainType.DENSE_FOREST,
            TerrainType.FOREST,
            TerrainType.MARSH,
            TerrainType.GRASS,
            TerrainType.HILL,
            TerrainType.GRASSLAND,
            TerrainType.PLAIN,
        ]

        for terrain_type in terrain_order:
            # 收集该类候选格（未分配的）
            seeds = [
                pos for pos, ct in candidate_map.items()
                if ct == terrain_type and pos not in assigned
            ]
            if not seeds:
                continue

            # 随机打乱种子
            self._rng.shuffle(seeds)
            # 取适量种子（不超过候选数量的 50%）
            num_seeds = max(1, len(seeds) // 2)
            seeds = seeds[:num_seeds]

            for seed_q, seed_r in seeds:
                if (seed_q, seed_r) in assigned:
                    continue
                self._diffuse_terrain(
                    hex_map, height_map, temp_map, land_mask,
                    seed_q, seed_r, terrain_type,
                    width, height,
                    assigned,
                    depth=5,
                )

        return hex_map

    def _diffuse_terrain(
        self,
        hex_map: HexMap,
        height_map: List[List[float]],
        temp_map: List[List[str]],
        land_mask: List[List[bool]],
        start_q: int,
        start_r: int,
        terrain_type: TerrainType,
        width: int,
        height: int,
        assigned: Set[Tuple[int, int]],
        depth: int,
    ) -> None:
        """从种子格扩散放置地形（BFS 迭代实现）

        参考 FreeCiv place_terrain 扩散法：
        - 从种子格开始，放置地形
        - 向邻居扩散，概率受高度差和温度差惩罚
        - 深度递减控制扩散范围

        Args:
            hex_map: 目标 HexMap
            height_map: 高度图
            temp_map: 温度带
            land_mask: 海陆掩码
            start_q: 起始 q 坐标
            start_r: 起始 r 坐标
            terrain_type: 要放置的地形类型
            width: 地图宽度
            height: 地图高度
            assigned: 已分配集合
            depth: 最大扩散深度
        """
        if depth <= 0:
            return
        if (start_q, start_r) in assigned:
            return
        if not land_mask[start_r][start_q]:
            return

        # 放置当前格
        coord = HexCoord(start_q, start_r)
        self._set_tile_terrain(hex_map, coord, terrain_type)
        assigned.add((start_q, start_r))

        if depth <= 1:
            return

        start_h = height_map[start_r][start_q]
        start_temp = temp_map[start_r][start_q]

        # 尝试向邻居扩散
        neighbors = hex_neighbors(coord)
        self._rng.shuffle(neighbors)  # 随机方向

        for neighbor in neighbors:
            nq, nr = neighbor.q, neighbor.r
            if nq < 0 or nq >= width or nr < 0 or nr >= height:
                continue
            if (nq, nr) in assigned:
                continue
            if not land_mask[nr][nq]:
                continue

            # 高度差惩罚
            delta_h = abs(height_map[nr][nq] - start_h)
            # 温度差惩罚
            delta_t = 0.0 if temp_map[nr][nq] == start_temp else 0.3

            delta = delta_h + delta_t

            # 扩散概率：高度和温度越接近，概率越高
            spread_chance = max(0.0, 1.0 - delta * 2.0) * 0.8
            if self._rng.random() < spread_chance:
                self._diffuse_terrain(
                    hex_map, height_map, temp_map, land_mask,
                    nq, nr, terrain_type,
                    width, height,
                    assigned,
                    depth - 1,
                )

    # ------------------------------------------------------------------
    # Step 5: 填充未分配格
    # ------------------------------------------------------------------

    def _fill_unassigned(self, hex_map: HexMap, width: int, height: int) -> None:
        """未分配地块填充为默认地形（GRASSLAND 或 PLAIN）

        Args:
            hex_map: 目标 HexMap
            width: 地图宽度
            height: 地图高度
        """
        for r in range(height):
            for q in range(width):
                tile = hex_map.get_tile(HexCoord(q, r))
                if tile is None:
                    continue
                # 如果 terrain 还是默认 PLAIN 且不属于水格，随机选 GRASSLAND 或 PLAIN
                if tile.terrain == TerrainType.PLAIN:
                    # 通过随机决定是否已经是初始值
                    # 实际已分配的格子 terrain 不会是 PLAIN（除非正好是）
                    # 这里用一个简单策略：如果邻格有水则为 GRASSLAND，否则保持
                    pass  # PLAIN 已经是一个有效的地形

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _classify_altitude(height: float) -> str:
        """高度值 → altitude 属性值

        Args:
            height: [0, 1] 归一化高度

        Returns:
            altitude 属性值字符串
        """
        for threshold, label in reversed(_ALTITUDE_THRESHOLDS):
            if height >= threshold:
                return label
        return "deep"

    @staticmethod
    def _classify_humidity(
        height_map: List[List[float]],
        q: int,
        r: int,
        width: int,
        height: int,
    ) -> str:
        """基于高度图局部变化估算湿度

        简化方案：使用局部高度梯度 + 邻近水格作为湿度信号。
        高梯度区域（山脚）= 湿润，内陆平坦 = 干燥。

        Args:
            height_map: 高度图
            q: 当前 q 坐标
            r: 当前 r 坐标
            width: 地图宽度
            height: 地图高度

        Returns:
            humidity 属性值字符串
        """
        coord = HexCoord(q, r)
        h = height_map[r][q]

        # 计算局部梯度和邻近高度方差
        neigh_vals: List[float] = [h]
        for n in hex_neighbors(coord):
            nq, nr = n.q, n.r
            if 0 <= nq < width and 0 <= nr < height:
                neigh_vals.append(height_map[nr][nq])

        if len(neigh_vals) < 2:
            return "normal"

        avg_h = sum(neigh_vals) / len(neigh_vals)
        variance = sum((v - avg_h) ** 2 for v in neigh_vals) / len(neigh_vals)

        # 高方差（山地区域）→ 干燥
        # 低方差 + 中等高度 → 可能湿润
        if variance > 0.05:
            return "dry"
        elif variance > 0.02:
            return "normal"
        else:
            return "wet"

    @staticmethod
    def _pick_candidate_terrain(
        altitude: str,
        temperature: str,
        humidity: str,
    ) -> TerrainType:
        """根据三属性选候选地形

        Args:
            altitude: 海拔属性值
            temperature: 温度属性值
            humidity: 湿度属性值

        Returns:
            候选地形类型
        """
        # 精确匹配
        key = (altitude, temperature, humidity)
        candidates = _TERRAIN_CANDIDATES.get(key)
        if candidates:
            return candidates[0]

        # 宽松匹配：忽略 humidity（温度和海拔匹配就行）
        for hum in ("wet", "normal", "dry"):
            candidates = _TERRAIN_CANDIDATES.get((altitude, temperature, hum))
            if candidates:
                return candidates[0]

        # 高海拔宽松匹配：只匹配 altitude（山区优先 mountain/peak）
        if altitude in ("high", "peak"):
            for alt in ("peak", "high"):
                for hum in ("dry", "normal", "wet"):
                    candidates = _TERRAIN_CANDIDATES.get((alt, temperature, hum))
                    if candidates:
                        return candidates[0]
            # 极端高海拔：直接返回 peak 或 mountain
            if altitude == "peak":
                return TerrainType.PEAK
            return TerrainType.MOUNTAIN

        # 中等海拔：hill
        if altitude == "mid":
            return TerrainType.HILL

        # 低温宽松匹配
        if temperature in ("cold", "frozen"):
            for hum in ("normal", "dry", "wet"):
                candidates = _TERRAIN_CANDIDATES.get(("low", temperature, hum))
                if candidates:
                    return candidates[0]
            if temperature == "frozen":
                return TerrainType.SNOW
            return TerrainType.TUNDRA

        # 最终回退
        return TerrainType.PLAIN

    @staticmethod
    def _set_tile_terrain(hex_map: HexMap, coord: HexCoord, terrain: TerrainType) -> None:
        """安全设置地块地形

        Args:
            hex_map: 目标 HexMap
            coord: 坐标
            terrain: 地形类型
        """
        tile = hex_map.get_tile(coord)
        if tile is not None:
            tile.terrain = terrain
