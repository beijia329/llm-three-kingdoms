"""州郡层差异化（生产 modifier）

## 为什么需要
`docs/qa/v4.1.2-audit.md` §5.3 指出的最小可行版本：v4.1.2 已完成**势力层**差异化
（相性 / 史实硬禁 / 信任档），但**州郡层完全未动** —— 31 座城在数值上只有 level
不同，地理只影响寻路距离，「抢哪个州」在开局没有非对称答案。

本模块给东汉十三州各挂一个**单一生产 modifier**（钱 / 粮 / 征兵成本），
让「富庶的扬州」「天府益州」「西凉铁骑」在地理上就有取舍。

## 设计口径
- `gold` / `food` = **产出倍率**（>1 增产，<1 减产）。乘在 `ResourceSystem`
  的产出公式末尾（民心/政治加成之后），因此与其它倍率正交。
- `recruit` = **征兵成本倍率**（<1 = 更便宜）。乘在 `CitySystem.recruit`
  的「每兵金钱 / 粮草成本」上（`RECRUIT_COST_GOLD` / `RECRUIT_COST_FOOD`）。
- 交州（`jiaozhou`）是**唯一负面**州：金钱 -10%，作为「蛮荒之地」的取舍。

## 单一数据源
`PROVINCE_MODIFIERS` / `PROVINCE_MODIFIER_DESC` 是**引擎侧的正本**（不依赖
数据加载顺序，单测可直接引用）；`data/provinces.json` 的同名字段是**数据行**
（供前端与人工核对）。两者必须一致，由
`tests/unit/test_province_modifiers.py::test_json_matches_constant_table` 守卫。

数值均为 v4.2.0 初版取值（可能随平衡实验调整），非史实常数。
"""

from __future__ import annotations

from typing import Dict, Optional

# ============================================================
# 州 → 生产 modifier
# ============================================================
# 键：州 id（与 data/provinces.json、City.province_id 一致）
# 值：{"gold": 倍率} | {"food": 倍率} | {"recruit": 成本倍率}
PROVINCE_MODIFIERS: Dict[str, Dict[str, float]] = {
    "sili":      {"gold": 1.15},   # 司隶 京畿重地
    "yangzhou":  {"gold": 1.15},   # 扬州 江东富庶
    "yuzhou":    {"gold": 1.10},   # 豫州 中原腹地
    "qingzhou":  {"gold": 1.10},   # 青州 渔盐之利
    "jizhou":    {"food": 1.15},   # 冀州 河北粮仓
    "yizhou":    {"food": 1.20},   # 益州 天府之国
    "yanzhou":   {"food": 1.10},   # 兖州 中原粮区
    "xuzhou":    {"food": 1.10},   # 徐州 沃野
    "jingzhou":  {"food": 1.10},   # 荆州 湖广熟
    "liangzhou": {"recruit": 0.90},  # 凉州 西凉铁骑
    "youzhou":   {"recruit": 0.90},  # 幽州 幽州突骑
    "bingzhou":  {"recruit": 0.95},  # 并州 边地尚武
    "jiaozhou":  {"gold": 0.90},   # 交州 蛮荒（负面）
}

# 州 → 人类可读说明（供事件流、前端、LLM 提示词）
PROVINCE_MODIFIER_DESC: Dict[str, str] = {
    "sili":      "京畿重地：金钱产出 +15%",
    "yangzhou":  "江东富庶：金钱产出 +15%",
    "yuzhou":    "中原腹地：金钱产出 +10%",
    "qingzhou":  "渔盐之利：金钱产出 +10%",
    "jizhou":    "河北粮仓：粮草产出 +15%",
    "yizhou":    "天府之国：粮草产出 +20%",
    "yanzhou":   "中原粮区：粮草产出 +10%",
    "xuzhou":    "沃野：粮草产出 +10%",
    "jingzhou":  "湖广熟：粮草产出 +10%",
    "liangzhou": "西凉铁骑：征兵成本 -10%",
    "youzhou":   "幽州突骑：征兵成本 -10%",
    "bingzhou":  "边地尚武：征兵成本 -5%",
    "jiaozhou":  "蛮荒之地：金钱产出 -10%",
}


# 州 → 中文名（与 data/provinces.json 的 name 一致，供提示词等无数据加载场景使用）
PROVINCE_NAMES: Dict[str, str] = {
    "sili": "司隶", "yuzhou": "豫州", "jizhou": "冀州", "yanzhou": "兖州",
    "xuzhou": "徐州", "qingzhou": "青州", "jingzhou": "荆州", "yangzhou": "扬州",
    "yizhou": "益州", "liangzhou": "凉州", "bingzhou": "并州", "youzhou": "幽州",
    "jiaozhou": "交州",
}


def get_province_modifiers(province_id: Optional[str]) -> Dict[str, float]:
    """取某州的生产 modifier 映射；未知/空州返回空 dict（等价于无修正）。

    Args:
        province_id: 州 id（`City.province_id`），可为 None（如中立城未分州）

    Returns:
        形如 ``{"gold": 1.15}`` 的映射；无修正时为 ``{}``
    """
    if not province_id:
        return {}
    return PROVINCE_MODIFIERS.get(province_id, {})


def get_modifier_desc(province_id: Optional[str]) -> str:
    """取某州 modifier 的人类可读说明；无则空串。"""
    if not province_id:
        return ""
    return PROVINCE_MODIFIER_DESC.get(province_id, "")


def province_gold_multiplier(province_id: Optional[str]) -> float:
    """州金钱产出倍率（无修正 = 1.0）。"""
    return float(get_province_modifiers(province_id).get("gold", 1.0))


def province_food_multiplier(province_id: Optional[str]) -> float:
    """州粮草产出倍率（无修正 = 1.0）。"""
    return float(get_province_modifiers(province_id).get("food", 1.0))


def province_recruit_cost_multiplier(province_id: Optional[str]) -> float:
    """州征兵成本倍率（无修正 = 1.0；<1 = 更便宜）。"""
    return float(get_province_modifiers(province_id).get("recruit", 1.0))
