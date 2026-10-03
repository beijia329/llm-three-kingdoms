"""忠诚度机制单元测试（v4.0 重写验收）

覆盖两类历史缺陷：
1. `int(loyalty - 0.5)` 向零截断 → 每回合精确掉 1 点 → 144 回合后全员归零
2. 投降率 `0.30 - loyalty×0.01` 在数据区间（65~100）内恒为负 → 投降永不发生
以及 v4.0 新增的「忠诚度影响战斗」。
"""

import pytest

from game.constants import (
    LOYALTY_COMBAT_BONUS_DEVOTED,
    LOYALTY_COMBAT_PENALTY_DANGEROUS,
    LOYALTY_COMBAT_PENALTY_UNSTABLE,
    LOYALTY_DEVOTED_THRESHOLD,
    LOYALTY_LOYAL_THRESHOLD,
    SURRENDER_CHANCE_DANGEROUS,
    SURRENDER_CHANCE_DEVOTED,
    SURRENDER_CHANCE_LOYAL,
    SURRENDER_CHANCE_NORMAL,
    SURRENDER_CHANCE_UNSTABLE,
    SURRENDER_INITIAL_LOYALTY,
    SURRENDER_LOYALTY_BASELINE,
)
from game.models import City, General
from game.random import GameRandom
from game.systems.general_system import GeneralSystem, loyalty_combat_factor


def _general(loyalty: int = 80, baseline: int = None, **kw) -> General:
    base = dict(
        id="g1", name="测试将", faction="caocao",
        command=70, politics=60, bravery=70, intelligence=60,
        loyalty=loyalty, location="test_city",
    )
    base.update(kw)
    if baseline is not None:
        base["loyalty_baseline"] = baseline
    return General(**base)


def _city(**kw) -> City:
    base = dict(
        id="test_city", name="测试城", faction="caocao", level=2,
        wall_hp=1000, wall_max_hp=1000, gold=1000, food=1000,
        population=15000, morale=70, garrison=500,
    )
    base.update(kw)
    return City(**base)


# ============================================================
# 忠诚度回归
# ============================================================

class TestLoyaltyRegression:
    """忠诚度向基准值回归"""

    def test_below_baseline_recovers(self):
        """低于基准 → 每回合 +1"""
        gs = GeneralSystem(GameRandom(seed=1))
        g = _general(loyalty=60, baseline=80)
        assert gs.process_turn_decay(g) == 1
        assert g.loyalty == 61

    def test_above_baseline_decays(self):
        """高于基准 → 每回合 -1"""
        gs = GeneralSystem(GameRandom(seed=1))
        g = _general(loyalty=90, baseline=80)
        assert gs.process_turn_decay(g) == -1
        assert g.loyalty == 89

    def test_at_baseline_is_stable(self):
        """等于基准 → 不变"""
        gs = GeneralSystem(GameRandom(seed=1))
        g = _general(loyalty=80, baseline=80)
        assert gs.process_turn_decay(g) == 0
        assert g.loyalty == 80

    def test_never_collapses_to_zero(self):
        """🔴 回归测试：跑 200 回合忠诚度不会归零【历史缺陷】

        原实现每回合精确掉 1 点，192 回合后全员忠诚度 = 0。
        新机制下应稳定在基准附近。
        """
        gs = GeneralSystem(GameRandom(seed=1))
        g = _general(loyalty=80, baseline=80)
        for _ in range(200):
            gs.process_turn_decay(g)
        assert g.loyalty == 80

    def test_recovers_to_baseline_after_loss(self):
        """被俘/失城造成的偏离会自动回归"""
        gs = GeneralSystem(GameRandom(seed=1))
        g = _general(loyalty=30, baseline=85)
        for _ in range(100):
            gs.process_turn_decay(g)
        assert g.loyalty == 85

    def test_captured_general_does_not_change(self):
        """被俘期间忠诚度不参与回归"""
        gs = GeneralSystem(GameRandom(seed=1))
        g = _general(loyalty=50, baseline=80, is_captured=True)
        assert gs.process_turn_decay(g) == 0
        assert g.loyalty == 50

    def test_default_baseline_when_unset(self):
        """未设置基准时回退默认值，不会崩"""
        gs = GeneralSystem(GameRandom(seed=1))
        g = _general(loyalty=50)
        g.loyalty_baseline = None
        assert gs.process_turn_decay(g) == 1  # 50 < 70 → 回升


