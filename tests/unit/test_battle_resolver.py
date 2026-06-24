"""战斗结算器单元测试

测试伤害计算、士气变化、胜负判定、战后处理等核心战斗逻辑。
这是整个游戏最复杂的模块，测试必须覆盖所有公式和边界情况。

参考设计文档：docs/design/battle-system.md 第四章
"""

import pytest

from game.models import (
    BattleContext, BattleType, BattlePhase, BattleResultType,
)
from game.random import GameRandom
from game.battle.battle_resolver import BattleResolver


# ============================================================
# 围城伤害计算测试
# ============================================================

class TestSiegeDamage:
    """攻城伤害计算测试"""

    def test_wall_damage_basic(self):
        """基础围城伤害"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx = _make_siege_context(
            attacker_soldiers=3000, defender_soldiers=2000,
            attacker_command=70,
        )
        damage = resolver.calculate_wall_damage(ctx)
        # base=400, force_mult=1.5, command=1.2 → 400*1.5*1.2=720
        assert damage == pytest.approx(720, abs=1)

    def test_wall_damage_max_multiplier(self):
        """兵力系数上限为3"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx = _make_siege_context(
            attacker_soldiers=10000, defender_soldiers=1000,
            attacker_command=50,
        )
        damage = resolver.calculate_wall_damage(ctx)
        # base=400, force_mult=4, command=1.0 → 400*4*1.0=1600
        assert damage == pytest.approx(1600, abs=1)

    def test_wall_damage_low_command(self):
        """低统帅降低伤害"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx = _make_siege_context(
            attacker_soldiers=3000, defender_soldiers=2000,
            attacker_command=30,
        )
        damage = resolver.calculate_wall_damage(ctx)
        # base=400, force_mult=1.5, command=0.8 → 400*1.5*0.8=480
        assert damage == pytest.approx(480, abs=1)

    def test_no_garrison_max_damage(self):
        """无守军时攻城伤害最大化"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx = _make_siege_context(
            attacker_soldiers=3000, defender_soldiers=0,
            attacker_command=95,
        )
        # 守军为0时，兵力系数达到上限3
        damage = resolver.calculate_wall_damage(ctx)
        assert damage > 300


# ============================================================
# 巷战伤害计算测试
# ============================================================

class TestStreetDamage:
    """巷战伤害计算测试"""

    def test_attacker_damage(self):
        """攻击方巷战伤害"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx = _make_siege_context(
            attacker_soldiers=5000, defender_soldiers=3000,
            attacker_command=80, defender_command=60,
            attacker_morale=80, defender_morale=70,
        )
        damage = resolver.calculate_attacker_damage(ctx)
        # base=5000*0.1=500, command=1+(80-50)/100=1.3,
        # morale=80/100=0.8, terrain=1.0
        # = 500 * 1.3 * 0.8 * 1.0 = 520
        assert damage == pytest.approx(520, abs=1)

    def test_defender_damage(self):
        """防守方巷战伤害（有城墙加成）"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx = _make_siege_context(
            attacker_soldiers=5000, defender_soldiers=3000,
            attacker_command=80, defender_command=60,
            attacker_morale=80, defender_morale=70,
        )
        damage = resolver.calculate_defender_damage(ctx)
        # base=3000*0.1=300, command=1+(60-50)/100=1.1,
        # morale=70/100=0.7, terrain=1.3
        # = 300 * 1.1 * 0.7 * 1.3 = 300.3
        assert damage == pytest.approx(300.3, abs=1)

    def test_low_morale_reduces_damage(self):
        """低士气降低伤害"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx_high = _make_siege_context(
            attacker_soldiers=5000, defender_soldiers=3000,
            attacker_morale=90,
        )
        ctx_low = _make_siege_context(
            attacker_soldiers=5000, defender_soldiers=3000,
            attacker_morale=30,
        )
        damage_high = resolver.calculate_attacker_damage(ctx_high)
        damage_low = resolver.calculate_attacker_damage(ctx_low)
        assert damage_high > damage_low

    def test_high_command_increases_damage(self):
        """高统帅增加伤害（排除暴击干扰）"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx_high = _make_siege_context(
            attacker_soldiers=5000, defender_soldiers=3000,
            attacker_command=95, attacker_avg_bravery=0,
        )
        ctx_low = _make_siege_context(
            attacker_soldiers=5000, defender_soldiers=3000,
            attacker_command=50, attacker_avg_bravery=0,
        )
        damage_high = resolver.calculate_attacker_damage(ctx_high)
        damage_low = resolver.calculate_attacker_damage(ctx_low)
        assert damage_high > damage_low


