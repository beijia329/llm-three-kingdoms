"""回合相位钩子（Turn-Phase Hook Registry）测试

核心断言（对应批 2「注册假命令」的证明模式）：
**不修改 GameEngine.process_turn，就能注册一个"每回合结算"的新机制。**
"""

from __future__ import annotations

import pytest

from game.data_loader import load_game_data
from game.engine import GameEngine
from game.turn_phase import (
    PHASE_ORDER,
    TurnPhase,
    clear_phase_hooks,
    list_phase_hooks,
    register_phase_hook,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    """每个测试前后清空钩子注册表，避免污染（注册表是模块级全局）。"""
    clear_phase_hooks()
    yield
    clear_phase_hooks()


def _engine() -> GameEngine:
    engine = GameEngine(seed=42)
    engine.max_turns = 12
    engine.init_game(load_game_data())
    return engine


class TestPhaseOrdering:
    def test_five_phases_defined_in_order(self):
        assert [p.value for p in PHASE_ORDER] == [
            "turn_start",
            "after_production",
            "after_movement",
            "after_resolution",
            "turn_end",
        ]

    def test_default_registry_empty(self):
        for p in PHASE_ORDER:
            assert list_phase_hooks(p) == []

    def test_hooks_run_in_phase_order(self):
        """各相位钩子在自己的相位、按 PHASE_ORDER 顺序被调用。"""
        calls = []
        for p in PHASE_ORDER:
            register_phase_hook(p, (lambda e, r, _p=p: calls.append(_p.value)), name=p.value)
        _engine().process_turn()
        assert calls == [p.value for p in PHASE_ORDER]

    def test_priority_then_registration_order(self):
        """同相位内按 (priority, 注册序) 排序 —— 不依赖 dict/hash 序。"""
        seq = []
        register_phase_hook(TurnPhase.AFTER_PRODUCTION, lambda e, r: seq.append("b"),
                            priority=200, name="b")
        register_phase_hook(TurnPhase.AFTER_PRODUCTION, lambda e, r: seq.append("a"),
                            priority=100, name="a")
        register_phase_hook(TurnPhase.AFTER_PRODUCTION, lambda e, r: seq.append("c"),
                            priority=100, name="c")  # 与 a 同优先级 → 按注册序在 a 之后
        assert list_phase_hooks(TurnPhase.AFTER_PRODUCTION) == ["a", "c", "b"]
        _engine().process_turn()
        assert seq == ["a", "c", "b"]


class TestErrorPolicy:
    """钩子失败：记录 + 继续 + 可观测，绝不静默、绝不中止整局。"""

    def test_failing_hook_is_recorded_and_does_not_stop_others(self):
        ran = []
        register_phase_hook(
            TurnPhase.TURN_END,
            lambda e, r: (_ for _ in ()).throw(RuntimeError("boom")),
            name="bad",
        )
        register_phase_hook(TurnPhase.TURN_END, lambda e, r: ran.append("good"), name="good")

        result = _engine().process_turn()

        # 后续钩子仍执行
        assert ran == ["good"]
        # 失败被显式记录（可观测），不是静默
        errs = result.get("hook_errors")
        assert errs and errs[0]["hook"] == "bad"
        assert errs[0]["phase"] == "turn_end"
        assert "boom" in errs[0]["error"]

    def test_no_error_means_no_hook_errors_key(self):
        """无错误时不写 hook_errors（零行为变更：result 结构与原先一致）。"""
        register_phase_hook(TurnPhase.TURN_END, lambda e, r: None, name="ok")
        result = _engine().process_turn()
        assert "hook_errors" not in result


class TestPluggableMechanic:
    """证明：注册一个「每回合结算」的新机制，无需改 process_turn。"""

    def test_register_per_turn_mechanic_without_touching_engine(self):
        appliesturns = []

        def famine_hook(engine, result):
            # 一个假想的「每回合天灾」：每回合让 caocao 的第一座城民心 -1
            for city in engine.cities.values():
                if city.faction == "caocao":
                    city.morale = max(0, city.morale - 1)
                    appliesturns.append(city.id)
                    break

        register_phase_hook(
            TurnPhase.AFTER_PRODUCTION, famine_hook, priority=10, name="famine"
        )

        engine = _engine()
        boom = [c for c in engine.cities.values() if c.faction == "caocao"][0]
        before = boom.morale
        engine.process_turn()
        assert appliesturns, "钩子未被调用——扩展点不成立"
        # 钩子确实改到了状态（且 process_turn 本体未改动）
        assert boom.morale <= max(0, before - 1)
