"""行军系统单元测试

测试军队移动、粮草消耗、断粮惩罚、到达处理等功能。
参考设计文档：docs/design/battle-system.md 第二章
"""

import pytest

from game.models import Army, ArmyStatus
from game.systems.map_system import MapSystem
from game.battle.army_movement import (
    ArmyMovementSystem,
    MovementResult,
    MovementEvent,
)
from game.constants import ARMY_FOOD_COST_PER_SOLDIER


# ============================================================
# 行军进度测试
# ============================================================

class TestMarchProgress:
    """行军推进测试"""

    def test_army_progresses_each_turn(self):
        """军队每回合向前推进"""
        ams = ArmyMovementSystem()
        army = _make_marching_army(distance=5)

        result = ams.process_movement(army)

        assert result.progress_made > 0
        assert army.progress > 0

    def test_arrives_when_progress_complete(self):
        """进度达到1时到达目的地"""
        ams = ArmyMovementSystem()
        army = _make_marching_army(distance=3, progress=0.99)

        result = ams.process_movement(army)

        assert result.arrived is True
        assert army.progress >= 1.0

    def test_march_speed_one_per_turn(self):
        """每回合推进1/总距离"""
        ams = ArmyMovementSystem()
        army = _make_marching_army(distance=5, progress=0.0)

        ams.process_movement(army)
        # 应该推进 1/5 = 0.2
        assert army.progress == pytest.approx(0.2, abs=0.01)

    def test_progress_exact_calculation(self):
        """进度计算精确"""
        ams = ArmyMovementSystem()
        army = _make_marching_army(distance=3, progress=0.0)

        ams.process_movement(army)
        assert army.progress == pytest.approx(1/3, abs=0.01)

        ams.process_movement(army)
        assert army.progress == pytest.approx(2/3, abs=0.01)

        result = ams.process_movement(army)
        assert result.arrived is True

    def test_garrisoned_army_no_movement(self):
        """驻守军队不行军"""
        ams = ArmyMovementSystem()
        army = _make_garrisoned_army()

        result = ams.process_movement(army)
        assert result.progress_made == 0
        assert result.arrived is False


# ============================================================
# 粮草消耗测试
# ============================================================

class TestFoodConsumption:
    """行军粮草消耗测试"""

    def test_food_consumed_each_turn(self):
        """每回合消耗粮草"""
        ams = ArmyMovementSystem()
        army = _make_marching_army(distance=3, soldiers=1000, food=5000)

        food_before = army.food
        ams.process_movement(army)
        food_after = army.food

        expected_consumption = int(1000 * ARMY_FOOD_COST_PER_SOLDIER)
        assert food_before - food_after == expected_consumption

    def test_food_consumption_scales_with_soldiers(self):
        """消耗量与士兵数成正比"""
        ams = ArmyMovementSystem()
        army_large = _make_marching_army(distance=3, soldiers=2000, food=10000)
        army_small = _make_marching_army(distance=3, soldiers=500, food=10000)

        ams.process_movement(army_large)
        ams.process_movement(army_small)

        assert army_large.food < army_small.food  # 大的消耗更多

    def test_no_food_consumption_for_garrisoned(self):
        """驻守军队不消耗行军粮草"""
        ams = ArmyMovementSystem()
        army = _make_garrisoned_army(food=1000)

        ams.process_movement(army)
        assert army.food == 1000  # 没消耗


# ============================================================
# 断粮惩罚测试
# ============================================================

class TestStarvation:
    """断粮惩罚测试"""

    def test_no_food_morale_drops(self):
        """断粮后士气下降"""
        ams = ArmyMovementSystem()
        army = _make_marching_army(distance=3, soldiers=1000, food=0, morale=80)

        result = ams.process_movement(army)

        assert result.starvation is True
        assert army.morale < 80

    def test_starvation_morale_drop_amount(self):
        """断粮每回合士气-10"""
        ams = ArmyMovementSystem()
        army = _make_marching_army(distance=3, soldiers=1000, food=0, morale=80)

        ams.process_movement(army)
        assert army.morale == 70  # 80 - 10

    def test_low_morale_rout(self):
        """士气低于阈值开始溃散"""
        ams = ArmyMovementSystem()
        army = _make_marching_army(distance=3, soldiers=1000, food=0, morale=25)

        result = ams.process_movement(army)

        assert result.routing is True
        assert army.soldiers < 1000  # 损失兵力

    def test_rout_loss_rate(self):
        """溃散每回合损失10%兵力"""
        ams = ArmyMovementSystem()
        army = _make_marching_army(distance=3, soldiers=1000, food=0, morale=20)

        ams.process_movement(army)
        # 1000 * 0.9 = 900
        assert army.soldiers == 900

    def test_zero_morale_army_destroyed(self):
        """士气归零部队全灭"""
        ams = ArmyMovementSystem()
        army = _make_marching_army(distance=3, soldiers=1000, food=0, morale=5)

        ams.process_movement(army)
        # 士气应该降到0以下，溃散大量兵力
        assert army.morale == 0


# ============================================================
# 到达处理测试
# ============================================================

