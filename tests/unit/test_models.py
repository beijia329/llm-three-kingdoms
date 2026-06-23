"""核心数据模型单元测试"""

import pytest
from pydantic import ValidationError

from game.hex_grid import HexCoord
from game.models import (
    Faction,
    City,
    Army,
    General,
    ArmyStatus,
    BattleResultType,
    Command,
    DevelopCommand,
    RecruitCommand,
    AttackCommand,
    RewardCommand,
    ExploreCommand,
    MessageCommand,
    RumorCommand,
    GameObservation,
    CityInfo,
    ArmyInfo,
)


# ============================================================
# Faction 枚举测试
# ============================================================

class TestFaction:
    """势力枚举测试"""

    def test_faction_values(self):
        assert Faction.WEI.value == "wei"
        assert Faction.SHU.value == "shu"
        assert Faction.WU.value == "wu"

    def test_faction_count(self):
        assert len(Faction) == 3

    def test_faction_from_string(self):
        assert Faction("wei") == Faction.WEI
        assert Faction("shu") == Faction.SHU


# ============================================================
# City 模型测试
# ============================================================

class TestCity:
    """城市模型测试"""

    def test_create_city(self):
        city = City(
            id="chengdu",
            name="成都",
            faction="shu",
            level=3,
            wall_hp=2000,
            wall_max_hp=2000,
            gold=800,
            food=1000,
            population=30000,
            morale=70,
            garrison=2000,
            position=HexCoord(100, 200),
        )
        assert city.id == "chengdu"
        assert city.name == "成都"
        assert city.faction == "shu"
        assert city.level == 3
        assert not city.is_besieged

    def test_city_defaults(self):
        """测试默认值"""
        city = City(
            id="test",
            name="测试城",
            faction="wei",
            level=1,
            wall_hp=500,
            wall_max_hp=500,
            gold=200,
            food=300,
            population=5000,
            morale=70,
            garrison=500,
            position=HexCoord(0, 0),
        )
        assert city.generals == []
        assert city.neighbors == []
        assert city.is_besieged is False
        assert city.besieging_armies == []

    def test_city_level_range(self):
        """等级必须在1-5之间"""
        with pytest.raises(ValidationError):
            City(
                id="bad", name="坏城", faction="wei", level=0,
                wall_hp=500, wall_max_hp=500, gold=200, food=300,
                population=5000, morale=70, garrison=500, position=HexCoord(0, 0),
            )

    def test_city_morale_range(self):
        """民心必须在0-100之间"""
        with pytest.raises(ValidationError):
            City(
                id="bad", name="坏城", faction="wei", level=1,
                wall_hp=500, wall_max_hp=500, gold=200, food=300,
                population=5000, morale=150, garrison=500, position=HexCoord(0, 0),
            )

    def test_city_negative_resources(self):
        """资源不能为负"""
        with pytest.raises(ValidationError):
            City(
                id="bad", name="坏城", faction="wei", level=1,
                wall_hp=500, wall_max_hp=500, gold=-1, food=300,
                population=5000, morale=70, garrison=500, position=HexCoord(0, 0),
            )


# ============================================================
# Army 模型测试
# ============================================================

class TestArmy:
    """军队模型测试"""

    def test_create_army(self):
        army = Army(
            id="army_001",
            faction="wei",
            general_id="caocao",
            soldiers=5000,
            food=1000,
            food_consumption_per_turn=100,
            status=ArmyStatus.GARRISONED,
            from_city="xuchang",
            to_city="xuchang",
            total_distance=1,
        )
        assert army.id == "army_001"
        assert army.status == ArmyStatus.GARRISONED
        assert army.morale == 80  # default

    def test_army_defaults(self):
        army = Army(
            id="army_002", faction="shu", general_id="guanyu",
            soldiers=3000, food=500, food_consumption_per_turn=60,
            status=ArmyStatus.MARCHING, from_city="chengdu",
            to_city="hanzhong", total_distance=3,
        )
        assert army.casualties == 0
        assert army.morale == 80
        assert army.progress == 0.0
        assert not army.is_in_battle

    def test_army_soldiers_positive(self):
        """兵力必须为正数"""
        with pytest.raises(ValidationError):
            Army(
                id="bad", faction="wei", general_id="x",
                soldiers=0, food=100, food_consumption_per_turn=10,
                status=ArmyStatus.GARRISONED, from_city="a",
                to_city="a", total_distance=1,
            )

    def test_army_progress_range(self):
        """行军进度必须在0-1之间"""
        with pytest.raises(ValidationError):
            Army(
                id="bad", faction="wei", general_id="x",
                soldiers=100, food=100, food_consumption_per_turn=10,
                status=ArmyStatus.MARCHING, from_city="a",
                to_city="b", total_distance=3, progress=1.5,
            )

    def test_army_morale_range(self):
        """士气必须在0-100之间"""
        with pytest.raises(ValidationError):
            Army(
                id="bad", faction="wei", general_id="x",
                soldiers=100, food=100, food_consumption_per_turn=10,
                status=ArmyStatus.GARRISONED, from_city="a",
                to_city="a", total_distance=1, morale=150,
            )


