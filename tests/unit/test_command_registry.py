"""命令处理器注册表测试（可插拔命令扩展点）

核心断言：**不修改 GameEngine 的分发代码，就能注册并执行一条新命令**。
这是「玩法像 mod 一样可插入」的第一块地基。
"""

from __future__ import annotations

import pytest

import game.engine  # noqa: F401  —— import 触发内置命令注册
from game.command_registry import (
    get_handler,
    is_registered,
    register_command,
    registered_command_types,
    unregister_command,
)
from game.engine import CommandResult, GameEngine
from game.models import Command, DevelopCommand


BUILTIN_TYPES = [
    "develop",
    "recruit",
    "attack",
    "reward",
    "explore",
    "message",
    "rumor",
    "propose_alliance",
    "declare_war",
    "truce",
]


class TestBuiltinRegistration:
    """内置 10 条命令已注册，且顺序确定。"""

    def test_all_builtins_registered(self):
        for t in BUILTIN_TYPES:
            assert is_registered(t), f"内置命令未注册: {t}"

    def test_registration_order_is_deterministic(self):
        """注册表有序：dict 保插入序 → 遍历顺序确定（ADR-0002 相关）。"""
        assert registered_command_types() == BUILTIN_TYPES

    def test_engine_dispatch_routes_to_builtin_handler(self):
        """引擎分发经注册表路由到正确的处理器。

        用一个「城市不存在」的 develop 命令区分：
        若路由到 _execute_develop → 描述含「不存在」；
        若没路由到（未知命令）→ 描述为「未知命令类型」。
        """
        engine = GameEngine(seed=42)
        result = engine.execute_command(
            DevelopCommand(faction="caocao", turn=1, city="__no_such__", develop_type="economy")
        )
        assert result.command_type == "develop"
        assert result.success is False
        assert "不存在" in result.description, result.description

    def test_unknown_command_type_is_rejected(self):
        engine = GameEngine(seed=42)
        result = engine.execute_command(Command(type="__nope__", faction="caocao", turn=1))
        assert result.success is False
        assert "未知命令类型" in result.description


class TestPluggableCommand:
    """证明：注册一条新命令无需改动引擎分发代码。"""

    def test_register_and_execute_new_command(self):
        fake_type = "__probe_plugin_cmd__"
        assert not is_registered(fake_type), "测试前置：该类型不应已注册"

        calls = []

        class ProbeCommand(Command):
            type: str = fake_type

        def probe_handler(engine, cmd):
            calls.append(cmd)
            return CommandResult(
                success=True, command_type=fake_type, description="probe-executed"
            )

        register_command(fake_type, ProbeCommand, probe_handler)
        try:
            engine = GameEngine(seed=42)
            # 引擎的 execute_command 未做任何修改，仍能分发到新命令
            result = engine.execute_command(ProbeCommand(faction="caocao", turn=1))
            assert result.success is True
            assert result.description == "probe-executed"
            assert len(calls) == 1  # 处理器确实被调用
            # 新命令也会进入本回合动作记录（人设代价判定用），说明走的是同一条正规路径
            assert ("caocao", fake_type) in engine._turn_actions
        finally:
            unregister_command(fake_type)

    def test_handler_lookup_returns_registered_pair(self):
        entry = get_handler("develop")
        assert entry is not None
        cls, handler = entry
        assert cls is DevelopCommand
        assert callable(handler)

    def test_type_mismatch_is_treated_as_unknown(self):
        """type 命中但命令类不匹配（isinstance 失败）→ 仍按未知命令处理（保留原语义）。"""
        engine = GameEngine(seed=42)
        # type="develop" 但给的是基类 Command（不是 DevelopCommand）
        result = engine.execute_command(Command(type="develop", faction="caocao", turn=1))
        assert result.success is False
        assert "未知命令类型" in result.description

    def test_duplicate_registration_raises(self):
        with pytest.raises(ValueError):
            register_command("develop", DevelopCommand, GameEngine._execute_develop)
