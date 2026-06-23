"""玩家基类

所有玩家（CLI、GUI、LLM）必须继承此类。
定义统一的接口规范。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from game.models import Command, GameObservation


class BasePlayer(ABC):
    """玩家基类

    定义玩家与游戏引擎交互的标准接口。
    """

    def __init__(self, faction: str) -> None:
        self.faction: str = faction

    @abstractmethod
    def get_commands(self, observation: GameObservation) -> List[Command]:
        """根据当前观察数据生成命令

        Args:
            observation: 当前游戏状态观察

        Returns:
            该玩家要执行的命令列表
        """
        ...

    def receive_message(self, from_faction: str, content: str) -> None:
        """接收外交消息

        Args:
            from_faction: 发送方势力
            content: 消息内容
        """
        pass
