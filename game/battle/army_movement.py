"""行军系统

管理军队在地图上的移动、粮草消耗、断粮惩罚和到达处理。

核心逻辑：
1. 传统模式：每回合向前推进 1/total_distance 的进度
2. Hex模式：沿六角格路径推进，考虑地形消耗和季节影响
3. 每回合消耗粮草（soldiers × 0.2）
4. 断粮后每回合士气-10，士气低于20%开始溃散（每回合-10%兵力）
5. 到达目的地后：友方城市→入城增援，敌方城市→开始围城

参考设计文档：docs/design/battle-system.md 第二章
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from game.constants import (
    ARMY_FOOD_COST_PER_SOLDIER,
    MORALE_LOSS_NO_FOOD,
    MORALE_BREAK_THRESHOLD,
    ROUT_LOSS_RATE,
    SEASON_MOVEMENT_FACTOR,
)
from game.models import Army, ArmyStatus


# ============================================================
# 结果数据结构
# ============================================================


@dataclass
class MovementResult:
    """行军单回合处理结果"""

    progress_made: float = 0.0
    """本回合推进的进度"""

    food_consumed: int = 0
    """本回合消耗的粮草"""

    arrived: bool = False
    """本回合是否到达目的地"""

    arrival_type: str = ""
    """到达类型: besiege / reinforce / none"""

    starvation: bool = False
    """是否处于断粮状态"""

    routing: bool = False
    """是否正在溃散"""

    soldiers_lost_to_rout: int = 0
    """本回合因溃散损失的兵力"""

    status_changed: bool = False
    """状态是否发生变化"""

    disbanded: bool = False
    """是否已并入城市守军（到达友方城市后）"""


@dataclass
class MovementEvent:
    """行军事件（用于事件总线/日志）"""

    army_id: str = ""
    faction: str = ""
    from_city: str = ""
    to_city: str = ""
    progress_before: float = 0.0
    progress_after: float = 0.0
    arrived: bool = False
    arrival_type: str = ""

    def to_dict(self) -> dict:
        return {
            "army_id": self.army_id,
            "faction": self.faction,
            "from_city": self.from_city,
            "to_city": self.to_city,
            "progress_before": self.progress_before,
            "progress_after": self.progress_after,
            "arrived": self.arrived,
            "arrival_type": self.arrival_type,
        }


class ArmyMovementSystem:
    """行军系统

    负责处理军队每回合的行军推进、粮草消耗、断粮惩罚和到达事件。
    所有修改直接作用于 Army 对象。
    """

    # ============================================================
    # 主处理入口
    # ============================================================

    def process_movement(
        self,
        army: Army,
        hex_map: Optional[object] = None,
        season: str = "spring",
        cities: Optional[dict] = None,
        generals: Optional[dict] = None,
    ) -> MovementResult:
        """处理一回合的军队移动

        包含：进度推进、粮草消耗、断粮判定、溃散判定、到达判定。

        支持两种模式：
        - 传统模式（无 hex_map）：按 progress 0→1 推进
        - Hex 模式（有 hex_map）：沿 path_hexes 按地形消耗推进

        Args:
            army: 要处理的军队对象（会被修改）
            hex_map: 六角格地图（可选，启用 Hex 模式）
            season: 当前季节（默认 spring）
            cities: 城市字典，用于判断到达城市归属
            generals: 将领字典，用于友方到达时更新将领位置

        Returns:
            本回合行军处理结果
        """
        result = MovementResult()

        # 只有行军、围城、撤退中的军队需要处理消耗
        if army.status not in (
            ArmyStatus.MARCHING,
            ArmyStatus.RETREATING,
            ArmyStatus.BESIEGING,
        ):
            return result

        # 使用 Hex 模式还是传统模式
        if hex_map is not None and army.path_hexes:
            self._process_hex_movement(army, hex_map, season, result)
        else:
            self._process_legacy_movement(army, result)

        # 2. 消耗粮草
        result.food_consumed = self._consume_food(army)

        # 3. 断粮判定
        if army.food <= 0:
            result.starvation = True
            self._apply_starvation(army)

        # 4. 溃散判定
        if army.morale <= MORALE_BREAK_THRESHOLD:
            soldiers_lost = self._apply_rout(army)
            result.routing = soldiers_lost > 0
            result.soldiers_lost_to_rout = soldiers_lost

        # 5. 到达判定
        # 🔴 撤退中的军队同样需要到达判定（2026-10-03 v4.0）：
        #    原实现只对 MARCHING 分支做到达处理，导致战败撤退的军队走完路径后
        #    既不触发 _handle_arrival（无法入城归建）、也不会被清理，
        #    永远停在 RETREATING 状态成为"野外僵尸军队"——不参战、不消失，
        #    只能靠每回合断粮（士气 -10 → 溃散 -10% 兵力）慢慢掉光兵。
        #    实证：5 局 48 回合共 155 场战斗，其中 35 场 RETREAT(22.6%) +
        #    8 场 DEFENDER_WIN 的攻方残部全部进入该状态，兵力凭空蒸发，
        #    直接造成"12 方谁也打不完"的僵局。
        if army.status in (ArmyStatus.MARCHING, ArmyStatus.RETREATING):
            if hex_map is not None and army.path_hexes:
                if army.path_index >= len(army.path_hexes) - 1:
                    army.progress = 1.0
                    arrival_result = self._handle_arrival(army, cities, generals)
                    result.arrived = arrival_result["arrived"]
                    result.arrival_type = arrival_result["type"]
                    result.status_changed = arrival_result["status_changed"]
                    result.disbanded = arrival_result.get("disbanded", False)
            elif army.progress >= 1.0:
                army.progress = 1.0
                arrival_result = self._handle_arrival(army, cities, generals)
                result.arrived = arrival_result["arrived"]
                result.arrival_type = arrival_result["type"]
                result.status_changed = arrival_result["status_changed"]
                result.disbanded = arrival_result.get("disbanded", False)

        return result

    def _process_legacy_movement(
        self, army: Army, result: MovementResult
    ) -> None:
        """传统模式：基于 progress 的行军"""
        if army.status == ArmyStatus.MARCHING and army.total_distance > 0:
            progress_step = 1.0 / army.total_distance
            old_progress = army.progress
            army.progress = min(1.0, army.progress + progress_step)
            result.progress_made = army.progress - old_progress
        elif army.status == ArmyStatus.RETREATING:
            progress_step = 2.0 / max(army.total_distance, 1)
            old_progress = army.progress
            army.progress = min(1.0, army.progress + progress_step)
            result.progress_made = army.progress - old_progress

    def _process_hex_movement(
        self,
        army: Army,
        hex_map: object,
        season: str,
        result: MovementResult,
    ) -> None:
        """Hex 模式：沿六角格路径推进"""
        from game.hex_map import HexMap
        from game.constants import ARMY_MARCH_SPEED

        if army.status not in (ArmyStatus.MARCHING, ArmyStatus.RETREATING):
            return

        # 移动力预算
        base_speed = float(ARMY_MARCH_SPEED * 2) if army.status == ArmyStatus.RETREATING else float(ARMY_MARCH_SPEED)
        season_factor = SEASON_MOVEMENT_FACTOR.get(season, 1.0)
        movement_budget = base_speed * season_factor

        old_index = army.path_index

        # 沿路径推进
        while movement_budget > 0 and army.path_index < len(army.path_hexes) - 1:
            next_hex = army.path_hexes[army.path_index + 1]
            tile = hex_map.get_tile(next_hex)
            if tile is None:
                break
            cost = HexMap.terrain_move_cost(tile.terrain)
            if cost == float("inf"):
                break
            if movement_budget < cost:
                break
            movement_budget -= cost
            army.path_index += 1
            army.current_hex = next_hex

        total_steps = max(1, len(army.path_hexes) - 1)
        if total_steps > 0:
            army.progress = army.path_index / total_steps
            result.progress_made = (army.path_index - old_index) / total_steps

    # ============================================================
    # 粮草消耗
    # ============================================================

    def _consume_food(self, army: Army) -> int:
        """消耗本回合粮草

        行军/围城/撤退中的军队都会消耗粮草。

        Args:
            army: 军队对象

        Returns:
            本回合消耗的粮草数量
        """
        if army.food <= 0:
            return 0

        consumption = int(army.soldiers * ARMY_FOOD_COST_PER_SOLDIER)
        actual_consumption = min(consumption, army.food)
        army.food -= actual_consumption

        return actual_consumption

    # ============================================================
    # 断粮惩罚
    # ============================================================

    def _apply_starvation(self, army: Army) -> None:
        """执行断粮惩罚

        断粮时：
        1. 士气每回合下降 MORALE_LOSS_NO_FOOD (10) 点
        2. 士气不会低于 0

        Args:
            army: 军队对象
        """
        army.morale = max(0, army.morale - MORALE_LOSS_NO_FOOD)

    # ============================================================
    # 溃散
    # ============================================================

    def _apply_rout(self, army: Army) -> int:
        """执行溃散

        士气低于 MORALE_BREAK_THRESHOLD (20) 时触发。
        每回合损失 ROUT_LOSS_RATE (10%) 的兵力。

        Args:
            army: 军队对象

        Returns:
            本回合损失的兵力
        """
        soldiers_lost = int(army.soldiers * ROUT_LOSS_RATE)
        army.soldiers = max(0, army.soldiers - soldiers_lost)
        army.casualties += soldiers_lost

        # 士气归零则全军覆没
        if army.morale <= 0:
            army.soldiers = 0

        return soldiers_lost

    # ============================================================
    # 到达处理
    # ============================================================

    def _handle_arrival(
        self,
        army: Army,
        cities: Optional[dict] = None,
        generals: Optional[dict] = None,
    ) -> dict:
        """处理军队到达目的地

        根据目标城市归属决定：
        - 友方城市：入城增援，兵力并入守军，将领返回城市
        - 敌方/中立城市：开始围城，标记城市被围状态（撤退中的军队除外）
        - 同城：驻守

        撤退中的军队（status == RETREATING）特殊处理：
        - 到达友方城市 → 并入守军、军队解散（残部归建，兵力不蒸发）
        - 到达敌方/中立城市 → 不停留、不进入围城状态，返回 arrived=False，
          等待 engine 把它的目标改回自家城市

        Args:
            army: 军队对象
            cities: 城市字典 {id: City}，用于判断城市归属
            generals: 将领字典 {id: General}，用于更新将领位置

        Returns:
            包含 arrived、type、status_changed、disbanded 的字典
        """
        retreating = army.status == ArmyStatus.RETREATING

        if army.from_city == army.to_city:
            army.status = ArmyStatus.GARRISONED
            return {"arrived": True, "type": "garrison", "status_changed": True, "disbanded": False}

        # 判断目标城市归属
        if cities and army.to_city in cities:
            target_city = cities[army.to_city]
            if target_city.faction == army.faction:
                # 友方城市：兵力并入守军，将领返回城市
                target_city.garrison += army.soldiers
                army.soldiers = 0
                army.status = ArmyStatus.GARRISONED
                if generals and army.general_id in generals:
                    generals[army.general_id].location = target_city.id
                return {"arrived": True, "type": "reinforce", "status_changed": True, "disbanded": True}

            # 敌方/中立城市
            if retreating:
                # 撤退途中途经敌城：不围城、不标记，保持撤退
                return {"arrived": False, "type": "retreat_pass",
                        "status_changed": False, "disbanded": False}

            target_city.is_besieged = True
            if army.id not in target_city.besieging_armies:
                target_city.besieging_armies.append(army.id)

        if retreating:
            # 撤退且终点不是友方城市：不转为围城（否则残部又去送死）
            return {"arrived": False, "type": "retreat_no_target",
                    "status_changed": False, "disbanded": False}

        army.status = ArmyStatus.BESIEGING
        return {"arrived": True, "type": "besiege", "status_changed": True, "disbanded": False}

    # ============================================================
    # 辅助方法
    # ============================================================

    @staticmethod
    def calculate_turns_to_arrive(army: Army) -> int:
        """计算还需要几回合到达目的地

        Args:
            army: 军队对象

        Returns:
            还需回合数，已到达返回 0
        """
        if army.progress >= 1.0 or army.status == ArmyStatus.GARRISONED:
            return 0

        remaining_progress = 1.0 - army.progress
        if army.total_distance <= 0:
            return 0

        return int(remaining_progress * army.total_distance)
