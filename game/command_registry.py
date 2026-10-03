"""命令处理器注册表（可插拔命令扩展点）

背景
----
`GameEngine.execute_command` 原先是 9 分支的硬编码 `if/elif`。每加一种命令，
不仅要写命令类与处理器，还必须在**多处平行清单**里同步登记（引擎分发 /
`llm_player.COMMAND_CLASSES` / `output_parser.VALID_COMMAND_TYPES` /
`api.game_manager._deserialize_command` / 前端 `commands.ts`），漏一处就出
「后端认、前端不认 / LLM 不知道有这条命令」的不一致。这使「像 mod 一样加玩法」
的成本极高（加一条命令 ≈ 改 8 个文件）。

本模块把「命令类型 → 处理器」抽成一张**有序注册表**，作为单一扩展点：
- 引擎只认注册表，不再枚举命令；
- 新增命令 = 注册一条（+ 写一个处理器），**不改引擎分发代码**。

确定性
------
注册表用 `dict` 存储，Python 3.7+ 保插入序 → `registered_command_types()`
返回的顺序是**注册顺序**（确定），可安全用于需要稳定顺序的遍历。
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple, Type

from game.models import Command

# 处理器签名：(engine, command) -> CommandResult
# 用 object 标注返回值，避免本模块反向依赖 game.engine（防循环 import）。
CommandHandler = Callable[[object, Command], object]

# 有序注册表：command.type -> (期望的命令类, 处理器)
_ENTRIES: Dict[str, Tuple[Type[Command], CommandHandler]] = {}


def register_command(
    command_type: str,
    command_cls: Type[Command],
    handler: CommandHandler,
    *,
    override: bool = False,
) -> None:
    """注册一个命令处理器。

    Args:
        command_type: `Command.type` 的取值（如 "develop"）
        command_cls: 期望的命令类（用于 isinstance 校验，防「type 对但类不对」）
        handler: 处理器，签名 `(engine, command) -> CommandResult`
        override: 是否允许覆盖已注册的同名命令（默认 False，重复注册即报错，
            以免并行/测试场景静默顶替真实命令）
    """
    if command_type in _ENTRIES and not override:
        raise ValueError(f"命令类型已注册: {command_type}")
    _ENTRIES[command_type] = (command_cls, handler)


def unregister_command(command_type: str) -> None:
    """移除一个命令注册（主要用于测试清理，防止污染全局注册表）。"""
    _ENTRIES.pop(command_type, None)


def get_handler(
    command_type: str,
) -> Optional[Tuple[Type[Command], CommandHandler]]:
    """取某命令类型的 (期望类, 处理器)；未注册返回 None。"""
    return _ENTRIES.get(command_type)


def registered_command_types() -> List[str]:
    """返回全部已注册命令类型（**注册顺序**，确定）。"""
    return list(_ENTRIES.keys())


def is_registered(command_type: str) -> bool:
    """该命令类型是否已注册。"""
    return command_type in _ENTRIES
