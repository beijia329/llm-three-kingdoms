"""战斗调度器单元测试

测试战斗检测、配对、上下文创建等功能。
参考设计文档：docs/design/battle-system.md 第三章
"""

import pytest

from game.models import (
    Army, ArmyStatus, City, BattleContext, BattleType, BattlePhase, General,
)
from game.systems.map_system import MapSystem
from game.battle.battle_scheduler import BattleScheduler
from game.random import GameRandom
from game.constants import CITY_LEVELS
from game.hex_grid import HexCoord


class TestBattleDetection:
    """战斗检测测试"""

    def test_detect_no_battles(self):
        """没有军队时无战斗"""
        scheduler = BattleScheduler(rng=GameRandom(seed=42))
        battles = scheduler.detect_battles(
            armies={},
            cities={},
            map_system=MapSystem(),
        )
        assert len(battles) == 0

    def test_garrisoned_army_no_battle(self):
        """驻守军队不触发战斗"""
        scheduler = BattleScheduler(rng=GameRandom(seed=42))
        army = _make_army(status=ArmyStatus.GARRISONED)
        city = _make_city(owner="caocao", city_id="city_wei")

        battles = scheduler.detect_battles(
            armies={"army1": army},
            cities={"city_wei": city},
            map_system=MapSystem(),
        )
        assert len(battles) == 0

    def test_besieging_army_triggers_siege(self):
        """围城军队触发攻城战"""
        scheduler = BattleScheduler(rng=GameRandom(seed=42))
        army = _make_army(
            id="besieger",
            faction="caocao",
            status=ArmyStatus.BESIEGING,
            to_city="city_shu",
        )
        city = _make_city(owner="liubei", city_id="city_shu")

        battles = scheduler.detect_battles(
            armies={"besieger": army},
            cities={"city_shu": city},
            map_system=MapSystem(),
        )
        assert len(battles) == 1
        assert battles[0].battle_type == BattleType.SIEGE
        assert battles[0].attacker_faction == "caocao"
        assert battles[0].defender_faction == "liubei"

    def test_own_city_no_battle(self):
        """友方城市不触发战斗"""
        scheduler = BattleScheduler(rng=GameRandom(seed=42))
        army = _make_army(
            id="friend",
            faction="caocao",
            status=ArmyStatus.BESIEGING,
            to_city="city_wei",
        )
        city = _make_city(owner="caocao", city_id="city_wei")

        battles = scheduler.detect_battles(
            armies={"friend": army},
            cities={"city_wei": city},
            map_system=MapSystem(),
        )
        assert len(battles) == 0

    def test_multiple_armies_same_target(self):
        """多支部队攻击同一目标时合并"""
        scheduler = BattleScheduler(rng=GameRandom(seed=42))
        armies = {
            "a1": _make_army(id="a1", faction="caocao", status=ArmyStatus.BESIEGING,
                             to_city="city_shu", soldiers=3000),
            "a2": _make_army(id="a2", faction="caocao", status=ArmyStatus.BESIEGING,
                             to_city="city_shu", soldiers=2000),
        }
        city = _make_city(owner="liubei", city_id="city_shu")

        battles = scheduler.detect_battles(
            armies=armies,
            cities={"city_shu": city},
            map_system=MapSystem(),
        )
        assert len(battles) == 1
        # 应合并为一场战斗
        assert len(battles[0].attacker_armies) == 2

    def test_different_targets_different_battles(self):
        """不同目标分别创建战斗"""
        scheduler = BattleScheduler(rng=GameRandom(seed=42))
        armies = {
            "a1": _make_army(id="a1", faction="caocao", status=ArmyStatus.BESIEGING,
                             to_city="city_shu", soldiers=3000),
            "a2": _make_army(id="a2", faction="liubei", status=ArmyStatus.BESIEGING,
                             to_city="city_wei", soldiers=2000),
        }
        cities = {
            "city_shu": _make_city(owner="liubei", city_id="city_shu"),
            "city_wei": _make_city(owner="caocao", city_id="city_wei"),
        }

        battles = scheduler.detect_battles(
            armies=armies,
            cities=cities,
            map_system=MapSystem(),
        )
        assert len(battles) == 2


