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
        assert engine.max_turns == 192
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

        faction_cities = [c.id for c in engine.cities.values() if c.faction == "caocao"]
        assert "city_caocao_1" in faction_cities


class TestCommandExecution:
    """命令执行测试"""

    def test_execute_develop(self):
        """执行发展命令"""
        engine = _make_initialized_engine()
        cmd = DevelopCommand(
            faction="caocao", turn=1,
            city="city_caocao_1", develop_type="economy",
        )
        result = engine.execute_command(cmd)
        assert result.success is True
        assert result.command_type == "develop"

    def test_execute_recruit(self):
        """执行征兵命令"""
        engine = _make_initialized_engine()
        # 多给点钱
        engine.cities["city_caocao_1"].gold = 10000
        cmd = RecruitCommand(
            faction="caocao", turn=1,
            city="city_caocao_1", troops=500,
        )
        result = engine.execute_command(cmd)
        assert result.success is True

    def test_execute_invalid_command(self):
        """无效命令"""
        engine = _make_initialized_engine()
        cmd = Command(type="invalid", faction="caocao", turn=1)
        result = engine.execute_command(cmd)
        assert result.success is False

    def test_execute_wrong_faction(self):
        """不是该势力的城市"""
        engine = _make_initialized_engine()
        cmd = DevelopCommand(
            faction="caocao", turn=1,
            city="city_liubei_1", develop_type="economy",
        )
        result = engine.execute_command(cmd)
        assert result.success is False

    def test_execute_attack(self):
        """执行进攻命令"""
        engine = _make_initialized_engine()
        cmd = AttackCommand(
            faction="caocao", turn=1,
            from_city="city_caocao_1", to_city="city_liubei_1",
            troops=500, general="general_caocao_1",
        )
        result = engine.execute_command(cmd)
        assert result.success is True
        # 应创建一支军队
        assert len(engine.armies) > 0

    def test_execute_reward(self):
        """执行赏赐命令"""
        engine = _make_initialized_engine()
        engine.cities["city_caocao_1"].gold = 5000
        cmd = RewardCommand(
            faction="caocao", turn=1,
            general="general_caocao_1", gold=200,
        )
        result = engine.execute_command(cmd)
        assert result.success is True

    def test_execute_explore(self):
        """执行探索命令"""
        engine = _make_initialized_engine()
        cmd = ExploreCommand(
            faction="caocao", turn=1,
            city="city_caocao_1",
        )
        result = engine.execute_command(cmd)
        assert result.success is True

    def test_execute_message(self):
        """执行外交消息命令"""
        engine = _make_initialized_engine()
        cmd = MessageCommand(
            faction="caocao", turn=1,
            to="liubei", content="结盟吧",
        )
        result = engine.execute_command(cmd)
        assert result.success is True

    def test_execute_propose_alliance(self):
        """执行提出同盟命令 — 用一对**史实允许且信任度足够**的组合。

        ⚠️ v4.1.2 起结盟有两道门槛：史实硬禁（`FORBIDDEN_ALLIANCE`）
        与信任度下限（`DIPLOMACY_TRUST_MIN_FOR_ALLIANCE` = 45）。
        原来的「曹操→刘备」信任度仅 35，已被结构性挡住（这正是修玩家反馈的
        「曹操、刘备、孙坚居然互相都结盟」所必需的行为）。
        本测试改用「曹操→袁绍」——184 年同为何进心腹、初值 65。
        """
        engine = _make_initialized_engine()
        from game.models import ProposeAllianceCommand, DiplomaticStatus
        cmd = ProposeAllianceCommand(faction="caocao", turn=1, to="yuanshao")
        result = engine.execute_command(cmd)
        assert result.success is True
        status = engine._diplomacy_relation_system.get_status("caocao", "yuanshao")
        assert status == DiplomaticStatus.ALLIANCE

    def test_alliance_blocked_for_historical_nemesis(self):
        """史实宿敌不得结盟（硬拒绝，不是概率降低）。"""
        engine = _make_initialized_engine()
        from game.models import ProposeAllianceCommand, DiplomaticStatus

        for a, b in [("yuanshao", "yuanshu"), ("han", "zhangjiao"),
                     ("dongzhuo", "caocao"), ("sunjian", "liubiao")]:
            cmd = ProposeAllianceCommand(faction=a, turn=1, to=b)
            result = engine.execute_command(cmd)
            assert result.success is False, f"{a}×{b} 是史实宿敌，不该能结盟"
            status = engine._diplomacy_relation_system.get_status(a, b)
            assert status != DiplomaticStatus.ALLIANCE

    def test_alliance_blocked_when_trust_too_low(self):
        """信任度不足时不得结盟 —— 让 `trust` 成为真正的判据。

        反例守卫：在 v4.1.2 之前 `trust` 只被显示、从不参与任何决策，
        属于装饰。若有人把这道门槛去掉，本测试会红。
        """
        engine = _make_initialized_engine()
        from game.models import ProposeAllianceCommand, DiplomaticStatus
        from game.constants import DIPLOMACY_TRUST_MIN_FOR_ALLIANCE as MIN
        from game.personality import initial_trust

        # 找一对「非硬禁、但初始信任度低于门槛」的组合
        pair = next(
            (a, b)
            for a in ("caocao", "liubei")
            for b in ("sunjian", "yuanshu", "mateng", "liubiao")
            if a != b and initial_trust(a, b) < MIN
        )
        a, b = pair
        assert engine._diplomacy_relation_system.get_relation(a, b).trust < MIN

        result = engine.execute_command(
            ProposeAllianceCommand(faction=a, turn=1, to=b)
        )
        assert result.success is False, f"{a}×{b} 信任度不足 {MIN}，不该能结盟"
        assert "信任度" in result.description

    def test_alliance_becomes_possible_after_trust_buildup(self):
        """信任度是可以"攒"出来的：信使往来把它抬过门槛后即可结盟。

        这条保证门槛不是死路——否则「竞争」关系永远无法结盟，
        外交就失去了投资意义。
        """
        engine = _make_initialized_engine()
        from game.models import ProposeAllianceCommand, DiplomaticStatus
        from game.constants import DIPLOMACY_TRUST_MIN_FOR_ALLIANCE as MIN

        a, b = "caocao", "liubei"  # 初值 35（竞争）
        system = engine._diplomacy_relation_system
        assert system.get_relation(a, b).trust < MIN

        # 攒到门槛之上（走真实的 change_trust 路径）
        guard = 0
        while system.get_relation(a, b).trust < MIN and guard < 50:
            system.change_trust(a, b, 2)
            guard += 1
        assert system.get_relation(a, b).trust >= MIN

        result = engine.execute_command(
            ProposeAllianceCommand(faction=a, turn=1, to=b)
        )
        assert result.success is True, "信任度攒够后应当允许结盟"
        assert system.get_status(a, b) == DiplomaticStatus.ALLIANCE

    def test_execute_declare_war(self):
        """执行宣战命令"""
        engine = _make_initialized_engine()
        from game.models import DeclareWarCommand, DiplomaticStatus
        cmd = DeclareWarCommand(faction="caocao", turn=1, to="liubei")
        result = engine.execute_command(cmd)
        assert result.success is True
        status = engine._diplomacy_relation_system.get_status("caocao", "liubei")
        assert status == DiplomaticStatus.WAR

    def test_cannot_attack_ally(self):
        """同盟后不能攻击"""
        engine = _make_initialized_engine()
        from game.models import ProposeAllianceCommand, DiplomaticStatus
        engine._diplomacy_relation_system.set_status(
            "caocao", "liubei", DiplomaticStatus.ALLIANCE, turn=1
        )
        cmd = ProposeAllianceCommand(faction="caocao", turn=1, to="liubei")  # 先执行同盟
        engine.execute_command(cmd)
        from game.models import AttackCommand
        cmd = AttackCommand(
            faction="caocao", turn=1,
            from_city="city_caocao_1", to_city="city_liubei_1",
            troops=500, general="general_caocao_1",
        )
        result = engine.execute_command(cmd)
        assert result.success is False
        assert "无法攻击" in result.description or "处于" in result.description


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
        gold_before = engine.cities["city_caocao_1"].gold

        engine.process_turn()

        assert engine.cities["city_caocao_1"].gold > gold_before


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
            faction="caocao",
            general_id="general_caocao_1",
            soldiers=1000,
            food=1000,
            food_consumption_per_turn=200,
            morale=80,
            status="besieging",
            from_city="city_caocao_1",
            to_city="city_liubei_1",
            progress=1.0,
            total_distance=1,
        )
        engine.armies["army_test"] = army

        # 手动构建战斗上下文：初始1000，战斗后剩余800，伤亡200
        from game.models import BattleContext, BattlePhase, BattleResult, BattleResultType, BattleType
        ctx = BattleContext(
            battle_id="test_battle",
            turn=1,
            attacker_faction="caocao",
            defender_faction="liubei",
            attacker_armies=["army_test"],
            attacker_total_soldiers=800,  # 战斗后剩余
            attacker_initial_soldiers=1000,  # 战斗前初始
            attacker_avg_morale=80.0,
            attacker_avg_command=70.0,
            defender_city="city_liubei_1",
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
            captured_city="city_liubei_1",
        )

        captured_city = engine.cities["city_liubei_1"]
        garrison_before = captured_city.garrison

        engine._apply_battle_result(ctx, result)

        # 伤亡比例 = 200/1000 = 20%，幸存 1000 * 0.8 = 800
        # 攻击方胜利后，幸存者应并入被占领城市的守军
        # 原守军被战斗过程清零（ctx.defender_total_soldiers 已归零）
        assert captured_city.faction == "caocao"
        assert captured_city.garrison == garrison_before + 800

    def test_reward_general_in_army(self):
        """出征中的将领也可以被赏赐，金钱从军队出发城市扣除"""
        engine = _make_initialized_engine()
        general = engine.generals["general_caocao_1"]
        from_city = engine.cities["city_caocao_1"]

        # 创建军队并指派将领
        engine._army_counter += 1
        army = Army(
            id="army_reward_test",
            faction="caocao",
            general_id="general_caocao_1",
            soldiers=500,
            food=500,
            food_consumption_per_turn=100,
            morale=80,
            status="marching",
            from_city="city_caocao_1",
            to_city="city_liubei_1",
            progress=0.5,
            total_distance=1,
        )
        engine.armies["army_reward_test"] = army
        general.location = "army_reward_test"

        from_city.gold = 500
        old_loyalty = general.loyalty

        cmd = RewardCommand(
            faction="caocao", turn=1,
            general="general_caocao_1", gold=200,
        )
        result = engine.execute_command(cmd)

        assert result.success is True
        assert from_city.gold == 300
        assert general.loyalty > old_loyalty


