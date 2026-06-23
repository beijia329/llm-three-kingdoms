"""将领系统

管理将领的招募、忠诚度、赏赐、俘虏与投降等功能。
使用确定性随机数保证结果可复现。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from game.constants import (
    EXPLORE_BASE_CHANCE,
    EXPLORE_MORALE_FACTOR,
    LOYALTY_DECAY_PER_TURN,
    REWARD_LOYALTY_BONUS_PER_100_GOLD,
    CAPTURE_SURRENDER_BASE_CHANCE,
    CAPTURE_SURRENDER_LOYALTY_FACTOR,
)
from game.models import City, General
from game.random import GameRandom


# ============================================================
# 结果数据结构
# ============================================================


@dataclass
class ExploreResult:
    """探索结果"""

    found: bool = False
    general_name: str = ""
    general_command: int = 0
    general_politics: int = 0
    general_bravery: int = 0
    general_intelligence: int = 0
    description: str = ""


@dataclass
class RewardResult:
    """赏赐结果"""

    success: bool = False
    gold_spent: int = 0
    loyalty_change: int = 0
    description: str = ""


@dataclass
class CaptureResult:
    """被俘结果"""

    is_captured: bool = False
    surrendered: bool = False
    description: str = ""


# ============================================================
# 探索用将领名字库
# ============================================================

POTENTIAL_GENERAL_NAMES: List[str] = [
    "徐庶", "法正", "庞统", "姜维", "魏延",
    "张辽", "徐晃", "张郃", "于禁", "乐进",
    "甘宁", "吕蒙", "陆逊", "周泰", "黄盖",
    "马超", "黄忠", "严颜", "王平", "廖化",
]


class GeneralSystem:
    """将领系统

    管理将领的完整生命周期：探索发现、忠诚度管理、俘虏与投降。
    """

    def __init__(self, rng: GameRandom) -> None:
        """初始化将领系统

        Args:
            rng: 确定性随机数生成器
        """
        self._rng = rng
        self._next_general_index: int = 0

    # ============================================================
    # 探索人才
    # ============================================================

    def explore(self, city: City) -> ExploreResult:
        """在城市探索发现新将领

        探索概率受城市民心影响。

        Args:
            city: 探索目标城市

        Returns:
            探索结果
        """
        # 计算探索成功率
        success_chance = EXPLORE_BASE_CHANCE + city.morale * EXPLORE_MORALE_FACTOR
        success_chance = min(success_chance, 0.8)  # 上限80%

        if self._rng.random() < success_chance:
            # 发现新将领
            name = self._generate_general_name()

            # 生成随机属性（60-95之间）
            command = self._rng.randint(60, 95)
            politics = self._rng.randint(40, 90)
            bravery = self._rng.randint(50, 95)
            intelligence = self._rng.randint(40, 90)

            return ExploreResult(
                found=True,
                general_name=name,
                general_command=command,
                general_politics=politics,
                general_bravery=bravery,
                general_intelligence=intelligence,
                description=f"发现了人才【{name}】！统帅{command}，政治{politics}，"
                f"勇武{bravery}，智力{intelligence}",
            )

        return ExploreResult(description="本次探索没有发现人才")

    def _generate_general_name(self) -> str:
        """生成探索发现的将领名字

        Returns:
            将领名字
        """
        names = POTENTIAL_GENERAL_NAMES
        name = names[self._next_general_index % len(names)]
        self._next_general_index += 1
        return name

    # ============================================================
    # 赏赐将领
    # ============================================================

    def reward(self, general: General, city: City, gold: int) -> RewardResult:
        """赏赐将领提升忠诚度

        每100金提升5点忠诚度（受MAX_LOYALTY_FROM_REWARD限制）。

        Args:
            general: 目标将领
            city: 从哪个城市支付（从城市金库扣除）
            gold: 赏赐金额

        Returns:
            赏赐结果
        """
        if gold <= 0:
            return RewardResult(
                success=False,
                description="赏赐金额必须大于0",
            )

        if city.gold < gold:
            return RewardResult(
                success=False,
                description=f"金钱不足: 需要{gold}, 当前{city.gold}",
            )

        # 计算忠诚度提升
        loyalty_increase = int(gold / 100) * REWARD_LOYALTY_BONUS_PER_100_GOLD
        if loyalty_increase <= 0:
            loyalty_increase = 1  # 不足100金也有1点提升

        # 执行赏赐
        city.gold -= gold
        old_loyalty = general.loyalty
        general.loyalty = min(general.loyalty + loyalty_increase, 100)
        actual_increase = general.loyalty - old_loyalty

        return RewardResult(
            success=True,
            gold_spent=gold,
            loyalty_change=actual_increase,
            description=f"赏赐{general.name} {gold}金，忠诚度+{actual_increase}",
        )

    # ============================================================
    # 忠诚度衰减（每回合）
    # ============================================================

    def process_turn_decay(self, general: General) -> int:
        """处理将领每回合忠诚度衰减

        Args:
            general: 目标将领

        Returns:
            忠诚度变化量（负值表示衰减）
        """
        if general.is_captured:
            return 0

        old_loyalty = general.loyalty
        general.loyalty = max(0, int(general.loyalty - LOYALTY_DECAY_PER_TURN))

        return general.loyalty - old_loyalty

    # ============================================================
    # 俘虏与投降
    # ============================================================

    def process_capture(
        self,
        general: General,
        captor_faction: str,
        turn: int = 0,
    ) -> CaptureResult:
        """处理将领被俘及投降判定

        Args:
            general: 被俘将领
            captor_faction: 俘虏方势力
            turn: 当前回合

        Returns:
            被俘结果
        """
        # 标记为被俘
        general.is_captured = True
        general.captured_turn = turn
        general.captor_faction = captor_faction

        # 投降判定
        surrender_chance = self._calculate_surrender_chance(general)

        if self._rng.random() < surrender_chance:
            # 投降
            general.faction = captor_faction
            general.is_captured = False
            general.loyalty = 50  # 投降后初始忠诚

            return CaptureResult(
                is_captured=True,
                surrendered=True,
                description=f"{general.name}投降了{captor_faction}！",
            )

        return CaptureResult(
            is_captured=True,
            surrendered=False,
            description=f"{general.name}宁死不降，被关押中",
        )

    def _calculate_surrender_chance(self, general: General) -> float:
        """计算投降概率

        基础概率30%，每点忠诚度降低1%概率。

        Args:
            general: 被俘将领

        Returns:
            投降概率 (0-1)
        """
        chance = CAPTURE_SURRENDER_BASE_CHANCE
        chance -= general.loyalty * CAPTURE_SURRENDER_LOYALTY_FACTOR
        return max(0.0, min(1.0, chance))
