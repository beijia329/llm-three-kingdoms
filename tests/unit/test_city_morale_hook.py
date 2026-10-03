"""民心自然变化的「生产可达性」回归守卫（v4.1）

背景（与 tests/balance/exp18_siege_morale_reachability.py 一一对应）
------------------------------------------------------------------
「民心自然变化」原在 `CitySystem.update_city` 内，而 `update_city` **只在
`process_turn` 的「无六角地图」else 分支被调用**；生产环境恒有地图 → 该机制
**从未执行**（探针实测：修复前 5 局 × 48 回合调用数 = 0）。

修复：迁到引擎 AFTER_MOVEMENT 相位钩子 `city_morale`（`game/engine.py::_hook_city_morale`）。

为什么单列一个文件
------------------
这是本项目**最贵的教训**：单测全绿而生产链路从未执行
（`update_city`、`defender_generals` 两例，见 docs/design/modding-guide.md §4 第 5 条）。
因此这里不只测「函数算得对」（那在 test_city_system.py），
而是测「**机制在产品路径上真的被执行**」——即钩子已注册、且每回合对每座城都跑到。
"""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest  # noqa: E402

from game.engine import GameEngine, _hook_city_morale  # noqa: E402
from game.data_loader import load_game_data  # noqa: E402
from game.models import City  # noqa: E402
from game.systems.city_system import CitySystem  # noqa: E402
from game.turn_phase import TurnPhase, list_phase_hooks  # noqa: E402
from game.hex_grid import HexCoord  # noqa: E402
from game.constants import CITY_LEVELS  # noqa: E402


def _city(cid: str, morale: int, food: int, garrison: int, besieged: bool = False) -> City:
    lc = CITY_LEVELS[1]
    c = City(
        id=cid, name=cid, faction="wei", level=1,
        wall_hp=lc["wall_hp"], wall_max_hp=lc["wall_hp"],
        gold=100, food=food, population=5000, morale=morale, garrison=garrison,
        position=HexCoord(0, 0),
    )
    c.is_besieged = besieged
    return c


class _FakeEngine:
    """只喂给 _hook_city_morale 所需的最小接口（cities + _city_system）。"""

    def __init__(self, cities):
        self.cities = {c.id: c for c in cities}
        self._city_system = CitySystem()


class TestHookRegistration:
    """钩子已注册到正确相位。"""

    def test_registered_after_movement(self):
        assert "city_morale" in list_phase_hooks(TurnPhase.AFTER_MOVEMENT)

    def test_runs_after_nature_strain(self):
        """与既有 nature_strain 同相位（priority=100），注册序在后 → 后执行。"""
        hooks = list_phase_hooks(TurnPhase.AFTER_MOVEMENT)
        assert hooks.index("city_morale") > hooks.index("nature_strain")


class TestHookBehaviour:
    """钩子本体：施加变化、夹到 [0,100]。"""

    def test_applies_morale_change(self):
        c = _city("a", morale=50, food=0, garrison=500)   # 断粮 → -5
        _hook_city_morale(_FakeEngine([c]), {})
        assert c.morale == 45

    def test_clamps_integer_floor_at_zero(self):
        """民心 2、围困 + 断粮（-8）→ 夹到 0，不出现负数。"""
        c = _city("a", morale=2, food=0, garrison=500, besieged=True)
        _hook_city_morale(_FakeEngine([c]), {})
        assert c.morale == 0

    def test_zero_change_leaves_morale_intact(self):
        c = _city("a", morale=50, food=1000, garrison=500)  # 中性 → 0
        _hook_city_morale(_FakeEngine([c]), {})
        assert c.morale == 50

    def test_deterministic_regardless_of_insertion_order(self):
        """遍历按 city.id 升序：插入顺序不同，结果一致（ADR-0002）。"""

        def run(order):
            cities = {
                "a": _city("a", morale=50, food=0, garrison=500),
                "b": _city("b", morale=2, food=0, garrison=500, besieged=True),
            }
            _hook_city_morale(_FakeEngine([cities[i] for i in order]), {})
            return cities["a"].morale, cities["b"].morale

        assert run(["a", "b"]) == run(["b", "a"]) == (45, 0)


class TestProductionReachability:
    """核心回归守卫：机制在**真实引擎 + 有地图**的生产路径上确实每回合执行。"""

    def test_morale_change_executes_every_city_every_turn(self, monkeypatch):
        calls = {"n": 0}
        orig = CitySystem._calculate_morale_change

        def counted(city):  # noqa: ANN001
            calls["n"] += 1
            return orig(city)

        monkeypatch.setattr(CitySystem, "_calculate_morale_change", staticmethod(counted))

        engine = GameEngine(seed=1)
        engine.init_game(load_game_data())
        engine.max_turns = 3
        # 前提：生产分支（有六角地图）—— 正是历史缺陷中被跳过的那条路径
        assert engine.hex_map is not None

        n_cities = len(engine.cities)
        for _ in range(3):
            engine.process_turn()

        assert calls["n"] >= n_cities * 3, (
            f"民心自然变化在 3 回合 × {n_cities} 城下只被调用 {calls['n']} 次 —— "
            "机制未在生产路径执行（历史缺陷回归）"
        )

    def test_morale_actually_moves_over_turns(self):
        """端到端：跑若干回合后，至少一座城的民心发生变化（机制非空转）。"""
        engine = GameEngine(seed=1)
        engine.init_game(load_game_data())
        engine.max_turns = 8
        before = {cid: c.morale for cid, c in engine.cities.items()}
        for _ in range(8):
            engine.process_turn()
        after = {cid: c.morale for cid, c in engine.cities.items()}
        assert before != after


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