class TestYearCalculation:
    """年份计算测试 B-09"""

    def test_initial_year_is_184(self):
        """初始年份为 184 AD"""
        engine = _make_initialized_engine()
        assert engine.year == 184

    def test_year_after_4_turns(self):
        """每 4 回合推进 1 年"""
        engine = _make_initialized_engine()
        assert engine.year == 184
        # process_turn 在开始时用当前 turn 计算 year，然后 turn+=1
        # 0 次调用: turn=1, year=184
        # 1 次调用: year=184+(1-1)//4=184, turn=2
        # 2 次调用: year=184+(2-1)//4=184, turn=3
        # 3 次调用: year=184+(3-1)//4=184, turn=4
        # 4 次调用: year=184+(4-1)//4=184, turn=5
        # 5 次调用: year=184+(5-1)//4=185, turn=6
        for _ in range(4):
            engine.process_turn()
        assert engine.turn == 5
        assert engine.year == 184  # (5-1)//4 = 1, but year calculated at turn=4 start
        # One more call to push year over the threshold
        engine.process_turn()
        assert engine.turn == 6
        assert engine.year == 185  # 184 + (5-1)//4 = 184 + 1

    def test_year_at_turn_192(self):
        """第 192 回合时年份为 231 AD"""
        engine = _make_initialized_engine()
        engine.turn = 192
        engine.process_turn()
        assert engine.year == 231  # 184 + (192-1)//4 = 184+47 = 231

    def test_game_state_includes_year_and_max_turns(self):
        """GameState 快照包含 year 和 max_turns B-03"""
        engine = _make_initialized_engine()
        engine.process_turn()
        snapshot = engine.get_state_snapshot()
        assert snapshot.year == 184
        assert snapshot.max_turns == 192
        assert snapshot.turn == 2
        # 验证序列化
        data = snapshot.model_dump(mode="json")
        assert data["year"] == 184
        assert data["max_turns"] == 192


