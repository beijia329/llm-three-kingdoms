"""行军系统

管理军队在地图上的移动、粮草消耗、断粮惩罚和到达处理。

核心逻辑：
1. 每回合向前推进 1/total_distance 的进度
2. 每回合消耗粮草（soldiers × 0.2）
3. 断粮后每回合士气-10，士气低于20%开始溃散（每回合-10%兵力）
4. 到达目的地后：友方城市→入城增援，敌方城市→开始围城

参考设计文档：docs/design/battle-system.md 第二章
"""

from __future__ import annotations

from dataclasses import dataclass, field

from game.constants import (
    ARMY_FOOD_COST_PER_SOLDIER,
    MORALE_LOSS_NO_FOOD,
    MORALE_BREAK_THRESHOLD,
    ROUT_LOSS_RATE,
)
from game.models import Army, ArmyStatus


# ============================================================
# 结果数据结构
# ============================================================


@dataclass
class MovementResult:
    """行军单回合处理结果"""

    progress_made: float = 0.0
    """本回合推进的进度"""

    food_consumed: int = 0
    """本回合消耗的粮草"""

    arrived: bool = False
    """本回合是否到达目的地"""

    arrival_type: str = ""
    """到达类型: besiege / reinforce / none"""

    starvation: bool = False
    """是否处于断粮状态"""

    routing: bool = False
    """是否正在溃散"""

    soldiers_lost_to_rout: int = 0
    """本回合因溃散损失的兵力"""

    status_changed: bool = False
    """状态是否发生变化"""


@dataclass
class MovementEvent:
    """行军事件（用于事件总线/日志）"""

    army_id: str = ""
    faction: str = ""
    from_city: str = ""
    to_city: str = ""
    progress_before: float = 0.0
    progress_after: float = 0.0
    arrived: bool = False
    arrival_type: str = ""

    def to_dict(self) -> dict:
        return {
            "army_id": self.army_id,
            "faction": self.faction,
            "from_city": self.from_city,
            "to_city": self.to_city,
            "progress_before": self.progress_before,
            "progress_after": self.progress_after,
            "arrived": self.arrived,
            "arrival_type": self.arrival_type,
        }


class ArmyMovementSystem:
    """行军系统

    负责处理军队每回合的行军推进、粮草消耗、断粮惩罚和到达事件。
    所有修改直接作用于 Army 对象。
    """

    # ============================================================
    # 主处理入口
    # ============================================================

    def process_movement(self, army: Army) -> MovementResult:
        """处理一回合的军队移动

        包含：进度推进、粮草消耗、断粮判定、溃散判定、到达判定。

        Args:
            army: 要处理的军队对象（会被修改）

        Returns:
            本回合行军处理结果
        """
        result = MovementResult()

        # 只有行军、围城、撤退中的军队需要处理消耗
        if army.status not in (
            ArmyStatus.MARCHING,
            ArmyStatus.RETREATING,
            ArmyStatus.BESIEGING,
        ):
            return result

        # 1. 推进进度（仅行军和撤退）
        if army.status == ArmyStatus.MARCHING and army.total_distance > 0:
            progress_step = 1.0 / army.total_distance
            old_progress = army.progress
            army.progress = min(1.0, army.progress + progress_step)
            result.progress_made = army.progress - old_progress
        elif army.status == ArmyStatus.RETREATING:
            # 撤退中的军队以双倍速度返回
            progress_step = 2.0 / max(army.total_distance, 1)
            old_progress = army.progress
            army.progress = min(1.0, army.progress + progress_step)
            result.progress_made = army.progress - old_progress

        # 2. 消耗粮草
        result.food_consumed = self._consume_food(army)

        # 3. 断粮判定：如果粮草为0（不管是已耗尽还是一开始就为0）
        if army.food <= 0:
            result.starvation = True
            self._apply_starvation(army)

        # 4. 溃散判定
        if army.morale <= MORALE_BREAK_THRESHOLD:
            soldiers_lost = self._apply_rout(army)
            result.routing = soldiers_lost > 0
            result.soldiers_lost_to_rout = soldiers_lost

        # 5. 到达判定（仅行军中军队）
        if army.status == ArmyStatus.MARCHING and army.progress >= 1.0:
            army.progress = 1.0
            arrival_result = self._handle_arrival(army)
            result.arrived = arrival_result["arrived"]
            result.arrival_type = arrival_result["type"]
            result.status_changed = arrival_result["status_changed"]

        return result

    # ============================================================
    # 粮草消耗
    # ============================================================

    def _consume_food(self, army: Army) -> int:
        """消耗本回合粮草

        行军/围城/撤退中的军队都会消耗粮草。

        Args:
            army: 军队对象

        Returns:
            本回合消耗的粮草数量
        """
        if army.food <= 0:
            return 0

        consumption = int(army.soldiers * ARMY_FOOD_COST_PER_SOLDIER)
        actual_consumption = min(consumption, army.food)
        army.food -= actual_consumption

        return actual_consumption

    # ============================================================
    # 断粮惩罚
    # ============================================================

    def _apply_starvation(self, army: Army) -> None:
        """执行断粮惩罚

        断粮时：
        1. 士气每回合下降 MORALE_LOSS_NO_FOOD (10) 点
        2. 士气不会低于 0

        Args:
            army: 军队对象
        """
        army.morale = max(0, army.morale - MORALE_LOSS_NO_FOOD)

    # ============================================================
    # 溃散
    # ============================================================

    def _apply_rout(self, army: Army) -> int:
        """执行溃散

        士气低于 MORALE_BREAK_THRESHOLD (20) 时触发。
        每回合损失 ROUT_LOSS_RATE (10%) 的兵力。

        Args:
            army: 军队对象

        Returns:
            本回合损失的兵力
        """
        soldiers_lost = int(army.soldiers * ROUT_LOSS_RATE)
        army.soldiers = max(0, army.soldiers - soldiers_lost)
        army.casualties += soldiers_lost

        # 士气归零则全军覆没
        if army.morale <= 0:
            army.soldiers = 0

        return soldiers_lost

    # ============================================================
    # 到达处理
    # ============================================================

    def _handle_arrival(self, army: Army) -> dict:
        """处理军队到达目的地

        根据目标城市归属决定：
        - 友方城市：入城增援（军队变为驻守状态）
        - 敌方城市：开始围城（军队变为围城状态）

        Args:
            army: 军队对象

        Returns:
            包含 arrived 和 type 的字典
        """
        # 简化处理：根据 from/to 城市所属势力判断
        # 如果是同一势力（通过 faction 判断），视为增援
        # 否则视为围城
        # 注意：这里简化处理，实际应该在 GameEngine 层面根据城市归属判断

        if army.from_city == army.to_city:
            # 同一城市，直接驻守
            army.status = ArmyStatus.GARRISONED
            return {"arrived": True, "type": "garrison", "status_changed": True}

        # 默认：到达敌方城市开始围城
        army.status = ArmyStatus.BESIEGING
        return {"arrived": True, "type": "besiege", "status_changed": True}

    # ============================================================
    # 辅助方法
    # ============================================================

    @staticmethod
    def calculate_turns_to_arrive(army: Army) -> int:
        """计算还需要几回合到达目的地

        Args:
            army: 军队对象

        Returns:
            还需回合数，已到达返回 0
        """
        if army.progress >= 1.0 or army.status == ArmyStatus.GARRISONED:
            return 0

        remaining_progress = 1.0 - army.progress
        if army.total_distance <= 0:
            return 0

        return int(remaining_progress * army.total_distance)
