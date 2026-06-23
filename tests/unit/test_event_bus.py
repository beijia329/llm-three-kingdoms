"""事件总线单元测试"""

import pytest
from game.event_bus import (
    Event,
    EventBus,
    CityCapturedEvent,
    BattleStartedEvent,
    BattleEndedEvent,
    ArmyCreatedEvent,
    GeneralRecruitedEvent,
    TurnStartedEvent,
    TurnEndedEvent,
    DiplomacyMessageSentEvent,
    GeneralDefectedEvent,
    GameOverEvent,
)


class TestEvent:
    """事件基类测试"""

    def test_event_creation(self):
        event = Event(event_type="test", data={"key": "value"})
        assert event.event_type == "test"
        assert event.data == {"key": "value"}

    def test_event_type_is_immutable(self):
        """事件类型不应被修改"""
        event = Event(event_type="test")
        with pytest.raises((TypeError, AttributeError)):
            event.event_type = "changed"


class TestSpecificEvents:
    """具体事件类型测试"""

    def test_city_captured_event(self):
        event = CityCapturedEvent(
            city_id="chengdu",
            city_name="成都",
            attacker_faction="wei",
            defender_faction="shu",
            turn=10,
        )
        assert event.event_type == "city_captured"
        assert event.city_id == "chengdu"
        assert event.attacker_faction == "wei"
        assert event.data["city_name"] == "成都"

    def test_battle_started_event(self):
        event = BattleStartedEvent(
            battle_id="battle_001",
            battle_type="siege",
            attacker_faction="wei",
            defender_faction="shu",
            attacker_soldiers=5000,
            defender_soldiers=3000,
            turn=8,
        )
        assert event.battle_type == "siege"
        assert event.attacker_soldiers == 5000

    def test_battle_ended_event(self):
        event = BattleEndedEvent(
            battle_id="battle_001",
            result="attacker_win",
            attacker_faction="wei",
            defender_faction="shu",
            attacker_casualties=1000,
            defender_casualties=2000,
            captured_city="chengdu",
            turn=10,
        )
        assert event.result == "attacker_win"
        assert event.captured_city == "chengdu"

    def test_army_created_event(self):
        event = ArmyCreatedEvent(
            army_id="army_001",
            faction="shu",
            general="zhaoyun",
            soldiers=3000,
            from_city="chengdu",
            to_city="hanzhong",
            turn=5,
        )
        assert event.general == "zhaoyun"

    def test_general_recruited_event(self):
        event = GeneralRecruitedEvent(
            general_id="machao",
            general_name="马超",
            faction="shu",
            city="chengdu",
            turn=7,
        )
        assert event.general_name == "马超"

    def test_turn_started_and_ended(self):
        start = TurnStartedEvent(turn=5, faction_order=["wei", "shu", "wu"])
        assert start.turn == 5
        assert start.faction_order == ["wei", "shu", "wu"]

        end = TurnEndedEvent(turn=5, summary={"num_commands": 9})
        assert end.turn == 5
        assert end.summary["num_commands"] == 9

    def test_diplomacy_message_sent_event(self):
        event = DiplomacyMessageSentEvent(
            message_id="msg_001",
            from_faction="shu",
            to_faction="wei",
            content="我们结盟吧",
            turn=6,
        )
        assert event.content == "我们结盟吧"

    def test_general_defected_event(self):
        event = GeneralDefectedEvent(
            general_id="mengda",
            general_name="孟达",
            from_faction="shu",
            to_faction="wei",
            turn=12,
        )
        assert event.to_faction == "wei"

    def test_game_over_event(self):
        event = GameOverEvent(
            winner="wei",
            final_turn=24,
            reason="max_turns_reached",
            city_counts={"wei": 8, "shu": 4, "wu": 3},
        )
        assert event.winner == "wei"
        assert event.city_counts["wei"] == 8


