"""游戏模式枚举"""

from __future__ import annotations

from enum import Enum


class GameMode(str, Enum):
    """游戏模式"""

    STANDARD = "standard"
    """标准模式：192 回合，城市最多者胜"""

    INFINITE = "infinite"
    """无限模式：无回合上限，以统一全国为胜利条件"""
