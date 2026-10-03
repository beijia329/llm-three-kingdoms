"""六角格地块数据模型

定义地形类型枚举和地块 (Tile) 数据模型。
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, Field, ConfigDict

from game.hex_grid import HexCoord


class TerrainType(str, Enum):
    """地形类型枚举（15 种，Phase 1 地图生成器）"""

    GRASS = "grass"
    GRASSLAND = "grassland"
    PLAIN = "plain"
    FOREST = "forest"
    DENSE_FOREST = "dense_forest"
    HILL = "hill"
    MOUNTAIN = "mountain"
    PEAK = "peak"
    DESERT = "desert"
    MARSH = "marsh"
    TUNDRA = "tundra"
    SNOW = "snow"
    WATER = "water"
    DEEP_WATER = "deep_water"
    RIVER = "river"


class Tile(BaseModel):
    """六角格地块

    代表地图上的一个六角格，包含地形、产出、控制权等信息。

    Attributes:
        coord: 六角格坐标
        terrain: 地形类型
        elevation: 海拔高度
        owner_city_id: 归属城市 ID
        faction: 实际控制势力
        gold_yield: 金钱产出
        food_yield: 粮草产出
        pop_yield: 人口产出
        development_level: 开发等级
        influence: 各势力影响力值 {faction: value}
        morale: 本地民心 (0-100)
    """

    coord: HexCoord = Field(description="六角格坐标")
    terrain: TerrainType = Field(description="地形类型")
    elevation: int = Field(default=0, ge=0, description="海拔")

    owner_city_id: Optional[str] = Field(default=None, description="归属城市ID")
    province_id: Optional[str] = Field(default=None, description="所属州ID")
    faction: Optional[str] = Field(default=None, description="实际控制势力")

    gold_yield: float = Field(default=0.0, ge=0, description="金钱产出")
    food_yield: float = Field(default=0.0, ge=0, description="粮草产出")
    pop_yield: float = Field(default=0.0, ge=0, description="人口产出")

    development_level: int = Field(default=0, ge=0, description="开发等级")
    influence: Dict[str, float] = Field(default_factory=dict, description="势力影响力")
    morale: int = Field(default=50, ge=0, le=100, description="本地民心")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def is_passable(self) -> bool:
        """判断该地块军队是否可以通行

        不可通行的地形：
        - MOUNTAIN：山脉（保留为天然屏障，维持战略纵深）
        - WATER / DEEP_WATER：水域（陆地行军视角）

        RIVER 可通行但减速（移动成本在常量中定义）。

        🔴 PEAK 于2026-10-03 改为可通行（v3.1 平衡修复）。
        原把 PEAK 与 MOUNTAIN/WATER 一同列为不可通行，实测导致：
          - 31 城465 城对中 114 对（24.5%）**永久不可达**
          - 刘备（白帝）与刘焉（成都）被完全孤立，接触不到任何中立城
          - 北海、临淄两座中立城任何势力都到不了
          → 直接表现为"9 座中立城无人碰、大局打不起来"。

        实测对照（tests/balance/exp4_terrain.py，8 局/组）：
          base（PEAK 不可通行） → 不可达城对 114 (24.5%)
          nopeak（仅 PEAK 可通行）→ 不可达城对   0 (0.0%)✅ 且山脉屏障仍在
        因此 PEAK 单独放开、山脉继续挡住，是修复连通性的最小改动。
        """
        return self.terrain not in (
            TerrainType.MOUNTAIN,
            TerrainType.WATER,
            TerrainType.DEEP_WATER,
        )