class TestEventBus:
    """事件总线核心功能测试"""

    def test_subscribe_and_publish(self):
        """可以订阅并接收事件"""
        bus = EventBus()
        received_events = []

        bus.subscribe("city_captured", lambda e: received_events.append(e))

        event = CityCapturedEvent(
            city_id="chengdu", city_name="成都",
            attacker_faction="wei", defender_faction="shu", turn=10,
        )
        bus.publish(event)

        assert len(received_events) == 1
        assert received_events[0].city_id == "chengdu"

    def test_multiple_subscribers(self):
        """同一事件可以有多个订阅者"""
        bus = EventBus()
        results = []

        bus.subscribe("test_event", lambda e: results.append("a"))
        bus.subscribe("test_event", lambda e: results.append("b"))

        bus.publish(Event(event_type="test_event"))
        assert len(results) == 2
        assert "a" in results
        assert "b" in results

    def test_unsubscribe(self):
        """取消订阅后不再接收事件"""
        bus = EventBus()

        def handler(e):
            pytest.fail("Should not be called after unsubscribe")

        bus.subscribe("test", handler)
        bus.unsubscribe("test", handler)
        bus.publish(Event(event_type="test"))

    def test_different_event_types(self):
        """订阅不同类型的事件"""
        bus = EventBus()
        results = []

        bus.subscribe("type_a", lambda e: results.append("a"))
        bus.subscribe("type_b", lambda e: results.append("b"))

        bus.publish(Event(event_type="type_a"))
        assert results == ["a"]

        bus.publish(Event(event_type="type_b"))
        assert results == ["a", "b"]

    def test_no_subscriber(self):
        """没有订阅者时发布事件不应报错"""
        bus = EventBus()
        bus.publish(Event(event_type="orphan_event"))  # should not raise

    def test_subscribe_all(self):
        """可以订阅所有事件"""
        bus = EventBus()
        results = []

        bus.subscribe_all(lambda e: results.append(e.event_type))

        bus.publish(Event(event_type="type_a"))
        bus.publish(Event(event_type="type_b"))

        assert results == ["type_a", "type_b"]

    def test_handler_exception_isolation(self):
        """一个handler抛异常不应影响其他handler"""
        bus = EventBus()
        results = []

        def bad_handler(e):
            raise ValueError("Bad!")

        def good_handler(e):
            results.append("ok")

        bus.subscribe("test", bad_handler)
        bus.subscribe("test", good_handler)

        # 应该不抛出异常
        bus.publish(Event(event_type="test"))
        assert results == ["ok"]

    def test_clear_all_subscribers(self):
        """清除所有订阅者"""
        bus = EventBus()
        results = []

        bus.subscribe("a", lambda e: results.append("a"))
        bus.subscribe("b", lambda e: results.append("b"))

        bus.clear()
        bus.publish(Event(event_type="a"))
        assert results == []

    def test_subscriber_count(self):
        """订阅者计数"""
        bus = EventBus()
        assert bus.subscriber_count() == 0

        bus.subscribe("a", lambda e: None)
        assert bus.subscriber_count() == 1

        bus.subscribe("a", lambda e: None)
        assert bus.subscriber_count() == 2

        bus.subscribe("b", lambda e: None)
        assert bus.subscriber_count() == 3


class TestEventBusEdgeCases:
    """事件总线边界情况测试"""

    def test_subscribe_same_handler_twice(self):
        """同一个handler订阅两次应只收到一次"""
        bus = EventBus()
        results = []

        def handler(e):
            results.append("called")

        bus.subscribe("test", handler)
        bus.subscribe("test", handler)  # 再次订阅
        bus.publish(Event(event_type="test"))

        assert len(results) == 1  # 只调用一次

    def test_unsubscribe_nonexistent(self):
        """取消不存在的订阅不应报错"""
        bus = EventBus()
        bus.unsubscribe("test", lambda e: None)  # should not raise

    def test_publish_none(self):
        """发布None不应报错"""
        bus = EventBus()
        bus.publish(None)  # should not raise
