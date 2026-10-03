"""回合相位钩子注册表（Turn-Phase Hook Registry）

为什么需要
----------
`GameEngine.process_turn` 原是一条**硬编码固定序列**
（外交到期 → 资源产出 → 行军 → 收容撤退军 → 人设代价 → 忠诚衰减 → 战斗 →
清理死军 → 胜利判定 → 建国检测 → 回合递增）。任何「每回合要结算的新机制」
（真围城的逐回合损耗、经济出口、弱方被动加成……）都必须**改 process_turn 本体**，
这是「加玩法成本高」的结构性根因。

本模块提供一根**回合相位钩子**：新机制在某个相位 `register_phase_hook(...)` 注册即可，
`process_turn` **不再改动**。

与 EventBus 的分工（**不是替代关系**）
------------------------------------
- `EventBus` = **通知已发生的事**（广播 → 多个订阅者被动响应；发布者不关心谁听）。
- 相位钩子 = **在固定时机执行逻辑**（引擎保证在各相位按确定顺序调用；注册者主动
  在指定时机做结算，可修改状态）。

一句话：EventBus 是「事后广播」，相位钩子是「到点执行」。

确定性（本项目头号教训）
------------------------
钩子按 **(priority, 注册序 seq)** 双键排序后执行——**绝不依赖 dict/hash 迭代序**
（历史 3 次「集合迭代序非确定性」事故，见 `docs/audit/2026-10-determinism-set-iteration-scan.md`）。

失败策略（显式回执，不静默）
----------------------------
钩子抛异常时：**记录（logger.exception）+ 计入 `result["hook_errors"]` + 继续执行后续钩子**。
理由：
- 一个 mod/新系统的 bug **不应让整局崩**（与 ADR-0004「游戏必须跑到结束」一致）；
- 但**必须可观测**——写进 `result["hook_errors"]` 且打日志，绝不静默吞掉
  （本项目反复栽在「静默兜底掩盖真问题」上，如 `getattr` 兜底、`except: pass`）。
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class TurnPhase(str, Enum):
    """回合相位

    覆盖 `process_turn` 中「新机制可能想挂的位置」。名字即语义边界。
    """

    TURN_START = "turn_start"
    """回合开始（外交到期之前）。"""

    AFTER_PRODUCTION = "after_production"
    """资源产出之后、行军之前（例：影响力扩散）。"""

    AFTER_MOVEMENT = "after_movement"
    """行军推进与撤退军收容之后、忠诚衰减之前（例：人设代价）。"""

    AFTER_RESOLUTION = "after_resolution"
    """战斗结算与清理死军之后、胜利判定之前。"""

    TURN_END = "turn_end"
    """回合递增之后、写日志/广播回合结束之前。"""


PHASE_ORDER: Tuple[TurnPhase, ...] = (
    TurnPhase.TURN_START,
    TurnPhase.AFTER_PRODUCTION,
    TurnPhase.AFTER_MOVEMENT,
    TurnPhase.AFTER_RESOLUTION,
    TurnPhase.TURN_END,
)
"""引擎在 process_turn 内按此顺序触发各相位。"""


# 钩子签名：(engine, result) -> None。用 object 标注 engine，避免反向依赖 game.engine。
PhaseHook = Callable[[object, Dict[str, Any]], None]


@dataclass(frozen=True)
class _HookEntry:
    phase: TurnPhase
    priority: int
    seq: int          # 注册序（确定性并列裁决）
    name: str
    fn: PhaseHook


_ENTRIES: Dict[TurnPhase, List[_HookEntry]] = {p: [] for p in PHASE_ORDER}
_seq_counter = itertools.count()


def register_phase_hook(
    phase: TurnPhase,
    fn: PhaseHook,
    *,
    priority: int = 100,
    name: Optional[str] = None,
) -> None:
    """注册一个相位钩子。

    Args:
        phase: 目标相位
        fn: 钩子函数，签名 `(engine, result) -> None`
        priority: 越小越先执行（默认 100）
        name: 展示/日志用名（默认取函数名）
    """
    entry = _HookEntry(
        phase=phase,
        priority=priority,
        seq=next(_seq_counter),
        name=name or getattr(fn, "__name__", repr(fn)),
        fn=fn,
    )
    _ENTRIES[phase].append(entry)
    # 双键排序：priority 主键 + 注册序 seq 次键 → 完全确定，与容器类型无关
    _ENTRIES[phase].sort(key=lambda h: (h.priority, h.seq))


def run_phase_hooks(engine: object, phase: TurnPhase, result: Dict[str, Any]) -> int:
    """在指定相位按确定顺序执行全部钩子。

    Args:
        engine: GameEngine 实例
        phase: 当前相位
        result: 本回合结果字典；钩子出错时写入 `result["hook_errors"]`

    Returns:
        出错的钩子数量
    """
    errors = 0
    # 对列表做快照副本：钩子内若再注册/注销，不影响本次迭代
    for entry in list(_ENTRIES.get(phase, [])):
        try:
            entry.fn(engine, result)
        except Exception as exc:  # noqa: BLE001 —— 按策略：记录 + 继续，不中止整局
            errors += 1
            record = {"phase": phase.value, "hook": entry.name, "error": repr(exc)}
            result.setdefault("hook_errors", []).append(record)
            logger.exception(
                "相位钩子执行失败（已记录并继续）: phase=%s hook=%s",
                phase.value, entry.name,
            )
    return errors


def list_phase_hooks(phase: TurnPhase) -> List[str]:
    """返回某相位已注册钩子的名字（执行顺序），供测试/检视用。"""
    return [e.name for e in _ENTRIES.get(phase, [])]


def clear_phase_hooks() -> None:
    """清空所有相位钩子（仅供测试清理，避免污染全局注册表）。"""
    for phase in PHASE_ORDER:
        _ENTRIES[phase].clear()
