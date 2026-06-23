"""记忆管理器

LLM记忆分层管理：
- 长期记忆：整局保留的总体战略
- 中期记忆：重要事件摘要（压缩后）
- 短期记忆：最近几回合的完整思考（滑动窗口）

参考设计文档：docs/design/llm-integration.md 第四章
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class MemoryManager:
    """LLM记忆管理器

    管理AI的"记忆"，帮助模型保持战略一致性。
    """

    def __init__(self, faction: str) -> None:
        """初始化记忆管理器

        Args:
            faction: 势力名称
        """
        self.faction: str = faction
        self.long_term: str = ""  # 长期战略
        self.medium_term: List[str] = []  # 中期摘要列表
        self.short_term: List[Dict[str, Any]] = []  # 短期完整记忆

        # 配置
        self.max_short_term: int = 5
        """短期记忆保留最近N回合"""

        self.compression_interval: int = 3
        """每N回合压缩一次短期→中期"""

    # ============================================================
    # 记忆添加
    # ============================================================

    def add_turn_memory(
        self,
        turn: int,
        thought: str,
        commands: list,
        events: Optional[List[str]] = None,
    ) -> None:
        """添加一回合的记忆

        Args:
            turn: 回合数
            thought: LLM的思考过程
            commands: 执行的命令
            events: 本回合发生的事件
        """
        if events is None:
            events = []

        self.short_term.append({
            "turn": turn,
            "thought": thought,
            "commands": commands,
            "events": events,
        })

        # 如果短期记忆超限，移除最早的
        while len(self.short_term) > self.max_short_term:
            oldest = self.short_term.pop(0)
            # 压缩到中期记忆
            summary = self._compress_to_medium(oldest)
            self.medium_term.append(summary)

    def set_long_term(self, strategy: str) -> None:
        """设置长期战略

        Args:
            strategy: 战略描述
        """
        self.long_term = strategy

    # ============================================================
    # 记忆获取
    # ============================================================

    def get_context(self) -> str:
        """获取用于prompt的记忆上下文

        Returns:
            格式化的记忆文本
        """
        parts: List[str] = []

        # 长期战略
        if self.long_term:
            parts.append(f"## 长期战略\n{self.long_term}")

        # 中期摘要（最近5条）
        if self.medium_term:
            parts.append("## 历史摘要")
            for summary in self.medium_term[-5:]:
                parts.append(f"- {summary}")

        # 短期记忆（最近回合的思考）
        if self.short_term:
            parts.append("## 最近回合")
            for mem in self.short_term[-3:]:
                thought_preview = mem["thought"][:150] + "..." if len(mem["thought"]) > 150 else mem["thought"]
                cmd_summary = ", ".join(
                    f"{c.get('type', '?')}" for c in (mem.get("commands") or [])
                )
                parts.append(
                    f"第{mem['turn']}回合: {thought_preview}"
                )
                if cmd_summary:
                    parts.append(f"  执行: {cmd_summary}")
                if mem.get("events"):
                    parts.append(f"  事件: {'; '.join(mem['events'][-3:])}")

        return "\n\n".join(parts)

    # ============================================================
    # 压缩
    # ============================================================

    @staticmethod
    def _compress_to_medium(memory: Dict[str, Any]) -> str:
        """将一条短期记忆压缩为中期摘要

        Args:
            memory: 短期记忆条目

        Returns:
            摘要文本
        """
        turn = memory.get("turn", "?")
        events = memory.get("events", [])
        commands = memory.get("commands", [])

        cmd_types = [c.get("type", "?") for c in commands]
        event_summary = "; ".join(events[:3]) if events else "无重要事件"

        return f"第{turn}回合: 执行{cmd_types}. {event_summary}"

    # ============================================================
    # 重置
    # ============================================================

    def clear(self) -> None:
        """清除所有记忆"""
        self.long_term = ""
        self.medium_term.clear()
        self.short_term.clear()