class TestBattleContextCreation:
    """战斗上下文创建测试"""

    def test_context_has_attacker_info(self):
        """上下文包含攻击方信息"""
        scheduler = BattleScheduler(rng=GameRandom(seed=42))
        army = _make_army(
            faction="caocao", status=ArmyStatus.BESIEGING,
            to_city="city_shu", soldiers=5000, morale=80,
            general_id="caocao",
        )
        general = _make_general(general_id="caocao", command=95)
        city = _make_city(owner="liubei", city_id="city_shu", garrison=3000)

        battles = scheduler.detect_battles(
            armies={"a1": army},
            cities={"city_shu": city},
            map_system=MapSystem(),
            generals={"caocao": general},
        )
        ctx = battles[0]
        assert ctx.attacker_total_soldiers == 5000
        assert ctx.defender_total_soldiers == 3000
        assert ctx.defender_city == "city_shu"

    def test_context_has_battle_id(self):
        """上下文有唯一ID"""
        scheduler = BattleScheduler(rng=GameRandom(seed=42))
        army = _make_army(faction="caocao", status=ArmyStatus.BESIEGING, to_city="city_shu")

        battles = scheduler.detect_battles(
            armies={"a1": army},
            cities={"city_shu": _make_city(owner="liubei")},
            map_system=MapSystem(),
        )
        assert battles[0].battle_id.startswith("battle_")

    def test_context_phase_init(self):
        """上下文初始阶段为siege"""
        scheduler = BattleScheduler(rng=GameRandom(seed=42))
        army = _make_army(faction="caocao", status=ArmyStatus.BESIEGING, to_city="city_shu")

        battles = scheduler.detect_battles(
            armies={"a1": army},
            cities={"city_shu": _make_city(owner="liubei")},
            map_system=MapSystem(),
        )
        assert battles[0].battle_phase == BattlePhase.SIEGE


# ============================================================
# 辅助函数
# ============================================================

def _make_army(
    id: str = "test_army",
    faction: str = "wei",
    status: ArmyStatus = ArmyStatus.BESIEGING,
    to_city: str = "target_city",
    soldiers: int = 3000,
    morale: int = 80,
    general_id: str = "test_gen",
    from_city: str = "home_city",
) -> Army:
    """创建测试用军队"""
    return Army(
        id=id,
        faction=faction,
        general_id=general_id,
        soldiers=soldiers,
        food=5000,
        food_consumption_per_turn=int(soldiers * 0.2),
        morale=morale,
        status=status,
        from_city=from_city,
        to_city=to_city,
        progress=1.0 if status == ArmyStatus.BESIEGING else 0.0,
        total_distance=3,
    )


def _make_city(
    owner: str = "wei",
    city_id: str = "test_city",
    garrison: int = 2000,
    generals: list = None,
) -> City:
    """创建测试用城市"""
    lc = CITY_LEVELS[3]
    if generals is None:
        generals = []
    return City(
        id=city_id,
        name=f"城-{city_id}",
        faction=owner,
        level=3,
        wall_hp=lc["wall_hp"],
        wall_max_hp=lc["wall_hp"],
        gold=1000,
        food=1000,
        population=30000,
        morale=70,
        garrison=garrison,
        generals=generals,
        position=HexCoord(0, 0),
        neighbors=[],
    )


def _make_general(
    general_id: str = "test_gen",
    command: int = 80,
    bravery: int = 60,
) -> General:
    """创建测试用将领"""
    return General(
        id=general_id,
        name="测试将",
        faction="caocao",
        command=command,
        politics=50,
        bravery=bravery,
        intelligence=55,
        loyalty=70,
        location="test_city",
    )


class TestDefenderStatsFromGenerals:
    """防守方属性从驻城将领计算"""

    def test_defender_command_from_generals(self):
        """驻城将领的统帅影响防守方平均统帅"""
        scheduler = BattleScheduler(rng=GameRandom(seed=42))
        army = _make_army(
            faction="caocao", status=ArmyStatus.BESIEGING, to_city="city_shu",
        )
        city = _make_city(owner="liubei", city_id="city_shu", generals=["gen1", "gen2"])
        gen1 = _make_general(general_id="gen1", command=80)
        gen2 = _make_general(general_id="gen2", command=60)

        battles = scheduler.detect_battles(
            armies={"a1": army}, cities={"city_shu": city},
            map_system=MapSystem(), generals={"gen1": gen1, "gen2": gen2},
        )
        assert battles[0].defender_avg_command == 70.0  # (80+60)/2

    def test_defender_bravery_from_generals(self):
        """驻城将领的勇武影响防守方平均勇武"""
        scheduler = BattleScheduler(rng=GameRandom(seed=42))
        army = _make_army(
            faction="caocao", status=ArmyStatus.BESIEGING, to_city="city_shu",
        )
        city = _make_city(owner="liubei", city_id="city_shu", generals=["gen_a", "gen_b"])
        gen_a = _make_general(general_id="gen_a", bravery=90)
        gen_b = _make_general(general_id="gen_b", bravery=50)

        battles = scheduler.detect_battles(
            armies={"a1": army}, cities={"city_shu": city},
            map_system=MapSystem(), generals={"gen_a": gen_a, "gen_b": gen_b},
        )
        assert battles[0].defender_avg_bravery == 70.0  # (90+50)/2
