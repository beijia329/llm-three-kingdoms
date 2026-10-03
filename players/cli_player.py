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


# ============================================================
# 平衡常量（v4.0「灭国压力」修复）
# ============================================================

ATTACK_FORCE_RATIO: float = 0.9
"""进攻所需兵力 / 目标守军的比例门槛。

🔴 2026-10-0X v4.0 新增（原为硬编码 1.0）。
满员时本城可派兵力 = 本城守军 − 100；而守军约与城市等级成正比
（CITY_LEVELS.initial_garrison：500/1000/2000/3500/5000）。
于是门槛 `troops >= tgt_garrison * 1.0` 在满员时等价于
`本城等级 > 目标等级`：同级城之间永久互不可攻 —— 最后一座城被同级邻居
永久豁免，这是「从不灭国」的绝对地板。必须 < 1.0 才能解开同级城互不可攻。

数据来源：tests/balance/data/exp15_landed_96t.json（落地版 G+A 下 top_share 0.28，
在 0.30 红线内）；对照组 G+A 无刹车时 top_share 冲到 0.49（单局 0.74）。
"""


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

        # [G 解将荒 2026-10-0X v4.0] 本回合已被派出的将领 id 集合。
        # 同一回合内不让同一名将领被多路复用（避免"一将多路"重复领兵超发）。
        assigned: Set[str] = set()

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
                    # 门槛分层：中立/无主城 → 低门槛扩张；敌城 → 兵力需达其守军
                    # ATTACK_FORCE_RATIO 倍才打（v4.0：1.0 → 0.9，解开同级城互不可攻）
                    if tgt_is_neutral:
                        confident = troops >= 200
                    else:
                        confident = (troops >= 200) and (
                            tgt_garrison == 0 or troops >= tgt_garrison * ATTACK_FORCE_RATIO
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
                        # [G 一将一路 2026-10-0X v4.0] 本地驻将也须避开本回合已派出者：
                        # 否则同一将领可能先被"调出"去领 A 城的兵、又被当作 C 城的本地
                        # 驻将再次选中，生成一条必被引擎拒绝的命令（白白浪费一次进攻）。
                        # 与 exp15 落地版 one_general 的 _USED_GEN 口径严格一致。
                        if gen is not None and gen.id in assigned:
                            gen = None
                        if gen is None:
                            # [G 解将荒 2026-10-0X v4.0] 出发城无本地驻将时，从
                            # 「位于己方城市中的空闲将领」里挑一名（引擎会自动调他前来
                            # 领兵）。不再因缺将而放弃进攻 —— 这是「无本地将领的城市
                            # 永久瘫痪 → 地图第 26~31 回合冻结」的直接解法。
                            gen = self._find_dispatchable_general(observation, assigned)
                        if gen:
                            assigned.add(gen.id)
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
        """找驻守在 city_id 的将领。

        🔴 2026-10-03 二次修复（v3.1）：删除原先末尾的
            `return obs.own_generals[0] if obs.own_generals else None`
        —— 那是**跨城兜底**，会把别的城的将领塞进 attack 命令，
        然后被 engine.py:508 `general.location != from_city.id` 拒绝。

        为什么 150fa87 只改调用处不够：调用处加了 `if gen:` 判断，
        但本函数在找不到本地将领时仍会返回「己方第一个将领」，
        `if gen:` 永远为真 → 兜底依然生效。
        实测（exp6_attack_reject，同seed 三次逐位一致）：
          修复前 general_not_in_city = 609/935（65.1%）
          150fa87 之后      =93/154（60.4%）← 仍大量存在
        改为真找不到就返回 None，调用处`if gen:` 才能真正拦住。
        """
        for g in obs.own_generals:
            if g.location == city_id:
                return g
        return None

    def _find_dispatchable_general(
        self, obs: GameObservation, assigned: Set[str]
    ) -> Optional[General]:
        """从「位于己方城市中的空闲将领」挑一名可调度者（引擎会自动调他前来领兵）。

        [G 解将荒 2026-10-0X v4.0] 与 engine._execute_attack 放宽后的校验同口径：
          - general.faction == self.faction（obs.own_generals 通常已保证，仍显式校验）
          - not general.is_captured
          - general.location 是己方城市（出现在 obs.own_cities 中）
          - 不在 assigned 中（同一回合不重复派同一名将领）

        选择规则 max(candidates, key=lambda g: (g.command, g.id))：统帅最高者优先，
        并列时按 id 二级排序 —— **不能只按 command**，否则同统帅并列时结果依赖
        obs.own_generals 的输入顺序，可能破坏确定性（本项目对可复现性有硬要求，
        见 tests/balance/pacing_lib）。
        """
        own_city_ids = {c.id for c in obs.own_cities}
        candidates = [
            g for g in obs.own_generals
            if g.faction == self.faction
            and not g.is_captured
            and g.location in own_city_ids
            and g.id not in assigned
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda g: (g.command, g.id))

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
