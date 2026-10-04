"""外交系统

管理势力间的外交互动：
- 信使系统：发送和接收外交消息
- 流言系统：散布流言降低敌方将领忠诚度
- 消息限额：每回合每个势力限发1条
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from game.constants import (
    MAX_MESSAGES_PER_TURN,
    RUMOR_LOYALTY_DECREASE,
    RUMOR_MORALE_DECREASE,
    RUMOR_BASE_SUCCESS_RATE,
    RUMOR_INTELLIGENCE_FACTOR,
)
from game.models import City, DiplomacyMessage, General
from game.random import GameRandom


# ============================================================
# 结果数据结构
# ============================================================


@dataclass
class SendMessageResult:
    """发送消息结果"""

    success: bool = False
    message_id: str = ""
    description: str = ""


@dataclass
class RumorResult:
    """流言结果"""

    success: bool = False
    loyalty_decrease: int = 0
    description: str = ""


class DiplomacySystem:
    """外交系统

    管理外交消息的发送、接收、查询，以及流言的散布。
    每回合各势力发送消息有数量限制。
    """

    def __init__(self, rng: GameRandom) -> None:
        self._rng = rng
        self._messages: List[DiplomacyMessage] = []
        self._sent_count: Dict[str, int] = {}  # faction -> count per turn
        self._current_turn: int = 0
        self._message_counter: int = 0

    # ============================================================
    # 消息发送
    # ============================================================

    def send_message(
        self,
        from_faction: str,
        to_faction: str,
        content: str,
        turn: int,
    ) -> SendMessageResult:
        """发送外交消息

        每回合每个势力最多发送 MAX_MESSAGES_PER_TURN 条消息。

        Args:
            from_faction: 发送方势力
            to_faction: 接收方势力
            content: 消息内容
            turn: 当前回合

        Returns:
            发送结果
        """
        # 检查回合限制
        if turn != self._current_turn:
            self._current_turn = turn
            self._sent_count.clear()

        sent_this_turn = self._sent_count.get(from_faction, 0)
        if sent_this_turn >= MAX_MESSAGES_PER_TURN:
            return SendMessageResult(
                success=False,
                description=f"本回合已发送{sent_this_turn}条消息，已达上限",
            )

        # 创建消息
        self._message_counter += 1
        message = DiplomacyMessage(
            id=f"msg_{self._message_counter}",
            from_faction=from_faction,
            to_faction=to_faction,
            content=content,
            turn=turn,
        )

        self._messages.append(message)
        self._sent_count[from_faction] = sent_this_turn + 1

        return SendMessageResult(
            success=True,
            message_id=message.id,
            description=f"消息已发送至{to_faction}",
        )

    # ============================================================
    # 消息查询
    # ============================================================

    def get_messages_for_faction(self, faction: str) -> List[DiplomacyMessage]:
        """获取指定势力收到的所有消息

        Args:
            faction: 势力名称

        Returns:
            收到的消息列表（按时间顺序）
        """
        return [
            msg for msg in self._messages
            if msg.to_faction == faction
        ]

    def get_sent_messages(self, faction: str) -> List[DiplomacyMessage]:
        """获取指定势力发送的所有消息

        Args:
            faction: 势力名称

        Returns:
            发送的消息列表
        """
        return [
            msg for msg in self._messages
            if msg.from_faction == faction
        ]

    def mark_as_read(self, message_id: str) -> bool:
        """将消息标记为已读

        Args:
            message_id: 消息ID

        Returns:
            找到并标记返回 True，未找到返回 False
        """
        for msg in self._messages:
            if msg.id == message_id:
                msg.is_read = True
                return True
        return False

    # ============================================================
    # 流言系统
    # ============================================================

    def spread_rumor(
        self,
        target_city_id: str,
        target_faction: str,
        spy_intelligence: int,
        target_general: Optional[General] = None,
        city: Optional["City"] = None,
        turn: int = 0,
    ) -> RumorResult:
        """散布流言

        成功效果：降低目标将领忠诚度，或降低目标城市民心。
        成功率受执行间谍的智力和基础概率影响。

        Args:
            target_city_id: 流言目标城市
            target_faction: 流言目标势力
            spy_intelligence: 执行间谍的智力值
            target_general: 流言目标将领（可选）
            turn: 当前回合

        Returns:
            流言结果
        """
        # 计算流言成功率
        success_chance = (
            RUMOR_BASE_SUCCESS_RATE
            + spy_intelligence * RUMOR_INTELLIGENCE_FACTOR
        )
        success_chance = min(success_chance, 0.9)  # 上限90%

        if self._rng.random() < success_chance:
            if target_general is not None:
                # 降低将领忠诚度
                loyalty_decrease = RUMOR_LOYALTY_DECREASE
                old_loyalty = target_general.loyalty
                target_general.loyalty = max(0, target_general.loyalty - loyalty_decrease)
                actual_decrease = old_loyalty - target_general.loyalty

                return RumorResult(
                    success=True,
                    loyalty_decrease=actual_decrease,
                    description=f"流言成功！{target_general.name}忠诚度降低{actual_decrease}",
                )
            # 无具体目标将领：流言动摇守军民心（真实效果，不再谎报成功）。
            # city 由引擎传入；直接调本函数而不传 city 时退化为失败（如实返回）。
            if city is not None:
                morale_drop = RUMOR_MORALE_DECREASE
                old_morale = city.morale
                city.morale = max(0, city.morale - morale_drop)
                actual_drop = old_morale - city.morale
                return RumorResult(
                    success=True,
                    loyalty_decrease=0,
                    description=f"流言在{target_city_id}散布，守军民心下降{actual_drop}",
                )
            return RumorResult(
                success=False,
                description=f"流言在{target_city_id}散布失败（无有效目标）",
            )

        return RumorResult(
            success=False,
            description=f"流言在{target_city_id}散布失败",
        )
