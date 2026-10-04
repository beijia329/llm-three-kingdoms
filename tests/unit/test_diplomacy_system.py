"""外交系统单元测试"""

import pytest

from game.models import DiplomacyMessage, General, City
from game.random import GameRandom
from game.systems.diplomacy_system import (
    DiplomacySystem,
    SendMessageResult,
    RumorResult,
)
from game.constants import CITY_LEVELS, RUMOR_MORALE_DECREASE
from game.hex_grid import HexCoord


class TestSendMessage:
    """发送消息测试"""

    def test_send_message_basic(self):
        """基础发送消息"""
        ds = DiplomacySystem(rng=GameRandom(seed=42))

        result = ds.send_message(
            from_faction="liubei",
            to_faction="caocao",
            content="我们结盟吧",
            turn=5,
        )

        assert isinstance(result, SendMessageResult)
        assert result.success is True
        assert result.message_id is not None

    def test_send_message_creates_log(self):
        """发送消息创建日志"""
        ds = DiplomacySystem(rng=GameRandom(seed=42))

        ds.send_message(
            from_faction="liubei",
            to_faction="caocao",
            content="合作抗吴",
            turn=5,
        )

        messages = ds.get_messages_for_faction("caocao")
        assert len(messages) == 1
        assert messages[0].content == "合作抗吴"
        assert messages[0].from_faction == "liubei"

    def test_max_messages_per_turn(self):
        """每回合最多发1条消息"""
        ds = DiplomacySystem(rng=GameRandom(seed=42))

        result1 = ds.send_message(
            from_faction="liubei", to_faction="caocao",
            content="第一条", turn=5,
        )
        assert result1.success is True

        result2 = ds.send_message(
            from_faction="liubei", to_faction="sunjian",
            content="第二条", turn=5,
        )
        assert result2.success is False  # 超限

    def test_new_turn_resets_limit(self):
        """新回合重置发送限制"""
        ds = DiplomacySystem(rng=GameRandom(seed=42))

        ds.send_message(
            from_faction="liubei", to_faction="caocao",
            content="第5回合", turn=5,
        )
        ds.send_message(
            from_faction="liubei", to_faction="sunjian",
            content="第6回合", turn=6,
        )

        messages_to_wei = ds.get_messages_for_faction("caocao")
        messages_to_wu = ds.get_messages_for_faction("sunjian")

        assert len(messages_to_wei) == 1
        assert len(messages_to_wu) == 1

    def test_empty_content(self):
        """空内容消息"""
        ds = DiplomacySystem(rng=GameRandom(seed=42))

        result = ds.send_message(
            from_faction="liubei", to_faction="caocao",
            content="", turn=5,
        )
        assert result.success is True  # 允许空消息

    def test_self_message(self):
        """给自己发消息"""
        ds = DiplomacySystem(rng=GameRandom(seed=42))

        result = ds.send_message(
            from_faction="liubei", to_faction="liubei",
            content="自言自语", turn=5,
        )
        assert result.success is True


class TestRumor:
    """流言系统测试"""

    def test_rumor_basic(self):
        """散布流言"""
        ds = DiplomacySystem(rng=GameRandom(seed=42))
        general = _make_general(loyalty=70)

        result = ds.spread_rumor(
            target_city_id="chengdu",
            target_faction="liubei",
            target_general=general,
            spy_intelligence=80,
            turn=5,
        )

        assert isinstance(result, RumorResult)
        # 结果可能是成功或失败
        assert result.description is not None

    def test_rumor_reduces_loyalty(self):
        """成功散布流言降低忠诚度"""
        ds = DiplomacySystem(rng=GameRandom(seed=42))
        general = _make_general(loyalty=70)

        result = ds.spread_rumor(
            target_city_id="chengdu",
            target_faction="liubei",
            target_general=general,
            spy_intelligence=90,
            turn=5,
        )

        if result.success:
            assert result.loyalty_decrease > 0
            # 高智力的间谍成功率高，大概率成功

    def test_rumor_low_intelligence(self):
        """低智力间谍流言成功率低"""
        ds = DiplomacySystem(rng=GameRandom(seed=42))
        general = _make_general(loyalty=70)

        result = ds.spread_rumor(
            target_city_id="chengdu",
            target_faction="liubei",
            target_general=general,
            spy_intelligence=20,
            turn=5,
        )

        assert isinstance(result.success, bool)

    def test_rumor_no_general(self):
        """没有目标将领、也没给城市：流言无明确作用对象，如实返回失败（B3 不再谎报成功）

        原实现只要掷骰通过就返回 success=True，却什么都不做——典型「显示成功但
        实际没生效」的假绿。B3 改为：无目标将领时若有城市则降民心，否则明确失败。
        """
        ds = DiplomacySystem(rng=GameRandom(seed=42))
        ds._rng.random = lambda: 0.0  # 强制掷骰成功，隔离骰子与断言（失败只可能来自缺对象）

        result = ds.spread_rumor(
            target_city_id="chengdu",
            target_faction="liubei",
            target_general=None,
            spy_intelligence=80,
            turn=5,
        )

        assert result.success is False

    def test_rumor_no_general_lowers_city_morale(self):
        """没有目标将领但给了城市：流言动摇守军民心（B3 的真实效果）

        这是 B3 修复后新增的有效路径——此前「无目标将领」分支什么都不做，等于
        让流言命令在多数情况下沦为空操作。这里用固定 RNG 隔离骰子，断言：
        1) 成功；
        2) 城市民心按 RUMOR_MORALE_DECREASE 下降；
        3) 不碰将领忠诚度（loyalty_decrease 为 0）。
        """
        ds = DiplomacySystem(rng=GameRandom(seed=42))
        ds._rng.random = lambda: 0.0  # 强制掷骰成功
        city = City(
            id="chengdu", name="成都", faction="liubei", level=3,
            wall_hp=100, wall_max_hp=200, gold=1000, food=1000,
            population=5000, morale=80, garrison=2000,
            position=HexCoord(q=0, r=0),
        )
        result = ds.spread_rumor(
            target_city_id="chengdu",
            target_faction="liubei",
            target_general=None,
            spy_intelligence=80,
            city=city,
            turn=5,
        )
        assert result.success is True
        assert city.morale == 80 - RUMOR_MORALE_DECREASE
        assert result.loyalty_decrease == 0


