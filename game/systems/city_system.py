"""城市系统

管理城市的发展和运营：
- 发展城市（经济、军事、文化）
- 征兵
- 城市回合更新（资源产出、人口增长）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

from game.constants import (
    CITY_LEVELS,
    CITY_TERRITORY_RADIUS,
    RECRUIT_COST_GOLD,
    RECRUIT_COST_FOOD,
)
from game.hex_grid import HexCoord, hex_distance
from game.hex_map import HexMap
from game.models import City, General
from game.systems.resource_system import ResourceSystem


# ============================================================
# 结果数据结构
# ============================================================


@dataclass
class DevelopResult:
    """城市发展结果"""

    success: bool = False
    develop_type: str = ""
    gold_cost: int = 0
    description: str = ""
    effect_value: int = 0  # 具体效果值


@dataclass
class RecruitResult:
    """征兵结果"""

    success: bool = False
    troops_recruited: int = 0
    gold_cost: int = 0
    food_cost: int = 0
    description: str = ""


@dataclass
class CityUpdateResult:
    """城市更新结果"""

    gold_change: int = 0
    food_change: int = 0
    population_change: int = 0
    morale_change: int = 0


# ============================================================
# 城市发展成本配置
# ============================================================

DEVELOP_COST_BASE: int = 200
"""发展基础成本"""

DEVELOP_COST_LEVEL_MULTIPLIER: int = 100
"""每级城市额外成本"""

ECONOMY_GOLD_BONUS: int = 20
"""每次发展经济额外增加的基础金钱产出"""

MILITARY_WALL_REPAIR: int = 200
"""每次发展军事修复的城墙耐久（不抬高上限）"""

MILITARY_TRAIN_GARRISON: int = 100
"""城墙已满时，"发展军事"改为训练守军的人数

