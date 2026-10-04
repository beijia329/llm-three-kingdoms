"""州郡生产 modifier 单元测试（v4.2.0 任务A）

覆盖：
1. 常数表 / 描述 / JSON 数据三者一致（13 州全覆盖）；
2. gold / food 产出倍率真的进入 `ResourceSystem` 产出公式；
3. recruit 成本倍率真的进入 `CitySystem.recruit`；
4. 未知 / 空州 = 无修正（等价于乘 1.0）。

## 改坏验证（每条断言的"破坏方式"）
- 断言 2/3（产出倍率）：删掉 `resource_system.py` 里的 `* province_bonus`
  → 司隶与基线产出相同 → 变红。
- 断言 4/5（征兵成本）：删掉 `city_system.py` 的 `recruit_mult`（令其恒 1.0）
  → 凉州与基线成本相同 → 变红。
- 断言 1（数据一致）：从 `PROVINCE_MODIFIERS` 删一个州、或改 provinces.json 一个值
  → 变红。
"""

from __future__ import annotations

import json
from pathlib import Path

from game.constants import CITY_LEVELS
from game.hex_grid import HexCoord
from game.models import City
from game.provinces import (
    PROVINCE_MODIFIER_DESC,
    PROVINCE_MODIFIERS,
    PROVINCE_NAMES,
    get_modifier_desc,
    get_province_modifiers,
    province_gold_multiplier,
    province_recruit_cost_multiplier,
)
from game.systems.city_system import CitySystem
from game.systems.resource_system import ResourceSystem

_ROOT = Path(__file__).resolve().parents[2]
_PROVINCES_JSON = _ROOT / "data" / "provinces.json"

# 任务规格的分配表（13 州 → modifier），与实现口径逐条对齐
_EXPECTED: dict = {
    "sili": {"gold": 1.15},
    "yangzhou": {"gold": 1.15},
    "yuzhou": {"gold": 1.10},
    "qingzhou": {"gold": 1.10},
    "jizhou": {"food": 1.15},
    "yizhou": {"food": 1.20},
    "yanzhou": {"food": 1.10},
    "xuzhou": {"food": 1.10},
    "jingzhou": {"food": 1.10},
    "liangzhou": {"recruit": 0.90},
    "youzhou": {"recruit": 0.90},
    "bingzhou": {"recruit": 0.95},
    "jiaozhou": {"gold": 0.90},
}


def _city(
    cid: str = "c",
    province_id=None,
    faction: str = "caocao",
    level: int = 3,
    morale: int = 70,
    population: int = 30000,
    gold: int = 10000,
    food: int = 10000,
    garrison: int = 0,
) -> City:
    lc = CITY_LEVELS[level]
    return City(
        id=cid, name=cid, faction=faction, level=level,
        wall_hp=lc["wall_hp"], wall_max_hp=lc["wall_hp"],
        gold=gold, food=food, population=population, morale=morale,
        garrison=garrison, position=HexCoord(0, 0),
        province_id=province_id,
    )


# ============================================================
# 1. 数据一致性（常数表 / 描述 / JSON）
# ============================================================

class TestDataTable:
    def test_all_13_provinces_present(self):
        assert set(PROVINCE_MODIFIERS.keys()) == set(_EXPECTED.keys())
        assert len(PROVINCE_MODIFIERS) == 13

    def test_values_match_spec(self):
        assert PROVINCE_MODIFIERS == _EXPECTED

    def test_every_province_has_description_and_name(self):
        for pid in PROVINCE_MODIFIERS:
            assert pid in PROVINCE_MODIFIER_DESC, f"{pid} 缺说明"
            assert pid in PROVINCE_NAMES, f"{pid} 缺中文名"

    def test_json_matches_constant_table(self):
        """data/provinces.json 的 modifier 字段必须与常数表逐条一致。

        这是防漂移守卫：数据行与引擎正本若分叉，game 用常数表、前端看 JSON，
        两边会显示不同的数字。
        """
        rows = json.loads(_PROVINCES_JSON.read_text(encoding="utf-8"))
        assert len(rows) == 13
        for row in rows:
            pid = row["id"]
            assert row.get("modifiers") == PROVINCE_MODIFIERS[pid], (
                f"{pid} 的 JSON modifier 与常数表不一致: "
                f"{row.get('modifiers')} != {PROVINCE_MODIFIERS[pid]}"
            )
            assert row.get("modifier_desc") == PROVINCE_MODIFIER_DESC[pid]

    def test_unknown_or_none_returns_empty(self):
        assert get_province_modifiers(None) == {}
        assert get_province_modifiers("") == {}
        assert get_province_modifiers("not_a_province") == {}
        assert get_modifier_desc(None) == ""
        assert get_modifier_desc("not_a_province") == ""