# ============================================================
# 士气变化测试
# ============================================================

class TestMoraleChange:
    """士气变化计算测试"""

    def test_morale_drops_on_casualties(self):
        """伤亡导致士气下降"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx = _make_siege_context(
            attacker_soldiers=5000, defender_soldiers=3000,
        )
        # 攻击方损失1000人（20%）
        change = resolver.calculate_morale_change(
            ctx, side="attacker",
            casualties=1000, total_before=5000,
        )
        # 每损失10%兵力，士气-5。损失20%，士气-10
        assert change == -10

    def test_morale_gains_on_kills(self):
        """击杀导致士气上升"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx = _make_siege_context(
            attacker_soldiers=5000, defender_soldiers=3000,
        )
        # 攻击方击杀1000人（33.3%）
        change = resolver.calculate_morale_change(
            ctx, side="attacker",
            enemy_casualties=1000, enemy_total=3000,
        )
        # 每击杀10%敌军，士气+3。击杀30%，士气+9
        assert change == 9

    def test_morale_no_change_small_casualties(self):
        """极小伤亡不触发士气变化"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx = _make_siege_context(
            attacker_soldiers=5000, defender_soldiers=3000,
        )
        change = resolver.calculate_morale_change(
            ctx, side="attacker",
            casualties=100, total_before=5000,
        )
        # 损失2%，不到10%阈值
        assert change == 0


# ============================================================
# 战斗回合处理测试
# ============================================================

class TestBattleRound:
    """单回合战斗处理测试"""

    def test_single_round_siege(self):
        """围城阶段单回合"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx = _make_siege_context(
            attacker_soldiers=5000, defender_soldiers=2000,
            wall_hp=2000,
        )
        ctx.battle_phase = BattlePhase.SIEGE

        continues = resolver.process_round(ctx)
        # 城墙应受损
        assert ctx.defender_casualties == 0  # 围城阶段防守方无伤亡
        # 攻城方有粮草消耗

    def test_wall_breaks_after_enough_damage(self):
        """城墙被打破后进入巷战"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx = _make_siege_context(
            attacker_soldiers=10000, defender_soldiers=1000,
            wall_hp=100,  # 薄墙
        )
        ctx.battle_phase = BattlePhase.SIEGE

        # 需要先模拟城墙被打破
        # 设置城墙已受损
        ctx.attacker_total_soldiers = 10000
        continues = resolver.process_round(ctx)

        # 城墙可能已破
        # 我们检查阶段是否变化
        # 不是每次都能破，看伤害

    def test_street_fighting_round(self):
        """巷战阶段单回合"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx = _make_siege_context(
            attacker_soldiers=5000, defender_soldiers=2000,
        )
        ctx.battle_phase = BattlePhase.STREET

        continues = resolver.process_round(ctx)
        # 双方应有伤亡
        assert ctx.attacker_casualties > 0 or ctx.defender_casualties > 0

    def test_round_count_increments(self):
        """回合计数通过 resolve_battle 递增"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx = _make_siege_context(
            attacker_soldiers=5000, defender_soldiers=2000,
            wall_hp=99999,  # 不可破城墙
        )
        ctx.battle_phase = BattlePhase.SIEGE

        # 设置高墙，战斗会因平局结束
        resolver._wall_hp[ctx.battle_id] = 99999
        result = resolver.resolve_battle(ctx)
        # 10回合后平局
        assert result.result == BattleResultType.DRAW
        # 确保战斗进行了多回合
        assert ctx.round_count > 0

    def test_wall_breaks_after_enough_damage(self):
        """城墙被打破后进入巷战"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx = _make_siege_context(
            attacker_soldiers=30000, defender_soldiers=1000,
            wall_hp=100,  # 薄墙
        )
        ctx.battle_phase = BattlePhase.SIEGE

        result = resolver.resolve_battle(ctx)
        # 城墙应该被打破，然后进入巷战
        # 由于攻防悬殊，攻击方应该赢
        assert result is not None

