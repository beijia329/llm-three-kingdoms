"""外交关系系统单元测试"""

import pytest

from game.systems.diplomacy_relation import DiplomacyRelationSystem
from game.models import DiplomaticStatus
from game.constants import FACTIONS


class TestDiplomacyRelation:
    """外交关系系统测试"""

    FACTIONS = list(FACTIONS.keys())

    @pytest.fixture
    def system(self) -> DiplomacyRelationSystem:
        return DiplomacyRelationSystem(self.FACTIONS)

    def test_init_all_neutral(self, system):
        """初始化后所有关系为中立"""
        rel = system.get_relation("caocao", "liubei")
        assert rel is not None
        assert rel.status == DiplomaticStatus.NEUTRAL
        assert rel.trust == 50

    def test_can_attack_neutral(self, system):
        """可以攻击中立势力"""
        assert system.can_attack("caocao", "liubei") is True

    def test_cannot_attack_alliance(self, system):
        """不能攻击同盟势力"""
        system.set_status("caocao", "liubei", DiplomaticStatus.ALLIANCE, turn=1)
        assert system.can_attack("caocao", "liubei") is False

    def test_cannot_attack_truce(self, system):
        """不能攻击停战势力"""
        system.set_status("caocao", "liubei", DiplomaticStatus.TRUCE, turn=1)
        assert system.can_attack("caocao", "liubei") is False

    def test_propose_alliance_increases_trust(self, system):
        """提出同盟后信任度+5"""
        system.propose_alliance("caocao", "liubei")
        rel = system.get_relation("caocao", "liubei")
        assert rel.trust == 55

    def test_form_alliance(self, system):
        """结盟后信任度+10，设置到期回合"""
        rel = system.set_status("caocao", "liubei", DiplomaticStatus.ALLIANCE, turn=5)
        assert rel.status == DiplomaticStatus.ALLIANCE
        assert rel.trust == 60  # 50 + 10
        assert rel.alliance_end_turn == 17  # 5 + 12

    def test_declare_war_decreases_trust(self, system):
        """宣战后信任度-30"""
        rel = system.set_status("caocao", "liubei", DiplomaticStatus.WAR, turn=1)
        assert rel.status == DiplomaticStatus.WAR
        assert rel.trust == 20  # 50 - 30

    def test_break_alliance_punishment(self, system):
        """破坏同盟信任度-50"""
        system.set_status("caocao", "liubei", DiplomaticStatus.ALLIANCE, turn=1)
        rel = system.set_status("caocao", "liubei", DiplomaticStatus.WAR, turn=2)
        assert rel.status == DiplomaticStatus.WAR
        assert rel.trust == 10  # 60 - 50

    def test_alliance_expires(self, system):
        """同盟到期后自动变为中立"""
        system.set_status("caocao", "liubei", DiplomaticStatus.ALLIANCE, turn=1)
        # alliance_end_turn = 1 + 12 = 13
        changes = system.update_turn(13)
        assert len(changes) == 1
        rel = system.get_relation("caocao", "liubei")
        assert rel.status == DiplomaticStatus.NEUTRAL
        assert rel.alliance_end_turn is None

    def test_truce_expires(self, system):
        """停战到期后自动变为中立"""
        system.set_status("caocao", "liubei", DiplomaticStatus.WAR, turn=1)
        system.set_status("caocao", "liubei", DiplomaticStatus.TRUCE, turn=2)
        # truce_end_turn = 2 + 6 = 8
        changes = system.update_turn(8)
        assert len(changes) == 1
        rel = system.get_relation("caocao", "liubei")
        assert rel.status == DiplomaticStatus.NEUTRAL
        assert rel.truce_end_turn is None

    def test_on_city_captured(self, system):
        """占领城市后信任度-20，状态变为交战"""
        system.on_city_captured("caocao", "liubei")
        rel = system.get_relation("caocao", "liubei")
        assert rel.trust == 30  # 50 - 20

    def test_on_message_sent(self, system):
        """发送消息后信任度+2"""
        system.on_message_sent("caocao", "liubei", is_positive=True)
        rel = system.get_relation("caocao", "liubei")
        assert rel.trust == 52

    def test_reject_alliance_decreases_trust(self, system):
        """拒绝同盟后信任度-5"""
        system.reject_alliance("caocao", "liubei")
        rel = system.get_relation("caocao", "liubei")
        assert rel.trust == 45

    def test_trust_clamped(self, system):
        """信任度在 [0, 100] 之间"""
        # 多次降信任度
        for _ in range(5):
            system.set_status("caocao", "liubei", DiplomaticStatus.WAR, turn=1)
        rel = system.get_relation("caocao", "liubei")
        assert rel.trust >= 0

        # 多次升信任度
        system.set_status("caocao", "liubei", DiplomaticStatus.NEUTRAL, turn=1)
        for _ in range(10):
            system.on_message_sent("caocao", "liubei", is_positive=True)
        rel = system.get_relation("caocao", "liubei")
        assert rel.trust <= 100

    def test_get_all_relations_count(self, system):
        """所有势力对数量 = n*(n-1)/2"""
        n = len(self.FACTIONS)
        expected = n * (n - 1) // 2
        relations = system.get_all_relations()
        assert len(relations) == expected

    def test_get_faction_relations(self, system):
        """获取指定势力的所有关系"""
        rels = system.get_faction_relations("caocao")
        assert len(rels) == len(self.FACTIONS) - 1
