"""季节枚举

每 12 回合为一个年份循环，每 3 回合切换一个季节。
"""

from __future__ import annotations

from enum import Enum


class Season(str, Enum):
    """季节枚举"""

    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"

    @classmethod
    def from_turn(cls, turn: int) -> Season:
        """根据回合数计算当前季节

        每 12 回合为一个年份循环，每 3 回合一个季节：
        - 春：1-3, 13-15, ...
        - 夏：4-6, 16-18, ...
        - 秋：7-9, 19-21, ...
        - 冬：10-12, 22-24, ...

        Args:
            turn: 当前回合数（从 1 开始）

        Returns:
            当前季节
        """
        month = ((turn - 1) % 12) + 1
        if month <= 3:
            return cls.SPRING
        elif month <= 6:
            return cls.SUMMER
        elif month <= 9:
            return cls.AUTUMN
        else:
            return cls.WINTER

    @classmethod
    def season_names_zh(cls) -> dict:
        """获取季节中文名映射"""
        return {
            "spring": "春",
            "summer": "夏",
            "autumn": "秋",
            "winter": "冬",
        }