# ============================================================
# 2. 产出倍率真的进入 ResourceSystem
# ============================================================

class TestProductionMultiplier:
    def test_gold_multiplier_applied(self):
        rs = ResourceSystem()
        base = rs.calculate_gold_production(_city("base", province_id=None))
        rich = rs.calculate_gold_production(_city("rich", province_id="sili"))      # 1.15
        poor = rs.calculate_gold_production(_city("poor", province_id="jiaozhou"))  # 0.90

        assert rich > base > poor, (rich, base, poor)
        # 精确验证倍率（level3/pop30000/morale70/无将无地块 → 基线 500）
        assert base == 500
        assert rich == int(500 * 1.15)
        assert poor == int(500 * 0.90)

    def test_food_multiplier_applied(self):
        rs = ResourceSystem()
        base = rs.calculate_food_production(_city("base", province_id=None))
        top = rs.calculate_food_production(_city("yizhou", province_id="yizhou"))    # 1.20
        mid = rs.calculate_food_production(_city("jizhou", province_id="jizhou"))    # 1.15

        assert top > mid > base, (top, mid, base)
        assert base == 700
        assert top == int(700 * 1.20)
        assert mid == int(700 * 1.15)

    def test_multiplier_only_affects_matching_resource(self):
        """gold modifier 不应改粮草产出，反之亦然（倍率正交）。"""
        rs = ResourceSystem()
        base_food = rs.calculate_food_production(_city("b", province_id=None))
        sili_food = rs.calculate_food_production(_city("s", province_id="sili"))
        assert sili_food == base_food  # 司隶只有 gold modifier

        base_gold = rs.calculate_gold_production(_city("b2", province_id=None))
        yizhou_gold = rs.calculate_gold_production(_city("y", province_id="yizhou"))
        assert yizhou_gold == base_gold  # 益州只有 food modifier


# ============================================================
# 3. 征兵成本倍率真的进入 CitySystem.recruit
# ============================================================

class TestRecruitCostMultiplier:
    def test_recruit_cheaper_in_liangzhou(self):
        cs = CitySystem()
        base = cs.recruit(_city("base", province_id=None, garrison=0), 100)
        cheap = cs.recruit(_city("liang", province_id="liangzhou", garrison=0), 100)

        assert base.success and cheap.success
        assert base.troops_recruited == cheap.troops_recruited == 100
        # 基线：100 金 + 200 粮；凉州 -10%：90 金 + 180 粮
        assert base.gold_cost == 100 and base.food_cost == 200
        assert cheap.gold_cost == 90 and cheap.food_cost == 180
        assert cheap.gold_cost < base.gold_cost

    def test_recruit_cost_multiplier_value(self):
        assert province_recruit_cost_multiplier("liangzhou") == 0.90
        assert province_recruit_cost_multiplier("youzhou") == 0.90
        assert province_recruit_cost_multiplier("bingzhou") == 0.95
        assert province_recruit_cost_multiplier(None) == 1.0
        assert province_recruit_cost_multiplier("sili") == 1.0  # 司隶无征兵 modifier


def test_gold_multiplier_helper_values():
    assert province_gold_multiplier("sili") == 1.15
    assert province_gold_multiplier("jiaozhou") == 0.90
    assert province_gold_multiplier(None) == 1.0
    assert province_gold_multiplier("jizhou") == 1.0  # 冀州是 food modifier


# ============================================================
# 4. 加载链：provinces.json → Province 模型（modifier 字段不丢）
# ============================================================

class TestProvinceModelLoadsModifiers:
    def test_province_model_carries_modifiers(self):
        from game.data_loader import load_game_data
        from game.models import Province

        data = load_game_data()
        for row in data["provinces"]:
            prov = Province(**row)
            assert prov.modifiers == PROVINCE_MODIFIERS[prov.id], (
                f"{prov.id} 经 Province 模型后 modifier 丢失/被忽略"
            )
            assert prov.modifier_desc == PROVINCE_MODIFIER_DESC[prov.id]