# ============================================================
# 辅助函数
# ============================================================

def _make_game_data() -> dict:
    """创建测试用游戏数据"""
    return {
        "cities": [
            {
                "id": "city_caocao_1", "name": "曹城1", "faction": "caocao", "level": 3,
                "wall_hp": 2000, "wall_max_hp": 2000,
                "gold": 1000, "food": 1000, "population": 30000,
                "morale": 70, "garrison": 2000,
                "position": {"q": 83, "r": 63}, "neighbors": ["city_liubei_1"],
                "generals": ["general_caocao_1"],
            },
            {
                "id": "city_liubei_1", "name": "刘城1", "faction": "liubei", "level": 3,
                "wall_hp": 2000, "wall_max_hp": 2000,
                "gold": 1000, "food": 1000, "population": 30000,
                "morale": 70, "garrison": 2000,
                "position": {"q": 88, "r": 63}, "neighbors": ["city_caocao_1", "city_sunjian_1"],
                "generals": ["general_liubei_1"],
            },
            {
                "id": "city_sunjian_1", "name": "孙城1", "faction": "sunjian", "level": 3,
                "wall_hp": 2000, "wall_max_hp": 2000,
                "gold": 1000, "food": 1000, "population": 30000,
                "morale": 70, "garrison": 2000,
                "position": {"q": 93, "r": 63}, "neighbors": ["city_liubei_1"],
                "generals": ["general_sunjian_1"],
            },
        ],
        "generals": [
            {
                "id": "general_caocao_1", "name": "曹将", "faction": "caocao",
                "command": 85, "politics": 70, "bravery": 80, "intelligence": 75,
                "loyalty": 80, "location": "city_caocao_1",
            },
            {
                "id": "general_liubei_1", "name": "刘将", "faction": "liubei",
                "command": 85, "politics": 70, "bravery": 80, "intelligence": 75,
                "loyalty": 80, "location": "city_liubei_1",
            },
            {
                "id": "general_sunjian_1", "name": "孙将", "faction": "sunjian",
                "command": 85, "politics": 70, "bravery": 80, "intelligence": 75,
                "loyalty": 80, "location": "city_sunjian_1",
            },
        ],
        "map_topology": {
            "city_caocao_1": ["city_liubei_1"],
            "city_liubei_1": ["city_caocao_1", "city_sunjian_1"],
            "city_sunjian_1": ["city_liubei_1"],
        },
    }


