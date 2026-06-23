"""LLM Player 主类

整合LLM客户端、Prompt构建器、输出解析器、记忆管理器。
提供完整的AI决策流程：
1. 获取观察 → 2. 构建Prompt → 3. 调用LLM → 4. 解析输出 → 5. 校验命令

三级降级体系：
L0: 正常输出
L1: 重试（最多2次）
L2: 返回空命令（跳过本回合）
L3: 降级为随机AI（连续失败）

参考设计文档：docs/design/llm-integration.md 第六章
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from game.models import (
    Command,
    AttackCommand,
    DevelopCommand,
    ExploreCommand,
    GameObservation,
    MessageCommand,
    RecruitCommand,
    RewardCommand,
    RumorCommand,
)
from game.random import GameRandom
from players.base_player import BasePlayer
from players.llm.llm_client import LLMClient
from players.llm.memory_manager import MemoryManager
from players.llm.output_parser import OutputParser
from players.llm.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)

# 命令类型到Command类的映射
COMMAND_CLASSES = {
    "develop": DevelopCommand,
    "recruit": RecruitCommand,
    "attack": AttackCommand,
    "reward": RewardCommand,
    "explore": ExploreCommand,
    "message": MessageCommand,
    "rumor": RumorCommand,
}

# 命令参数映射（LLM输出字段 -> Command类字段）
PARAM_MAPPING = {
    "develop": {"city": "city", "type": "develop_type"},
    "recruit": {"city": "city", "troops": "troops"},
    "attack": {"from": "from_city", "to": "to_city", "troops": "troops", "general": "general"},
    "reward": {"general": "general", "gold": "gold"},
    "explore": {"city": "city", "general": "general"},
    "message": {"to": "to", "content": "content"},
    "rumor": {"city": "city", "target_general": "target_general", "spy_general": "spy_general"},
}


class LLMPlayer(BasePlayer):
    """LLM玩家

    使用大语言模型进行策略决策。
    支持降级机制，LLM失败时自动切换为随机策略。
    """

    def __init__(
        self,
        faction: str,
        llm_client: LLMClient,
        memory_manager: Optional[MemoryManager] = None,
        rng: Optional[GameRandom] = None,
        max_retries: int = 2,
        consecutive_fail_limit: int = 3,
    ) -> None:
        """初始化LLM玩家

        Args:
            faction: 势力名称
            llm_client: LLM API客户端
            memory_manager: 记忆管理器（不传则自动创建）
            rng: 随机数生成器（降级时使用）
            max_retries: 最大重试次数
            consecutive_fail_limit: 连续失败次数上限，超过后降级为随机AI
        """
        super().__init__(faction)
        self.llm = llm_client
        self.memory = memory_manager or MemoryManager(faction)
        self.rng = rng or GameRandom(42)
        self.max_retries = max_retries
        self.consecutive_fail_limit = consecutive_fail_limit

        # 内部状态
        self._consecutive_fails: int = 0
        self._degraded: bool = False  # 是否已降级
        self._parser = OutputParser()
        self._prompt_builder = PromptBuilder()
        self._last_response: str = ""  # 上次的LLM响应（用于重试时反馈）

    # ============================================================
    # 核心方法
    # ============================================================

    def get_commands(self, observation: GameObservation) -> List[Command]:
        """获取本回合的命令

        标准流程：构建Prompt → 调用LLM → 解析输出 → 校验 → 返回

        Args:
            observation: 游戏观察数据

        Returns:
            命令列表（可能为空）
        """
        # 如果已降级，使用随机策略
        if self._degraded:
            logger.warning("[%s] 已降级为随机AI", self.faction)
            return self._get_fallback_commands(observation)

        # 构建Prompt
        memory_context = self.memory.get_context()
        messages = self._prompt_builder.build_full_prompt(
            faction=self.faction,
            observation=observation,
            memory_context=memory_context,
        )

        # 调用LLM（带重试）
        for attempt in range(self.max_retries + 1):
            try:
                response = self.llm.chat(messages)
                self._last_response = response

                # 解析输出
                raw_commands = self._parser.parse_commands(response)
                if raw_commands is None:
                    logger.warning(
                        "[%s] 解析失败 (尝试 %d/%d)",
                        self.faction, attempt + 1, self.max_retries + 1,
                    )
                    # 重试：把错误加回去
                    if attempt < self.max_retries:
                        messages.append({"role": "assistant", "content": response})
                        messages.append({
                            "role": "user",
                            "content": "JSON格式解析失败，请只输出JSON数组，不要包含解释文字。",
                        })
                    continue

                # 过滤非法命令
                valid_commands = self._parser.filter_commands(raw_commands)

                # 转换为 Command 对象
                commands = self._convert_to_commands(valid_commands, observation.turn)

                # 记录成功
                self._consecutive_fails = 0

                # 保存记忆
                self.memory.add_turn_memory(
                    turn=observation.turn,
                    thought=response,
                    commands=valid_commands,
                )

                return commands

            except Exception as e:
                logger.error(
                    "[%s] LLM调用异常 (尝试 %d/%d): %s",
                    self.faction, attempt + 1, self.max_retries + 1, e,
                )
                if attempt < self.max_retries:
                    continue

        # 全部重试失败
        self._consecutive_fails += 1
        logger.error(
            "[%s] LLM调用全部失败 (连续%d次)",
            self.faction, self._consecutive_fails,
        )

        # 检查是否需要降级
        if self._consecutive_fails >= self.consecutive_fail_limit:
            logger.warning("[%s] 连续失败%d次，降级为随机AI", self.faction, self.consecutive_fail_limit)
            self._degraded = True

        return []

    # ============================================================
    # 降级策略
    # ============================================================

    def _get_fallback_commands(self, observation: GameObservation) -> List[Command]:
        """降级后的回退策略

        简单的随机策略，保证游戏能继续。

        Args:
            observation: 游戏观察

        Returns:
            命令列表
        """
        commands: List[Command] = []
        turn = observation.turn

        if not observation.own_cities:
            return commands

        city = observation.own_cities[0]

        # 随机选择：发展或征兵
        if self.rng.random() < 0.7:
            dev_types = ["economy", "military", "culture"]
            dev_type = dev_types[turn % 3]
            commands.append(
                DevelopCommand(
                    faction=self.faction, turn=turn,
                    city=city.id, develop_type=dev_type,
                )
            )
        else:
            troops = min(500, max(100, city.gold // 3))
            commands.append(
                RecruitCommand(
                    faction=self.faction, turn=turn,
                    city=city.id, troops=troops,
                )
            )

        return commands

    # ============================================================
    # 命令转换
    # ============================================================

    def _convert_to_commands(
        self,
        raw_commands: List[Dict[str, Any]],
        turn: int,
    ) -> List[Command]:
        """将解析后的字典列表转换为Command对象

        Args:
            raw_commands: 原始命令字典列表
            turn: 当前回合

        Returns:
            Command对象列表
        """
        commands: List[Command] = []

        for raw in raw_commands:
            cmd_type = raw.get("type", "")
            params = raw.get("params", {})

            cmd_class = COMMAND_CLASSES.get(cmd_type)
            if cmd_class is None:
                continue

            # 映射参数
            mapping = PARAM_MAPPING.get(cmd_type, {})
            kwargs = {"faction": self.faction, "turn": turn}
            for llm_key, model_key in mapping.items():
                if llm_key in params:
                    kwargs[model_key] = params[llm_key]

            try:
                cmd = cmd_class(**kwargs)
                commands.append(cmd)
            except Exception as e:
                logger.warning("命令创建失败: %s - %s", raw, e)

        return commands

    # ============================================================
    # 外交消息
    # ============================================================

    def receive_message(self, from_faction: str, content: str) -> None:
        """接收外交消息（保存到记忆）

        Args:
            from_faction: 发送方
            content: 消息内容
        """
        logger.info("[%s] 收到来自%s的消息: %s", self.faction, from_faction, content[:100])

    def is_degraded(self) -> bool:
        """是否已降级为随机AI

        Returns:
            降级状态
        """
        return self._degraded
