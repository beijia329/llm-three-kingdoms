"""EventBus 接线验证：订阅者是「承重」的，不是装饰

背景：EventBus 曾长期是「定义了 10 类事件、0 个订阅者」的死基础设施。
本次把「建国/称王」「战斗」两条事件记录从 `GameManager.process_turn` 的手写
`_add_event` 改为由引擎广播 `TurnEndedEvent` + `GameManager` 订阅驱动。

本文件验证：
1. GameManager 确实订阅了 turn_ended；
2. 订阅者会据事件产生正确的记录；
3. **订阅者被移除后，广播不再产生记录** —— 证明它是承重的（不是静默兜底）。
"""

from __future__ import annotations

from api.game_manager import GameConfig, GameManager
from game.event_bus import TurnEndedEvent


def _manager() -> GameManager:
    cfg = GameConfig(
        seed=42, max_turns=24, use_llm=False,
        factions=["caocao", "liubei", "sunjian"],
    )
    return GameManager(cfg)


class TestEventBusWired:
    def test_manager_subscribes_turn_ended(self):
        m = _manager()
        assert m.engine is not None
        assert m.engine.events.subscriber_count() >= 1
        assert "turn_ended" in m.engine.events._subscribers

    def test_subscriber_produces_battle_event(self):
        m = _manager()
        before = len(m._events)
        m.engine.events.publish(TurnEndedEvent(turn=7, summary={"battles_fought": 2}))
        new = m._events[before:]
        battles = [e for e in new if e["type"] == "battle"]
        assert len(battles) == 1
        assert battles[0]["text"] == "第 7 回合: 2 场战斗"

    def test_no_battle_no_event(self):
        m = _manager()
        before = len(m._events)
        m.engine.events.publish(TurnEndedEvent(turn=3, summary={"battles_fought": 0}))
        assert len(m._events) == before  # 0 场战斗不产生记录（与原逻辑一致）

    def test_subscriber_is_load_bearing(self):
        """🔴 关键：移除订阅者后，同样的广播不再产生记录。

        证明这些事件记录确实由订阅者产生（订阅者失效会立刻暴露），
        而不是另有兜底在静默维持。
        """
        m = _manager()
        # 有订阅者：广播 → 产生 battle 记录
        b1 = len(m._events)
        m.engine.events.publish(TurnEndedEvent(turn=5, summary={"battles_fought": 1}))
        assert len(m._events) == b1 + 1

        # 移除全部订阅者：同样的广播 → 不再产生任何记录
        m.engine.events.clear()
        b2 = len(m._events)
        m.engine.events.publish(TurnEndedEvent(turn=6, summary={"battles_fought": 1}))
        assert len(m._events) == b2, "订阅者被移除后仍在产生记录——说明存在静默兜底，接线无效"
