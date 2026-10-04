"""战斗结算器

处理战斗的核心逻辑：伤害计算、士气变化、胜负判定、战后处理。

战斗流程：
1. 围城阶段：攻击方每回合对城墙造成伤害
2. 城墙破后进入巷战阶段：双方每回合互伤
3. 满足任一结束条件时停止，执行战后处理

公式参考：docs/design/battle-system.md 第四章

围城伤害：
    wall_damage = WALL_DAMAGE_BASE × force_multiplier × command_bonus
    force_multiplier = min(attack_soldiers / garrison, 3)
    command_bonus = 1 + (command - 50) / 100

巷战伤害：
    base_damage = soldiers × 0.1
    command_bonus = 1 + (command - 50) / 100
    morale_bonus = morale / 100
    terrain_bonus = 1.0 (攻方) / 1.3 (守方)
    final_damage = base_damage × command_bonus × morale_bonus × terrain_bonus

士气变化：
    损失10%兵力 → -5士气
    击杀10%敌军 → +3士气

胜负条件（任一满足）：
    1. 攻击方兵力 ≤ 0 → 防守方胜利
    2. 防守方兵力 ≤ 0 → 攻击方胜利
    3. 超过10回合 → 平局
    4. 攻击方士气 < 20 → 攻击方撤退
"""

from __future__ import annotations

import logging
import math
from typing import List, Optional

from game.constants import (
    WALL_DAMAGE_BASE,
    WALL_DAMAGE_FORCE_MULTIPLIER_CAP,
    COMMAND_ATTACK_BONUS_RATE,
    BASE_DAMAGE_RATE,
    DEFENDER_WALL_BONUS,
    MORALE_LOSS_PER_10_PERCENT_CASUALTY,
    MORALE_GAIN_PER_10_PERCENT_KILL,
    MORALE_BREAK_THRESHOLD,
    MAX_BATTLE_ROUNDS,
    COMMAND_COMBAT_BONUS_RATE,
    BRAVERY_CRITICAL_CHANCE_RATE,
    SIEGE_ENGINEER_INTELLIGENCE_RATE,
)
from game.models import (
    BattleContext,
    BattlePhase,
    BattleResult,
    BattleResultType,
    BattleType,
)
from game.random import GameRandom

logger = logging.getLogger(__name__)


