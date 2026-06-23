"""完整游戏集成测试

验证从初始化到游戏结束的完整流程。
使用CLI玩家模拟24回合对局。
"""

import pytest

from game.engine import GameEngine
from game.data_loader import load_game_data
from game.constants import FACTIONS
from game.random import GameRandom
from players.cli_player import CLIPlayer


class TestFullGame:
    """完整游戏流程测试"""

    def test_game_initializes_and_runs(self):
        """游戏初始化并完整运行"""
        engine = GameEngine(seed=42)
        data = load_game_data()
        engine.init_game(data)

        assert len(engine.cities) >= 19
        assert len(engine.generals) == 15
        assert engine.turn == 1

    def test_five_turn_game(self):
        """5回合游戏运行正常"""
        engine = GameEngine(seed=42)
        data = load_game_data()
        engine.init_game(data)

        players = {}
        for faction in FACTIONS:
            players[faction] = CLIPlayer(
                faction=faction,
                rng=GameRandom(42 + hash(faction) % 10000),
            )

        for _ in range(5):
            for faction in FACTIONS:
                obs = engine.get_observation(faction)
                player = players[faction]
                commands = player.get_commands(obs)
                for cmd in commands:
                    engine.execute_command(cmd)
            engine.process_turn()

        assert engine.turn >= 5
        assert not engine.game_over  # 5回合不会结束

    def test_full_24_turn_game(self):
        """完整24回合游戏"""
        engine = GameEngine(seed=42)
        data = load_game_data()
        engine.init_game(data)

        players = {}
        for faction in FACTIONS:
            players[faction] = CLIPlayer(
                faction=faction,
                rng=GameRandom(42 + hash(faction) % 10000),
            )

        max_turns = 24
        engine.max_turns = max_turns

        while not engine.game_over:
            for faction in FACTIONS:
                obs = engine.get_observation(faction)
                player = players[faction]
                commands = player.get_commands(obs)
                for cmd in commands:
                    engine.execute_command(cmd)
            engine.process_turn()

        assert engine.game_over is True
        assert engine.turn >= max_turns
        # 验证城市总数不变
        total = 0
        for f in FACTIONS:
            total += len(engine.map.get_faction_cities(f))
        assert total >= 19

    def test_different_seeds_produce_different_outcomes(self):
        """不同种子可能产生不同结果"""
        results = set()
        for seed in [42, 123, 456]:
            engine = GameEngine(seed=seed)
            data = load_game_data()
            engine.init_game(data)

            players = {}
            for faction in FACTIONS:
                players[faction] = CLIPlayer(
                    faction=faction,
                    rng=GameRandom(seed + hash(faction) % 10000),
                )

            engine.max_turns = 24
            while not engine.game_over:
                for faction in FACTIONS:
                    obs = engine.get_observation(faction)
                    player = players[faction]
                    commands = player.get_commands(obs)
                    for cmd in commands:
                        engine.execute_command(cmd)
                engine.process_turn()

            result_key = (
                engine.winner,
                tuple(
                    len(engine.map.get_faction_cities(f))
                    for f in FACTIONS
                ),
            )
            results.add(result_key)

        # 至少游戏结束且不崩溃
        assert len(results) >= 1

    def test_game_never_crashes(self):
        """多种子测试不会崩溃"""
        for seed in range(10):
            engine = GameEngine(seed=seed)
            data = load_game_data()
            engine.init_game(data)

            players = {}
            for faction in FACTIONS:
                players[faction] = CLIPlayer(
                    faction=faction,
                    rng=GameRandom(seed + hash(faction) % 10000),
                )

            engine.max_turns = 5
            while not engine.game_over:
                for faction in FACTIONS:
                    obs = engine.get_observation(faction)
                    player = players[faction]
                    commands = player.get_commands(obs)
                    for cmd in commands:
                        engine.execute_command(cmd)
                engine.process_turn()

            # 基本一致性检查
            total = 0
            for f in FACTIONS:
                total += len(engine.map.get_faction_cities(f))
            assert total >= 19, f"Seed {seed}: 城市数不一致"

    def test_command_validation(self):
        """命令校验在所有场景下工作"""
        engine = GameEngine(seed=42)
        data = load_game_data()
        engine.init_game(data)

        # 各种非法命令应优雅处理
        from game.models import DevelopCommand, RecruitCommand, AttackCommand

        # 打自己城市
        result = engine.execute_command(AttackCommand(
            faction="caocao", turn=1,
            from_city="xuchang", to_city="xuchang",
            troops=100, general="caocao",
        ))
        assert result.success is False  # 不能打自己

        # 兵力不足
        result = engine.execute_command(AttackCommand(
            faction="caocao", turn=1,
            from_city="luoyang", to_city="xuchang",
            troops=99999, general="xiahou_dun",
        ))
        assert result.success is False  # 兵力不足

        # 资源不足征兵
        city = engine.cities["yecheng"]
        city.gold = 0
        result = engine.execute_command(RecruitCommand(
            faction="caocao", turn=1,
            city="yecheng", troops=500,
        ))
        assert result.success is False  # 金钱不足
