"""C2 后端：BattleReport / recent_battles 测试

契约：`web/src/types.ts` 的 `BattleReport`（来源 `docs/design/v4.1-gameplay-gaps.md` §4.3）。
后端经 `BattleEndedEvent` 事件（EventBus）累积 `recent_battles`，供前端画进攻箭头。
"""

from __future__ import annotations

import pytest

from api.game_manager import MAX_RECENT_BATTLES, GameConfig, GameManager
from game.event_bus import BattleEndedEvent

# 前端 BattleReport 契约的必填字段（见 web/src/types.ts）
_REQUIRED = (
    "battle_id", "turn", "attacker_faction", "defender_faction",
    "attacker_from_cities", "defender_city", "attacker_soldiers",
    "defender_soldiers", "attacker_casualties", "defender_casualties", "result",
)


def _manager(max_turns: int = 24) -> GameManager:
    return GameManager(GameConfig(seed=42, max_turns=max_turns, use_llm=False))


class TestRecentBattlesSchema:
    def test_entries_match_contract_and_are_bounded(self):
        m = _manager()
        for _ in range(24):
            if m.engine and m.engine.game_over:
                break
            m.process_turn()
        rb = m.get_state()["recent_battles"]
        assert isinstance(rb, list)
        assert len(rb) <= MAX_RECENT_BATTLES
        for b in rb:
            for k in _REQUIRED:
                assert k in b, f"BattleReport 缺字段: {k}"
            assert isinstance(b["attacker_from_cities"], list)
            # 🔴 去重 + 排序（集合迭代序确定性，ADR-0002）
            assert b["attacker_from_cities"] == sorted(set(b["attacker_from_cities"]))

    def test_attacker_from_cities_is_plural(self):
        """多出发城战斗是真实存在的（设计文档 §4.3.1），字段必须是列表。"""
        m = _manager(max_turns=48)
        for _ in range(48):
            if m.engine and m.engine.game_over:
                break
            m.process_turn()
        rb = m.get_state()["recent_battles"]
        # 至少能观察到战斗；不强制一定有 mult（依赖随机），但若有必须 >1
        multis = [b for b in rb if len(b["attacker_from_cities"]) > 1]
        for b in multis:
            assert len(b["attacker_from_cities"]) >= 2


class TestBattleEndedSubscriber:
    def test_packs_event_fields(self):
        m = _manager()
        evt = BattleEndedEvent(
            battle_id="b1", result="attacker_win",
            attacker_faction="caocao", defender_faction="liubei",
            attacker_casualties=100, defender_casualties=200,
            captured_city="changan", turn=7,
            defender_city="changan",
            # 排序在引擎侧完成（sorted(set(...))）；订阅者按原样转存，故此处传已排序
            attacker_from_cities=["luoyang", "xuchang"],
            attacker_soldiers=5000, defender_soldiers=1200,
            wall_hp_before=2000, wall_hp_after=0,
            attacker_general_name="曹操",
        )
        before = len(m._recent_battles)
        m.engine.events.publish(evt)
        assert len(m._recent_battles) == before + 1
        got = m._recent_battles[-1]
        assert got["attacker_from_cities"] == ["luoyang", "xuchang"]  # 原样转存
        assert got["defender_city"] == "changan"
        assert got["wall_hp_before"] == 2000 and got["wall_hp_after"] == 0
        assert got["attacker_general_name"] == "曹操"
        assert got["result"] == "attacker_win"

    def test_cap_enforced(self):
        m = _manager()
        for i in range(MAX_RECENT_BATTLES + 5):
            m.engine.events.publish(
                BattleEndedEvent(battle_id=f"b{i}", turn=i, attacker_from_cities=["a"])
            )
        assert len(m._recent_battles) == MAX_RECENT_BATTLES
        # 保留的是最后 N 场
        assert m._recent_battles[-1]["battle_id"] == f"b{MAX_RECENT_BATTLES + 4}"

    def test_subscriber_is_loaded(self):
        m = _manager()
        assert "battle_ended" in m.engine.events._subscribers
