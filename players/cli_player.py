"""CLI 自动玩家（用于测试/AI对战）

提供自动化的命令生成逻辑，用于测试游戏引擎。
策略优先级：进攻 > 征兵 > 发展
"""

from __future__ import annotations

from typing import List, Optional, Set

from game.models import (
    Command,
    DevelopCommand,
    RecruitCommand,
    AttackCommand,
    City,
    GameObservation,
    General,
)
from game.random import GameRandom
from players.base_player import BasePlayer


class CLIPlayer(BasePlayer):
    """CLI 自动玩家"""

    def __init__(self, faction: str, rng: GameRandom) -> None:
        super().__init__(faction)
        self._rng = rng

    def get_commands(self, observation: GameObservation) -> List[Command]:
        commands: List[Command] = []
        turn = observation.turn

        # 敌方城市ID集合
        enemy_ids: Set[str] = {c.id for c in observation.known_cities}

        # 第一遍：军事行动（进攻 > 征兵）
        for city in observation.own_cities:
            border = any(nid in enemy_ids for nid in city.neighbors)

            if not border:
                continue  # 内陆城市，军事先放放

            # 边境城市：优先进攻
            if city.garrison >= 1500 and observation.own_generals:
                target = self._find_attack_target(city, enemy_ids, observation)
                if target:
                    troops = min(city.garrison - 200, 2000)
                    if troops >= 300:
                        # 找在该城市的将领
                        gen = self._find_general_in_city(city.id, observation)
                        if gen:
                            commands.append(AttackCommand(
                                faction=self.faction, turn=turn,
                                from_city=city.id, to_city=target,
                                troops=troops, general=gen.id,
                            ))
                            continue  # 已有进攻，该城市够了

            # 边境城市：补兵
            if city.gold >= 500 and city.garrison < 3000:
                troops = min(1000, city.gold // 2)
                commands.append(RecruitCommand(
                    faction=self.faction, turn=turn,
                    city=city.id, troops=troops,
                ))

        # 第二遍：发展（填满剩余命令槽）
        for city in observation.own_cities:
            if len(commands) >= 4:
                break
            if city.gold >= 400:
                dev_types = ["economy", "military", "culture"]
                dev_type = dev_types[(turn + len(commands)) % 3]
                commands.append(DevelopCommand(
                    faction=self.faction, turn=turn,
                    city=city.id, develop_type=dev_type,
                ))

        return commands[:4]  # 最多4个命令

    @staticmethod
    def _find_general_in_city(
        city_id: str, observation: GameObservation
    ) -> Optional[General]:
        """查找在指定城市的己方将领

        Args:
            city_id: 城市ID
            observation: 游戏观察

        Returns:
            将领对象，未找到返回 None
        """
        for g in observation.own_generals:
            if g.location == city_id:
                return g
        # 找不到时返回第一个将领（可能失败，但尽力而为）
        return observation.own_generals[0] if observation.own_generals else None

    @staticmethod
    def _find_attack_target(
        city: City,
        enemy_ids: Set[str],
        observation: GameObservation,
    ) -> str:
        """查找进攻目标

        Args:
            city: 进攻方城市
            enemy_ids: 敌方城市ID集合
            observation: 游戏观察

        Returns:
            目标城市ID，无可攻击目标返回空字符串
        """
        for nid in city.neighbors:
            if nid in enemy_ids:
                return nid
        return ""