class BattleResolver:
    """战斗结算器

    处理攻城战和野战的完整战斗流程。
    所有随机操作使用 GameRandom 保证确定性。
    """

    def __init__(self, rng: GameRandom) -> None:
        """初始化战斗结算器

        Args:
            rng: 确定性随机数生成器
        """
        self._rng = rng
        self._wall_hp: dict = {}  # battle_id -> current wall HP

    # ============================================================
    # 主入口：完整战斗结算
    # ============================================================

    def resolve_battle(self, context: BattleContext) -> BattleResult:
        """结算一场完整的战斗

        从当前阶段开始，逐回合处理直到战斗结束。

        Args:
            context: 战斗上下文（会被修改）

        Returns:
            战斗结果
        """
        battle_log: List[str] = []
        battle_log.append(
            f"战斗开始: {context.attacker_faction} vs {context.defender_faction}"
            f" (类型: {context.battle_type.value})"
        )

        # 初始化城墙耐久（攻城战才有）
        if context.battle_type == BattleType.SIEGE and context.battle_phase == BattlePhase.SIEGE:
            if context.wall_hp > 0:
                # 使用实际城市城墙耐久（含此前战斗已造成的损伤）
                self._wall_hp[context.battle_id] = context.wall_hp
                battle_log.append(
                    f"城墙耐久: {self._wall_hp[context.battle_id]}"
                )
            else:
                # [主系统修复 2026-10-01] 城墙耐久为 0 说明已被先前战斗打穿：
                # 直接进巷战，绝不用 _estimate_wall_hp 把城墙"复原"。
                self._wall_hp[context.battle_id] = 0
                context.battle_phase = BattlePhase.STREET
                battle_log.append("城墙已破(0)，直接进入巷战阶段")

        # 战斗回合循环
        while True:
            # 检查战斗是否应该结束
            end_result = self.check_battle_end(context)
            if end_result is not None:
                context.result = end_result
                battle_log.append(
                    f"战斗结束: {end_result.value} "
                    f"(回合 {context.round_count})"
                )
                break

            # 处理一个回合（含阶段切换逻辑）
            phase_changed = self.process_round(context)

            context.round_count += 1

            if phase_changed:
                # 阶段切换（如城墙被打破），记录但不额外递增
                battle_log.append(
                    f"城墙已破！进入巷战阶段 (回合 {context.round_count})"
                )
            else:
                battle_log.append(
                    f"回合 {context.round_count}: "
                    f"攻方{context.attacker_total_soldiers}人, "
                    f"守方{context.defender_total_soldiers}人, "
                    f"城墙剩余{self._wall_hp.get(context.battle_id, 'N/A')}"
                )

        # [主系统修复 2026-10-01] 回写城墙耐久到 context，
        # 使 GameEngine 的 defender_city.wall_hp = ctx.wall_hp 能持久化损伤，
        # 让跨回合围城可以累积（原实现从不回写，城墙每回合复原为满血）。
        if context.battle_id in self._wall_hp:
            context.wall_hp = self._wall_hp[context.battle_id]

        # 战后处理
        # 🔴 v4.0：必须把守方将领传进去。
        # 原实现只传 defender_city_owner=""，defender_generals 取默认 None → []，
        # process_aftermath 里 `for gen_id in defender_generals` 永不执行
        # → captured_generals 恒为空 → GameEngine 的 process_capture 永不被调用
        # → 俘虏、投降、降将转投整条链在生产环境完全断裂。
        result = self.process_aftermath(
            context,
            defender_city_owner="",  # 由 GameEngine 填充
            # 🔴 v4.0 修复，**勿删**：必须把守方将领传进去。
            #    不传 → defender_generals 取默认 None → [] →
            #    process_aftermath 里 `for gen_id in defender_generals` 永不执行 →
            #    captured_generals 恒为空 → GameEngine.process_capture 永不被调用 →
            #    俘虏 / 投降 / 降将转投整条链在生产环境完全断裂。
            #
            #    为什么加了注释还要加测试：单元测试曾全绿，是因为测试**直接给
            #    process_aftermath 传参**，绕过了本调用链（本项目"假绿"的经典形态）。
            #    2026-10-03 这行曾被发现误删（工作区未提交状态）。
            #
            #    🔴 2026-10-03 更正：以下原句为**失真声明**，已作废重写——
            #      「故由 tests/integration/test_battle_report.py 在生产链路上断言锁定」
            #    该说法不成立：test_battle_report.py 只断言 BattleReport /
            #    recent_battles 的字段契约，对 defender_generals 与
            #    process_capture **无任何断言**。原句出自凭文件名推断而非实跑，
            #    属本项目「记录失真」家族，此处保留痕迹以示警戒。
            #
            #    实测（改坏验证，2026-10-03）：把本行注释掉后跑
            #    tests/unit + tests/integration → 631 passed, 1 skipped, **0 failed**。
            #    即：本行曾经**没有任何自动化测试保护**——摘掉它 CI 不会报警，
            #    俘虏 / 投降 / 降将转投三条链会静默失效。
            #
            #    ✅ 2026-10-03 已补上生产链路回归守卫：
            #    `tests/integration/test_capture_chain.py`。该文件**不碰
            #    process_aftermath**，只走 `resolve_battle` + `_apply_battle_result`
            #    两个生产调用点，断言 captured_generals 与 process_capture 调用。
            #    并已做**改坏验证**：把本行注释掉后该文件 2 个用例全部变红
            #    （captured_generals == []），还原后复绿。篡改本行会被它挡住。
            defender_generals=list(context.defender_general_ids),
        )
        result.battle_log = battle_log

        return result

    # ============================================================
    # 单回合处理
    # ============================================================

    def process_round(self, context: BattleContext) -> bool:
        """处理一个战斗回合

        Args:
            context: 战斗上下文

        Returns:
            True 表示回合正常结束，False 表示阶段切换需要重新检测
        """
        if context.battle_phase == BattlePhase.SIEGE:
            return self._process_siege_round(context)
        elif context.battle_phase == BattlePhase.STREET:
            return self._process_street_round(context)
        else:
            return True

    def _process_siege_round(self, context: BattleContext) -> bool:
        """处理围城阶段的一个回合

        攻击方对城墙造成伤害。如果城墙被打破，切换到巷战阶段。

        Args:
            context: 战斗上下文

        Returns:
            True 表示回合结束，False 表示切换到巷战阶段
        """
        wall_damage = self.calculate_wall_damage(context)

        # 应用城墙伤害
        current_wall = self._wall_hp.get(context.battle_id, 0)
        current_wall -= wall_damage
        self._wall_hp[context.battle_id] = max(0, current_wall)

        # 检查城墙是否被打破
        if current_wall <= 0 and context.battle_phase == BattlePhase.SIEGE:
            context.battle_phase = BattlePhase.STREET
            return False

        return True

    @staticmethod
    def _estimate_wall_hp(context: BattleContext) -> int:
        """根据上下文估算城墙耐久

        基于防守方兵力和城市等级估算城墙耐久。
        实际游戏中由 GameEngine 传递准确值。

        Args:
            context: 战斗上下文

        Returns:
            估算的城墙耐久
        """
        # 防守方兵力 * 1.5 作为城墙耐久的粗略估算
        # 实际游戏中应该从城市数据获取
        base_hp = max(500, context.defender_total_soldiers * 2)
        return min(base_hp, 5000)  # 不超过5000

    def _process_street_round(self, context: BattleContext) -> bool:
        """处理巷战阶段的一个回合

        双方互相造成伤害，更新士气。

        Args:
            context: 战斗上下文
        """
        # 计算双方伤害
        attacker_damage = self.calculate_attacker_damage(context)
        defender_damage = self.calculate_defender_damage(context)

        # 应用伤害
        attacker_damage = min(attacker_damage, context.attacker_total_soldiers)
        defender_damage = min(defender_damage, context.defender_total_soldiers)

        context.attacker_total_soldiers -= defender_damage
        context.defender_total_soldiers -= attacker_damage

        # 确保不为负
        context.attacker_total_soldiers = max(0, context.attacker_total_soldiers)
        context.defender_total_soldiers = max(0, context.defender_total_soldiers)

        # 更新累计伤亡
        context.attacker_casualties += defender_damage
        context.defender_casualties += attacker_damage

        # 更新士气
        attacker_morale_change = self.calculate_morale_change(
            context, "attacker",
            casualties=defender_damage,
            total_before=context.attacker_total_soldiers + defender_damage,
            enemy_casualties=attacker_damage,
            enemy_total=context.defender_total_soldiers + attacker_damage,
        )
        defender_morale_change = self.calculate_morale_change(
            context, "defender",
            casualties=attacker_damage,
            total_before=context.defender_total_soldiers + attacker_damage,
            enemy_casualties=defender_damage,
            enemy_total=context.attacker_total_soldiers + defender_damage,
        )

        context.attacker_avg_morale = max(0.0,
            context.attacker_avg_morale + attacker_morale_change)
        context.defender_avg_morale = max(0.0,
            context.defender_avg_morale + defender_morale_change)

        return True

    # ============================================================
    # 伤害计算
    # ============================================================

    @staticmethod
    def calculate_wall_damage(context: BattleContext) -> int:
        """计算攻城战中对城墙的伤害

        公式：
            base = WALL_DAMAGE_BASE (400)
            force_multiplier = min(attack_soldiers / garrison, 4)
            command_bonus = 1 + (command - 50) / 100
            intelligence_bonus = 1 + (intelligence - 50) × SIEGE_ENGINEER_INTELLIGENCE_RATE
            damage = base × force_multiplier × command_bonus × intelligence_bonus

        v4.0 新增 intelligence_bonus：智力代表器械/工程能力（冲车、云梯、土山），
        让「谋士」第一次在战场上有实际作用——此前 intelligence 对战斗零影响。

        Args:
            context: 战斗上下文

        Returns:
            本回合对城墙造成的伤害
        """
        base = WALL_DAMAGE_BASE

        # 兵力系数
        garrison = max(context.defender_total_soldiers, 1)
        force_mult = min(
            context.attacker_total_soldiers / garrison,
            WALL_DAMAGE_FORCE_MULTIPLIER_CAP,
        )

        # 统帅加成
        command_bonus = 1.0 + (
            (context.attacker_avg_command - 50.0) * COMMAND_ATTACK_BONUS_RATE
        )
        command_bonus = max(0.5, command_bonus)  # 不低于50%

        # 智力加成（攻城器械效率）
        intelligence_bonus = 1.0 + (
            (context.attacker_avg_intelligence - 50.0)
            * SIEGE_ENGINEER_INTELLIGENCE_RATE
        )
        intelligence_bonus = max(0.5, intelligence_bonus)

        return int(base * force_mult * command_bonus * intelligence_bonus)

    def calculate_attacker_damage(self, context: BattleContext) -> int:
        """计算攻击方巷战伤害

        公式：
            base = attacker_soldiers × BASE_DAMAGE_RATE (0.1)
            command_bonus = 1 + (avg_command - 50) / 100
            morale_bonus = (avg_morale + morale_bonus) / 100
            terrain_bonus = 1.0 (攻方无地形加成)
            damage = base × command_bonus × morale_bonus × terrain_bonus
                     × loyalty_factor × counter_bonus

        Args:
            context: 战斗上下文

        Returns:
            对防守方造成的伤害
        """
        return self._calculate_damage(
            soldiers=context.attacker_total_soldiers,
            avg_command=context.attacker_avg_command,
            avg_morale=context.attacker_avg_morale + context.attacker_morale_bonus,
            avg_bravery=context.attacker_avg_bravery,
            terrain_bonus=1.0,  # 攻方
            # v4.0：将领忠诚度战力系数 + 五行相克系数
            loyalty_factor=context.attacker_loyalty_factor,
            counter_bonus=context.attacker_counter_bonus,
        )

    def calculate_defender_damage(self, context: BattleContext) -> int:
        """计算防守方巷战伤害（城墙完好时才有城墙加成）

        公式：
            base = defender_soldiers × BASE_DAMAGE_RATE
            command_bonus = 1 + (avg_command - 50) / 100
            morale_bonus = (avg_morale + morale_bonus) / 100
            terrain_bonus = 1.1 (城墙完好) / 1.0 (城墙已破，巷战)
            damage = base × command_bonus × morale_bonus × terrain_bonus
                     × loyalty_factor × counter_bonus

        🔴 城墙加成只在城墙仍完好时生效。原实现无条件给 1.1，等于"城墙已被
        打破、双方在街巷里肉搏"时守方还享受城墙保护，这在语义上矛盾，
        也让攻方在巷战里长期吃亏（防方伤害恒高 10%）。
        城墙一破就应转为势均力敌的巷战，守方的优势只来自兵力和统帅。

        Args:
            context: 战斗上下文

        Returns:
            对攻击方造成的伤害
        """
        # 城墙耐久 > 0 表示城墙仍未被打破，守方享受城墙加成；
        # 巷战阶段（STREET）城墙必然已被打穿（或因城墙此前已破而直接进巷战）
        # → 无城墙加成。
        # 兼容：单测/直接调用本方法时未经过 resolve_battle，_wall_hp 为空字典，
        # 此时回退读 context.wall_hp，避免误判为"城墙已破"。
        current_wall = self._wall_hp.get(context.battle_id)
        if current_wall is None:
            current_wall = context.wall_hp or 0
        wall_intact = (
            context.battle_phase != BattlePhase.STREET and current_wall > 0
        )
        terrain_bonus = 1.0 + DEFENDER_WALL_BONUS if wall_intact else 1.0

        return self._calculate_damage(
            soldiers=context.defender_total_soldiers,
            avg_command=context.defender_avg_command,
            avg_morale=context.defender_avg_morale + context.defender_morale_bonus,
            avg_bravery=context.defender_avg_bravery,
            terrain_bonus=terrain_bonus,
            # v4.0：将领忠诚度战力系数 + 五行相克系数
            loyalty_factor=context.defender_loyalty_factor,
            counter_bonus=context.defender_counter_bonus,
        )

    def _calculate_damage(
        self,
        soldiers: int,
        avg_command: float,
        avg_morale: float,
        avg_bravery: float,
        terrain_bonus: float,
        loyalty_factor: float = 1.0,
        counter_bonus: float = 1.0,
    ) -> int:
        """计算单方伤害（内部方法）

        加成项：
            统帅：每点 ±1%（commmand_bonus）
            士气：每点 +1%
            勇武暴击：crit_chance = min(0.5, avg_bravery × 0.005)，暴击 ×1.5
            忠诚度：死忠 +10% / 哗变边缘 -20%（v4.0）
            五行相克：克制 +15% / 被克 -15%（v4.0）

        Args:
            soldiers: 本方兵力
            avg_command: 本方平均统帅
            avg_morale: 本方平均士气
            avg_bravery: 本方平均勇武
            terrain_bonus: 地形加成
            loyalty_factor: 将领忠诚度战力系数
            counter_bonus: 五行相克系数

        Returns:
            对敌方造成的伤害
        """
        base = soldiers * BASE_DAMAGE_RATE

        # 统帅加成（每点统帅+1%）
        command_bonus = 1.0 + (avg_command - 50.0) * COMMAND_COMBAT_BONUS_RATE
        command_bonus = max(0.5, command_bonus)

        # 士气加成（每点士气+1%）
        morale_bonus = avg_morale / 100.0
        morale_bonus = max(0.1, morale_bonus)  # 最低10%

        damage = base * command_bonus * morale_bonus * terrain_bonus
        damage *= loyalty_factor * counter_bonus

        # 勇武暴击
        crit_chance = min(0.5, avg_bravery * BRAVERY_CRITICAL_CHANCE_RATE)
        if self._rng.random() < crit_chance:
            damage = damage * 1.5

        return int(damage)

    # ============================================================
    # 士气变化计算
    # ============================================================

    @staticmethod
    def calculate_morale_change(
        context: BattleContext,
        side: str,
        casualties: int = 0,
        total_before: int = 0,
        enemy_casualties: int = 0,
        enemy_total: int = 0,
    ) -> int:
        """计算士气变化

        规则：
        - 每损失10%兵力 → -5士气（向下取整）
        - 每击杀10%敌军 → +3士气（向下取整）

        Args:
            context: 战斗上下文
            side: "attacker" 或 "defender"
            casualties: 本方伤亡
            total_before: 本方战前兵力
            enemy_casualties: 击杀敌军数
            enemy_total: 敌军战前总兵力

        Returns:
            士气变化量（可为负数）
        """
        change = 0

        # 伤亡惩罚
        if total_before > 0:
            loss_pct = casualties / total_before
            loss_units = int(loss_pct * 10)  # 每10%为1单位
            change -= loss_units * MORALE_LOSS_PER_10_PERCENT_CASUALTY

        # 击杀奖励
        if enemy_total > 0:
            kill_pct = enemy_casualties / enemy_total
            kill_units = int(kill_pct * 10)
            change += kill_units * MORALE_GAIN_PER_10_PERCENT_KILL

        return change

    # ============================================================
    # 胜负判定
    # ============================================================

    @staticmethod
    def check_battle_end(context: BattleContext) -> Optional[BattleResultType]:
        """检查战斗是否应该结束

        结束条件（任一满足）：
        1. 攻击方兵力 ≤ 0 → 防守方胜利
        2. 防守方兵力 ≤ 0 → 攻击方胜利
        3. 超过 MAX_BATTLE_ROUNDS (10) → 平局
        4. 攻击方士气 < MORALE_BREAK_THRESHOLD (20) → 撤退

        Args:
            context: 战斗上下文

        Returns:
            战斗结果类型，未结束返回 None
        """
        # 条件1：攻击方全灭
        if context.attacker_total_soldiers <= 0:
            return BattleResultType.DEFENDER_WIN

        # 条件2：防守方全灭
        if context.defender_total_soldiers <= 0:
            return BattleResultType.ATTACKER_WIN

        # 条件3：超过最大回合
        if context.round_count >= MAX_BATTLE_ROUNDS:
            return BattleResultType.DRAW

        # 条件4：攻击方士气崩溃
        if context.attacker_avg_morale < MORALE_BREAK_THRESHOLD:
            return BattleResultType.RETREAT

        return None

    # ============================================================
    # 战后处理
    # ============================================================

    def process_aftermath(
        self,
        context: BattleContext,
        defender_city_owner: str = "",
        defender_generals: Optional[List[str]] = None,
    ) -> BattleResult:
        """处理战斗 aftermath

        根据战斗结果执行：
        - 攻击方胜利：占领城市、处理俘虏
        - 防守方胜利：攻击方撤退
        - 平局：双方撤退

        Args:
            context: 战斗上下文（已设置 result）
            defender_city_owner: 防守方城市原归属
            defender_generals: 防守方将领ID列表

        Returns:
            战斗结果
        """
        if defender_generals is None:
            defender_generals = []

        result = BattleResult(
            battle_id=context.battle_id,
            battle_type=context.battle_type,
            result=context.result or BattleResultType.DRAW,
            attacker_casualties=context.attacker_casualties,
            defender_casualties=context.defender_casualties,
            attacker_morale_change=0,
            defender_morale_change=0,
        )

        if context.result == BattleResultType.ATTACKER_WIN:
            # 攻击方胜利：占领城市
            result.captured_city = context.defender_city
            result.attacker_morale_change = 10
            result.defender_morale_change = -15

            # 处理俘虏
            for gen_id in defender_generals:
                # 被俘概率基于兵力比和将领忠诚度
                if context.defender_total_soldiers <= 0 and context.attacker_total_soldiers > 0:
                    # 防守方全灭时，所有将领被俘
                    result.captured_generals.append(gen_id)
                elif self._rng.random() < 0.3:
                    result.captured_generals.append(gen_id)

        elif context.result == BattleResultType.DEFENDER_WIN:
            # 防守方胜利：设置士气变化
            result.defender_morale_change = 10
            result.attacker_morale_change = -10

        elif context.result == BattleResultType.DRAW:
            # 平局：士气微降
            result.attacker_morale_change = -5
            result.defender_morale_change = -5

        return result
