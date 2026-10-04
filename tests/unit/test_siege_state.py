"""围城持续化 + 断粮 单元测试（v4.2.0 任务B）

覆盖规格第 8 条要求的全部行为：
- 围城跨回合保持 / 城墙逐回合降 / 断粮减员 / 总攻触发 / 攻方断粮撤围 / flag=False 回退。

## 改坏验证（每条断言对应的"破坏方式"，改坏后须变红）
- 城墙逐回合降：删掉 `game/siege.py` 的 `city.wall_hp = max(0, wall_before - SIEGE_WALL_DAMAGE_PER_TURN)`
  → `test_wall_decreases_each_turn` 红。
- 断粮减员：删掉守军减员两行 → `test_starvation_garrison_loss` / `test_never_reduces_garrison_to_zero` 红。
- 攻方断粮撤围：删掉 famine 循环里的 `engine._redirect_army_home(army)` → `test_attacker_famine_lifts_siege` 红。
- 总攻门控：删掉 `battle_scheduler.py` 的 `and not assault_ready(...)` 过滤 → `test_detect_gating_when_persistent` 红。
- flag 回退：删掉 `resolve_siege_turn` 开头的 `if not getattr(engine,'siege_persistent',False): return`
  → `test_flag_false_short_circuits` 红。
- 被围断粮：删掉 `resource_system.calculate_food_production` 的 `if city.is_besieged: return 0`
  → `test_besieged_city_produces_no_food` 红。
"""

from __future__ import annotations

from typing import Dict, List

import pytest

from game.constants import CITY_LEVELS, SIEGE_WALL_DAMAGE_PER_TURN
from game.data_loader import load_game_data
from game.engine import GameEngine
from game.hex_grid import HexCoord
from game.models import Army, ArmyStatus, City
from game.siege import assault_ready, end_siege, resolve_siege_turn
from game.systems.map_system import MapSystem
from game.systems.resource_system import ResourceSystem
from game.battle.battle_scheduler import BattleScheduler
from game.random import GameRandom
from game.turn_phase import TurnPhase, list_phase_hooks


# ============================================================
# 辅助：轻量 fake 引擎 + 数据构造
# ============================================================

class _FakeEngine:
    """只喂给 `resolve_siege_turn` 所需的最小接口。"""

    def __init__(self, cities: List[City], armies: Dict[str, Army], turn: int = 1,
                 persistent: bool = True) -> None:
        self.cities = {c.id: c for c in cities}
        self.armies = armies
        self.turn = turn
        self.siege_persistent = persistent
        self.redirected: List[str] = []

    def _redirect_army_home(self, army: Army) -> None:  # noqa: SLF001
        self.redirected.append(army.id)
        army.status = ArmyStatus.RETREATING


def _city(cid="c", faction="liubei", level=3, wall=None, food=1000, garrison=1000,
          besieged=True, province_id=None) -> City:
    lc = CITY_LEVELS[level]
    c = City(
        id=cid, name=cid, faction=faction, level=level,
        wall_hp=lc["wall_hp"] if wall is None else wall, wall_max_hp=lc["wall_hp"],
        gold=1000, food=food, population=30000, morale=70, garrison=garrison,
        position=HexCoord(0, 0), province_id=province_id,
    )
    c.is_besieged = besieged
    return c


def _army(aid="a1", faction="caocao", to_city="c", food=5000, soldiers=3000,
          status=ArmyStatus.BESIEGING) -> Army:
    return Army(
        id=aid, faction=faction, general_id="g1", soldiers=soldiers, food=food,
        food_consumption_per_turn=int(soldiers * 0.15), morale=80, status=status,
        from_city="home", to_city=to_city, progress=1.0, total_distance=3,
    )


# ============================================================
# 1. 钩子注册 & assault_ready 纯逻辑
# ============================================================

def test_hook_registered():
    assert "city_siege" in list_phase_hooks(TurnPhase.AFTER_MOVEMENT)


class TestAssaultReady:
    def test_wall_broken_triggers(self):
        c = _city(wall=0, besieged=True)
        c.siege_started_turn = 5
        assert assault_ready(c, 5) is True

    def test_starvation_triggers(self):
        c = _city(wall=2000, besieged=True)
        c.starving_turns = 2
        c.siege_started_turn = 5
        assert assault_ready(c, 5) is True

    def test_duration_triggers(self):
        c = _city(wall=2000, besieged=True)
        c.siege_started_turn = 5
        assert assault_ready(c, 5) is False   # 持续 0
        assert assault_ready(c, 7) is False   # 持续 2
        assert assault_ready(c, 8) is True    # 持续 3 == SIEGE_ASSAULT_AFTER_TURNS

    def test_not_ready_fresh_siege(self):
        c = _city(wall=2000, besieged=True)
        c.siege_started_turn = 5
        assert assault_ready(c, 6) is False


# ============================================================
# 2. 围城跨回合保持 / 城墙逐回合降 / 断粮减员
# ============================================================