def _make_initialized_engine() -> GameEngine:
    """创建并初始化引擎"""
    engine = GameEngine(seed=42)
    data = _make_game_data()
    engine.init_game(data)
    return engine


class TestMapGeneratorIntegration:
    """MapGenerator 接入 GameEngine 集成测试"""

    def test_engine_generates_hex_map_from_map_generator(self):
        """引擎初始化后应通过 MapGenerator 生成有效的 HexMap"""
        engine = GameEngine(seed=42)
        data = _make_game_data()
        engine.init_game(data)

        assert engine.hex_map is not None, (
            "hex_map should not be None after init_game()"
        )
        tiles = list(engine.hex_map.iter_tiles())
        assert len(tiles) > 0, "hex_map should have tiles"
        # 所有 tile 应有合法的 terrain
        from game.tile import TerrainType
        for tile in tiles:
            assert isinstance(tile.terrain, TerrainType), (
                f"Tile at {tile.coord} has invalid terrain: {tile.terrain}"
            )

    def test_engine_hex_map_has_15_terrain_types(self):
        """生成的 HexMap 应包含多种 15-terrain 系统中的地形"""
        engine = GameEngine(seed=42)
        data = _make_game_data()
        engine.init_game(data)

        terrains = {t.terrain for t in engine.hex_map.iter_tiles()}
        # 至少应有水有陆有山
        from game.tile import TerrainType
        assert any(
            t in (TerrainType.WATER, TerrainType.DEEP_WATER) for t in terrains
        ), f"Should have water terrain, got: {terrains}"
        assert any(
            t in (TerrainType.GRASS, TerrainType.PLAIN, TerrainType.GRASSLAND)
            for t in terrains
        ), f"Should have flat land, got: {terrains}"

    def test_engine_hex_map_deterministic(self):
        """相同 seed 应生成相同 HexMap"""
        engine1 = GameEngine(seed=42)
        engine2 = GameEngine(seed=42)
        data1 = _make_game_data()
        data2 = _make_game_data()
        engine1.init_game(data1)
        engine2.init_game(data2)

        tiles1 = sorted(
            engine1.hex_map.iter_tiles(), key=lambda t: t.coord.to_tuple()
        )
        tiles2 = sorted(
            engine2.hex_map.iter_tiles(), key=lambda t: t.coord.to_tuple()
        )

        assert len(tiles1) == len(tiles2)
        for t1, t2 in zip(tiles1, tiles2):
            assert t1.terrain == t2.terrain, (
                f"Terrain mismatch at {t1.coord}: {t1.terrain} vs {t2.terrain}"
            )

    def test_engine_different_seeds_produce_different_hex_maps(self):
        """不同 seed 应生成不同的 HexMap"""
        engine1 = GameEngine(seed=42)
        engine2 = GameEngine(seed=999)
        data = _make_game_data()
        engine1.init_game(data)
        engine2.init_game(data)

        t1 = [
            t.terrain for t in sorted(
                engine1.hex_map.iter_tiles(), key=lambda x: x.coord.to_tuple()
            )
        ]
        t2 = [
            t.terrain for t in sorted(
                engine2.hex_map.iter_tiles(), key=lambda x: x.coord.to_tuple()
            )
        ]
        assert t1 != t2, "Different seeds should produce different hex maps"


