"""GameEngine 主类单元测试

测试引擎的初始化、命令执行、回合处理、胜利判定等核心流程。
这是整个游戏的整合层，所有子系统在此汇聚。
"""

import pytest

from game.models import (
    City, Army, General, Faction,
    Command, DevelopCommand, RecruitCommand, AttackCommand,
    RewardCommand, ExploreCommand, MessageCommand, RumorCommand,
)
from game.engine import GameEngine


class TestEngineInit:
    """引擎初始化测试"""

    def test_engine_creates_with_defaults(self):
        """默认初始化"""
        engine = GameEngine(seed=42)
        assert engine.turn == 1
        assert engine.max_turns == 24
        assert engine.game_over is False
        assert engine.winner is None
        assert engine.rng is not None

    def test_init_without_data(self):
        """空数据初始化"""
        engine = GameEngine(seed=42)
        assert len(engine.cities) == 0
        assert len(engine.armies) == 0
        assert len(engine.generals) == 0

    def test_init_with_game_data(self):
        """加载游戏数据初始化"""
        engine = GameEngine(seed=42)
        data = _make_game_data()
        engine.init_game(data)

        assert len(engine.cities) == 3
        assert len(engine.generals) == 3
        assert engine.map.get_city_count() == 3

    def test_init_sets_faction_cities(self):
        """初始化后各势力有对应城市"""
        engine = GameEngine(seed=42)
        data = _make_game_data()
        engine.init_game(data)

        wei_cities = engine.map.get_faction_cities("wei")
        assert "city_wei_1" in wei_cities


class TestCommandExecution:
    """命令执行测试"""

    def test_execute_develop(self):
        """执行发展命令"""
        engine = _make_initialized_engine()
        cmd = DevelopCommand(
            faction="wei", turn=1,
            city="city_wei_1", develop_type="economy",
        )
        result = engine.execute_command(cmd)
        assert result.success is True
        assert result.command_type == "develop"

    def test_execute_recruit(self):
        """执行征兵命令"""
        engine = _make_initialized_engine()
        # 多给点钱
        engine.cities["city_wei_1"].gold = 10000
        cmd = RecruitCommand(
            faction="wei", turn=1,
            city="city_wei_1", troops=500,
        )
        result = engine.execute_command(cmd)
        assert result.success is True

    def test_execute_invalid_command(self):
        """无效命令"""
        engine = _make_initialized_engine()
        cmd = Command(type="invalid", faction="wei", turn=1)
        result = engine.execute_command(cmd)
        assert result.success is False

    def test_execute_wrong_faction(self):
        """不是该势力的城市"""
        engine = _make_initialized_engine()
        cmd = DevelopCommand(
            faction="wei", turn=1,
            city="city_shu_1", develop_type="economy",
        )
        result = engine.execute_command(cmd)
        assert result.success is False

    def test_execute_attack(self):
        """执行进攻命令"""
        engine = _make_initialized_engine()
        cmd = AttackCommand(
            faction="wei", turn=1,
            from_city="city_wei_1", to_city="city_shu_1",
            troops=500, general="general_wei_1",
        )
        result = engine.execute_command(cmd)
        assert result.success is True
        # 应创建一支军队
        assert len(engine.armies) > 0

    def test_execute_reward(self):
        """执行赏赐命令"""
        engine = _make_initialized_engine()
        engine.cities["city_wei_1"].gold = 5000
        cmd = RewardCommand(
            faction="wei", turn=1,
            general="general_wei_1", gold=200,
        )
        result = engine.execute_command(cmd)
        assert result.success is True

    def test_execute_explore(self):
        """执行探索命令"""
        engine = _make_initialized_engine()
        cmd = ExploreCommand(
            faction="wei", turn=1,
            city="city_wei_1",
        )
        result = engine.execute_command(cmd)
        assert result.success is True

    def test_execute_message(self):
        """执行外交消息命令"""
        engine = _make_initialized_engine()
        cmd = MessageCommand(
            faction="wei", turn=1,
            to="shu", content="结盟吧",
        )
        result = engine.execute_command(cmd)
        assert result.success is True


