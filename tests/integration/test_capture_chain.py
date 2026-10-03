"""俘虏链在生产调用链上的回归守卫

## 这个文件为什么存在

`game/battle/battle_resolver.py` 的 `resolve_battle` 在调用 `process_aftermath` 时，
`defender_generals=` 这个实参（截至 2026-10-03 位于 `:187`）是把
「战斗结算」接到「战后处理」的**唯一一根线**：

    result = self.process_aftermath(
        context,
        defender_city_owner="",
        defender_generals=list(context.defender_general_ids),   # ← 唯一接线
    )

不传它 → `process_aftermath` 里 `for gen_id in defender_generals` 永不执行
→ `captured_generals` 恒为空 → `GameEngine.process_capture` 永不被调用
→ **俘虏 / 投降 / 降将转投三条链整体静默失效**。

（行号会随注释增删漂移，引用时请按符号定位：`resolve_battle` 内
`process_aftermath(...)` 调用的 `defender_generals` 实参。）

## 改坏验证（本文件的存在依据）

2026-10-03 实测：把那个 `defender_generals=` 实参注释掉后跑
`tests/unit + tests/integration` → **631 passed, 1 skipped, 0 failed**。
即：**当时整仓库对这条链零保护**。
quality-lead 的审计（`docs/qa/2026-10-quality-audit.md`）把它列为质量门 CONCERNS。

## 为什么旧测试挡不住（「假绿」的经典形态）

`tests/unit/test_battle_resolver.py::test_aftermath_captured_generals` 是这样写的：

    result = resolver.process_aftermath(
        ctx, defender_city_owner="shu",
        defender_generals=["guanyu", "zhangfei"],   # ← 自己把参数喂进去
    )
    assert result is not None                        # ← 这句恒真，等于没断言

它**绕过 `resolve_battle`** 直接调被调函数，所以接线断没断它都绿。
本文件**刻意不碰 `process_aftermath`**，只走两个生产调用点：
`engine._battle_resolver.resolve_battle(ctx)` 与 `engine._apply_battle_result(ctx, result)`。

## 唯一判据（已验证成立）

**把那个实参注释掉，本文件必须变红。** 实测结果：

    改坏后：2 failed（captured_generals == [] → AssertionError）
    还原后：2 passed

`defender_generals` 由 `resolve_battle` 自己从 `context.defender_general_ids` 取，
本文件只负责把 `defender_general_ids` 填进 context —— 这正是生产里
`BattleScheduler` 做的事，所以这条路径与真实对局同构。
"""

from __future__ import annotations

from typing import List

import pytest

from game.data_loader import load_game_data
from game.engine import GameEngine
from game.models import BattleContext, BattleResultType, BattleType


@pytest.fixture
def engine() -> GameEngine:
    e = GameEngine(seed=42)
    e.init_game(load_game_data())
    return e


def _siege_ctx(
    engine: GameEngine,
    city_id: str,
    defender_general_ids: List[str],
    attacker_faction: str,
) -> BattleContext:
    """构造一个「守方已被打空」的攻城上下文。

    把 `defender_total_soldiers` 设为 0 是为了让结果**确定性**：
    `BattleResolver.check_battle_end` 的第一条判定就是
    「防守方兵力 ≤ 0 → ATTACKER_WIN」，不掷骰、不依赖 rng；
    而 `process_aftermath` 在「守方全灭 + 攻方 > 0」时会**无条件**俘获全部守将。
    所以本测试不需要跑多回合模拟，也不会有 flaky。
    """
    city = engine.cities[city_id]
    return BattleContext(
        battle_id="regression_capture_chain",
        turn=engine.turn,
        attacker_faction=attacker_faction,
        defender_faction=city.faction,
        attacker_armies=[],
        attacker_total_soldiers=5000,
        attacker_initial_soldiers=5000,
        attacker_avg_morale=80.0,
        attacker_avg_command=70.0,
        attacker_avg_bravery=50.0,
        defender_city=city_id,
        defender_armies=[],
        defender_general_ids=list(defender_general_ids),
        defender_total_soldiers=0,
        defender_initial_soldiers=0,
        defender_avg_morale=70.0,
        defender_avg_command=50.0,
        defender_avg_bravery=50.0,
        wall_hp=0,
        wall_max_hp=0,
        battle_type=BattleType.SIEGE,
    )


