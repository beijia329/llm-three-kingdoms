"""资源系统

管理游戏中的资源产出与消耗：
- 金钱产出（基础 + 人口系数 + 民心影响）
- 粮草产出（基础 + 人口系数 + 民心影响）
- 人口增长（基础增长率 + 民心影响）
- 守军粮草消耗
- 民心变化
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from game.constants import (
    CITY_LEVELS,
    GOLD_PER_POPULATION,
    FOOD_PER_POPULATION,
    MORALE_GOLD_PENALTY,
    MORALE_FOOD_PENALTY,
    MORALE_BONUS_THRESHOLD,
    MORALE_BONUS_RATE,
    MIN_MORALE_FOR_PRODUCTION,
    POPULATION_GROWTH_BASE,
    POPULATION_GROWTH_MORALE_FACTOR,
    MAX_POPULATION_GROWTH_RATE,
    GARRISON_FOOD_COST_PER_SOLDIER,
    SEASON_FOOD_BONUS,
)
from game.models import City
from game.tile import Tile


class ResourceSystem:
    """资源系统

    负责计算每个城市每回合的资源产出、人口增长和消耗。
    所有计算基于城市当前状态和全局常量。
    """

    # ============================================================
    # 金钱产出
    # ============================================================

    def calculate_gold_production(
        self, city: City, tiles: Optional[List[Tile]] = None
    ) -> int:
        """计算城市每回合金钱产出

        公式：
            基础产出 = CITY_LEVELS[level].base_gold
            人口产出 = population × GOLD_PER_POPULATION
            地块产出 = sum(tile.gold_yield)
            民心倍率 = 根据民心计算（惩罚或加成）
            总产出 = (基础产出 + 人口产出 + 地块产出) × 民心倍率

        Args:
            city: 城市对象
            tiles: 城市控制的地块列表（可选）

        Returns:
            本回合金钱产出（向下取整）
        """
        if city.morale < MIN_MORALE_FOR_PRODUCTION:
            return 0

        level_config = CITY_LEVELS[city.level]
        base = level_config["base_gold"]
        population_output = city.population * GOLD_PER_POPULATION
        tile_gold = sum(t.gold_yield for t in tiles) if tiles else 0.0
        total_before_morale = base + population_output + tile_gold + city.economic_bonus

        multiplier = self._get_morale_multiplier(
            city.morale, MORALE_GOLD_PENALTY
        )

        return int(total_before_morale * multiplier)

    # ============================================================
    # 粮草产出
    # ============================================================

    def calculate_food_production(
        self,
        city: City,
        tiles: Optional[List[Tile]] = None,
        season: Optional[str] = None,
    ) -> int:
        """计算城市每回合粮草产出

        公式：
            基础产出 = CITY_LEVELS[level].base_food
            人口产出 = population × FOOD_PER_POPULATION
            地块产出 = sum(tile.food_yield)
            民心倍率 = 根据民心计算
            季节倍率 = SEASON_FOOD_BONUS[season]
            总产出 = (基础产出 + 人口产出 + 地块产出) × 民心倍率 × 季节倍率

        Args:
            city: 城市对象
            tiles: 城市控制的地块列表（可选）
            season: 当前季节（默认 spring）

        Returns:
            本回合粮草产出（向下取整）
        """
        if city.morale < MIN_MORALE_FOR_PRODUCTION:
            return 0

        level_config = CITY_LEVELS[city.level]
        base = level_config["base_food"]
        population_output = city.population * FOOD_PER_POPULATION
        tile_food = sum(t.food_yield for t in tiles) if tiles else 0.0
        total_before_morale = base + population_output + tile_food

        multiplier = self._get_morale_multiplier(
            city.morale, MORALE_FOOD_PENALTY
        )
        season_factor = SEASON_FOOD_BONUS.get(season, 1.0) if season else 1.0

        return int(total_before_morale * multiplier * season_factor)

    # ============================================================
    # 民心倍率计算
    # ============================================================

    @staticmethod
    def _get_morale_multiplier(morale: int, penalty_rate: float) -> float:
        """根据民心计算产出倍率

        规则：
        - 民心 >= MORALE_BONUS_THRESHOLD (80)：每多1点+1%产出
        - 民心 < 50：每少1点-0.5%产出（由 penalty_rate 控制）
        - 50-80之间：无修正

        Args:
            morale: 当前民心值
            penalty_rate: 每点低于50的惩罚率

        Returns:
            产出倍率（>= 0）
        """
        if morale >= MORALE_BONUS_THRESHOLD:
            # 高于80民心，每点+1%产出
            bonus = (morale - MORALE_BONUS_THRESHOLD) * MORALE_BONUS_RATE
            return 1.0 + bonus
        elif morale < 50:
            # 低于50民心，每点-0.5%产出
            penalty = (50 - morale) * penalty_rate
            return max(0.0, 1.0 - penalty)
        else:
            # 50-80之间，无修正
            return 1.0

    # ============================================================
    # 人口增长
    # ============================================================

    def calculate_population_growth(
        self, city: City, tiles: Optional[List[Tile]] = None
    ) -> int:
        """计算城市本回合人口增长

        公式：
            基础增长率 = POPULATION_GROWTH_BASE
            民心加成 = morale × POPULATION_GROWTH_MORALE_FACTOR
            地块加成 = sum(tile.pop_yield)
            实际增长率 = 基础增长率 + 民心加成（受上限限制）
            增长人口 = population × 实际增长率 + 地块加成

        如果民心为0，人口减少（负增长）。

        Args:
            city: 城市对象
            tiles: 城市控制的地块列表（可选）

        Returns:
            本回合人口变化（正数增长，负数减少，0为无变化）
        """
        if city.population <= 0:
            return 0

        level_config = CITY_LEVELS[city.level]
        max_population = level_config["max_population"]

        if city.population >= max_population:
            return 0

        # 计算增长率
        morale_factor = city.morale * POPULATION_GROWTH_MORALE_FACTOR

        if city.morale <= 0:
            # 民心为0时人口减少
            growth_rate = -POPULATION_GROWTH_BASE
        else:
            growth_rate = POPULATION_GROWTH_BASE + morale_factor
            growth_rate = min(growth_rate, MAX_POPULATION_GROWTH_RATE)

        tile_pop = sum(t.pop_yield for t in tiles) if tiles else 0.0
        growth = int(city.population * growth_rate) + int(tile_pop)

        # 不超过最大人口
        if growth > 0:
            growth = min(growth, max_population - city.population)
        elif growth < 0:
            # 人口减少不超过当前人口的10%
            growth = max(growth, -int(city.population * 0.1))

        return growth

    # ============================================================
    # 粮草消耗
    # ============================================================

    def calculate_food_consumption(self, city: City) -> int:
        """计算城市每回合守军粮草消耗

        Args:
            city: 城市对象

        Returns:
            本回合粮草消耗
        """
        return int(city.garrison * GARRISON_FOOD_COST_PER_SOLDIER)

    # ============================================================
    # 城市资源更新（综合）
    # ============================================================

    def update_city_resources(self, city: City) -> Dict[str, Any]:
        """计算城市本回合所有资源变化（向后兼容，不使用地块）

        一次性计算金钱产出、粮草产出/消耗、人口增长。

        Args:
            city: 城市对象

        Returns:
            包含以下字段的字典：
            - gold_change: 金钱变化
            - food_change: 粮草变化（产出 - 消耗）
            - population_change: 人口变化
        """
        return self.calculate_resources(city)

    def calculate_resources(
        self,
        city: City,
        tiles: Optional[List[Tile]] = None,
        season: str = "spring",
    ) -> Dict[str, Any]:
        """计算城市本回合所有资源变化（含地块和季节）

        Args:
            city: 城市对象
            tiles: 城市控制的地块列表
            season: 当前季节

        Returns:
            包含 gold_change, food_change, population_change 的字典
        """
        gold_change = self.calculate_gold_production(city, tiles=tiles)
        food_production = self.calculate_food_production(
            city, tiles=tiles, season=season
        )
        food_consumption = self.calculate_food_consumption(city)
        population_change = self.calculate_population_growth(city, tiles=tiles)

        return {
            "gold_change": gold_change,
            "food_change": food_production - food_consumption,
            "population_change": population_change,
        }
