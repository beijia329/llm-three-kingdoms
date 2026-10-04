"""围城持续化 + 断粮结算（v4.2.0 任务B）

## 现状（v4.1.2）
军队抵达敌城（`army_movement._handle_arrival` 置 `BESIEGING` + `city.is_besieged=True`）
→ **同回合立即总攻** → 结算时清零。于是「围城」只是单回合内的瞬时状态，
任何回合边界的外部观察者（LLM / 前端 / 回放）都看不到它；「断粮」也只有军队层面
（army food=0 → 士气 -10），城市层面没有。设计依据见
`docs/design/v4.1-gameplay-gaps.md` §3。

## 本模块做的
把围城变成**跨回合的持续状态机**：

1. **不立即总攻**：抵达后保持围城；`battle_scheduler.detect_battles` 改为
   「仅当总攻条件满足（`assault_ready`）时才产出战斗」。
2. **每回合围城结算**（挂 `AFTER_MOVEMENT` 相位钩子，注册名 `city_siege`，
   由 `engine._hook_city_siege` 调用本模块的 `resolve_siege_turn`）：
   - 城墙持续受损（`SIEGE_WALL_DAMAGE_PER_TURN`）；
   - 被围城市粮草**不产出**（`ResourceSystem.calculate_food_production` 内 `is_besieged` 判定）
     + 照常扣守军消耗（`calculate_food_consumption`）；
   - 粮草 ≤ 0 → 断粮：民心 -5（已有机制，`_calculate_morale_change`）；
     **新增守军减员**（`SIEGE_STARVATION_GARRISON_RATE`，整数截断，绝不打到 0）；
   - 攻方粮草 ≤ 0 → 撤围（调 `engine._redirect_army_home`）。
3. **总攻条件**（满足任一）：城墙 hp ≤ 0 ／ 守军断粮累计 ≥ `SIEGE_STARVATION_ASSAULT_TURNS`
   回合 ／ 围城持续 ≥ `SIEGE_ASSAULT_AFTER_TURNS` 回合。

## 回滚开关
`GameEngine.siege_persistent`（默认 True，来源 `api.game_manager.GameConfig.siege_persistent`）。
设 False 时本模块两个入口（`assault_ready` 之上的过滤、`resolve_siege_turn`）全部短路，
行为**完全退回 v4.1.2**（抵达即总攻）。

## 确定性
遍历按 `city.id` 升序；不消耗 RNG（ADR-0002）。
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from game.constants import (
    SIEGE_ASSAULT_AFTER_TURNS,
    SIEGE_STARVATION_ASSAULT_TURNS,
    SIEGE_WALL_DAMAGE_PER_TURN,
    SIEGE_STARVATION_GARRISON_RATE,
    FACTIONS,
)

logger = logging.getLogger(__name__)


def assault_ready(city: Any, turn: Any) -> bool:
    """判断某座被围城市是否满足**总攻条件**（满足任一即 True）。

    Args:
        city: 目标城市（City）；读 `wall_hp` / `starving_turns` / `siege_started_turn`
        turn: 当前引擎回合号（`engine.turn`）；None 时「围城持续」一项不成立

    Returns:
        是否应立即发起总攻
    """
    # 1) 城墙被打破
    if getattr(city, "wall_hp", 1) <= 0:
        return True
    # 2) 守军断粮累计达阈值
    if getattr(city, "starving_turns", 0) >= SIEGE_STARVATION_ASSAULT_TURNS:
        return True
    # 3) 围城持续达阈值
    started = getattr(city, "siege_started_turn", None)
    if started is not None and turn is not None:
        if (int(turn) - int(started)) >= SIEGE_ASSAULT_AFTER_TURNS:
            return True
    return False


def end_siege(city: Any) -> None:
    """解除某城的围城状态并复位全部围城字段。

    统一入口：`_apply_battle_result`（总攻结算后）与围城钩子（无围城军 / 攻方全撤）
    都走这里，避免「is_besieged 清零了但 siege_started_turn 残留」导致下次围城
    的「持续回合」被错误累加。

    Args:
        city: 目标城市（会被就地修改）
    """
    city.is_besieged = False
    city.besieging_armies = []
    city.siege_started_turn = None
    city.starving_turns = 0


def resolve_siege_turn(engine: Any, result: Dict[str, Any]) -> None:
    """一个回合的围城结算（相位钩子 `city_siege` 的本体）。

    只处理 `is_besieged` 为真的城。回滚开关关闭时直接返回（完全退回现状）。

    Args:
        engine: GameEngine 实例
        result: 本回合结果字典；围城事件写入 `result["siege_events"]`
    """
    if not getattr(engine, "siege_persistent", False):
        return

    turn = engine.turn
    siege_events = result.setdefault("siege_events", [])

    for city in sorted(engine.cities.values(), key=lambda c: c.id):
        if not city.is_besieged:
            # 不再被围：复位残留字段（防御性）
            if city.siege_started_turn is not None or city.starving_turns:
                city.siege_started_turn = None
                city.starving_turns = 0
            continue

        # 剪枝：围城军名单里已不存在的军队
        live = [aid for aid in city.besieging_armies if aid in engine.armies]
        if not live:
            # 无实际围城军 → 解除围城（例如攻方已在别处被清理）
            end_siege(city)
            continue
        city.besieging_armies = live

        # 首次识别围城 → 记录开始回合（供「围城持续」判定）
        if city.siege_started_turn is None:
            city.siege_started_turn = turn

        # 1) 城墙持续受损
        wall_before = city.wall_hp
        if wall_before > 0:
            city.wall_hp = max(0, wall_before - SIEGE_WALL_DAMAGE_PER_TURN)

        # 2) 断粮：守军逐回合减员（整数截断，绝不打到 0）
        garrison_before = city.garrison
        starving = city.food <= 0 and city.garrison > 0
        if starving:
            city.starving_turns += 1
            loss = int(city.garrison * SIEGE_STARVATION_GARRISON_RATE)
            loss = min(loss, max(0, city.garrison - 1))  # 保护：至少留 1 兵
            city.garrison -= loss
        else:
            city.starving_turns = 0

        # 3) 攻方断粮 → 撤围（调 _redirect_army_home）
        famined: list = []
        for aid in list(city.besieging_armies):
            army = engine.armies.get(aid)
            if army is not None and army.food <= 0:
                engine._redirect_army_home(army)  # noqa: SLF001 —— 同包内协作
                famined.append(aid)
        if famined:
            for aid in famined:
                if aid in city.besieging_armies:
                    city.besieging_armies.remove(aid)
            if not city.besieging_armies:
                end_siege(city)

        # 4) 可观测（事件流：持续叙事，而非一次性弹窗）
        attacker_faction = ""
        for aid in city.besieging_armies:
            army = engine.armies.get(aid)
            if army is not None:
                attacker_faction = army.faction
                break
        attacker_name = FACTIONS.get(attacker_faction, attacker_faction)
        msg = (
            f"【围城】{attacker_name} 围困 {city.name}"
            f"（城墙 {wall_before}→{city.wall_hp}，守军 {garrison_before}→{city.garrison}"
            + (f"，断粮 {city.starving_turns} 回合" if city.starving_turns else "")
            + "）"
        )
        logger.info(msg)
        siege_events.append({
            "type": "siege",
            "turn": turn,
            "city_id": city.id,
            "city_name": city.name,
            "attacker_faction": attacker_faction,
            "wall_hp_before": wall_before,
            "wall_hp_after": city.wall_hp,
            "garrison_before": garrison_before,
            "garrison_after": city.garrison,
            "starving_turns": city.starving_turns,
            "message": msg,
        })