class TestTurnProcessing:
    """回合处理测试"""

    def test_process_turn(self):
        """处理一个完整回合"""
        engine = _make_initialized_engine()
        result = engine.process_turn()

        assert result["turn"] == 1
        assert "cities_updated" in result

    def test_turn_increments(self):
        """回合数递增"""
        engine = _make_initialized_engine()

        engine.process_turn()
        assert engine.turn == 2

        engine.process_turn()
        assert engine.turn == 3

    def test_resource_production_happens(self):
        """回合处理产生资源"""
        engine = _make_initialized_engine()
        gold_before = engine.cities["city_wei_1"].gold

        engine.process_turn()

        assert engine.cities["city_wei_1"].gold > gold_before


class TestVictoryConditions:
    """胜利条件测试"""

    def test_game_not_over_initially(self):
        """初始状态游戏未结束"""
        engine = _make_initialized_engine()
        assert engine.game_over is False

    def test_max_turns_ends_game(self):
        """达到最大回合游戏结束"""
        engine = _make_initialized_engine()
        engine.turn = engine.max_turns

        engine.process_turn()
        assert engine.game_over is True
        # 三城平分，所以是平局（winner 可能是 None）
        # 至少有一个 winner 或者 game_over 为 True

    def test_faction_without_cities_loses(self):
        """无城市的势力失败"""
        engine = _make_initialized_engine()
        # 移除两个势力的所有城市（只剩一个势力）
        for city in engine.cities.values():
            city.faction = "wei"  # 全部给魏

        engine.process_turn()
        # 只剩一个势力，游戏结束
        assert engine.game_over is True
        assert engine.winner == "wei"


class TestFullGameFlow:
    """完整游戏流程测试"""

    def test_full_game_loop(self):
        """完整的游戏循环"""
        engine = _make_initialized_engine()

        # 模拟几个回合
        for turn_num in range(1, 6):
            # 给每个势力发发展命令
            for faction in ["wei", "shu", "wu"]:
                # 找一个该势力的城市
                city = None
                for c in engine.cities.values():
                    if c.faction == faction:
                        city = c
                        break
                if city and city.gold >= 300:
                    cmd = DevelopCommand(
                        faction=faction, turn=turn_num,
                        city=city.id, develop_type="economy",
                    )
                    engine.execute_command(cmd)

            engine.process_turn()
            assert engine.turn == turn_num + 1

        # 应该能正常运行5回合
        assert engine.turn == 6


class TestBattleResultApplication:
    """战斗结果应用测试"""

    def test_casualty_ratio_uses_initial_soldiers(self):
        """伤亡比例应基于战斗前初始兵力，而非战斗后剩余兵力"""
        engine = _make_initialized_engine()

        # 创建攻击方军队
        engine._army_counter += 1
        army = Army(
            id="army_test",
            faction="wei",
            general_id="general_wei_1",
            soldiers=1000,
            food=1000,
            food_consumption_per_turn=200,
            morale=80,
            status="besieging",
            from_city="city_wei_1",
            to_city="city_shu_1",
            progress=1.0,
            total_distance=1,
        )
        engine.armies["army_test"] = army

        # 手动构建战斗上下文：初始1000，战斗后剩余800，伤亡200
        from game.models import BattleContext, BattlePhase, BattleResult, BattleResultType, BattleType
        ctx = BattleContext(
            battle_id="test_battle",
            turn=1,
            attacker_faction="wei",
            defender_faction="shu",
            attacker_armies=["army_test"],
            attacker_total_soldiers=800,  # 战斗后剩余
            attacker_initial_soldiers=1000,  # 战斗前初始
            attacker_avg_morale=80.0,
            attacker_avg_command=70.0,
            defender_city="city_shu_1",
            defender_total_soldiers=500,
            defender_initial_soldiers=500,
            defender_avg_morale=50.0,
            defender_avg_command=50.0,
            battle_type=BattleType.SIEGE,
            battle_phase=BattlePhase.STREET,
            round_count=5,
        )
        result = BattleResult(
            battle_id="test_battle",
            battle_type=BattleType.SIEGE,
            result=BattleResultType.ATTACKER_WIN,
            attacker_casualties=200,
            defender_casualties=500,
            captured_city="city_shu_1",
        )

        engine._apply_battle_result(ctx, result)

        # 伤亡比例 = 200/1000 = 20%，军队剩余应为 1000 * 0.8 = 800
        # 如果按旧的 bug 用 800 作分母，会得到 200/800 = 25%，剩余 750
        assert army.soldiers == 800

    def test_reward_general_in_army(self):
        """出征中的将领也可以被赏赐，金钱从军队出发城市扣除"""
        engine = _make_initialized_engine()
        general = engine.generals["general_wei_1"]
        from_city = engine.cities["city_wei_1"]

        # 创建军队并指派将领
        engine._army_counter += 1
        army = Army(
            id="army_reward_test",
            faction="wei",
            general_id="general_wei_1",
            soldiers=500,
            food=500,
            food_consumption_per_turn=100,
            morale=80,
            status="marching",
            from_city="city_wei_1",
            to_city="city_shu_1",
            progress=0.5,
            total_distance=1,
        )
        engine.armies["army_reward_test"] = army
        general.location = "army_reward_test"

        from_city.gold = 500
        old_loyalty = general.loyalty

        cmd = RewardCommand(
            faction="wei", turn=1,
            general="general_wei_1", gold=200,
        )
        result = engine.execute_command(cmd)

        assert result.success is True
        assert from_city.gold == 300
        assert general.loyalty > old_loyalty