# ============================================================
# G「解将荒」——跨城调将（2026-10-0X v4.0）
# ============================================================

def _make_two_city_data(
    general_caocao_location: str,
    city_caocao_1_generals: list,
    city_caocao_2_generals: list,
    city_liubei_1_generals: list,
) -> dict:
    """曹方占两城（一城有将、一城无将），用于跨城调将测试。

    city_caocao_1 与 city_liubei_1 相邻（可发起进攻）；
    city_caocao_2 与 city_caocao_1 相邻（仅用于安放待调度的将领）。
    """
    return {
        "cities": [
            {
                "id": "city_caocao_1", "name": "曹城1", "faction": "caocao", "level": 3,
                "wall_hp": 2000, "wall_max_hp": 2000,
                "gold": 1000, "food": 1000, "population": 30000,
                "morale": 70, "garrison": 2000,
                "position": {"q": 83, "r": 63},
                "neighbors": ["city_caocao_2", "city_liubei_1"],
                "generals": city_caocao_1_generals,
            },
            {
                "id": "city_caocao_2", "name": "曹城2", "faction": "caocao", "level": 2,
                "wall_hp": 1000, "wall_max_hp": 1000,
                "gold": 800, "food": 800, "population": 20000,
                "morale": 70, "garrison": 1000,
                "position": {"q": 83, "r": 58},
                "neighbors": ["city_caocao_1"],
                "generals": city_caocao_2_generals,
            },
            {
                "id": "city_liubei_1", "name": "刘城1", "faction": "liubei", "level": 3,
                "wall_hp": 2000, "wall_max_hp": 2000,
                "gold": 1000, "food": 1000, "population": 30000,
                "morale": 70, "garrison": 2000,
                "position": {"q": 88, "r": 63},
                "neighbors": ["city_caocao_1"],
                "generals": city_liubei_1_generals,
            },
        ],
        "generals": [
            {
                "id": "general_caocao_1", "name": "曹将", "faction": "caocao",
                "command": 85, "politics": 70, "bravery": 80, "intelligence": 75,
                "loyalty": 80, "location": general_caocao_location,
            },
            {
                "id": "general_liubei_1", "name": "刘将", "faction": "liubei",
                "command": 85, "politics": 70, "bravery": 80, "intelligence": 75,
                "loyalty": 80, "location": "city_liubei_1",
            },
        ],
        "map_topology": {
            "city_caocao_1": ["city_caocao_2", "city_liubei_1"],
            "city_caocao_2": ["city_caocao_1"],
            "city_liubei_1": ["city_caocao_1"],
        },
    }


