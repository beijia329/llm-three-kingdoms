"""外交关系系统单元测试

测试势力间外交关系的状态管理、信任度变化、同盟/停战期限等功能。
"""

import pytest

from game.systems.diplomacy_relation import DiplomacyRelationSystem
from game.models import DiplomaticStatus, FactionRelation


class TestDiplomacyRelation:
    """外交关系系统核心测试"""

    # 全部 12 方势力（与 constants.FACTIONS 一致）
    FACTIONS = [
        "han",
        "zhangjiao",
        "dongzhuo",
        "yuanshao",
        "caocao",
        "liubei",
        "sunjian",
        "liubiao",
        "liuyan",
        "gongsunzan",
        "mateng",
        "yuanshu",
    ]

    @pytest.fixture
    def system(self) -> DiplomacyRelationSystem:
        """创建外交关系系统实例，所有势力对初始为中立"""
        return DiplomacyRelationSystem(self.FACTIONS)

    # ================================================================
    # 初始化测试
    # ================================================================

    def test_init_all_neutral(self, system):
        """初始化：所有 12 方势力对的初始状态均为 NEUTRAL，信任度 50"""
        relations = system.get_all_relations()
        assert len(relations) == 66  # C(12, 2)

        for key, rel in relations.items():
            assert rel.status == DiplomaticStatus.NEUTRAL
            assert rel.trust == 50
            assert rel.alliance_end_turn is None
            assert rel.truce_end_turn is None

    def test_get_relation_returns_correct_object(self, system):
        """get_relation 返回正确的 FactionRelation 对象"""
        rel = system.get_relation("caocao", "liubei")
        assert isinstance(rel, FactionRelation)
        assert rel.status == DiplomaticStatus.NEUTRAL
        assert rel.trust == 50

    def test_get_relation_order_independent(self, system):
        """get_relation 不依赖参数顺序"""
        rel_ab = system.get_relation("caocao", "liubei")
        rel_ba = system.get_relation("liubei", "caocao")
        assert rel_ab is rel_ba
        assert rel_ab.status == rel_ba.status
        assert rel_ab.trust == rel_ba.trust

    def test_get_faction_relations_returns_11(self, system):
        """每个势力对应 11 条关系记录"""
        rels = system.get_faction_relations("caocao")
        assert len(rels) == 11
        for rel in rels:
            assert "caocao" in (rel.faction_a, rel.faction_b)

    # ================================================================
    # can_attack 测试
    # ================================================================

    def test_can_attack_neutral(self, system):
        """中立状态下可以攻击"""
        assert system.can_attack("caocao", "liubei") is True

    def test_can_attack_war(self, system):
        """交战状态下可以攻击"""
        system.set_status("caocao", "liubei", DiplomaticStatus.WAR)
        assert system.can_attack("caocao", "liubei") is True

    def test_cannot_attack_alliance(self, system):
        """同盟状态下不能攻击"""
        system.set_status("caocao", "liubei", DiplomaticStatus.ALLIANCE, turn=1)
        assert system.can_attack("caocao", "liubei") is False

    def test_cannot_attack_truce(self, system):
        """停战状态下不能攻击"""
        system.set_status("caocao", "liubei", DiplomaticStatus.WAR)
        system.set_status("caocao", "liubei", DiplomaticStatus.TRUCE, turn=1)
        assert system.can_attack("caocao", "liubei") is False

    # ================================================================
    # 信任度变化测试
    # ================================================================

    def test_propose_alliance_increases_trust(self, system):
        """提出同盟：信任度 +5"""
        system.propose_alliance("caocao", "liubei")
        rel = system.get_relation("caocao", "liubei")
        assert rel.trust == 55

    def test_reject_alliance_decreases_trust(self, system):
        """拒绝同盟：信任度 -5"""
        system.reject_alliance("caocao", "liubei")
        rel = system.get_relation("caocao", "liubei")
        assert rel.trust == 45

    def test_declare_war_decreases_trust(self, system):
        """宣战（NEUTRAL -> WAR）：信任度 -30"""
        system.set_status("caocao", "liubei", DiplomaticStatus.WAR)
        rel = system.get_relation("caocao", "liubei")
        assert rel.status == DiplomaticStatus.WAR
        assert rel.trust == 20  # 50 - 30

    def test_break_alliance_punishment(self, system):
        """撕毁同盟（ALLIANCE -> WAR）：信任度 -50"""
        system.set_status("caocao", "liubei", DiplomaticStatus.ALLIANCE, turn=1)
        rel = system.get_relation("caocao", "liubei")
        assert rel.status == DiplomaticStatus.ALLIANCE
        assert rel.trust == 60  # 50 + 10

        system.set_status("caocao", "liubei", DiplomaticStatus.WAR)
        rel = system.get_relation("caocao", "liubei")
        assert rel.status == DiplomaticStatus.WAR
        assert rel.trust == 10  # 60 - 50

    def test_trust_clamped_to_zero(self, system):
        """信任度不低于 0"""
        system.set_status("caocao", "liubei", DiplomaticStatus.WAR)  # 50 -> 20
        system.set_status("caocao", "liubei", DiplomaticStatus.WAR)  # 20 -> -10, clamped to 0
        rel = system.get_relation("caocao", "liubei")
        assert rel.trust == 0

    def test_trust_clamped_to_100(self, system):
        """信任度不超过 100"""
        for _ in range(20):
            system.propose_alliance("caocao", "liubei")
        rel = system.get_relation("caocao", "liubei")
        assert rel.trust == 100

    # ================================================================
    # 同盟测试
    # ================================================================

    def test_form_alliance_sets_trust_and_end_turn(self, system):
        """结盟：信任度 +10，alliance_end_turn = turn + 12"""
        system.set_status("caocao", "liubei", DiplomaticStatus.ALLIANCE, turn=5)
        rel = system.get_relation("caocao", "liubei")
        assert rel.status == DiplomaticStatus.ALLIANCE
        assert rel.trust == 60
        assert rel.alliance_end_turn == 17  # 5 + 12
        assert rel.truce_end_turn is None

    def test_form_alliance_clears_truce(self, system):
        """结盟清除停战期限"""
        system.set_status("caocao", "liubei", DiplomaticStatus.WAR)
        system.set_status("caocao", "liubei", DiplomaticStatus.TRUCE, turn=3)
        rel = system.get_relation("caocao", "liubei")
        assert rel.truce_end_turn == 9  # 3 + 6

        system.set_status("caocao", "liubei", DiplomaticStatus.ALLIANCE, turn=5)
        rel = system.get_relation("caocao", "liubei")
        assert rel.status == DiplomaticStatus.ALLIANCE
        assert rel.truce_end_turn is None
        assert rel.alliance_end_turn == 17

    def test_alliance_expires(self, system):
        """同盟到期自动恢复中立"""
        system.set_status("caocao", "liubei", DiplomaticStatus.ALLIANCE, turn=5)
        rel = system.get_relation("caocao", "liubei")
        assert rel.status == DiplomaticStatus.ALLIANCE

        changes = system.update_turn(17)  # 5 + 12
        rel = system.get_relation("caocao", "liubei")
        assert rel.status == DiplomaticStatus.NEUTRAL
        assert rel.alliance_end_turn is None
        assert len(changes) == 1

    def test_alliance_not_expired_before_end_turn(self, system):
        """同盟未到期时保持同盟状态"""
        system.set_status("caocao", "liubei", DiplomaticStatus.ALLIANCE, turn=5)
        changes = system.update_turn(16)  # 不到 17
        rel = system.get_relation("caocao", "liubei")
        assert rel.status == DiplomaticStatus.ALLIANCE
        assert len(changes) == 0

    # ================================================================
    # 停战测试
    # ================================================================

    def test_truce_from_war_sets_end_turn(self, system):
        """交战转停战：truce_end_turn = turn + 6"""
        system.set_status("caocao", "liubei", DiplomaticStatus.WAR)
        system.set_status("caocao", "liubei", DiplomaticStatus.TRUCE, turn=5)
        rel = system.get_relation("caocao", "liubei")
        assert rel.status == DiplomaticStatus.TRUCE
        assert rel.truce_end_turn == 11  # 5 + 6
        assert rel.alliance_end_turn is None

    def test_truce_expires(self, system):
        """停战到期自动恢复中立"""
        system.set_status("caocao", "liubei", DiplomaticStatus.WAR)
        system.set_status("caocao", "liubei", DiplomaticStatus.TRUCE, turn=5)
        rel = system.get_relation("caocao", "liubei")
        assert rel.status == DiplomaticStatus.TRUCE
        assert rel.truce_end_turn == 11

        changes = system.update_turn(11)
        rel = system.get_relation("caocao", "liubei")
        assert rel.status == DiplomaticStatus.NEUTRAL
        assert rel.truce_end_turn is None
        assert len(changes) == 1

    # ================================================================
    # 辅助方法测试
    # ================================================================

    def test_is_allied(self, system):
        """is_allied 方法"""
        assert system.is_allied("caocao", "liubei") is False
        system.set_status("caocao", "liubei", DiplomaticStatus.ALLIANCE, turn=1)
        assert system.is_allied("caocao", "liubei") is True

    def test_is_at_war(self, system):
        """is_at_war 方法"""
        assert system.is_at_war("caocao", "liubei") is False
        system.set_status("caocao", "liubei", DiplomaticStatus.WAR)
        assert system.is_at_war("caocao", "liubei") is True

    def test_is_truce(self, system):
        """is_truce 方法"""
        assert system.is_truce("caocao", "liubei") is False
        system.set_status("caocao", "liubei", DiplomaticStatus.WAR)
        system.set_status("caocao", "liubei", DiplomaticStatus.TRUCE, turn=1)
        assert system.is_truce("caocao", "liubei") is True

    # ================================================================
    # 事件触发测试
    # ================================================================

    def test_on_city_captured(self, system):
        """城市被占领：信任度 -20"""
        rel_before = system.get_relation("caocao", "liubei")
        assert rel_before.trust == 50

        system.on_city_captured("caocao", "liubei")
        rel_after = system.get_relation("caocao", "liubei")
        assert rel_after.trust == 30  # 50 - 20

    def test_on_message_sent_positive(self, system):
        """发送积极外交消息：信任度 +2"""
        system.on_message_sent("caocao", "liubei", is_positive=True)
        rel = system.get_relation("caocao", "liubei")
        assert rel.trust == 52

    def test_on_message_sent_negative_no_change(self, system):
        """发送消极外交消息：不改变信任度"""
        system.on_message_sent("caocao", "liubei", is_positive=False)
        rel = system.get_relation("caocao", "liubei")
        assert rel.trust == 50  # 不变

    # ================================================================
    # 边界情况测试
    # ================================================================

    def test_multiple_faction_pairs_independent(self, system):
        """不同势力对关系互不影响"""
        system.set_status("caocao", "liubei", DiplomaticStatus.ALLIANCE, turn=1)
        system.set_status("sunjian", "liubei", DiplomaticStatus.WAR)

        assert system.get_status("caocao", "liubei") == DiplomaticStatus.ALLIANCE
        assert system.get_status("sunjian", "liubei") == DiplomaticStatus.WAR
        assert system.get_status("caocao", "sunjian") == DiplomaticStatus.NEUTRAL

    def test_update_turn_multiple_expirations(self, system):
        """多个同盟同时到期"""
        system.set_status("caocao", "liubei", DiplomaticStatus.ALLIANCE, turn=1)
        system.set_status("sunjian", "liubei", DiplomaticStatus.ALLIANCE, turn=1)

        changes = system.update_turn(13)  # 两者都是 1+12=13
        assert len(changes) == 2
        assert system.get_status("caocao", "liubei") == DiplomaticStatus.NEUTRAL
        assert system.get_status("sunjian", "liubei") == DiplomaticStatus.NEUTRAL

    def test_war_clears_alliance_end_turn(self, system):
        """宣战清除同盟截止回合"""
        system.set_status("caocao", "liubei", DiplomaticStatus.ALLIANCE, turn=1)
        assert system.get_relation("caocao", "liubei").alliance_end_turn == 13

        system.set_status("caocao", "liubei", DiplomaticStatus.WAR)
        rel = system.get_relation("caocao", "liubei")
        assert rel.alliance_end_turn is None
        assert rel.truce_end_turn is None
