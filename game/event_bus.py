"""事件总线

游戏中所有状态变更通过事件通知，实现模块间解耦。
- UI 和日志系统通过订阅事件获取状态变更
- 事件是不可变的（使用 NamedTuple / frozen dataclass）
- 一个事件可以有多个订阅者
- 一个订阅者可以订阅多个事件

🔴 2026-10 接线说明（原为「定义了但无人用」的死基础设施）：
本模块原来定义了 10 个事件类，但全仓只有 1 处 `publish`、0 处生产 `subscribe`，
被审计判为「假 Accepted」（ADR-0001 写了事件驱动，实际却全在轮询）。

现按「保留有真实产生点的事件、删掉无人产生的事件类」收口：
- **保留并接线（有产生点）**：
  `TurnStartedEvent` / `TurnEndedEvent` / `CityCapturedEvent` / `BattleEndedEvent`
  —— 由 `GameEngine.process_turn` 等发布；`GameManager` 订阅 `TurnEndedEvent`
    并据此产生事件记录（见 `api/game_manager.py`）。
  `DiplomacyMessageSentEvent` —— 由 `_execute_message` 发布（沿用既有产生点）。
- **删除（无产生点、且无订阅者）**：`BattleStartedEvent` / `ArmyCreatedEvent` /
  `GeneralRecruitedEvent` / `GeneralDefectedEvent` / `GameOverEvent`。
  待真要做「主动叛逃 / 阵亡」等机制时再按需加回，不预先挂空类。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# 事件处理器类型签名
EventHandler = Callable[["Event"], None]


@dataclass(frozen=True)
class Event:
    """事件基类

    所有事件的基类，使用 frozen=True 保证不可变性。
    event_type 用于路由到对应的订阅者。
    """

    event_type: str = field(compare=True)
    """事件类型标识符，用于路由"""

    data: Dict[str, Any] = field(default_factory=dict, compare=False)
    """事件数据，不可修改"""


# ============================================================
# 具体事件类型
# ============================================================


@dataclass(frozen=True)
class CityCapturedEvent(Event):
    """城市被占领事件"""

    event_type: str = field(default="city_captured", init=False)
    city_id: str = ""
    city_name: str = ""
    attacker_faction: str = ""
    defender_faction: str = ""
    turn: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", {
            "city_id": self.city_id,
            "city_name": self.city_name,
            "attacker_faction": self.attacker_faction,
            "defender_faction": self.defender_faction,
            "turn": self.turn,
        })


@dataclass(frozen=True)
class BattleEndedEvent(Event):
    """战斗结束事件"""

    event_type: str = field(default="battle_ended", init=False)
    battle_id: str = ""
    result: str = ""
    attacker_faction: str = ""
    defender_faction: str = ""
    attacker_casualties: int = 0
    defender_casualties: int = 0
    captured_city: Optional[str] = None
    turn: int = 0

    # ---- v4.1：为「战斗可见性」补充的打包字段（供 recent_battles 呈现）----
    defender_city: Optional[str] = None
    """目标城（守方城市）ID。与 captured_city 不同：守住了时 captured_city 为 None。"""

    attacker_from_cities: List[str] = field(default_factory=list)
    """该战斗**全部攻方部队**的出发城（去重+排序）。

    🔴 必须是复数：`battle_scheduler` 会把目标城相同的多支攻方军队合并进同一
    `BattleContext`，而各军队 `from_city` 可不同（实测约 15% 的战斗是多出发城）。
    后端打包用 `sorted(set(...))` 去重排序，避免集合迭代序非确定性（ADR-0002）。
    """

    attacker_soldiers: int = 0
    """攻方战斗前初始总兵力。"""
    defender_soldiers: int = 0
    """守方战斗前初始总兵力。"""

    wall_hp_before: int = 0
    """战斗前城墙耐久。"""
    wall_hp_after: int = 0
    """战斗后城墙耐久。"""

    attacker_general_name: str = ""
    """攻方主将姓名（可选，可能为空）。"""

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", {
            "battle_id": self.battle_id,
            "result": self.result,
            "attacker_faction": self.attacker_faction,
            "defender_faction": self.defender_faction,
            "attacker_casualties": self.attacker_casualties,
            "defender_casualties": self.defender_casualties,
            "captured_city": self.captured_city,
            "turn": self.turn,
            "defender_city": self.defender_city,
            "attacker_from_cities": list(self.attacker_from_cities),
            "attacker_soldiers": self.attacker_soldiers,
            "defender_soldiers": self.defender_soldiers,
            "wall_hp_before": self.wall_hp_before,
            "wall_hp_after": self.wall_hp_after,
            "attacker_general_name": self.attacker_general_name,
        })


@dataclass(frozen=True)
class TurnStartedEvent(Event):
    """回合开始事件"""

    event_type: str = field(default="turn_started", init=False)
    turn: int = 0
    faction_order: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", {
            "turn": self.turn,
            "faction_order": list(self.faction_order),
        })


@dataclass(frozen=True)
class TurnEndedEvent(Event):
    """回合结束事件"""

    event_type: str = field(default="turn_ended", init=False)
    turn: int = 0
    summary: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", {
            "turn": self.turn,
            **dict(self.summary),
        })


@dataclass(frozen=True)
class DiplomacyMessageSentEvent(Event):
    """外交消息发送事件"""

    event_type: str = field(default="diplomacy_message_sent", init=False)
    message_id: str = ""
    from_faction: str = ""
    to_faction: str = ""
    content: str = ""
    turn: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", {
            "message_id": self.message_id,
            "from_faction": self.from_faction,
            "to_faction": self.to_faction,
            "content": self.content,
            "turn": self.turn,
        })


# ============================================================
# 事件总线
# ============================================================


class EventBus:
    """事件总线

    提供事件的订阅、取消订阅和发布功能。
    支持通配符订阅（订阅所有事件）。
    单个 handler 的异常不会影响其他 handler。
    """

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[EventHandler]] = {}

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """订阅指定类型的事件

        Args:
            event_type: 事件类型标识符
            handler: 事件处理函数
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        # 避免重复订阅
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        """订阅所有事件

        Args:
            handler: 事件处理函数
        """
        self.subscribe("*", handler)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """取消订阅

        Args:
            event_type: 事件类型标识符
            handler: 之前注册的事件处理函数
        """
        if event_type in self._subscribers:
            if handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)

    def publish(self, event: Optional[Event]) -> None:
        """发布事件

        通知所有订阅了该事件类型的 handler。
        单个 handler 的异常会被捕获并记录，不影响其他 handler。

        Args:
            event: 要发布的事件对象。None 值会被忽略。
        """
        if event is None:
            return

        event_type = event.event_type

        # 通知特定类型的订阅者
        handlers = list(self._subscribers.get(event_type, []))
        self._notify_handlers(handlers, event)

        # 通知通配符订阅者
        wildcard_handlers = list(self._subscribers.get("*", []))
        self._notify_handlers(wildcard_handlers, event)

    def _notify_handlers(
        self, handlers: List[EventHandler], event: Event
    ) -> None:
        """通知一组 handler

        Args:
            handlers: handler 列表
            event: 事件对象
        """
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    "Event handler %s failed for event %s: %s",
                    handler.__name__,
                    event.event_type,
                    e,
                )

    def clear(self) -> None:
        """清除所有订阅者"""
        self._subscribers.clear()

    def subscriber_count(self) -> int:
        """获取当前订阅者总数

        Returns:
            所有事件类型的订阅者总数
        """
        count = 0
        for handlers in self._subscribers.values():
            count += len(handlers)
        return count

    def __repr__(self) -> str:
        return (
            f"EventBus(subscribers={self.subscriber_count()}, "
            f"types={list(self._subscribers.keys())})"
        )
