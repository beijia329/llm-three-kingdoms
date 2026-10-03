"""五行属性与相克系统单元测试（v4.0 新增）"""

import pytest

from game.element import (
    ELEMENT_COUNTER_BONUS,
    ELEMENT_EARTH,
    ELEMENT_FIRE,
    ELEMENT_METAL,
    ELEMENT_ORDER,
    ELEMENT_WATER,
    ELEMENT_WOOD,
    counter_factor,
    derive_element,
    element_label,
    element_of,
)
from game.models import General


def _general(**kw) -> General:
    base = dict(
        id="g1", name="测试将", faction="caocao",
        command=50, politics=50, bravery=50, intelligence=50,
        loyalty=50, location="test_city",
    )
    base.update(kw)
    return General(**base)


class TestDeriveElement:
    """五行推导"""

    def test_bravery_dominant_is_fire(self):
        """勇武最高 → 火（猛将）"""
        assert derive_element(bravery=95, command=60, intelligence=50, politics=40, loyalty=70) == ELEMENT_FIRE

    def test_command_dominant_is_earth(self):
        """统帅最高 → 土（统帅）"""
        assert derive_element(bravery=60, command=95, intelligence=50, politics=40, loyalty=70) == ELEMENT_EARTH

    def test_intelligence_dominant_is_metal(self):
        """智力最高 → 金（谋士）"""
        assert derive_element(bravery=30, command=40, intelligence=96, politics=60, loyalty=85) == ELEMENT_METAL

    def test_politics_dominant_is_water(self):
        """政治最高 → 水（能臣）"""
        assert derive_element(bravery=30, command=50, intelligence=60, politics=95, loyalty=70) == ELEMENT_WATER

    def test_loyalty_dominant_is_wood(self):
        """忠诚突出且四维平庸 → 木（忠臣）"""
        assert derive_element(bravery=50, command=50, intelligence=50, politics=50, loyalty=100) == ELEMENT_WOOD

    def test_loyalty_weighted_not_overwhelming(self):
        """忠诚度必须加权，不能因普遍偏高就让所有人都变「木」

        数据里忠诚度均值 88.8、区间 65~100，而其它四维均值 62~72。
        若不加权，一名智力 90 的谋士（忠诚 90）会被误判成「木」。
        加权 0.8 后：智力 90 > 忠诚 90×0.8=72 → 正确判为「金」。
        """
        assert derive_element(bravery=30, command=40, intelligence=90, politics=50, loyalty=90) == ELEMENT_METAL

    def test_tie_break_is_deterministic(self):
        """并列时按 ELEMENT_ORDER 固定优先级裁决（可复现）"""
        results = {
            derive_element(bravery=80, command=80, intelligence=80, politics=80, loyalty=100)
            for _ in range(20)
        }
        assert len(results) == 1
        # 火在 ELEMENT_ORDER 中优先级最高（忠诚 100×0.8=80 与四维 80 并列）
        assert results.pop() == ELEMENT_FIRE

    def test_returns_valid_element(self):
        """返回值必须在五行集合内"""
        for b in (10, 50, 99):
            for c in (10, 50, 99):
                e = derive_element(bravery=b, command=c, intelligence=50, politics=50, loyalty=70)
                assert e in ELEMENT_ORDER

    def test_element_of_general(self):
        """element_of 与 derive_element 对同一将领结果一致"""
        g = _general(bravery=95, command=60, intelligence=50, politics=40, loyalty=70)
        assert element_of(g) == derive_element(95, 60, 50, 40, 70) == ELEMENT_FIRE


class TestCounterFactor:
    """五行相克"""

    @pytest.mark.parametrize("attacker,defender", [
        (ELEMENT_FIRE, ELEMENT_METAL),
        (ELEMENT_METAL, ELEMENT_WOOD),
        (ELEMENT_WOOD, ELEMENT_EARTH),
        (ELEMENT_EARTH, ELEMENT_WATER),
        (ELEMENT_WATER, ELEMENT_FIRE),
    ])
    def test_counter_cycle(self, attacker, defender):
        """完整相克环：火→金→木→土→水→火，克制方 +15%"""
        assert counter_factor(attacker, defender) == pytest.approx(1.0 + ELEMENT_COUNTER_BONUS)

    def test_countered_side_gets_penalty(self):
        """反向即为被克，-15%"""
        assert counter_factor(ELEMENT_METAL, ELEMENT_FIRE) == pytest.approx(1.0 - ELEMENT_COUNTER_BONUS)

    def test_same_element_is_neutral(self):
        """同行相争无克制"""
        assert counter_factor(ELEMENT_FIRE, ELEMENT_FIRE) == 1.0

    def test_non_counter_pair_is_neutral(self):
        """不相克的组合为 1.0（火 vs 土）"""
        assert counter_factor(ELEMENT_FIRE, ELEMENT_EARTH) == 1.0

    def test_empty_element_is_neutral(self):
        """未知五行（空串）不产生克制，避免无将部队被莫名克制"""
        assert counter_factor("", ELEMENT_FIRE) == 1.0
        assert counter_factor(ELEMENT_FIRE, "") == 1.0
        assert counter_factor("", "") == 1.0

    def test_counter_is_antisymmetric(self):
        """A 克 B 与 B 被 A 克必须互补且都偏离 1.0"""
        up = counter_factor(ELEMENT_FIRE, ELEMENT_METAL)
        down = counter_factor(ELEMENT_METAL, ELEMENT_FIRE)
        assert up > 1.0 > down


class TestElementLabel:
    def test_label_contains_name_and_role(self):
        assert "火" in element_label(ELEMENT_FIRE)
        assert "猛将" in element_label(ELEMENT_FIRE)

    def test_unknown_label(self):
        assert element_label("") == "—"
