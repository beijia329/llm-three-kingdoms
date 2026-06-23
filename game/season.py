"""季节枚举

每 4 回合为一个年份循环（每回合 = 1 个季度/3个月）：
- 春：turn 1, 5, 9, ...
- 夏：turn 2, 6, 10, ...
- 秋：turn 3, 7, 11, ...
- 冬：turn 4, 8, 12, ...
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

        每 4 回合为一个年份循环（每回合 = 1 个季度）：
        - 春：1, 5, 9, ...
        - 夏：2, 6, 10, ...
        - 秋：3, 7, 11, ...
        - 冬：4, 8, 12, ...

        Args:
            turn: 当前回合数（从 1 开始）

        Returns:
            当前季节
        """
        season_index = ((turn - 1) % 4) + 1
        if season_index == 1:
            return cls.SPRING
        elif season_index == 2:
            return cls.SUMMER
        elif season_index == 3:
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