# ============================================================
# 投降判定
# ============================================================

class TestSurrenderChance:
    """投降概率分档"""

    @pytest.mark.parametrize("loyalty,expected", [
        (100, SURRENDER_CHANCE_DEVOTED),
        (LOYALTY_DEVOTED_THRESHOLD, SURRENDER_CHANCE_DEVOTED),
        (89, SURRENDER_CHANCE_LOYAL),
        (70, SURRENDER_CHANCE_LOYAL),
        (69, SURRENDER_CHANCE_NORMAL),
        (50, SURRENDER_CHANCE_NORMAL),
        (49, SURRENDER_CHANCE_UNSTABLE),
        (30, SURRENDER_CHANCE_UNSTABLE),
        (29, SURRENDER_CHANCE_DANGEROUS),
        (0, SURRENDER_CHANCE_DANGEROUS),
    ])
    def test_surrender_tiers(self, loyalty, expected):
        gs = GeneralSystem(GameRandom(seed=1))
        assert gs._calculate_surrender_chance(_general(loyalty=loyalty)) == pytest.approx(expected)

    def test_devoted_never_surrenders(self):
        """死忠（>=90）绝不投降"""
        gs = GeneralSystem(GameRandom(seed=1))
        assert gs._calculate_surrender_chance(_general(loyalty=95)) == 0.0

    def test_high_loyalty_can_still_surrender(self):
        """🔴 回归测试：高忠诚度将领并非永不投降【历史缺陷】

        原公式 0.30 - 65×0.01 = -0.35 → 被截断为 0，导致数据中
        全部 53 名武将（忠诚 65~100）都不可能投降过。
        新机制下忠诚 60 的将领应有 25% 概率。
        """
        gs = GeneralSystem(GameRandom(seed=1))
        assert gs._calculate_surrender_chance(_general(loyalty=60)) > 0.0
        assert gs._calculate_surrender_chance(_general(loyalty=60)) == pytest.approx(SURRENDER_CHANCE_NORMAL)

    def test_surrender_lowers_baseline(self):
        """投降后忠诚基准必须同步下调，否则降将很快又变死忠"""
        gs = GeneralSystem(GameRandom(seed=1))
        g = _general(loyalty=20, baseline=95)  # 低忠诚 + 高基准 → 高投降率
        result = gs.process_capture(g, captor_faction="liubei", turn=10)
        assert result.surrendered is True
        assert g.faction == "liubei"
        assert g.loyalty == SURRENDER_INITIAL_LOYALTY
        assert g.loyalty_baseline == SURRENDER_LOYALTY_BASELINE


# ============================================================
# 忠诚度 → 战斗力
# ============================================================

class TestLoyaltyCombatFactor:
    """LOYALTY_COMBAT_* 死常量接入战斗（v4.0）"""

    def test_devoted_bonus(self):
        """死忠 +10%"""
        assert loyalty_combat_factor(95) == pytest.approx(1.0 + LOYALTY_COMBAT_BONUS_DEVOTED)

    def test_normal_is_neutral(self):
        """忠诚 70~89 无修正"""
        assert loyalty_combat_factor(80) == pytest.approx(1.0)
        assert loyalty_combat_factor(LOYALTY_DEVOTED_THRESHOLD - 1) == pytest.approx(1.0)
        assert loyalty_combat_factor(LOYALTY_LOYAL_THRESHOLD) == pytest.approx(1.0)

    def test_unstable_penalty(self):
        """不稳（30~49）-10%"""
        assert loyalty_combat_factor(40) == pytest.approx(1.0 + LOYALTY_COMBAT_PENALTY_UNSTABLE)

    def test_dangerous_penalty(self):
        """危险（<30）-20%"""
        assert loyalty_combat_factor(10) == pytest.approx(1.0 + LOYALTY_COMBAT_PENALTY_DANGEROUS)

    def test_monotonic_non_increasing(self):
        """忠诚度越高，战力系数不得越低"""
        factors = [loyalty_combat_factor(l) for l in range(0, 101, 5)]
        assert all(a <= b for a, b in zip(factors, factors[1:]))
