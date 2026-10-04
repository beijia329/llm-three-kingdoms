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
        """初始化：所有 12 方势力对的初始状态均为 NEUTRAL。

        ⚠️ v4.1.2 起**信任度不再统一为 50** —— 改为按史实推导
        （`personality.initial_trust()`：史实硬禁 > 184 年实际关系 > 相性距离）。
        故此处断言「等于该组合的史实初值」，而不是写死 50。
        """
        from game.personality import initial_trust

        relations = system.get_all_relations()
        assert len(relations) == 66  # C(12, 2)

        for key, rel in relations.items():
            assert rel.status == DiplomaticStatus.NEUTRAL
            assert rel.trust == initial_trust(rel.faction_a, rel.faction_b), (
                f"{key} 的初始信任度应为史实推导值，而非写死的 50"
            )
            assert rel.alliance_end_turn is None
            assert rel.truce_end_turn is None

    def test_init_trust_is_not_blank_slate(self, system):
        """反例守卫：初始信任度**不能**退化成"人人 50"的白板。

        白板是玩家实测反馈的根因之一（「曹操、刘备、孙坚居然互相都结盟」）：
        12 方在模型眼里完全对称 → 谁跟谁结盟纯看当回合随机 → 必然同质化。
        """
        trusts = {
            r.trust for r in system.get_all_relations().values()
        }
        assert len(trusts) > 1, f"所有关系的初始信任度都相同（{trusts}）——白板起手又回来了"

        # 具体核对几个史实锚点
        assert system.get_relation("yuanshao", "yuanshu").trust < 20, "袁绍×袁术应是死敌"
        assert system.get_relation("han", "zhangjiao").trust < 20, "汉室×黄巾应是死敌"
        assert system.get_relation("liubei", "gongsunzan").trust >= 75, "刘备×公孙瓒是故交"

    def test_get_relation_returns_correct_object(self, system):
        """get_relation 返回正确的 FactionRelation 对象"""
        rel = system.get_relation("caocao", "liubei")
        assert isinstance(rel, FactionRelation)
        assert rel.status == DiplomaticStatus.NEUTRAL
        # 初始信任度由史实推导（v4.1.2 起不再是白板 50）
        from game.personality import initial_trust
        assert rel.trust == initial_trust("caocao", "liubei")

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
        """提出同盟：信任度 +5

        ⚠️ 断言**增量**而非绝对值 —— 初始值自 v4.1.2 起按史实推导，
        写死绝对值会让本测试在调整史实表时无谓变红。
        """
        before = system.get_relation("caocao", "liubei").trust
        system.propose_alliance("caocao", "liubei")
        rel = system.get_relation("caocao", "liubei")
        assert rel.trust == before + 5

    def test_reject_alliance_decreases_trust(self, system):
        """拒绝同盟：信任度 -5"""
        before = system.get_relation("caocao", "liubei").trust
        system.reject_alliance("caocao", "liubei")
        rel = system.get_relation("caocao", "liubei")
        assert rel.trust == before - 5

    def test_declare_war_decreases_trust(self, system):
        """宣战（NEUTRAL -> WAR）：信任度 -30"""
        before = system.get_relation("caocao", "liubei").trust
        system.set_status("caocao", "liubei", DiplomaticStatus.WAR)
        rel = system.get_relation("caocao", "liubei")
        assert rel.status == DiplomaticStatus.WAR
        assert rel.trust == before - 30

    def test_break_alliance_punishment(self, system):
        """撕毁同盟（ALLIANCE -> WAR）：信任度 -50

        ⚠️ 用「刘备×公孙瓒」（初值 80）而非「曹操×刘备」（35）：
        后者 35 → 结盟 +10 = 45 → 再 -50 会触到下限被 clamp 到 0，
        那样测的就不再是「-50」这个增量本身了。
        """
        before = system.get_relation("liubei", "gongsunzan").trust
        system.set_status("liubei", "gongsunzan", DiplomaticStatus.ALLIANCE, turn=1)
        rel = system.get_relation("liubei", "gongsunzan")
        assert rel.status == DiplomaticStatus.ALLIANCE
        assert rel.trust == before + 10

        after_form = rel.trust
        system.set_status("liubei", "gongsunzan", DiplomaticStatus.WAR)
        rel = system.get_relation("liubei", "gongsunzan")
        assert rel.status == DiplomaticStatus.WAR
        assert rel.trust == after_form - 50

    def test_trust_clamped_to_zero(self, system):
        """信任度不低于 0"""
        system.set_status("caocao", "liubei", DiplomaticStatus.WAR)  # 各 -30
        system.set_status("caocao", "liubei", DiplomaticStatus.WAR)
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
        before = system.get_relation("caocao", "liubei").trust
        system.set_status("caocao", "liubei", DiplomaticStatus.ALLIANCE, turn=5)
        rel = system.get_relation("caocao", "liubei")
        assert rel.status == DiplomaticStatus.ALLIANCE
        assert rel.trust == before + 10
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
        before = system.get_relation("caocao", "liubei").trust

        system.on_city_captured("caocao", "liubei")
        rel_after = system.get_relation("caocao", "liubei")
        assert rel_after.trust == before - 20

    def test_on_message_sent_positive(self, system):
        """发送积极外交消息：信任度 +2"""
        before = system.get_relation("caocao", "liubei").trust
        system.on_message_sent("caocao", "liubei", is_positive=True)
        rel = system.get_relation("caocao", "liubei")
        assert rel.trust == before + 2

    def test_on_message_sent_negative_no_change(self, system):
        """发送消极外交消息：不改变信任度"""
        before = system.get_relation("caocao", "liubei").trust
        system.on_message_sent("caocao", "liubei", is_positive=False)
        rel = system.get_relation("caocao", "liubei")
        assert rel.trust == before  # 不变

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

    # ================================================================
    # 结盟两步谈判（#2，第三批）
    # ================================================================

    def test_resolve_accepts_at_or_above_threshold(self, system):
        """待回应的结盟请求：信任度达到门槛 → 结成 ALLIANCE。

        断言增量（+DIPLOMACY_TRUST_ALLIANCE_FORM）而非绝对值。
        """
        from game.constants import (
            DIPLOMACY_ALLIANCE_DURATION,
            DIPLOMACY_TRUST_ALLIANCE_FORM,
            DIPLOMACY_TRUST_MIN_FOR_ALLIANCE,
        )

        system.set_status("caocao", "yuanshao", DiplomaticStatus.PROPOSED, turn=1)
        rel = system.get_relation("caocao", "yuanshao")
        rel.trust = DIPLOMACY_TRUST_MIN_FOR_ALLIANCE  # 恰好踩在门槛上

        changes = system.resolve_proposals(turn=2)

        rel = system.get_relation("caocao", "yuanshao")
        assert rel.status == DiplomaticStatus.ALLIANCE
        assert rel.trust == DIPLOMACY_TRUST_MIN_FOR_ALLIANCE + DIPLOMACY_TRUST_ALLIANCE_FORM
        assert rel.alliance_end_turn == 2 + DIPLOMACY_ALLIANCE_DURATION
        assert ("caocao", "yuanshao", DiplomaticStatus.ALLIANCE) in changes

    def test_resolve_rejects_below_threshold(self, system):
        """待回应的结盟请求：信任度不足 → 退回 NEUTRAL 并扣信任度。"""
        from game.constants import (
            DIPLOMACY_TRUST_ALLIANCE_REJECT,
            DIPLOMACY_TRUST_MIN_FOR_ALLIANCE,
        )

        system.set_status("caocao", "yuanshao", DiplomaticStatus.PROPOSED, turn=1)
        low = DIPLOMACY_TRUST_MIN_FOR_ALLIANCE - 1
        system.get_relation("caocao", "yuanshao").trust = low

        changes = system.resolve_proposals(turn=2)

        rel = system.get_relation("caocao", "yuanshao")
        assert rel.status == DiplomaticStatus.NEUTRAL
        assert rel.trust == low + DIPLOMACY_TRUST_ALLIANCE_REJECT
        assert ("caocao", "yuanshao", DiplomaticStatus.NEUTRAL) in changes

    def test_resolve_ignores_non_proposed(self, system):
        """非 PROPOSED 的关系不得被 resolve_proposals 触碰。"""
        system.set_status("caocao", "liubei", DiplomaticStatus.WAR)
        before_war = system.get_relation("caocao", "liubei").trust
        system.set_status("sunjian", "liubei", DiplomaticStatus.ALLIANCE, turn=1)
        before_ally = system.get_relation("sunjian", "liubei").trust

        changes = system.resolve_proposals(turn=2)

        assert changes == []
        assert system.get_status("caocao", "liubei") == DiplomaticStatus.WAR
        assert system.get_relation("caocao", "liubei").trust == before_war
        assert system.get_status("sunjian", "liubei") == DiplomaticStatus.ALLIANCE
        assert system.get_relation("sunjian", "liubei").trust == before_ally
