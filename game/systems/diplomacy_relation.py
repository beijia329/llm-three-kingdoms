"""外交关系系统

管理势力之间的外交关系状态：
- 关系状态：交战/中立/同盟/停战
- 信任度：0-100
- 同盟/停战的期限管理
- 外交状态对游戏行为的影响（如不能攻击同盟）
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from game.constants import (
    DIPLOMACY_TRUST_MAX,
    DIPLOMACY_TRUST_MIN,
    DIPLOMACY_TRUST_ALLIANCE_FORM,
    DIPLOMACY_TRUST_ALLIANCE_PROPOSE,
    DIPLOMACY_TRUST_ALLIANCE_REJECT,
    DIPLOMACY_TRUST_DECLARE_WAR,
    DIPLOMACY_TRUST_BREAK_ALLIANCE,
    DIPLOMACY_TRUST_CAPTURE_CITY,
    DIPLOMACY_TRUST_MESSAGE_POSITIVE,
    DIPLOMACY_TRUST_MIN_FOR_ALLIANCE,
    DIPLOMACY_ALLIANCE_DURATION,
    DIPLOMACY_TRUCE_DURATION,
)
from game.models import DiplomaticStatus, FactionRelation

logger = logging.getLogger(__name__)


class DiplomacyRelationSystem:
    """外交关系系统

    维护所有势力对之间的外交关系状态。
    使用有序元组 (faction_a, faction_b) 作为键，确保唯一性。
    """

    def __init__(self, factions: List[str]) -> None:
        """初始化外交关系系统

        Args:
            factions: 所有势力ID列表
        """
        self._relations: Dict[Tuple[str, str], FactionRelation] = {}
        self._factions = list(factions)

        # 初始化所有势力对的**史实**关系（v4.1.2）
        #
        # 🔴 此前是白板起手（全部 `NEUTRAL, trust=50`），导致 12 方在模型眼里
        #    完全对称 → 谁跟谁结盟纯看当回合随机 → 玩家实测反馈
        #    「曹操、刘备、孙坚居然互相都结盟，破坏历史沉浸感」。
        #    现在初始信任度由 `personality.initial_trust()` 按
        #    史实硬禁 > 184 年实际关系 > 相性距离 三级推导得出。
        from game.personality import initial_trust

        for i, fa in enumerate(factions):
            for fb in factions[i + 1:]:
                key = self._make_key(fa, fb)
                self._relations[key] = FactionRelation(
                    faction_a=fa,
                    faction_b=fb,
                    status=DiplomaticStatus.NEUTRAL,
                    trust=initial_trust(fa, fb),
                )

    @staticmethod
    def _make_key(fa: str, fb: str) -> Tuple[str, str]:
        """生成关系键（有序，确保唯一性）"""
        return (fa, fb) if fa < fb else (fb, fa)

    def get_relation(self, fa: str, fb: str) -> Optional[FactionRelation]:
        """获取两个势力之间的关系

        Args:
            fa: 势力A
            fb: 势力B

        Returns:
            关系对象，不存在返回 None
        """
        return self._relations.get(self._make_key(fa, fb))

    def get_all_relations(self) -> Dict[Tuple[str, str], FactionRelation]:
        """获取所有关系"""
        return dict(self._relations)

    def get_faction_relations(self, faction: str) -> List[FactionRelation]:
        """获取指定势力的所有外交关系

        Args:
            faction: 势力ID

        Returns:
            该势力与其他所有势力的关系列表
        """
        return [
            rel for key, rel in self._relations.items()
            if faction in key
        ]

    def get_status(self, fa: str, fb: str) -> DiplomaticStatus:
        """获取两个势力之间的外交状态

        Args:
            fa: 势力A
            fb: 势力B

        Returns:
            外交状态，无记录返回 NEUTRAL
        """
        rel = self.get_relation(fa, fb)
        return rel.status if rel else DiplomaticStatus.NEUTRAL

    def is_allied(self, fa: str, fb: str) -> bool:
        """判断两个势力是否为同盟"""
        return self.get_status(fa, fb) == DiplomaticStatus.ALLIANCE

    def is_at_war(self, fa: str, fb: str) -> bool:
        """判断两个势力是否交战"""
        return self.get_status(fa, fb) == DiplomaticStatus.WAR

    def is_truce(self, fa: str, fb: str) -> bool:
        """判断两个势力是否停战"""
        return self.get_status(fa, fb) == DiplomaticStatus.TRUCE

    def can_attack(self, attacker: str, defender: str) -> bool:
        """判断攻击方是否可以攻击防守方

        同盟和停战期间不能攻击。

        Args:
            attacker: 攻击方势力
            defender: 防守方势力

        Returns:
            可以攻击返回 True
        """
        status = self.get_status(attacker, defender)
        return status not in (DiplomaticStatus.ALLIANCE, DiplomaticStatus.TRUCE)

    def change_trust(self, fa: str, fb: str, delta: int) -> int:
        """改变两个势力之间的信任度

        Args:
            fa: 势力A
            fb: 势力B
            delta: 信任度变化量（正数增加，负数减少）

        Returns:
            变化后的信任度
        """
        key = self._make_key(fa, fb)
        rel = self._relations.get(key)
        if rel is None:
            return 50
        rel.trust = max(DIPLOMACY_TRUST_MIN, min(DIPLOMACY_TRUST_MAX, rel.trust + delta))
        return rel.trust

    def set_status(
        self,
        fa: str,
        fb: str,
        status: DiplomaticStatus,
        turn: int = 0,
    ) -> FactionRelation:
        """设置两个势力之间的外交状态

        状态变更时自动调整信任度。

        Args:
            fa: 势力A
            fb: 势力B
            status: 新状态
            turn: 当前回合（用于计算同盟/停战到期）

        Returns:
            更新后的关系对象
        """
        key = self._make_key(fa, fb)
        rel = self._relations.get(key)
        if rel is None:
            rel = FactionRelation(faction_a=fa, faction_b=fb)
            self._relations[key] = rel

        old_status = rel.status
        rel.status = status

        # 根据状态变更调整信任度
        if status == DiplomaticStatus.ALLIANCE and old_status != DiplomaticStatus.ALLIANCE:
            rel.trust = max(DIPLOMACY_TRUST_MIN, min(DIPLOMACY_TRUST_MAX,
                rel.trust + DIPLOMACY_TRUST_ALLIANCE_FORM))
            rel.alliance_end_turn = turn + DIPLOMACY_ALLIANCE_DURATION
            rel.truce_end_turn = None
        elif status == DiplomaticStatus.WAR:
            if old_status == DiplomaticStatus.ALLIANCE:
                rel.trust = max(DIPLOMACY_TRUST_MIN, min(DIPLOMACY_TRUST_MAX,
                    rel.trust + DIPLOMACY_TRUST_BREAK_ALLIANCE))
            else:
                rel.trust = max(DIPLOMACY_TRUST_MIN, min(DIPLOMACY_TRUST_MAX,
                    rel.trust + DIPLOMACY_TRUST_DECLARE_WAR))
            rel.alliance_end_turn = None
            rel.truce_end_turn = None
        elif status == DiplomaticStatus.TRUCE and old_status == DiplomaticStatus.WAR:
            rel.truce_end_turn = turn + DIPLOMACY_TRUCE_DURATION
            rel.alliance_end_turn = None
        elif status == DiplomaticStatus.NEUTRAL:
            rel.alliance_end_turn = None
            rel.truce_end_turn = None

        return rel

    def propose_alliance(self, fa: str, fb: str) -> FactionRelation:
        """提出同盟（增加信任度，等待对方响应）"""
        self.change_trust(fa, fb, DIPLOMACY_TRUST_ALLIANCE_PROPOSE)
        return self.get_relation(fa, fb)

    def reject_alliance(self, fa: str, fb: str) -> FactionRelation:
        """拒绝同盟（降低信任度）"""
        self.change_trust(fa, fb, DIPLOMACY_TRUST_ALLIANCE_REJECT)
        return self.get_relation(fa, fb)

    def resolve_proposals(self, turn: int) -> List[Tuple[str, str, DiplomaticStatus]]:
        """结算所有待回应的结盟请求（两步谈判第二步，第三批 #2）。

        上一回合 `_execute_propose_alliance` 把状态置成了 PROPOSED（并加了信任度），
        本回合在这里决定「对方答不答应」：

        - 信任度仍达到门槛 `DIPLOMACY_TRUST_MIN_FOR_ALLIANCE` → 结为 ALLIANCE
          （走 `set_status(ALLIANCE)`：信任度 +`DIPLOMACY_TRUST_ALLIANCE_FORM`、
           并写入同盟到期回合）
        - 否则 → 退回 NEUTRAL，按 `reject_alliance` 扣信任度（让该方法复活）

        门槛之上再判一次、而不是提出即成立，是为了给「提出到回应之间」留出
        反应窗口：对方若在此期间宣战或夺城，信任度掉下来，请求就落空。

        遍历按关系键排序，保证确定性（ADR-0002）。

        Returns:
            状态变更列表 [(fa, fb, new_status), ...]
        """
        changes: List[Tuple[str, str, DiplomaticStatus]] = []
        for key in sorted(self._relations.keys()):
            rel = self._relations[key]
            if rel.status != DiplomaticStatus.PROPOSED:
                continue
            fa, fb = key
            if rel.trust >= DIPLOMACY_TRUST_MIN_FOR_ALLIANCE:
                self.set_status(fa, fb, DiplomaticStatus.ALLIANCE, turn=turn)
                changes.append((fa, fb, DiplomaticStatus.ALLIANCE))
                logger.info("结盟请求获准: %s <-> %s", fa, fb)
            else:
                self.reject_alliance(fa, fb)
                self.set_status(fa, fb, DiplomaticStatus.NEUTRAL, turn=turn)
                changes.append((fa, fb, DiplomaticStatus.NEUTRAL))
                logger.info("结盟请求被拒: %s <-> %s", fa, fb)
        return changes

    def on_city_captured(self, attacker: str, defender: str) -> None:
        """城市被占领时的外交影响"""
        self.change_trust(attacker, defender, DIPLOMACY_TRUST_CAPTURE_CITY)

    def on_message_sent(self, from_faction: str, to_faction: str, is_positive: bool = True) -> None:
        """发送外交消息时的信任度影响"""
        if is_positive:
            self.change_trust(from_faction, to_faction, DIPLOMACY_TRUST_MESSAGE_POSITIVE)

    def update_turn(self, turn: int) -> List[Tuple[str, str, DiplomaticStatus]]:
        """每回合更新：检查同盟/停战是否到期

        Args:
            turn: 当前回合

        Returns:
            状态变更列表 [(fa, fb, new_status), ...]
        """
        changes: List[Tuple[str, str, DiplomaticStatus]] = []
        for key, rel in self._relations.items():
            if rel.status == DiplomaticStatus.ALLIANCE and rel.alliance_end_turn is not None:
                if turn >= rel.alliance_end_turn:
                    rel.status = DiplomaticStatus.NEUTRAL
                    rel.alliance_end_turn = None
                    changes.append((*key, DiplomaticStatus.NEUTRAL))
                    logger.info("同盟到期: %s <-> %s", key[0], key[1])
            elif rel.status == DiplomaticStatus.TRUCE and rel.truce_end_turn is not None:
                if turn >= rel.truce_end_turn:
                    rel.status = DiplomaticStatus.NEUTRAL
                    rel.truce_end_turn = None
                    changes.append((*key, DiplomaticStatus.NEUTRAL))
                    logger.info("停战到期: %s <-> %s", key[0], key[1])
        return changes