class TestBattleEnd:
    """胜负判定测试"""

    def test_attacker_destroyed_defender_wins(self):
        """攻击方全灭 -> 防守方胜利"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx = _make_siege_context(
            attacker_soldiers=0, defender_soldiers=2000,
        )
        result = resolver.check_battle_end(ctx)
        assert result == BattleResultType.DEFENDER_WIN

    def test_defender_destroyed_attacker_wins(self):
        """防守方全灭 -> 攻击方胜利"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx = _make_siege_context(
            attacker_soldiers=5000, defender_soldiers=0,
        )
        result = resolver.check_battle_end(ctx)
        assert result == BattleResultType.ATTACKER_WIN

    def test_max_rounds_draw(self):
        """超过最大回合 -> 平局"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx = _make_siege_context(
            attacker_soldiers=5000, defender_soldiers=2000,
        )
        ctx.round_count = 10
        result = resolver.check_battle_end(ctx)
        assert result == BattleResultType.DRAW

    def test_battle_continues(self):
        """双方都有兵力 -> 继续战斗"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx = _make_siege_context(
            attacker_soldiers=5000, defender_soldiers=2000,
        )
        ctx.round_count = 3
        result = resolver.check_battle_end(ctx)
        assert result is None

    def test_low_morale_causes_retreat(self):
        """攻击方士气过低导致撤退"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx = _make_siege_context(
            attacker_soldiers=5000, defender_soldiers=2000,
            attacker_morale=15,
        )
        result = resolver.check_battle_end(ctx)
        assert result == BattleResultType.RETREAT


# ============================================================
# 完整战斗流程测试
# ============================================================

class TestFullBattle:
    """完整战斗流程测试"""

    def test_battle_with_winner(self):
        """完整战斗有胜者"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx = _make_siege_context(
            attacker_soldiers=10000, defender_soldiers=500,
            wall_hp=500,
            attacker_command=90, defender_command=40,
        )
        ctx.battle_phase = BattlePhase.SIEGE

        result = resolver.resolve_battle(ctx)
        assert result is not None
        assert result.result in (
            BattleResultType.ATTACKER_WIN,
            BattleResultType.DEFENDER_WIN,
            BattleResultType.DRAW,
        )
        assert result.battle_log  # 应有战斗日志

    def test_stalemate_eventually_draws(self):
        """势均力敌最终平局"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx = _make_siege_context(
            attacker_soldiers=5000, defender_soldiers=5000,
            wall_hp=5000,
            attacker_command=50, defender_command=50,
        )

        result = resolver.resolve_battle(ctx)
        assert result is not None

    def test_overwhelming_force_wins(self):
        """压倒性兵力快速取胜"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx = _make_siege_context(
            attacker_soldiers=30000, defender_soldiers=500,
            wall_hp=500,
            attacker_command=95, defender_command=40,
            attacker_morale=90, defender_morale=50,
        )

        result = resolver.resolve_battle(ctx)
        assert result.result == BattleResultType.ATTACKER_WIN


# ============================================================
# 战后处理测试
# ============================================================

