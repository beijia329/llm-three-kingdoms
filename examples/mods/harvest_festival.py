"""示例 mod：丰年祭（Harvest Festival）

这是一个**外部 mod**的真实样例，演示本项目两个扩展点怎么用：

  1. 相位钩子 —— 加一个「每回合自动结算」的被动机制
  2. 命令注册表 —— 加一条玩家/LLM 可下发的主动命令

设计意图
--------
机制刻意选得「与原版正交」：原版民心只能靠 `develop("culture")` 慢慢抬，
且民心 ≥ 80 的高民心城没有任何额外收益。本 mod 给高民心城一个滚雪球出口：

  被动（相位钩子，AFTER_PRODUCTION）：
    民心 ≥ 80 的城，每回合额外 +2 金（「丰年」）
    但民心 ≤ 20 的城，每回合 -1 金（「民不聊生，征不上税」）

  主动（新命令 `festival`）：
    花 300 金，本城民心 +8（上限 100）

用法
----
    import examples.mods.famine as festival   # 导入即完成注册
    ...                                        # 之后正常跑引擎即可

注意：注册是**进程级全局**的，导入一次即长期生效；
若要卸载（测试里常用），见本文件末尾 `uninstall()`。

🔴 写 mod 的硬约束（本项目血泪）
--------------------------------
1. **确定性**：禁止依赖 `set` / `dict` 之外无序遍历；遍历城市用 `engine.cities.values()`
   或显式 `sorted(...)`。本项目因集合迭代序非确定性栽过 4 次（ADR-0002）。
2. **不要吞异常**：钩子抛异常会被 `turn_phase` 记录进 `result["hook_errors"]` 并打日志。
   自己再写 `except: pass` 会让失败彻底不可观测——本项目反复栽在「静默兜底」上。
3. **不要改 `process_turn`**：如果你发现必须改，说明选错了扩展点，先提 issue。
"""

from __future__ import annotations

from typing import Any, Dict

from game.command_registry import register_command, unregister_command
from game.models import Command
from game.turn_phase import TurnPhase, register_phase_hook

# ---------------------------------------------------------------------------
# 1) 被动机制：相位钩子
# ---------------------------------------------------------------------------

MORALE_BOOM_THRESHOLD = 80    # 高于此民心 = 丰年
MORALE_RUIN_THRESHOLD = 20    # 低于此民心 = 民不聊生
BOOM_GOLD_BONUS = 2
RUIN_GOLD_PENALTY = 1

# 可观测计数器：让「mod 到底有没有跑」这件事**可验证**，而不是靠猜。
booms_applied = 0
ruins_applied = 0


def hook_harvest_festival(engine: object, result: Dict[str, Any]) -> None:
    """相位钩子（after_production）：按民心给城市加减金钱。"""
    global booms_applied, ruins_applied
    cities = getattr(engine, "cities", None)
    if not cities:
        return
    # 确定性：显式按 city.id 排序，不依赖容器迭代序
    for city_id in sorted(cities):
        city = cities[city_id]
        if city.morale >= MORALE_BOOM_THRESHOLD:
            city.gold += BOOM_GOLD_BONUS
            booms_applied += 1
        elif city.morale <= MORALE_RUIN_THRESHOLD:
            city.gold = max(0, city.gold - RUIN_GOLD_PENALTY)
            ruins_applied += 1


# ---------------------------------------------------------------------------
# 2) 主动机制：新命令
# ---------------------------------------------------------------------------

FESTIVAL_COST = 300
FESTIVAL_MORALE_BONUS = 8


class FestivalCommand(Command):
    """丰年祭命令（mod 自定义命令）。"""

    type: str = "festival"
    city: str = ""

    # 注意：不继承 pydantic 之外的任何东西，保持与内置命令同构即可。


def _execute_festival(engine: object, command: Command) -> Any:
    """处理器签名必须为 (engine, command) -> CommandResult。"""
    from game.engine import CommandResult

    city_id = getattr(command, "city", "") or ""
    cities = getattr(engine, "cities", {})
    city = cities.get(city_id)

    if city is None:
        return CommandResult(
            success=False, command_type="festival",
            description=f"城市不存在: {city_id}",
        )
    if city.faction != command.faction:
        return CommandResult(
            success=False, command_type="festival",
            description="不是你的城市",
        )
    if city.gold < FESTIVAL_COST:
        return CommandResult(
            success=False, command_type="festival",
            description=f"金不足（需 {FESTIVAL_COST}，现有 {city.gold}）",
        )

    city.gold -= FESTIVAL_COST
    before = city.morale
    city.morale = min(100, city.morale + FESTIVAL_MORALE_BONUS)
    gained = city.morale - before

    return CommandResult(
        success=True, command_type="festival",
        description=f"{city.name} 举办丰年祭，民心 +{gained}",
        data={"city": city.id, "morale_gained": gained},
    )


# ---------------------------------------------------------------------------
# 注册（导入即生效）
# ---------------------------------------------------------------------------

register_phase_hook(
    TurnPhase.AFTER_PRODUCTION, hook_harvest_festival,
    priority=150, name="harvest_festival",
)

register_command("festival", FestivalCommand, _execute_festival)


def uninstall() -> None:
    """卸载本 mod（测试清理用；生产不需要）。"""
    from game.turn_phase import _ENTRIES  # noqa: PLC0415 —— 仅测试用，故意直取内部表
    for phase in list(_ENTRIES):
        _ENTRIES[phase][:] = [
            e for e in _ENTRIES[phase] if e.name != "harvest_festival"
        ]
    unregister_command("festival")