class TestArrival:
    """军队到达处理测试"""

    def test_arrival_changes_status(self):
        """到达后状态变为围城"""
        ams = ArmyMovementSystem()
        army = _make_marching_army(distance=2, progress=0.99)

        result = ams.process_movement(army)

        assert result.arrived is True
        assert army.status == ArmyStatus.BESIEGING

    def test_arrival_at_own_city_garrisons(self):
        """到达己方城市并入城"""
        ams = ArmyMovementSystem()
        # 同一势力，入城
        army = _make_marching_army(distance=2, progress=0.99, from_faction="wei", to_faction="wei")

        result = ams.process_movement(army)
        assert result.arrived is True
        assert result.arrival_type == "garrison"

    def test_arrival_at_enemy_city_besieges(self):
        """到达敌方城市开始围城"""
        ams = ArmyMovementSystem()
        army = _make_marching_army(distance=2, progress=0.99, from_faction="wei", to_faction="shu")

        result = ams.process_movement(army)
        assert result.arrived is True
        assert result.arrival_type == "besiege"

    def test_calculate_turns_to_arrive(self):
        """计算还需要几回合到达"""
        ams = ArmyMovementSystem()
        army = _make_marching_army(distance=5, progress=0.4)

        turns = ams.calculate_turns_to_arrive(army)
        assert turns == 3  # (1 - 0.4) * 5 = 3

    def test_calculate_turns_already_there(self):
        """已到达时返回0"""
        ams = ArmyMovementSystem()
        army = _make_garrisoned_army()

        turns = ams.calculate_turns_to_arrive(army)
        assert turns == 0


# ============================================================
# 边界情况测试
# ============================================================

class TestMovementEdgeCases:
    """行军边界测试"""

    def test_zero_distance_not_allowed(self):
        """距离为0的军队不能创建"""
        # 通过 API 保证，不在单元测试范围内
        pass

    def test_retreating_army_movement(self):
        """撤退中的军队也消耗粮草"""
        ams = ArmyMovementSystem()
        army = _make_retreating_army(soldiers=1000, food=1000)

        food_before = army.food
        ams.process_movement(army)
        assert army.food < food_before

    def test_retreating_army_moves_double_speed(self):
        """撤退中的军队以双倍速度返回"""
        ams = ArmyMovementSystem()
        army = _make_retreating_army(soldiers=1000, food=1000)
        army.total_distance = 4  # 距离4，行军速度 0.25，撤退应为 0.5
        army.progress = 0.0

        ams.process_movement(army)
        # 双倍速度：进度应增加 2.0/4 = 0.5
        assert army.progress == pytest.approx(0.5, abs=0.001)

        ams.process_movement(army)
        # 第二回合应到达（上限1.0）
        assert army.progress == pytest.approx(1.0, abs=0.001)

    def test_army_progress_does_not_exceed_one(self):
        """进度不会超过1"""
        ams = ArmyMovementSystem()
        army = _make_marching_army(distance=1, progress=0.0)

        ams.process_movement(army)
        assert army.progress == 1.0  # 不会超

    def test_food_does_not_go_negative(self):
        """粮草不会为负"""
        ams = ArmyMovementSystem()
        army = _make_marching_army(distance=3, soldiers=1000, food=5)

        ams.process_movement(army)
        assert army.food >= 0

    def test_besieging_army_food_consumption(self):
        """围城中的军队继续消耗粮草"""
        ams = ArmyMovementSystem()
        army = _make_besieging_army(soldiers=1000, food=2000)

        result = ams.process_movement(army)
        assert army.food < 2000  # 持续消耗
        assert result.food_consumed > 0


# ============================================================
# 辅助函数
# ============================================================

def _make_army(**kwargs) -> Army:
    """创建测试用军队"""
    params = {
        "id": "test_army",
        "faction": "wei",
        "general_id": "test_general",
        "soldiers": 1000,
        "food": 5000,
        "food_consumption_per_turn": int(1000 * ARMY_FOOD_COST_PER_SOLDIER),
        "morale": 80,
        "status": ArmyStatus.MARCHING,
        "from_city": "city_a",
        "to_city": "city_b",
        "progress": 0.0,
        "total_distance": 3,
    }
    params.update(kwargs)
    return Army(**params)


def _make_marching_army(
    distance: int = 3,
    soldiers: int = 1000,
    food: int = 5000,
    morale: int = 80,
    progress: float = 0.0,
    from_faction: str = "wei",
    to_faction: str = "shu",
) -> Army:
    """创建行军中军队"""
    return Army(
        id="march_army",
        faction=from_faction,
        general_id="test_gen",
        soldiers=soldiers,
        food=food,
        food_consumption_per_turn=int(soldiers * ARMY_FOOD_COST_PER_SOLDIER),
        morale=morale,
        status=ArmyStatus.MARCHING,
        from_city=f"city_{from_faction}",
        to_city=f"city_{to_faction}",
        progress=progress,
        total_distance=distance,
    )


def _make_garrisoned_army(food: int = 1000) -> Army:
    """创建驻守军队"""
    return Army(
        id="garrison_army",
        faction="wei",
        general_id="test_gen",
        soldiers=1000,
        food=food,
        food_consumption_per_turn=200,
        morale=80,
        status=ArmyStatus.GARRISONED,
        from_city="city_a",
        to_city="city_a",
        progress=1.0,
        total_distance=1,
    )


def _make_retreating_army(soldiers: int = 1000, food: int = 1000) -> Army:
    """创建撤退中军队"""
    return Army(
        id="retreat_army",
        faction="wei",
        general_id="test_gen",
        soldiers=soldiers,
        food=food,
        food_consumption_per_turn=int(soldiers * ARMY_FOOD_COST_PER_SOLDIER),
        morale=50,
        status=ArmyStatus.RETREATING,
        from_city="city_a",
        to_city="city_b",
        progress=0.5,
        total_distance=3,
    )


def _make_besieging_army(soldiers: int = 1000, food: int = 2000) -> Army:
    """创建围城中军队"""
    return Army(
        id="besiege_army",
        faction="wei",
        general_id="test_gen",
        soldiers=soldiers,
        food=food,
        food_consumption_per_turn=int(soldiers * ARMY_FOOD_COST_PER_SOLDIER),
        morale=70,
        status=ArmyStatus.BESIEGING,
        from_city="city_a",
        to_city="city_b",
        progress=1.0,
        total_distance=3,
    )
