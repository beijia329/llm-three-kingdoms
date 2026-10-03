"""战斗调度器

负责检测即将发生的战斗、配对攻击方和防守方、创建战斗上下文。
支持多支部队合并为同一场战斗。

核心逻辑：
1. 遍历所有 BESIEGING 状态的军队
2. 按目标城市分组
3. 检测城市归属判断是否触发攻城战
4. 合并多支部队，计算总兵力/平均士气/平均统帅
5. 创建 BattleContext

参考设计文档：docs/design/battle-system.md 第三章
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from game.element import counter_factor, element_of
from game.models import (
    Army,
    ArmyStatus,
    BattleContext,
    BattlePhase,
    BattleType,
    City,
    General,
)
from game.random import GameRandom
from game.systems.general_system import loyalty_combat_factor
from game.systems.map_system import MapSystem

logger = logging.getLogger(__name__)


class BattleScheduler:
    """战斗调度器

    定期检测游戏状态，发现并创建战斗上下文。
    使用确定性随机数生成器以保证结果可复现。
    """

    def __init__(self, rng: GameRandom) -> None:
        """初始化战斗调度器

        Args:
            rng: 确定性随机数生成器
        """
        self._rng = rng
        self._next_battle_id: int = 0

    # ============================================================
    # 战斗检测
    # ============================================================

    def detect_battles(
        self,
        armies: Dict[str, Army],
        cities: Dict[str, City],
        map_system: MapSystem,
        generals: Optional[Dict[str, General]] = None,
    ) -> List[BattleContext]:
        """检测所有即将发生的战斗

        遍历所有围城状态的军队，按目标城市分组。
        每组创建一个战斗上下文。

        Args:
            armies: 所有军队（ID -> Army）
            cities: 所有城市（ID -> City）
            map_system: 地图系统
            generals: 所有将领（ID -> General），可选

        Returns:
            检测到的战斗上下文列表
        """
        if generals is None:
            generals = {}

        # 1. 收集所有围城军队
        besieging_armies = self._collect_besieging_armies(armies)

        # 2. 按目标城市分组
        city_groups = self._group_by_target(besieging_armies)

        # 3. 为每组创建战斗上下文
        battles: List[BattleContext] = []
        for city_id, army_list in city_groups.items():
            target_city = cities.get(city_id)
            if target_city is None:
                logger.warning("围城目标城市 %s 不存在，跳过", city_id)
                continue

            battle = self._create_battle_context(
                armies=army_list,
                target_city=target_city,
                all_armies=armies,
                all_cities=cities,
                all_generals=generals,
            )
            if battle is not None:
                battles.append(battle)

        return battles

    # ============================================================
    # 内部方法
    # ============================================================

    @staticmethod
    def _collect_besieging_armies(
        armies: Dict[str, Army],
    ) -> List[Army]:
        """收集所有围城状态的军队

        Args:
            armies: 所有军队

        Returns:
            围城状态的军队列表
        """
        return [
            army for army in armies.values()
            if army.status == ArmyStatus.BESIEGING and army.soldiers > 0
        ]

    @staticmethod
    def _group_by_target(
        armies: List[Army],
    ) -> Dict[str, List[Army]]:
        """按目标城市分组

        Args:
            armies: 军队列表

        Returns:
            目标城市ID -> 军队列表的映射
        """
        groups: Dict[str, List[Army]] = defaultdict(list)
        for army in armies:
            groups[army.to_city].append(army)
        return groups

    def _create_battle_context(
        self,
        armies: List[Army],
        target_city: City,
        all_armies: Dict[str, Army],
        all_cities: Dict[str, City],
        all_generals: Dict[str, General],
    ) -> Optional[BattleContext]:
        """为一组军队创建战斗上下文

        Args:
            armies: 攻击方军队列表
            target_city: 目标城市
            all_armies: 所有军队（用于查找防守方援军）
            all_cities: 所有城市
            all_generals: 所有将领

        Returns:
            战斗上下文，如果无有效战斗返回 None
        """
        if not armies:
            return None

        # 确定攻击方势力（以第一支部队为准）
        attacker_faction = armies[0].faction

        # 防守方势力
        defender_faction = target_city.faction

        # 友方城市不触发战斗：转换为驻防增援
        if attacker_faction == defender_faction:
            target_city.garrison += sum(a.soldiers for a in armies)
            for a in armies:
                a.status = ArmyStatus.GARRISONED
                a.soldiers = 0
                if a.general_id in all_generals:
                    all_generals[a.general_id].location = target_city.id
            return None

        # 计算攻击方统计数据
        (
            attacker_total,
            attacker_avg_morale,
            attacker_avg_command,
            attacker_avg_bravery,
        ) = self._calculate_force_stats(armies, all_generals)

        # 收集防守方军队（在目标城市的驻军和围城防守方）
        defender_armies = self._collect_defender_armies(
            target_city, all_armies, attacker_faction
        )

        # 计算防守方统计数据
        defender_total = target_city.garrison
        defender_avg_morale = 80.0  # 守军默认士气
        defender_avg_command = 50.0  # 默认统帅
        defender_avg_bravery = 50.0  # 默认勇武

        # 驻城将领属性
        stationed_generals = [
            all_generals[g_id] for g_id in target_city.generals
            if g_id in all_generals
        ]
        if stationed_generals:
            defender_avg_command = sum(g.command for g in stationed_generals) / len(stationed_generals)
            defender_avg_bravery = sum(g.bravery for g in stationed_generals) / len(stationed_generals)

        # 加上防守方军队的兵力
        if defender_armies:
            def_stats = self._calculate_force_stats(defender_armies, all_generals)
            defender_total += def_stats[0]
            # 加权平均士气、统帅、勇武
            if defender_total > 0:
                defender_avg_morale = (
                    target_city.garrison * defender_avg_morale
                    + def_stats[1] * def_stats[0]
                ) / defender_total
                defender_avg_command = (
                    target_city.garrison * defender_avg_command
                    + def_stats[2] * def_stats[0]
                ) / defender_total
                defender_avg_bravery = (
                    target_city.garrison * defender_avg_bravery
                    + def_stats[3] * def_stats[0]
                ) / defender_total

        # 生成战斗ID
        self._next_battle_id += 1
        battle_id = f"battle_{self._next_battle_id}_{attacker_faction}_vs_{defender_faction}"

        # v4.0：把「忠诚度」与「五行相克」接入战斗
        # 主将取统帅最高者（更能代表指挥者），并列时按 id 保证确定性
        attacker_leads = [
            all_generals[a.general_id]
            for a in armies
            if a.general_id in all_generals
        ]
        attacker_lead = self._pick_lead_general(attacker_leads)
        defender_lead = self._pick_lead_general(stationed_generals)

        attacker_element = element_of(attacker_lead) if attacker_lead else ""
        defender_element = element_of(defender_lead) if defender_lead else ""

        # v4.0：智力接入攻城——攻方平均智力决定攻城器械效率（谋士第一次有了战场作用）
        attacker_avg_intelligence = self._avg_attribute(attacker_leads, "intelligence")
        defender_avg_intelligence = self._avg_attribute(stationed_generals, "intelligence")

        return BattleContext(
            battle_id=battle_id,
            turn=0,  # 由 GameEngine 设置
            attacker_faction=attacker_faction,
            defender_faction=defender_faction,
            attacker_armies=[a.id for a in armies],
            attacker_total_soldiers=attacker_total,
            attacker_avg_morale=attacker_avg_morale,
            attacker_avg_command=attacker_avg_command,
            attacker_avg_bravery=attacker_avg_bravery,
            attacker_avg_intelligence=attacker_avg_intelligence,
            defender_city=target_city.id,
            defender_armies=[a.id for a in defender_armies],
            # v4.0：把守方将领传进战斗上下文。
            # 不传的话 process_aftermath 的 defender_generals 恒为空列表，
            # 俘虏/投降判定整条链在生产环境从不执行（历史缺陷）。
            defender_general_ids=[g.id for g in stationed_generals],
            defender_total_soldiers=defender_total,
            defender_avg_morale=defender_avg_morale,
            defender_avg_command=defender_avg_command,
            defender_avg_bravery=defender_avg_bravery,
            defender_avg_intelligence=defender_avg_intelligence,
            battle_type=BattleType.SIEGE,
            battle_phase=BattlePhase.SIEGE,
            # 忠诚度：死忠部队 +10% 伤害，哗变边缘 -20%（原为从未被引用的死常量）
            attacker_loyalty_factor=(
                loyalty_combat_factor(attacker_lead.loyalty) if attacker_lead else 1.0
            ),
            defender_loyalty_factor=(
                loyalty_combat_factor(defender_lead.loyalty) if defender_lead else 1.0
            ),
            # 五行相克：火→金→木→土→水→火，克制方 +15% / 被克方 -15%
            attacker_element=attacker_element,
            defender_element=defender_element,
            attacker_counter_bonus=counter_factor(attacker_element, defender_element),
            defender_counter_bonus=counter_factor(defender_element, attacker_element),
        )

    @staticmethod
    def _pick_lead_general(candidates: List[General]) -> Optional[General]:
        """从候选将领中选出主将（统帅最高；并列时按 id 字典序，保证确定性）"""
        if not candidates:
            return None
        return max(candidates, key=lambda g: (g.command, g.id))

    @staticmethod
    def _avg_attribute(candidates: List[General], attr: str) -> float:
        """计算候选将领某项属性的平均值（无将领时返回中性值 50.0）

        返回中性值而非 0，是为了让"没有将领参战"与"将领属性平庸"
        在伤害公式里表现一致，避免无将部队被额外重罚。

        Args:
            candidates: 候选将领
            attr: 属性名（command / bravery / intelligence / politics）

        Returns:
            平均值（无候选时为 50.0）
        """
        if not candidates:
            return 50.0
        return sum(getattr(g, attr) for g in candidates) / len(candidates)

    @staticmethod
    def _calculate_force_stats(
        armies: List[Army],
        generals: Dict[str, General],
    ) -> Tuple[int, float, float, float]:
        """计算军队集团的统计数据

        Args:
            armies: 军队列表
            generals: 将领字典

        Returns:
            (总兵力, 平均士气, 平均统帅, 平均勇武) 元组
        """
        total_soldiers = sum(a.soldiers for a in armies)
        if total_soldiers == 0:
            return 0, 0.0, 0.0, 0.0

        weighted_morale = sum(a.morale * a.soldiers for a in armies)
        weighted_command = 0.0
        weighted_bravery = 0.0

        for army in armies:
            gen = generals.get(army.general_id)
            if gen is not None:
                weighted_command += gen.command * army.soldiers
                weighted_bravery += gen.bravery * army.soldiers
            else:
                weighted_command += 50.0 * army.soldiers  # 无将领时默认50
                weighted_bravery += 50.0 * army.soldiers

        avg_morale = weighted_morale / total_soldiers
        avg_command = weighted_command / total_soldiers
        avg_bravery = weighted_bravery / total_soldiers

        return total_soldiers, avg_morale, avg_command, avg_bravery

    @staticmethod
    def _collect_defender_armies(
        target_city: City,
        all_armies: Dict[str, Army],
        attacker_faction: str,
    ) -> List[Army]:
        """收集防守方援军

        在目标城市附近、属于防守方的军队。

        Args:
            target_city: 目标城市
            all_armies: 所有军队
            attacker_faction: 攻击方势力

        Returns:
            防守方援军列表
        """
        defenders = []
        for army in all_armies.values():
            if army.faction == attacker_faction:
                continue  # 跳过攻击方
            if army.faction != target_city.faction:
                continue  # 不是防守方势力
            if army.status == ArmyStatus.GARRISONED:
                continue  # 驻守军队由城市守军代表
            if army.to_city == target_city.id:
                # 正在前往或已在该城市的友军
                defenders.append(army)
        return defenders