class TestSiegeTurnResolution:
    def test_siege_persists_across_turns(self):
        city = _city(wall=2000, food=1000)
        army = _army()
        city.besieging_armies = [army.id]
        eng = _FakeEngine([city], {army.id: army}, turn=1)

        resolve_siege_turn(eng, {})
        assert city.is_besieged is True
        assert city.siege_started_turn == 1

        eng.turn = 2
        resolve_siege_turn(eng, {})
        # 跨回合仍保持围城（关键：全回合内不清零）
        assert city.is_besieged is True
        assert city.siege_started_turn == 1  # 开始回合不被覆盖

    def test_wall_decreases_each_turn(self):
        city = _city(wall=2000)
        army = _army()
        city.besieging_armies = [army.id]
        eng = _FakeEngine([city], {army.id: army})

        resolve_siege_turn(eng, {})
        assert city.wall_hp == 2000 - SIEGE_WALL_DAMAGE_PER_TURN
        resolve_siege_turn(eng, {})
        assert city.wall_hp == 2000 - 2 * SIEGE_WALL_DAMAGE_PER_TURN

    def test_wall_never_negative(self):
        city = _city(wall=100)  # 不足一次伤害
        army = _army()
        city.besieging_armies = [army.id]
        eng = _FakeEngine([city], {army.id: army})
        resolve_siege_turn(eng, {})
        assert city.wall_hp == 0

    def test_starvation_garrison_loss(self):
        city = _city(food=0, garrison=1000)
        army = _army()
        city.besieging_armies = [army.id]
        eng = _FakeEngine([city], {army.id: army})

        resolve_siege_turn(eng, {})
        assert city.starving_turns == 1
        assert city.garrison == 1000 - 20  # int(1000 × 0.02)
        resolve_siege_turn(eng, {})
        assert city.starving_turns == 2
        assert city.garrison == 980 - int(980 * 0.02)  # int(19.6)=19 → 961

    def test_never_reduces_garrison_to_zero(self):
        # 极小守军：int(rate×n) 截断为 0，守军保持不变（绝不归零）
        for g in (1, 10, 49):
            city = _city(food=0, garrison=g)
            army = _army()
            city.besieging_armies = [army.id]
            eng = _FakeEngine([city], {army.id: army})
            resolve_siege_turn(eng, {})
            assert city.garrison >= 1, f"守军被减到 {city.garrison}（应至少保留 1）"

    def test_starvation_resets_when_food_returns(self):
        city = _city(food=0, garrison=1000)
        army = _army()
        city.besieging_armies = [army.id]
        eng = _FakeEngine([city], {army.id: army})
        resolve_siege_turn(eng, {})
        assert city.starving_turns == 1
        city.food = 500
        resolve_siege_turn(eng, {})
        assert city.starving_turns == 0

    def test_emits_observable_event(self):
        city = _city(wall=2000)
        army = _army()
        city.besieging_armies = [army.id]
        eng = _FakeEngine([city], {army.id: army})
        result: Dict = {}
        resolve_siege_turn(eng, result)
        assert result["siege_events"][0]["city_id"] == city.id
        assert result["siege_events"][0]["wall_hp_before"] == 2000
        assert result["siege_events"][0]["wall_hp_after"] == 2000 - SIEGE_WALL_DAMAGE_PER_TURN


# ============================================================
# 3. 攻方断粮撤围
# ============================================================

class TestAttackerFamine:
    def test_attacker_famine_lifts_siege(self):
        city = _city()
        army = _army(food=0)
        city.besieging_armies = [army.id]
        eng = _FakeEngine([city], {army.id: army})

        resolve_siege_turn(eng, {})
        assert eng.redirected == [army.id]
        assert city.besieging_armies == []
        assert city.is_besieged is False
        assert city.siege_started_turn is None
        assert city.starving_turns == 0

    def test_one_attacker_famine_keeps_other_siege(self):
        city = _city()
        a1 = _army(aid="a1", food=0)
        a2 = _army(aid="a2", food=5000)
        city.besieging_armies = ["a1", "a2"]
        eng = _FakeEngine([city], {"a1": a1, "a2": a2})

        resolve_siege_turn(eng, {})
        assert eng.redirected == ["a1"]
        assert city.besieging_armies == ["a2"]
        assert city.is_besieged is True

    def test_stale_army_pruned(self):
        """围城军名单里的幽灵军队被剪枝；剪净后解除围城。"""
        city = _city()
        city.besieging_armies = ["ghost"]
        eng = _FakeEngine([city], {})
        resolve_siege_turn(eng, {})
        assert city.is_besieged is False


# ============================================================
# 4. flag=False 回退（回滚开关有效）
# ============================================================

class TestRollbackFlag:
    def test_flag_false_short_circuits(self):
        city = _city(wall=2000, food=0, garrison=1000)
        army = _army(food=0)  # 即便攻方断粮，flag=False 也不应触发撤围
        city.besieging_armies = [army.id]
        eng = _FakeEngine([city], {army.id: army}, persistent=False)

        result: Dict = {}
        resolve_siege_turn(eng, result)
        assert city.wall_hp == 2000           # 城墙未受损
        assert city.garrison == 1000          # 守军未减员
        assert city.siege_started_turn is None
        assert city.starving_turns == 0
        assert eng.redirected == []           # 未撤围
        assert "siege_events" not in result   # 未产生任何围城事件


