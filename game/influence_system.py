"""影响力系统

管理各势力在地块上的文化/政治影响力扩散。
只提供 Buff/Debuff，不策反地块。地块 faction 只随城市占领而改变。

设计原则：
- 每回合从每个城市向其周边扩散影响力
- 基础影响力 = 城市等级 × 10 + 民心 / 10
- 每向外一格衰减 40%
- 己方高影响力 → 产出 +5%，防御 +5%
- 敌方支配影响力（≥己方 2 倍）→ 产出 -10%，防御 -10%，移动力 -1
"""

from __future__ import annotations

from typing import Dict, List

from game.constants import (
    INFLUENCE_DECAY_PER_HEX,
    INFLUENCE_OWN_BUFF_RATE,
    INFLUENCE_ENEMY_DEBUFF_RATE,
    INFLUENCE_ENEMY_DOMINANCE_RATIO,
)
from game.hex_grid import HexCoord, hex_distance
from game.hex_map import HexMap
from game.models import City
from game.tile import Tile


class InfluenceSystem:
    """影响力系统

    只提供 Buff/Debuff，不策反地块。
    """

    # 扩散半径
    SPREAD_RADIUS: int = 5

    def spread_influence(
        self,
        cities: List[City],
        hex_map: HexMap,
    ) -> None:
        """每回合从所有城市扩散影响力

        先清空所有地块的旧影响力，再从每个城市重新计算扩散。

        Args:
            cities: 所有城市列表
            hex_map: 六角格地图
        """
        # 清空旧影响力
        for tile in hex_map.iter_tiles():
            tile.influence.clear()

        # 从每个城市扩散
        for city in cities:
            self._spread_from_city(city, hex_map)

    def _spread_from_city(self, city: City, hex_map: HexMap) -> None:
        """从单个城市扩散影响力

        Args:
            city: 城市对象
            hex_map: 六角格地图
        """
        center = city.position
        radius = self.SPREAD_RADIUS
        base = city.level * 10 + city.morale / 10

        for dq in range(-radius, radius + 1):
            for dr in range(-radius, radius + 1):
                coord = HexCoord(center.q + dq, center.r + dr)
                dist = hex_distance(center, coord)
                if dist > radius:
                    continue
                tile = hex_map.get_tile(coord)
                if tile is None:
                    continue
                # 影响力随距离衰减
                value = base * ((1 - INFLUENCE_DECAY_PER_HEX) ** dist)
                tile.influence[city.faction] = (
                    tile.influence.get(city.faction, 0) + value
                )

    @staticmethod
    def get_tile_modifiers(tile: Tile, controlling_faction: str) -> Dict[str, float]:
        """获取某地块在当前控制势力下的 Buff/Debuff 修正

        规则：
        - 己方影响力最高 → 产出 +5%，防御 +5%
        - 敌方影响力达到己方 2 倍以上 → 产出 -10%，防御 -10%，移动力 -1

        Args:
            tile: 地块对象
            controlling_faction: 当前控制该地块的势力

        Returns:
            包含 production, defense, movement 修正值的字典
        """
        own = tile.influence.get(controlling_faction, 0.0)
        max_enemy = 0.0
        for faction, value in tile.influence.items():
            if faction != controlling_faction and value > max_enemy:
                max_enemy = value

        production_mod = 0.0
        defense_mod = 0.0
        movement_mod = 0.0

        # 己方 buff：己方影响力最高
        if own > 0 and own >= max_enemy:
            production_mod += INFLUENCE_OWN_BUFF_RATE
            defense_mod += INFLUENCE_OWN_BUFF_RATE

        # 敌方 debuff：敌方影响力达到己方 2 倍以上
        if max_enemy > 0 and max_enemy >= own * INFLUENCE_ENEMY_DOMINANCE_RATIO:
            production_mod -= INFLUENCE_ENEMY_DEBUFF_RATE
            defense_mod -= INFLUENCE_ENEMY_DEBUFF_RATE
            movement_mod -= 1.0

        return {
            "production": production_mod,
            "defense": defense_mod,
            "movement": movement_mod,
        }
