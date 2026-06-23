"""性格与战略倾向系统

武将有性格参数，影响 AI 决策倾向。
"""

from __future__ import annotations

from enum import Enum


class Personality(str, Enum):
    """武将性格"""

    AGGRESSIVE = "aggressive"     # 激进：偏好进攻
    CAUTIOUS = "cautious"         # 谨慎：偏好防守
    DIPLOMATIC = "diplomatic"     # 外交型：偏好外交手段
    AMBITIOUS = "ambitious"       # 野心家：容易叛变
    LOYAL = "loyal"               # 忠诚：不易叛变
    BALANCED = "balanced"         # 平衡：无明显倾向


# 势力战略倾向
FACTION_PERSONALITY: dict = {
    "han":        {"style": "cautious",    "aggression": 0.3, "diplomacy": 0.5, "expand": 0.2},
    "zhangjiao":  {"style": "aggressive",  "aggression": 0.8, "diplomacy": 0.1, "expand": 0.1},
    "dongzhuo":   {"style": "aggressive",  "aggression": 0.9, "diplomacy": 0.1, "expand": 0.0},
    "yuanshao":   {"style": "ambitious",   "aggression": 0.5, "diplomacy": 0.3, "expand": 0.2},
    "caocao":     {"style": "ambitious",   "aggression": 0.7, "diplomacy": 0.2, "expand": 0.1},
    "liubei":     {"style": "diplomatic",  "aggression": 0.3, "diplomacy": 0.5, "expand": 0.2},
    "sunjian":    {"style": "aggressive",  "aggression": 0.6, "diplomacy": 0.2, "expand": 0.2},
    "liubiao":    {"style": "cautious",    "aggression": 0.2, "diplomacy": 0.4, "expand": 0.4},
    "liuyan":     {"style": "cautious",    "aggression": 0.2, "diplomacy": 0.3, "expand": 0.5},
    "gongsunzan": {"style": "aggressive",  "aggression": 0.7, "diplomacy": 0.1, "expand": 0.2},
    "mateng":     {"style": "aggressive",  "aggression": 0.6, "diplomacy": 0.2, "expand": 0.2},
    "yuanshu":    {"style": "ambitious",   "aggression": 0.6, "diplomacy": 0.3, "expand": 0.1},
}

# 名将性格
GENERAL_PERSONALITIES: dict = {
    "caocao":    Personality.AMBITIOUS,
    "xiahou_dun":Personality.AGGRESSIVE,
    "xiahou_yuan":Personality.AGGRESSIVE,
    "zhang_liao":Personality.LOYAL,
    "xuchu":     Personality.LOYAL,
    "liubei":    Personality.DIPLOMATIC,
    "guanyu":    Personality.LOYAL,
    "zhangfei":  Personality.AGGRESSIVE,
    "zhaoyun":   Personality.LOYAL,
    "zhugeliang":Personality.BALANCED,
    "sunjian":   Personality.AGGRESSIVE,
    "sunce":     Personality.AGGRESSIVE,
    "zhouyu":    Personality.BALANCED,
    "ganning":   Personality.AGGRESSIVE,
    "lusu":      Personality.DIPLOMATIC,
    "dongzhuo":  Personality.AGGRESSIVE,
    "lvbu":      Personality.AMBITIOUS,
    "yuanshao":  Personality.AMBITIOUS,
    "yuanshu":   Personality.AMBITIOUS,
}


def get_aggression_weight(faction: str, general_personality: str = "balanced") -> float:
    """计算进攻倾向权重

    Args:
        faction: 势力键
        general_personality: 将领性格

    Returns:
        0.0-1.0 的进攻权重
    """
    base = FACTION_PERSONALITY.get(faction, {}).get("aggression", 0.5)
    # 性格修正
    modifiers = {
        "aggressive": 0.2,
        "cautious": -0.2,
        "ambitious": 0.1,
        "diplomatic": -0.15,
        "loyal": 0.0,
        "balanced": 0.0,
    }
    mod = modifiers.get(general_personality, 0.0)
    return max(0.0, min(1.0, base + mod))
