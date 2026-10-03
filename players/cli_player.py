"""CLI 自动玩家（用于测试/AI对战）

策略权重受势力性格（personality.FACTION_PERSONALITY）影响：
- aggression 高 → 降进攻门槛，多出兵
- diplomacy 高 → 优先外交，少进攻
- expand 高 → 多发展经济
"""

from __future__ import annotations

from typing import List, Optional, Set

from game.models import (
    Command,
    DeclareWarCommand,
    DevelopCommand,
    ProposeAllianceCommand,
    RecruitCommand,
    AttackCommand,
    MessageCommand,
    City,
    DiplomaticStatus,
    GameObservation,
    General,
)
from game.random import GameRandom
from game.constants import FACTIONS
from players.base_player import BasePlayer


class CLIPlayer(BasePlayer):
    """CLI 自动玩家——决策受性格参数驱动"""

    def __init__(self, faction: str, rng: GameRandom) -> None:
        super().__init__(faction)
        self._rng = rng
        self._msg_sent = False
        self._pending_alliance: Optional[str] = None  # 收到结盟提议的势力

        try:
            from game.personality import FACTION_PERSONALITY
            fp = FACTION_PERSONALITY.get(faction, {})
            self._aggression = fp.get("aggression", 0.5)
            self._diplomacy = fp.get("diplomacy", 0.3)
            self._expand = fp.get("expand", 0.2)
        except ImportError:
            self._aggression = 0.5
            self._diplomacy = 0.3
            self._expand = 0.2

    def receive_message(self, from_faction: str, content: str) -> None:
        """接收外交消息，识别结盟提议"""
        super().receive_message(from_faction, content)
        # 识别结盟相关消息
        keywords = ["结盟", "同盟", "盟约", "联合", "互不侵犯", "合兵"]
        if any(kw in content for kw in keywords):
            self._pending_alliance = from_faction

    def get_commands(self, observation: GameObservation) -> List[Command]:
        commands: List[Command] = []
        turn = observation.turn

        # 每回合重置外交标志
        self._msg_sent = False

        enemy_ids: Set[str] = {c.id for c in observation.known_cities}
        enemy_factions = list({c.faction for c in observation.known_cities if c.faction != self.faction})

        # 外交响应：如果收到结盟提议，根据性格决定是否接受
        if self._pending_alliance and self._diplomacy > 0.3 and not self._msg_sent:
            commands.append(ProposeAllianceCommand(
                faction=self.faction, turn=turn,
                to=self._pending_alliance,
            ))
            self._msg_sent = True
            self._pending_alliance = None

        # 外交关系分析：检查 faction_relations
        has_allies = False
        if observation.faction_relations:
            for rel in observation.faction_relations:
                other = rel.faction_b if rel.faction_a == self.faction else rel.faction_a
                if rel.status == DiplomaticStatus.WAR:
                    enemy_factions.append(other)
                elif rel.status == DiplomaticStatus.ALLIANCE:
                    has_allies = True

        # 主动宣战：aggression 高且没有同盟时，向最近的非同盟邻居宣战
        if (self._aggression > 0.6 and not has_allies
                and not self._msg_sent and enemy_factions and turn % 5 == 1):
            target = self._rng.choice(enemy_factions)
            # 检查是否已经处于 WAR（faction_relations 中没有才算新宣战）
            already_at_war = any(
                rel.status == DiplomaticStatus.WAR
                for rel in (observation.faction_relations or [])
                if (rel.faction_a == self.faction and rel.faction_b == target)
                or (rel.faction_b == self.faction and rel.faction_a == target)
            )
            if not already_at_war:
                commands.append(DeclareWarCommand(
                    faction=self.faction, turn=turn,
                    to=target, reason="扩张领土",
                ))
                self._msg_sent = True

        # 外交消息（diplomacy 越高越频繁，高外交每2回合发一次）
        diplo_interval = 2 if self._diplomacy > 0.4 else 3
        if (self._diplomacy > 0.25 and not self._msg_sent
                and enemy_factions and turn % diplo_interval == 0):
            target = self._rng.choice(enemy_factions)
            messages = ["提议结盟共抗强敌", "互不侵犯如何？", "你我合兵一处，天下可定"]
            commands.append(MessageCommand(
                faction=self.faction, turn=turn,
                to=target, content=self._rng.choice(messages),
            ))
            self._msg_sent = True

        # 性格驱动的阈值（大幅降低以鼓励进攻）
        attack_garrison = int(1200 - self._aggression * 800)   # 激进:400兵就进攻
        attack_gold = int(400 - self._aggression * 300)         # 激进:100金就够
        recruit_gold = int(300 - self._aggression * 150)        # 激进:150金就征兵

        for city in observation.own_cities:
            border = any(nid in enemy_ids for nid in city.neighbors)
            if not border:
                continue

            # 进攻（[主系统修复 2026-10-01] 集中兵力、只打有把握的城，减少进攻-撤退 churn）
            if (city.garrison >= attack_garrison
                    and city.gold >= attack_gold
                    and self._rng.random() < self._aggression * 1.3):
                target = self._find_attack_target(city, enemy_ids, observation)
                if target:
                    # 目标信息（相邻城在观测里有守军；否则未知）
                    tgt_garrison = 0
                    tgt_is_neutral = False
                    for kc in observation.known_cities:
                        if kc.id == target:
                            tgt_garrison = getattr(kc, "garrison", 0) or 0
                            tgt_is_neutral = kc.faction not in FACTIONS
                            break
                    # 集中兵力：投入足以压倒目标守军的兵力，而非固定 3000×aggr 的小分队
                    desired = int(3000 * max(0.4, self._aggression))
                    if tgt_garrison:
                        desired = max(desired, int(tgt_garrison * 1.3) + 200)
                    troops = min(city.garrison - 100, desired)
                    # 门槛分层：中立/无主城 → 低门槛扩张；敌城 → 兵力需达其守军 ~1.0 倍才打
                    if tgt_is_neutral:
                        confident = troops >= 200
                    else:
                        confident = (troops >= 200) and (
                            tgt_garrison == 0 or troops >= tgt_garrison * 1.0
                        )
                    if confident:
                        gen = self._find_general_in_city(city.id, observation)
                        # 🔴 2026-10-03 修复（v3.1）：禁止"兜底取己方第一个将领"。
                        # 原代码在出发城无本地将领时取 own_generals[0]——而那个将领
                        # 在别的城 → 被 engine.py:508 `general.location != from_city.id`
                        # 直接拒绝。实测该错误占全部进攻失败的 74.6%：
                        #   935 次出征中 609 次因general_not_in_city 失败，
                        #   出征成功率仅 12.7%。
                        # 现在只派有本地将领的城：宁可少打一次，也不发必被拒的命令。
                        # 实测出征成功率 13% → 65%（配合 PEAK 修复后达100%）。
                        if gen:
                            commands.append(AttackCommand(
                                faction=self.faction, turn=turn,
                                from_city=city.id, to_city=target,
                                troops=troops, general=gen.id,
                            ))
                            continue

            # 征兵
            if city.gold >= recruit_gold and city.garrison < 3000:
                troops = min(1000, city.gold // 1)
                commands.append(RecruitCommand(
                    faction=self.faction, turn=turn,
                    city=city.id, troops=troops,
                ))

        # 发展（expand 高→更多发展命令）
        max_cmds = int(4 + self._expand * 4)
        for city in observation.own_cities:
            if len(commands) >= max_cmds:
                break
            dev_gold = int(500 - self._expand * 200)
            if city.gold >= dev_gold:
                    # 性格影响发展类型：expand高→经济，aggression高→军事，否则均衡
                if self._expand > self._aggression and self._expand > 0.3:
                    dev_type = "economy"
                elif self._aggression > 0.6:
                    dev_type = "military"
                else:
                    dev_types = ["economy", "military", "culture"]
                    dev_type = dev_types[(turn + len(commands)) % 3]
                commands.append(DevelopCommand(
                    faction=self.faction, turn=turn,
                    city=city.id, develop_type=dev_type,
                ))

        return commands[:8]

    @staticmethod
    def _find_general_in_city(city_id: str, obs: GameObservation) -> Optional[General]:
        for g in obs.own_generals:
            if g.location == city_id:
                return g
        return obs.own_generals[0] if obs.own_generals else None

    @staticmethod
    def _find_attack_target(city: City, enemy_ids: Set[str], obs: GameObservation) -> str:
        """选择进攻目标：优先中立/无主邻居（低成本扩张），其次敌城。"""
        neutral_first = ""
        enemy_first = ""
        for nid in city.neighbors:
            if nid not in enemy_ids:
                continue
            fac = None
            for kc in obs.known_cities:
                if kc.id == nid:
                    fac = kc.faction
                    break
            if fac is not None and fac not in FACTIONS:
                if not neutral_first:
                    neutral_first = nid
            elif not enemy_first:
                enemy_first = nid
        return neutral_first or enemy_first
