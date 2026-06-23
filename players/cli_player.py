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
    DevelopCommand,
    RecruitCommand,
    AttackCommand,
    MessageCommand,
    City,
    GameObservation,
    General,
)
from game.random import GameRandom
from players.base_player import BasePlayer


class CLIPlayer(BasePlayer):
    """CLI 自动玩家——决策受性格参数驱动"""

    def __init__(self, faction: str, rng: GameRandom) -> None:
        super().__init__(faction)
        self._rng = rng
        self._msg_sent = False

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

    def get_commands(self, observation: GameObservation) -> List[Command]:
        commands: List[Command] = []
        turn = observation.turn

        # 每回合重置外交标志
        self._msg_sent = False

        enemy_ids: Set[str] = {c.id for c in observation.known_cities}
        enemy_factions = list({c.faction for c in observation.known_cities if c.faction != self.faction})

        # 外交（diplomacy > 0.3 的势力倾向外交, 每3回合发一次）
        if self._diplomacy > 0.3 and not self._msg_sent and enemy_factions and turn % 3 == 0:
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

            # 进攻（只要有兵就将领不必须）
            if (city.garrison >= attack_garrison
                    and city.gold >= attack_gold
                    and self._rng.random() < self._aggression * 1.3):
                target = self._find_attack_target(city, enemy_ids, observation)
                if target:
                    troops = min(city.garrison - 100, int(3000 * max(0.4, self._aggression)))
                    if troops >= 200:
                        gen = self._find_general_in_city(city.id, observation)
                        general_id = gen.id if gen else (observation.own_generals[0].id if observation.own_generals else "")
                        if general_id:
                            commands.append(AttackCommand(
                                faction=self.faction, turn=turn,
                                from_city=city.id, to_city=target,
                                troops=troops, general=general_id,
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
        for nid in city.neighbors:
            if nid in enemy_ids:
                return nid
        return ""