# ============================================================
# 5. 总攻门控（battle_scheduler.detect_battles）
# ============================================================

class TestDetectBattlesGating:
    @staticmethod
    def _scheduler_and_data():
        sched = BattleScheduler(rng=GameRandom(seed=42))
        army = _army(faction="caocao", to_city="target")
        city = _city(cid="target", faction="liubei", wall=2000, besieged=True)
        city.generals = []
        return sched, {"a1": army}, {"target": city}

    def test_detect_gating_when_persistent(self):
        sched, armies, cities = self._scheduler_and_data()
        city = cities["target"]
        city.siege_started_turn = 5
        city.starving_turns = 0

        # 持续 0 回合：不产出战斗
        assert sched.detect_battles(armies, cities, MapSystem(),
                                    current_turn=5, persistent_siege=True) == []
        # 持续 3 回合：产出总攻
        battles = sched.detect_battles(armies, cities, MapSystem(),
                                       current_turn=8, persistent_siege=True)
        assert len(battles) == 1

    def test_detect_wall_broken_immediate(self):
        sched, armies, cities = self._scheduler_and_data()
        cities["target"].wall_hp = 0  # 城墙已破
        battles = sched.detect_battles(armies, cities, MapSystem(),
                                       current_turn=5, persistent_siege=True)
        assert len(battles) == 1

    def test_detect_starving_immediate(self):
        sched, armies, cities = self._scheduler_and_data()
        cities["target"].starving_turns = 2
        battles = sched.detect_battles(armies, cities, MapSystem(),
                                       current_turn=5, persistent_siege=True)
        assert len(battles) == 1

    def test_detect_flag_false_immediate(self):
        """flag=False：即便围城刚起，也立即产出总攻（退回 v4.1.2）。"""
        sched, armies, cities = self._scheduler_and_data()
        battles = sched.detect_battles(armies, cities, MapSystem(),
                                       current_turn=5, persistent_siege=False)
        assert len(battles) == 1

    def test_detect_legacy_default_immediate(self):
        """不传 current_turn / persistent_siege（既有调用方）→ 旧行为，立即总攻。"""
        sched, armies, cities = self._scheduler_and_data()
        battles = sched.detect_battles(armies, cities, MapSystem())
        assert len(battles) == 1


# ============================================================
# 6. 被围城市粮草不产出
# ============================================================

class TestBesiegedNoFood:
    def test_besieged_city_produces_no_food(self):
        rs = ResourceSystem()
        normal = _city(cid="n", besieged=False, food=1000)
        besieged = _city(cid="b", besieged=True, food=1000)
        assert rs.calculate_food_production(normal) > 0
        assert rs.calculate_food_production(besieged) == 0

    def test_besieged_city_gold_still_produced(self):
        """spec 仅要求粮草停产出，金钱不受影响。"""
        rs = ResourceSystem()
        besieged = _city(cid="b", besieged=True, food=1000)
        assert rs.calculate_gold_production(besieged) > 0


# ============================================================
# 7. end_siege 复位
# ============================================================

def test_end_siege_resets_all_fields():
    c = _city(besieged=True)
    c.besieging_armies = ["a1"]
    c.siege_started_turn = 3
    c.starving_turns = 2
    end_siege(c)
    assert c.is_besieged is False
    assert c.besieging_armies == []
    assert c.siege_started_turn is None
    assert c.starving_turns == 0


# ============================================================
# 8. 生产可达性：真实引擎 + 有地图，围城状态在回合边界可观测
# ============================================================

@pytest.fixture(scope="module")
def real_engine() -> GameEngine:
    e = GameEngine(seed=1)
    e.init_game(load_game_data())
    return e


def test_persistent_siege_observable_at_turn_boundary(real_engine: GameEngine):
    """端到端：跑若干回合后，至少有一座城在**回合边界**处于围城态。

    这正是任务的目的 —— v4.1.2 里 is_besieged 在回合边界永为 False（瞬时状态），
    持续化之后它成为一个可被 LLM/前端/回放观察到的持续状态。
    """
    from game.constants import FACTIONS
    from players.cli_player import CLIPlayer

    e = GameEngine(seed=1)
    e.init_game(load_game_data())
    players = {f: CLIPlayer(faction=f, rng=GameRandom(1 + (hash(f) % 1000))) for f in FACTIONS}

    observed_besieged_turn = False
    observed_siege_started = False
    for _ in range(30):
        for f in FACTIONS:
            for cmd in players[f].get_commands(e.get_observation(f)):
                e.execute_command(cmd)
        e.process_turn()
        if any(c.is_besieged for c in e.cities.values()):
            observed_besieged_turn = True
        if any(c.siege_started_turn is not None for c in e.cities.values()):
            observed_siege_started = True
        if observed_besieged_turn and observed_siege_started:
            break

    assert observed_besieged_turn, "30 回合内从未在回合边界观察到围城状态（机制不可见）"
    assert observed_siege_started, "siege_started_turn 从未被设置（围城持续回合未生效）"