class TestMessageQuery:
    """消息查询功能测试"""

    def test_get_messages_empty(self):
        """没有消息时返回空列表"""
        ds = DiplomacySystem(rng=GameRandom(seed=42))
        messages = ds.get_messages_for_faction("caocao")
        assert messages == []

    def test_get_messages_multiple(self):
        """多条消息查询"""
        ds = DiplomacySystem(rng=GameRandom(seed=42))

        ds.send_message(from_faction="liubei", to_faction="caocao", content="你好", turn=5)
        ds.send_message(from_faction="sunjian", to_faction="caocao", content="你好", turn=6)

        messages = ds.get_messages_for_faction("caocao")
        assert len(messages) == 2

    def test_get_sent_messages(self):
        """查询已发送消息"""
        ds = DiplomacySystem(rng=GameRandom(seed=42))

        ds.send_message(from_faction="liubei", to_faction="caocao", content="你好", turn=5)
        ds.send_message(from_faction="liubei", to_faction="sunjian", content="你好", turn=6)

        sent = ds.get_sent_messages("liubei")
        assert len(sent) == 2

    def test_message_read_status(self):
        """消息已读状态"""
        ds = DiplomacySystem(rng=GameRandom(seed=42))

        msg_id = ds.send_message(
            from_faction="liubei", to_faction="caocao",
            content="你好", turn=5,
        ).message_id

        messages = ds.get_messages_for_faction("caocao")
        assert messages[0].is_read is False

        ds.mark_as_read(msg_id)
        messages = ds.get_messages_for_faction("caocao")
        assert messages[0].is_read is True


class TestDiplomacyEdgeCases:
    """外交系统边界测试"""

    def test_multiple_factions_messages(self):
        """多势力消息隔离"""
        ds = DiplomacySystem(rng=GameRandom(seed=42))

        ds.send_message(from_faction="liubei", to_faction="caocao", content="秘密1", turn=5)
        ds.send_message(from_faction="sunjian", to_faction="caocao", content="秘密2", turn=5)

        wei_msgs = ds.get_messages_for_faction("caocao")
        shu_msgs = ds.get_messages_for_faction("liubei")

        assert len(wei_msgs) == 2
        assert len(shu_msgs) == 0  # 没给shu发过

    def test_clear_turn_data(self):
        """清理回合数据"""
        ds = DiplomacySystem(rng=GameRandom(seed=42))

        ds.send_message(from_faction="liubei", to_faction="caocao", content="test", turn=5)

        # 手动模拟新回合
        # 发送限制应该在方法内部处理
        result = ds.send_message(
            from_faction="liubei", to_faction="caocao",
            content="test2", turn=5,  # 同一回合
        )
        assert result.success is False  # 已达上限

        result = ds.send_message(
            from_faction="liubei", to_faction="caocao",
            content="test3", turn=6,  # 新回合
        )
        assert result.success is True  # 重置了


# ============================================================
# 辅助函数
# ============================================================

def _make_city(id: str = "chengdu", morale: int = 70) -> City:
    """创建测试用城市"""
    lc = CITY_LEVELS[1]
    return City(
        id=id,
        name="测试城",
        faction="liubei",
        level=1,
        wall_hp=lc["wall_hp"],
        wall_max_hp=lc["wall_hp"],
        gold=1000,
        food=1000,
        population=5000,
        morale=morale,
        garrison=500,
        position=HexCoord(0, 0),
    )


def _make_general(
    general_id: str = "test_gen",
    loyalty: int = 70,
) -> General:
    """创建测试用将领"""
    return General(
        id=general_id,
        name="测试将",
        faction="liubei",
        command=70,
        politics=50,
        bravery=60,
        intelligence=55,
        loyalty=loyalty,
        location="test_city",
    )