def _make_two_city_engine(
    general_caocao_location: str,
    city_caocao_1_generals: list,
    city_caocao_2_generals: list,
    city_liubei_1_generals: list,
) -> GameEngine:
    engine = GameEngine(seed=42)
    engine.init_game(_make_two_city_data(
        general_caocao_location,
        city_caocao_1_generals,
        city_caocao_2_generals,
        city_liubei_1_generals,
    ))
    return engine


class TestGeneralDispatch:
    """G「解将荒」——允许调度位于己方城池中的空闲将领随军出征。"""

    def test_dispatch_from_own_city_and_maintains_city_generals(self):
        """① 跨城可调：出发城无本地驻将，从己方另一城调将；city.generals 正确维护。"""
        engine = _make_two_city_engine(
            general_caocao_location="city_caocao_2",
            city_caocao_1_generals=[],
            city_caocao_2_generals=["general_caocao_1"],
            city_liubei_1_generals=["general_liubei_1"],
        )
        general = engine.generals["general_caocao_1"]
        assert general.location == "city_caocao_2"

        cmd = AttackCommand(
            faction="caocao", turn=1,
            from_city="city_caocao_1", to_city="city_liubei_1",
            troops=500, general="general_caocao_1",
        )
        result = engine.execute_command(cmd)

        # 改前该命令必被拒（general.location != from_city.id）；G 放开后应成功
        assert result.success is True, result.description
        assert "调将" in result.description
        assert len(engine.armies) == 1
        army = next(iter(engine.armies.values()))
        assert army.general_id == "general_caocao_1"
        assert army.from_city == "city_caocao_1"

        # 🔴 city.generals 维护：旧城移除、出发城加入
        # （battle_scheduler.stationed_generals 直接读 city.generals，不维护会错乱）
        assert "general_caocao_1" not in engine.cities["city_caocao_2"].generals
        assert "general_caocao_1" in engine.cities["city_caocao_1"].generals

    def test_reject_dispatch_when_general_in_enemy_city(self):
        """② 敌城将不调：将位于敌方城池时拒绝出征，且不动 city.generals。"""
        engine = _make_two_city_engine(
            general_caocao_location="city_liubei_1",         # 曹将此刻在敌城
            city_caocao_1_generals=[],
            city_caocao_2_generals=[],
            city_liubei_1_generals=["general_liubei_1", "general_caocao_1"],
        )
        before_caocao1 = list(engine.cities["city_caocao_1"].generals)
        before_caocao2 = list(engine.cities["city_caocao_2"].generals)
        before_liubei = list(engine.cities["city_liubei_1"].generals)

        cmd = AttackCommand(
            faction="caocao", turn=1,
            from_city="city_caocao_1", to_city="city_liubei_1",
            troops=500, general="general_caocao_1",
        )
        result = engine.execute_command(cmd)

        assert result.success is False
        assert "不在" in result.description
        assert not engine.armies
        # city.generals 未被误改
        assert engine.cities["city_caocao_1"].generals == before_caocao1
        assert engine.cities["city_caocao_2"].generals == before_caocao2
        assert engine.cities["city_liubei_1"].generals == before_liubei