# ============================================================
# 辅助函数
# ============================================================

def _make_game_data() -> dict:
    """创建测试用游戏数据"""
    return {
        "cities": [
            {
                "id": "city_wei_1", "name": "魏城1", "faction": "wei", "level": 3,
                "wall_hp": 2000, "wall_max_hp": 2000,
                "gold": 1000, "food": 1000, "population": 30000,
                "morale": 70, "garrison": 2000,
                "position": {"q": 0, "r": 0}, "neighbors": ["city_shu_1"],
                "generals": ["general_wei_1"],
            },
            {
                "id": "city_shu_1", "name": "蜀城1", "faction": "shu", "level": 3,
                "wall_hp": 2000, "wall_max_hp": 2000,
                "gold": 1000, "food": 1000, "population": 30000,
                "morale": 70, "garrison": 2000,
                "position": {"q": 100, "r": 0}, "neighbors": ["city_wei_1", "city_wu_1"],
                "generals": ["general_shu_1"],
            },
            {
                "id": "city_wu_1", "name": "吴城1", "faction": "wu", "level": 3,
                "wall_hp": 2000, "wall_max_hp": 2000,
                "gold": 1000, "food": 1000, "population": 30000,
                "morale": 70, "garrison": 2000,
                "position": {"q": 200, "r": 0}, "neighbors": ["city_shu_1"],
                "generals": ["general_wu_1"],
            },
        ],
        "generals": [
            {
                "id": "general_wei_1", "name": "魏将", "faction": "wei",
                "command": 85, "politics": 70, "bravery": 80, "intelligence": 75,
                "loyalty": 80, "location": "city_wei_1",
            },
            {
                "id": "general_shu_1", "name": "蜀将", "faction": "shu",
                "command": 85, "politics": 70, "bravery": 80, "intelligence": 75,
                "loyalty": 80, "location": "city_shu_1",
            },
            {
                "id": "general_wu_1", "name": "吴将", "faction": "wu",
                "command": 85, "politics": 70, "bravery": 80, "intelligence": 75,
                "loyalty": 80, "location": "city_wu_1",
            },
        ],
        "map_topology": {
            "city_wei_1": ["city_shu_1"],
            "city_shu_1": ["city_wei_1", "city_wu_1"],
            "city_wu_1": ["city_shu_1"],
        },
    }


def _make_initialized_engine() -> GameEngine:
    """创建并初始化引擎"""
    engine = GameEngine(seed=42)
    data = _make_game_data()
    engine.init_game(data)
    return engine
