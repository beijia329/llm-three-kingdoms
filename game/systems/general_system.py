"""将领系统

管理将领的招募、忠诚度、赏赐、俘虏与投降等功能。
使用确定性随机数保证结果可复现。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from game.constants import (
    EXPLORE_BASE_CHANCE,
    EXPLORE_MORALE_FACTOR,
    REWARD_LOYALTY_BONUS_PER_100_GOLD,
    # v4.0 忠诚度机制重写新增
    DEFAULT_LOYALTY_BASELINE,
    LOYALTY_REGRESSION_PER_TURN,
    LOYALTY_DEVOTED_THRESHOLD,
    LOYALTY_LOYAL_THRESHOLD,
    LOYALTY_NORMAL_THRESHOLD,
    LOYALTY_UNSTABLE_THRESHOLD,
    SURRENDER_CHANCE_DEVOTED,
    SURRENDER_CHANCE_LOYAL,
    SURRENDER_CHANCE_NORMAL,
    SURRENDER_CHANCE_UNSTABLE,
    SURRENDER_CHANCE_DANGEROUS,
    SURRENDER_INITIAL_LOYALTY,
    SURRENDER_LOYALTY_BASELINE,
    LOYALTY_COMBAT_BONUS_DEVOTED,
    LOYALTY_COMBAT_PENALTY_UNSTABLE,
    LOYALTY_COMBAT_PENALTY_DANGEROUS,
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
    general_loyalty: int = 0
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

POTENTIAL_GENERALS: List[Dict[str, Any]] = [
    # 名字与五维均按史实设定（v4.0 修正）
    #
    # 🔴 原实现用 POTENTIAL_GENERAL_NAMES（徐庶/法正/庞统…这些真实人物名）
    #    配 `randint(60,95)` 的随机属性 → 探索出来的"庞统"可能统帅 60 政治 40，
    #    人设与数值完全脱节，同一局里"庞统"的属性还每次重开都不同。
    {"name": "徐庶", "command": 82, "politics": 78, "bravery": 68, "intelligence": 90, "loyalty": 88},
    {"name": "法正", "command": 78, "politics": 85, "bravery": 45, "intelligence": 92, "loyalty": 85},
    {"name": "庞统", "command": 80, "politics": 82, "bravery": 50, "intelligence": 93, "loyalty": 86},
    {"name": "姜维", "command": 90, "politics": 75, "bravery": 85, "intelligence": 88, "loyalty": 95},
    {"name": "魏延", "command": 85, "politics": 45, "bravery": 88, "intelligence": 65, "loyalty": 70},
    {"name": "张辽", "command": 92, "politics": 65, "bravery": 90, "intelligence": 78, "loyalty": 90},
    {"name": "徐晃", "command": 86, "politics": 60, "bravery": 85, "intelligence": 72, "loyalty": 88},
    {"name": "张郃", "command": 85, "politics": 62, "bravery": 82, "intelligence": 76, "loyalty": 80},
    {"name": "于禁", "command": 82, "politics": 65, "bravery": 78, "intelligence": 70, "loyalty": 75},
    {"name": "乐进", "command": 78, "politics": 50, "bravery": 82, "intelligence": 60, "loyalty": 85},
    {"name": "甘宁", "command": 80, "politics": 40, "bravery": 92, "intelligence": 65, "loyalty": 80},
    {"name": "吕蒙", "command": 88, "politics": 70, "bravery": 80, "intelligence": 86, "loyalty": 92},
    {"name": "陆逊", "command": 90, "politics": 82, "bravery": 65, "intelligence": 92, "loyalty": 90},
    {"name": "周泰", "command": 75, "politics": 40, "bravery": 88, "intelligence": 55, "loyalty": 95},
    {"name": "凌统", "command": 76, "politics": 45, "bravery": 85, "intelligence": 58, "loyalty": 88},
    {"name": "黄忠", "command": 82, "politics": 50, "bravery": 92, "intelligence": 65, "loyalty": 85},
    {"name": "王平", "command": 80, "politics": 68, "bravery": 78, "intelligence": 72, "loyalty": 88},
    {"name": "廖化", "command": 70, "politics": 60, "bravery": 72, "intelligence": 62, "loyalty": 90},
    {"name": "李严", "command": 78, "politics": 80, "bravery": 70, "intelligence": 75, "loyalty": 65},
    {"name": "邓艾", "command": 90, "politics": 78, "bravery": 80, "intelligence": 88, "loyalty": 82},
]
"""可被探索发现的人才池（名字与五维均为史实设定，按固定顺序取用保证确定性）"""


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
            # 发现新将领：从史实人才池按顺序取（确定性，且属性与人设一致）
            profile = POTENTIAL_GENERALS[
                self._next_general_index % len(POTENTIAL_GENERALS)
            ]
            self._next_general_index += 1

            name = profile["name"]
            command = profile["command"]
            politics = profile["politics"]
            bravery = profile["bravery"]
            intelligence = profile["intelligence"]
            loyalty = profile["loyalty"]

            return ExploreResult(
                found=True,
                general_name=name,
                general_command=command,
                general_politics=politics,
                general_bravery=bravery,
                general_intelligence=intelligence,
                general_loyalty=loyalty,
                description=f"发现了人才【{name}】！统帅{command}，政治{politics}，"
                f"勇武{bravery}，智力{intelligence}，忠诚{loyalty}",
            )

        return ExploreResult(description="本次探索没有发现人才")

    def _generate_general_name(self) -> str:
        """生成探索发现的将领名字（已废弃，保留以兼容旧引用与测试）

        Returns:
            人才池中下一个将领的名字
        """
        name = POTENTIAL_GENERALS[
            self._next_general_index % len(POTENTIAL_GENERALS)
        ]["name"]
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
        """处理将领每回合忠诚度变化（向基准值回归）

        🔴 v4.0 重写。原实现是 `int(general.loyalty - LOYALTY_DECAY_PER_TURN)`，
        有两个致命问题：

        1. **int() 是向零截断**：`int(88 - 0.5) = int(87.5) = 87` —— 实际每回合
           精确掉 **1 点**（而非设计意图的 0.5 点）。实测 192 回合：turn 96 忠诚度
           中位数已为 0，**turn 144 起全部 53 名武将忠诚度归零**。
        2. **单调递减、无回升途径**：唯一回升方式是 `reward` 命令，而 CLI AI
           全程不发（实测命令计数 RewardCommand = 0 次）→ 忠诚机制事实上不存在，
           连带 `LOYALTY_COMBAT_*`、投降判定、俘虏链全部失效。

        新机制：忠诚度向 `loyalty_baseline`（将领对本势力的本性归属感）回归 ——
        - 低于基准 → 每回合 +1（人心思归）
        - 高于基准 → 每回合 -1（功高震主/久疏赏赐）
        - 等于基准 → 不变
        这样忠诚度围绕人物本性小幅波动，既不会集体归零，也让「赏赐」「被俘」
        「失城」等事件造成的偏离有意义（偏离后会自动缓慢回归）。

        Args:
            general: 目标将领

        Returns:
            忠诚度变化量（负值表示下降，0 表示无变化）
        """
        if general.is_captured:
            return 0

        baseline = general.loyalty_baseline
        if baseline is None:
            baseline = DEFAULT_LOYALTY_BASELINE

        old_loyalty = general.loyalty
        if general.loyalty < baseline:
            general.loyalty = min(baseline, general.loyalty + LOYALTY_REGRESSION_PER_TURN)
        elif general.loyalty > baseline:
            general.loyalty = max(baseline, general.loyalty - LOYALTY_REGRESSION_PER_TURN)

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
            # v4.0：投降者的忠诚基准同步下调到 SURRENDER_LOYALTY_BASELINE。
            # 原实现只把当前忠诚设为 50，基准仍是旧主的开局值（可能 90+）→
            # 在新机制下会每回合 +1 一路回归 90，等于"降将三天变死忠"。
            general.loyalty = SURRENDER_INITIAL_LOYALTY
            general.loyalty_baseline = SURRENDER_LOYALTY_BASELINE

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
        """计算投降概率（按忠诚度分档）

        🔴 v4.0 重设。原公式 `0.30 - loyalty × 0.01` 在**所有可能的初始忠诚度下
        都算不出正概率**：数据里忠诚度范围是 65~100，代入即 0.30-0.65 = 负值，
        被 max(0.0, ...) 截为 0 → **投降永远不会发生**，
        连带 `process_capture` 的投降分支、俘虏转化机制全部形同虚设。

        新公式按既有忠诚度阈值分档（阈值常量本就在 constants 里定义，
        原实现却没有使用）：
            >= 90 死忠   → 0.00（绝不投降）
            >= 70 忠诚   → 0.05
            >= 50 一般   → 0.25
            >= 30 不稳   → 0.50
            <  30 危险   → 0.75

        Args:
            general: 被俘将领

        Returns:
            投降概率 (0-1)
        """
        loyalty = general.loyalty
        if loyalty >= LOYALTY_DEVOTED_THRESHOLD:
            return SURRENDER_CHANCE_DEVOTED
        if loyalty >= LOYALTY_LOYAL_THRESHOLD:
            return SURRENDER_CHANCE_LOYAL
        if loyalty >= LOYALTY_NORMAL_THRESHOLD:
            return SURRENDER_CHANCE_NORMAL
        if loyalty >= LOYALTY_UNSTABLE_THRESHOLD:
            return SURRENDER_CHANCE_UNSTABLE
        return SURRENDER_CHANCE_DANGEROUS


def loyalty_combat_factor(loyalty: int) -> float:
    """忠诚度 → 战斗力系数

    v4.0 新增：把原本定义了却从未被引用的 `LOYALTY_COMBAT_*` 常量真正接进战斗。
    按忠诚度阈值分档：
        >= 90 死忠 → ×1.10（士气高昂）
        >= 70 忠诚 → ×1.00（中性）
        >= 30 不稳 → ×0.90（军心浮动）
        <  30 危险 → ×0.80（随时哗变）
    这让「赏赐 / 民心 / 被俘 / 失城」等忠诚度事件第一次有了直接的军事后果。

    Args:
        loyalty: 将领当前忠诚度

    Returns:
        伤害系数（1.10 / 1.00 / 0.90 / 0.80）
    """
    if loyalty >= LOYALTY_DEVOTED_THRESHOLD:
        return 1.0 + LOYALTY_COMBAT_BONUS_DEVOTED
    if loyalty >= LOYALTY_LOYAL_THRESHOLD:
        return 1.0
    if loyalty >= LOYALTY_UNSTABLE_THRESHOLD:
        return 1.0 + LOYALTY_COMBAT_PENALTY_UNSTABLE
    return 1.0 + LOYALTY_COMBAT_PENALTY_DANGEROUS