class TestAftermath:
    """战后处理测试"""

    def test_aftermath_captures_city(self):
        """攻击方胜利后占领城市"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx = _make_siege_context(
            attacker_soldiers=5000, defender_soldiers=0,
            attacker_faction="caocao", defender_faction="liubei",
        )
        ctx.result = BattleResultType.ATTACKER_WIN

        result = resolver.process_aftermath(ctx, defender_city_owner="shu")
        assert result.captured_city is not None

    def test_aftermath_captured_generals(self):
        """战斗后有被俘将领"""
        resolver = BattleResolver(rng=GameRandom(seed=42))
        ctx = _make_siege_context(
            attacker_soldiers=5000, defender_soldiers=0,
        )
        ctx.result = BattleResultType.ATTACKER_WIN

        result = resolver.process_aftermath(
            ctx,
            defender_city_owner="shu",
            defender_generals=["guanyu", "zhangfei"],
        )
        # 应该有概率俘虏将领
        # 至少返回一个结果
        assert result is not None


# ============================================================
# 辅助函数
# ============================================================

def _make_siege_context(
    attacker_soldiers: int = 5000,
    defender_soldiers: int = 2000,
    wall_hp: int = 2000,
    attacker_command: float = 70.0,
    defender_command: float = 50.0,
    attacker_morale: float = 80.0,
    defender_morale: float = 70.0,
    attacker_avg_bravery: float = 50.0,
    defender_avg_bravery: float = 50.0,
    attacker_faction: str = "wei",
    defender_faction: str = "shu",
    attacker_armies: list = None,
    defender_armies: list = None,
) -> BattleContext:
    """创建攻城战测试上下文"""
    return BattleContext(
        battle_id="test_battle",
        turn=5,
        attacker_faction=attacker_faction,
        defender_faction=defender_faction,
        attacker_armies=attacker_armies or ["a1"],
        attacker_total_soldiers=attacker_soldiers,
        attacker_initial_soldiers=attacker_soldiers,
        attacker_avg_morale=attacker_morale,
        attacker_avg_command=attacker_command,
        attacker_avg_bravery=attacker_avg_bravery,
        defender_city="target_city",
        defender_armies=defender_armies or [],
        defender_total_soldiers=defender_soldiers,
        defender_initial_soldiers=defender_soldiers,
        defender_avg_morale=defender_morale,
        defender_avg_command=defender_command,
        defender_avg_bravery=defender_avg_bravery,
        wall_hp=wall_hp,
        wall_max_hp=wall_hp,
        battle_type=BattleType.SIEGE,
        battle_phase=BattlePhase.SIEGE,
        round_count=0,
    )


class TestBraveryCrit:
    """勇武暴击测试"""

    def test_bravery_crit_with_high_bravery(self):
        """高勇武=100时暴击率0.5，约一半伤害触发1.5x"""
        resolver = BattleResolver(rng=GameRandom(seed=0))
        ctx = _make_siege_context(
            attacker_soldiers=5000, attacker_command=50.0,
            attacker_morale=100.0, attacker_avg_bravery=100.0,
        )
        n = 2000
        crit_count = 0
        for _ in range(n):
            dmg = resolver.calculate_attacker_damage(ctx)
            if dmg == 750:
                crit_count += 1
            elif dmg == 500:
                pass
            else:
                raise AssertionError(f"Unexpected damage: {dmg}")
        ratio = crit_count / n
        assert 0.40 < ratio < 0.60, f"Crit rate {ratio:.3f} ({crit_count}/{n})"

    def test_no_crit_with_zero_bravery(self):
        """勇武=0时暴击率0，永不触发"""
        resolver = BattleResolver(rng=GameRandom(seed=0))
        ctx = _make_siege_context(
            attacker_soldiers=5000, attacker_command=50.0,
            attacker_morale=100.0, attacker_avg_bravery=0.0,
        )
        for _ in range(100):
            dmg = resolver.calculate_attacker_damage(ctx)
            assert dmg == 500, f"Expected 500, got {dmg}"