为什么需要：把城墙上限的无限增长去掉后，若城墙已是满值，"发展军事"就变成
零收益的浪费钱操作，AI 会持续踩坑。改为训练守军，使该操作在任何时候都有收益。
"""

CULTURE_MORALE_BONUS: int = 5
"""每次发展文化提升的民心"""

GARRISON_CAP_PER_LEVEL: int = 1000
"""每级城市守军上限"""


def add_garrison(city: "City", n: int) -> int:
    """把 n 名兵力并入城市守军，硬截断在等级上限内。返回实际并入数。

    守军写入的**统一入口**：征兵 / 发展军事(城墙满转训练) / 援军到达 /
    解散残军入城 / 占城并兵力，全部经此，避免任何一条路径把守军堆过上限
    （实测：援军到达路径可把洛阳守军从 4000 堆到 9000）。
    """
    cap = city.level * GARRISON_CAP_PER_LEVEL
    space = max(0, cap - city.garrison)
    added = max(0, min(n, space))
    city.garrison += added
    return added


class CitySystem:
    """城市系统

    管理城市的各项操作：发展、征兵、更新。
    内部使用 ResourceSystem 计算资源产出。
    """

    def __init__(self) -> None:
        self._resource_system: ResourceSystem = ResourceSystem()

    # ============================================================
    # 城市发展
    # ============================================================

    def develop(self, city: City, develop_type: str) -> DevelopResult:
        """发展城市

        三种发展类型：
        - economy: 提升经济产出（+基础金钱产出）
        - military: 强化城防（+城墙耐久）
        - culture: 提升民心（+民心值）

        Args:
            city: 目标城市
            develop_type: 发展类型 (economy/military/culture)

        Returns:
            发展结果
        """
        if develop_type not in ("economy", "military", "culture"):
            return DevelopResult(
                success=False,
                develop_type=develop_type,
                description=f"无效的发展类型: {develop_type}",
            )

        gold_cost = self._calculate_develop_cost(city)

        if city.gold < gold_cost:
            return DevelopResult(
                success=False,
                develop_type=develop_type,
                gold_cost=gold_cost,
                description=f"金钱不足: 需要{gold_cost}, 当前{city.gold}",
            )

        city.gold -= gold_cost
        effect_value = 0

        if develop_type == "economy":
            # 经济发展：永久提升城市金钱产出
            city.economic_bonus += ECONOMY_GOLD_BONUS
            effect_value = city.economic_bonus

        elif develop_type == "military":
            # 修复城墙耐久。🔴 不再抬高 wall_max_hp 上限。
            #
            # 原实现：city.wall_max_hp += 200（每次），即"越修越硬、永不回落"。
            # 实测后果（exp9 / design-strategist 复核）：许昌 40 回合 wall_max_hp
            # 3200 → 7400（+131%），而单次攻城对该城墙的伤害量级只有数百，
            # 反复发展军事的城市会变成理论上不可攻破的堡垒，
            # 直接表现为"围城消耗战打不下来"。
            # 城墙上限现由 data/cities.json 的 wall_max_hp 唯一决定（随城市等级）。
            old_wall = city.wall_hp
            city.wall_hp = min(city.wall_hp + MILITARY_WALL_REPAIR, city.wall_max_hp)
            repaired = city.wall_hp - old_wall

            if repaired > 0:
                effect_value = repaired
            else:
                # 城墙已满 → 转为训练守军，保证该操作始终有收益。
                # 经统一入口 add_garrison 截断在等级上限内。
                before = city.garrison
                add_garrison(city, MILITARY_TRAIN_GARRISON)
                effect_value = city.garrison - before

        elif develop_type == "culture":
            # 提升民心
            morale_increase = CULTURE_MORALE_BONUS
            city.morale = min(city.morale + morale_increase, 100)
            effect_value = morale_increase

        type_names = {
            "economy": "经济",
            "military": "军事",
            "culture": "文化",
        }

        return DevelopResult(
            success=True,
            develop_type=develop_type,
            gold_cost=gold_cost,
            effect_value=effect_value,
            description=(
                f"{type_names.get(develop_type, develop_type)}发展成功，"
                f"消耗{gold_cost}金钱"
            ),
        )

    def _calculate_develop_cost(self, city: City) -> int:
        """计算城市发展成本

        Args:
            city: 目标城市

        Returns:
            发展所需金钱
        """
        return DEVELOP_COST_BASE + city.level * DEVELOP_COST_LEVEL_MULTIPLIER

    # ============================================================
    # 征兵
    # ============================================================

    def recruit(self, city: City, troops: int) -> RecruitResult:
        """征兵

        消耗金钱和粮草，增加城市守军。

        Args:
            city: 目标城市
            troops: 征兵数量

        Returns:
            征兵结果
        """
        if troops <= 0:
            return RecruitResult(
                success=False,
                description="征兵数量必须大于0",
            )

        max_garrison = self._get_max_garrison(city)
        available_space = max_garrison - city.garrison

        if available_space <= 0:
            return RecruitResult(
                success=False,
                description=f"守军已达上限({max_garrison})",
            )

        # 实际可征兵数（受上限和资源限制）
        actual_troops = min(troops, available_space)

        # 计算所需资源
        gold_needed = actual_troops * RECRUIT_COST_GOLD
        food_needed = actual_troops * RECRUIT_COST_FOOD

        # 根据金钱上限调整
        max_by_gold = city.gold // RECRUIT_COST_GOLD
        actual_troops = min(actual_troops, max_by_gold)

        # 根据粮草上限调整
        max_by_food = city.food // RECRUIT_COST_FOOD
        actual_troops = min(actual_troops, max_by_food)

        if actual_troops <= 0:
            return RecruitResult(
                success=False,
                description="资源不足，无法征兵",
            )

        # 重新计算最终消耗
        gold_needed = actual_troops * RECRUIT_COST_GOLD
        food_needed = actual_troops * RECRUIT_COST_FOOD

        # 执行征兵
        city.gold -= gold_needed
        city.food -= food_needed
        add_garrison(city, actual_troops)

        return RecruitResult(
            success=True,
            troops_recruited=actual_troops,
            gold_cost=gold_needed,
            food_cost=food_needed,
            description=f"成功征兵{actual_troops}人，消耗{gold_needed}金钱、{food_needed}粮草",
        )

    def _get_max_garrison(self, city: City) -> int:
        """获取城市最大守军容量

        Args:
            city: 城市对象

        Returns:
            最大守军数量
        """
        return city.level * GARRISON_CAP_PER_LEVEL

    # ============================================================
    # 城市更新（每回合调用）
    # ============================================================

    def update_city(
        self, city: City, generals: Optional[Dict[str, General]] = None
    ) -> CityUpdateResult:
        """更新城市状态（每回合调用）

        处理：
        1. 资源产出（金钱、粮草）
        2. 人口增长
        3. 守军粮草消耗

        🔴 民心自然变化**不在本方法内**：已迁至引擎的 AFTER_MOVEMENT 相位钩子
        （`game/engine.py::_hook_city_morale`，注册名 `city_morale`），见下方注释。

        Args:
            city: 要更新的城市
            generals: 所有将领字典（ID -> General）

        Returns:
            更新结果
        """
        # 使用 ResourceSystem 计算资源变化
        resource_result = self._resource_system.update_city_resources(city, generals=generals)

        # 应用资源变化
        city.gold += resource_result["gold_change"]
        city.food += resource_result["food_change"]
        city.population += resource_result["population_change"]

        # 民心自然变化**已迁出本方法**，改由引擎 AFTER_MOVEMENT 相位钩子统一施加：
        #   game/engine.py::_hook_city_morale（name="city_morale"）
        #
        # 🔴 为什么必须迁：本方法只在 `process_turn` 的「无六角地图」else 分支被调用
        #   （engine.py 资源产出段），而**生产环境恒有 hex_map** → 恒走 if 分支 →
        #   放在这里的 `_calculate_morale_change` 从未执行（探针实测：
        #   tests/balance/exp18_siege_morale_reachability.py → 5 局 × 48 回合调用数 = 0），
        #   导致民心除「文化发展」外只降不升、无自校正。
        #   迁到相位钩子后无论有无地图一律生效；同时从本方法移除可**避免降级路径下双次应用**。

        # 确保资源不为负
        city.gold = max(0, city.gold)
        city.food = max(0, city.food)
        city.population = max(0, city.population)

        return CityUpdateResult(
            gold_change=resource_result["gold_change"],
            food_change=resource_result["food_change"],
            population_change=resource_result["population_change"],
            # 恒为 0：民心自然变化已迁至相位钩子（见上）。保留字段以兼容既有调用方。
            morale_change=0,
        )

    # ============================================================
    # 城市控制区（Hex Grid）
    # ============================================================

    @staticmethod
    def get_city_territory(city: City, hex_map: HexMap) -> set[HexCoord]:
        """获取城市控制区坐标集合

        根据城市等级和位置计算在六角格地图上的控制范围。

        Args:
            city: 城市对象
            hex_map: 六角格地图

        Returns:
            控制区内的 HexCoord 集合
        """
        radius = CITY_TERRITORY_RADIUS.get(city.level, 1)
        center = city.position
        territory: set[HexCoord] = set()
        for dq in range(-radius, radius + 1):
            for dr in range(-radius, radius + 1):
                coord = HexCoord(center.q + dq, center.r + dr)
                if hex_distance(center, coord) <= radius:
                    if hex_map.get_tile(coord) is not None:
                        territory.add(coord)
        return territory

    @staticmethod
    def _calculate_morale_change(city: City) -> int:
        """计算民心自然变化

        规则：
        - 如果被围困，每回合-3
        - 如果粮草为0，每回合-5
        - 如果粮草充足且有盈余，每回合+1（上限100）
        - 高于70民心每回合微降，低于30每回合微升（向50回归）

        Args:
            city: 城市对象

        Returns:
            本回合民心变化量
        """
        change = 0

        # 被围困惩罚
        if city.is_besieged:
            change -= 3

        # 粮草不足惩罚
        if city.food <= 0:
            change -= 5
        elif city.food > city.garrison * 2:
            # 粮草充足时民心微升
            change += 1

        # 向中间值回归
        if city.morale > 70:
            change -= 1
        elif city.morale < 30 and city.morale > 0:
            change += 1

        return change
