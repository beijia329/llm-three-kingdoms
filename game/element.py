"""五行属性与相克系统（v4.0 新增）

设计参考《全面战争：三国》的五行体系，把原本各自独立的四维属性 + 忠诚度
归并成五种「将道」，使将领之间产生**非对称对抗关系**——不再只是比数值大小，
而是"我这型克他那型"。

五行 ↔ 属性映射（取将领最突出的那一项作为其将道）：

    ========  ==========  ==============================
    五行       对应属性     战场定位
    ========  ==========  ==============================
    火 (fire)  勇武 bravery  猛将：正面冲杀、破城
    土 (earth) 统帅 command  统帅：阵战、守御
    金 (metal) 智力 intel    谋士：器械、计谋
    水 (water) 政治 politics 能臣：经营、外交
    木 (wood)  忠诚 loyalty  忠臣：死守、抚民
    ========  ==========  ==============================

相克环（克者对被克者伤害 +15%，被克者反过来 -15%）：

    火 → 金 → 木 → 土 → 水 → 火

    火克金（勇武破谋略）
    金克木（谋略破忠义）
    木克土（忠义克统御）
    土克水（统御克经营）
    水克火（经营克勇武）

为什么让 loyalty 以系数计入推导：数据里忠诚度区间是 65~100（均值 88.8），
若与其它四维（均值 62~72）直接比大小，会几乎所有人都被判成"木"。
乘 0.8 把它拉到同量级后，只有忠诚特别突出者（≥90 且其它维度不高）才是木。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Tuple

if TYPE_CHECKING:  # pragma: no cover
    from game.models import General

# ============================================================
# 常量
# ============================================================

ELEMENT_FIRE = "fire"
ELEMENT_EARTH = "earth"
ELEMENT_METAL = "metal"
ELEMENT_WATER = "water"
ELEMENT_WOOD = "wood"

ELEMENT_ORDER: Tuple[str, ...] = (
    ELEMENT_FIRE,
    ELEMENT_EARTH,
    ELEMENT_METAL,
    ELEMENT_WATER,
    ELEMENT_WOOD,
)
"""固定遍历顺序。

🔴 用途：属性并列时用它做确定性裁决（不依赖 dict 迭代顺序），
保证「同一份数据 → 同一五行 → 同一战斗结果」。
"""

ELEMENT_NAMES: Dict[str, str] = {
    ELEMENT_FIRE: "火",
    ELEMENT_EARTH: "土",
    ELEMENT_METAL: "金",
    ELEMENT_WATER: "水",
    ELEMENT_WOOD: "木",
}

ELEMENT_ROLES: Dict[str, str] = {
    ELEMENT_FIRE: "猛将",
    ELEMENT_EARTH: "统帅",
    ELEMENT_METAL: "谋士",
    ELEMENT_WATER: "能臣",
    ELEMENT_WOOD: "忠臣",
}

ELEMENT_COUNTERS: Dict[str, str] = {
    ELEMENT_FIRE: ELEMENT_METAL,   # 火克金
    ELEMENT_METAL: ELEMENT_WOOD,   # 金克木
    ELEMENT_WOOD: ELEMENT_EARTH,   # 木克土
    ELEMENT_EARTH: ELEMENT_WATER,  # 土克水
    ELEMENT_WATER: ELEMENT_FIRE,   # 水克火
}
"""相克环：key 克制 value。"""

ELEMENT_COUNTER_BONUS: float = 0.15
"""相克系数：克制方伤害 ×1.15，被克方 ×0.85"""

LOYALTY_ELEMENT_WEIGHT: float = 0.8
"""忠诚度参与五行推导时的权重（见模块 docstring 说明）"""


# ============================================================
# 推导与相克
# ============================================================

def derive_element(
    bravery: int,
    command: int,
    intelligence: int,
    politics: int,
    loyalty: int,
) -> str:
    """按五维推导将领的五行将道

    规则：取加权后最高的一项；并列时按 ELEMENT_ORDER 的固定优先级裁决
    （火 > 土 > 金 > 水 > 木），保证结果确定。

    Args:
        bravery: 勇武
        command: 统帅
        intelligence: 智力
        politics: 政治
        loyalty: 忠诚度

    Returns:
        五行键（fire/earth/metal/water/wood）
    """
    scores: Dict[str, float] = {
        ELEMENT_FIRE: float(bravery),
        ELEMENT_EARTH: float(command),
        ELEMENT_METAL: float(intelligence),
        ELEMENT_WATER: float(politics),
        ELEMENT_WOOD: float(loyalty) * LOYALTY_ELEMENT_WEIGHT,
    }
    return max(
        ELEMENT_ORDER,
        key=lambda e: (scores[e], -ELEMENT_ORDER.index(e)),
    )


def element_of(general: "General") -> str:
    """取将领的五行（便捷包装）

    Args:
        general: 将领对象

    Returns:
        五行键
    """
    return derive_element(
        bravery=general.bravery,
        command=general.command,
        intelligence=general.intelligence,
        politics=general.politics,
        loyalty=general.loyalty,
    )


def counter_factor(attacker_element: str, defender_element: str) -> float:
    """计算攻击方相对防守方的相克系数

    Args:
        attacker_element: 攻击方主将五行（空串表示未知 → 视为无相克）
        defender_element: 防守方主将五行

    Returns:
        >1.0 攻方克制守方；<1.0 攻方被克；1.0 无相克关系
    """
    if not attacker_element or not defender_element:
        return 1.0
    if ELEMENT_COUNTERS.get(attacker_element) == defender_element:
        return 1.0 + ELEMENT_COUNTER_BONUS
    if ELEMENT_COUNTERS.get(defender_element) == attacker_element:
        return 1.0 - ELEMENT_COUNTER_BONUS
    return 1.0


def element_label(element: str) -> str:
    """五行 → 中文展示文本（如 fire → 火·猛将）"""
    if not element:
        return "—"
    name = ELEMENT_NAMES.get(element, element)
    role = ELEMENT_ROLES.get(element, "")
    return f"{name}·{role}" if role else name