# ============================================================
# General 模型测试
# ============================================================

class TestGeneral:
    """将领模型测试"""

    def test_create_general(self):
        g = General(
            id="zhaoyun",
            name="赵云",
            faction="shu",
            command=90,
            politics=65,
            bravery=95,
            intelligence=75,
            location="chengdu",
        )
        assert g.id == "zhaoyun"
        assert g.loyalty == 70  # default

    def test_general_defaults(self):
        g = General(
            id="test", name="测试", faction="wei",
            command=50, politics=50, bravery=50, intelligence=50,
            location="xuchang",
        )
        assert g.loyalty == 70
        assert g.loyalty_decay_rate == 0.5
        assert not g.is_captured
        assert not g.is_injured

    def test_general_attribute_ranges(self):
        """属性必须在1-100之间"""
        with pytest.raises(ValidationError):
            General(
                id="bad", name="坏", faction="wei",
                command=0, politics=50, bravery=50, intelligence=50,
                location="x",
            )
        with pytest.raises(ValidationError):
            General(
                id="bad", name="坏2", faction="wei",
                command=50, politics=50, bravery=50, intelligence=101,
                location="x",
            )

    def test_general_loyalty_range(self):
        """忠诚度必须在0-100之间"""
        with pytest.raises(ValidationError):
            General(
                id="bad", name="坏", faction="wei",
                command=50, politics=50, bravery=50, intelligence=50,
                location="x", loyalty=150,
            )


# ============================================================
# Command 模型测试
# ============================================================

class TestCommands:
    """命令模型测试"""

    def test_base_command(self):
        cmd = Command(type="develop", faction="shu", turn=5)
        assert cmd.type == "develop"
        assert cmd.faction == "shu"
        assert cmd.turn == 5
        assert cmd.params == {}

    def test_develop_command(self):
        cmd = DevelopCommand(
            faction="shu", turn=5,
            city="chengdu", develop_type="economy",
        )
        assert cmd.city == "chengdu"
        assert cmd.develop_type == "economy"

    def test_recruit_command(self):
        cmd = RecruitCommand(
            faction="wei", turn=3,
            city="xuchang", troops=1000,
        )
        assert cmd.troops == 1000

    def test_attack_command(self):
        cmd = AttackCommand(
            faction="shu", turn=8,
            from_city="chengdu", to_city="hanzhong",
            troops=2000, general="zhaoyun",
        )
        assert cmd.general == "zhaoyun"

    def test_reward_command(self):
        cmd = RewardCommand(
            faction="wei", turn=4,
            general="caocao", gold=200,
        )
        assert cmd.gold == 200

    def test_explore_command(self):
        cmd = ExploreCommand(
            faction="wu", turn=6,
            city="jianye", general="zhouyu",
        )
        assert cmd.general == "zhouyu"

    def test_message_command(self):
        cmd = MessageCommand(
            faction="shu", turn=7,
            to="wei", content="我们结盟吧",
        )
        assert cmd.to == "wei"
        assert cmd.content == "我们结盟吧"

    def test_rumor_command(self):
        cmd = RumorCommand(
            faction="wei", turn=9,
            city="chengdu", target_general="zhugeliang",
            spy_general="simayi",
        )
        assert cmd.target_general == "zhugeliang"


# ============================================================
# GameObservation 模型测试
# ============================================================

class TestGameObservation:
    """观察数据模型测试"""

    def test_create_observation(self):
        city = City(
            id="chengdu", name="成都", faction="shu", level=3,
            wall_hp=2000, wall_max_hp=2000, gold=800, food=1000,
            population=30000, morale=70, garrison=2000,
            position=HexCoord(100, 200),
        )
        obs = GameObservation(
            faction="shu",
            turn=5,
            max_turns=192,
            own_cities=[city],
            own_armies=[],
            own_generals=[],
            known_cities=[],
            visible_armies=[],
            map_topology={"chengdu": ["hanzhong"]},
            received_messages=[],
            sent_messages=[],
            recent_events=[],
        )
        assert obs.faction == "shu"
        assert obs.turn == 5
        assert len(obs.own_cities) == 1

    def test_city_info_limited(self):
        """CityInfo 应该比 City 字段少（信息迷雾）"""
        city_info = CityInfo(
            id="xuchang",
            name="许昌",
            faction="wei",
            level=5,
            is_besieged=False,
        )
        assert city_info.id == "xuchang"
        assert city_info.garrison is None
        assert city_info.morale is None
