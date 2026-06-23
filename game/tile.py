"""六角格地块数据模型

定义地形类型枚举和地块 (Tile) 数据模型。
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, Field, ConfigDict

from game.hex_grid import HexCoord


class TerrainType(str, Enum):
    """地形类型枚举"""

    PLAIN = "plain"
    FOREST = "forest"
    HILL = "hill"
    MOUNTAIN = "mountain"
    RIVER = "river"
    DESERT = "desert"


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
    faction: Optional[str] = Field(default=None, description="实际控制势力")

    gold_yield: float = Field(default=0.0, ge=0, description="金钱产出")
    food_yield: float = Field(default=0.0, ge=0, description="粮草产出")
    pop_yield: float = Field(default=0.0, ge=0, description="人口产出")

    development_level: int = Field(default=0, ge=0, description="开发等级")
    influence: Dict[str, float] = Field(default_factory=dict, description="势力影响力")
    morale: int = Field(default=50, ge=0, le=100, description="本地民心")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def is_passable(self) -> bool:
        """判断该地块军队是否可以通行"""
        return self.terrain != TerrainType.MOUNTAIN