def _pick_defended_city(engine: GameEngine):
    """挑一座有守将的真实城市。"""
    for city in engine.cities.values():
        if city.faction != "neutral" and city.generals:
            return city
    raise AssertionError("测试前置失败：开局没有任何带守将的城市")


def _pick_attacker(engine: GameEngine, defender_faction: str) -> str:
    """挑一个与守方不同、且不是 neutral 的进攻方。"""
    for faction in sorted({c.faction for c in engine.cities.values()}):
        if faction not in ("neutral", defender_faction):
            return faction
    raise AssertionError("测试前置失败：找不到可用的进攻方")


def test_capture_chain_is_wired_through_production_calls(engine: GameEngine):
    """生产链：resolve_battle → _apply_battle_result 必须把守将一路送到 process_capture。

    🔴 这是本文件的核心断言。把 `battle_resolver.py:175` 注释掉，本用例必须失败。
    """
    city = _pick_defended_city(engine)
    gen_id = city.generals[0]
    attacker = _pick_attacker(engine, city.faction)

    # spy：记录引擎是否真的对俘虏调用了后处理
    captured_calls: List[str] = []
    original = engine._general_system.process_capture

    def spy(gen, **kwargs):  # type: ignore[no-untyped-def]
        captured_calls.append(gen.id)
        return original(gen, **kwargs)

    engine._general_system.process_capture = spy  # type: ignore[assignment]
    try:
        ctx = _siege_ctx(engine, city.id, [gen_id], attacker)

        # ↓↓↓ 两个生产调用点，全程不碰 process_aftermath ↓↓↓
        result = engine._battle_resolver.resolve_battle(ctx)
        engine._apply_battle_result(ctx, result)
    finally:
        engine._general_system.process_capture = original  # type: ignore[assignment]

    assert result.result == BattleResultType.ATTACKER_WIN, (
        "前置条件不成立：守方兵力为 0，check_battle_end 应直接判攻方胜"
    )

    # ① 战斗结算 → 战后处理这条线是否把守将传进去了
    assert result.captured_generals == [gen_id], (
        "resolve_battle 没有把 context.defender_general_ids 传给 process_aftermath —— "
        "`battle_resolver.py:175` 的 defender_generals=... 接线断了，"
        "俘虏/投降/降将转投三条链会静默失效"
    )

    # ② 战后处理 → 引擎俘虏处理这条线是否真的执行了
    assert captured_calls == [gen_id], (
        "引擎没有对 result.captured_generals 调用 process_capture —— "
        "_apply_battle_result 的俘虏循环断了"
    )


def test_capture_chain_ignores_hand_fed_defender_generals(engine: GameEngine):
    """反例守卫：证明「守将来自 context」而不是「来自调用方手工喂参」。

    若有人把 `:175` 改成硬编码/空列表，上面的用例会红；
    若有人把参数来源改成别处，本用例会先红（`captured_generals` 会包含
    context 之外的将领）。
    """
    city = _pick_defended_city(engine)
    gen_id = city.generals[0]
    other_gen = next(
        g.id for g in engine.generals.values() if g.id != gen_id
    )
    attacker = _pick_attacker(engine, city.faction)

    ctx = _siege_ctx(engine, city.id, [gen_id], attacker)
    result = engine._battle_resolver.resolve_battle(ctx)

    assert gen_id in result.captured_generals, (
        "context.defender_general_ids 里明确写了守将，却没被俘 —— 接线断了"
    )
    assert other_gen not in result.captured_generals, (
        "俘获了 context.defender_general_ids 之外的将领 —— "
        "说明俘虏名单不是从 context 来的，接线的数据来源被改错了"
    )
