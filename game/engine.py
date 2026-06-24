"""GameEngine 主类

游戏引擎的核心，负责：
1. 初始化游戏状态（加载城市、将领、地图数据）
2. 执行玩家命令（发展、征兵、进攻、赏赐、探索、外交）
3. 处理回合逻辑（资源产出、行军推进、战斗检测与结算）
4. 胜利判定（城市最多者胜）
5. 生成玩家观察数据（含信息迷雾）

所有子系统在此汇聚：
- MapSystem → 地图拓扑
- ResourceSystem → 资源产出
- CitySystem → 城市发展/征兵
- GeneralSystem → 将领探索/赏赐/忠诚
- DiplomacySystem → 外交消息/流言
- ArmyMovementSystem → 行军
- BattleScheduler/BattleResolver → 战斗
- EventBus → 事件通知
- StateManager → 状态快照（TODO: 任务4.3）

参考设计文档：docs/design/architecture.md 第二章
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from game.constants import (
    MAX_TURNS,
    NUM_FACTIONS,
    FACTIONS,
    ARMY_FOOD_COST_PER_SOLDIER,
)
from game.event_bus import EventBus
from game.models import (
    Army,
    ArmyStatus,
    BattleContext,
    BattlePhase,
    BattleResult,
    BattleResultType,
    City,
    Command,
    DevelopCommand,
    RecruitCommand,
    AttackCommand,
    RewardCommand,
    ExploreCommand,
    MessageCommand,
    RumorCommand,
    DiplomacyMessage,
    General,
    GameObservation,
    GameState,
    TurnLog,
)
from game.random import GameRandom
from game.systems.city_system import CitySystem
from game.systems.diplomacy_system import DiplomacySystem
from game.systems.general_system import GeneralSystem
from game.systems.map_system import MapSystem
from game.systems.resource_system import ResourceSystem
from game.battle.army_movement import ArmyMovementSystem
from game.battle.battle_scheduler import BattleScheduler
from game.battle.battle_resolver import BattleResolver

logger = logging.getLogger(__name__)


# ============================================================
# 命令执行结果
# ============================================================


@dataclass
class CommandResult:
    """命令执行结果"""

    success: bool = False
    command_type: str = ""
    description: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TurnResult:
    """回合处理结果"""

    turn: int = 0
    game_over: bool = False
    winner: str = ""
    cities_updated: int = 0
    armies_moved: int = 0
    battles_fought: int = 0
    events: List[Dict[str, Any]] = field(default_factory=list)


# ============================================================
# GameEngine 主类
# ============================================================


class GameEngine:
    """游戏引擎主类

    管理完整的游戏生命周期：初始化 → 回合循环 → 结束。
    所有系统通过此类协调工作。
    """

    def __init__(self, seed: int = 42) -> None:
        """初始化游戏引擎

        Args:
            seed: 随机种子，默认42
        """
        self.seed: int = seed
        self.rng: GameRandom = GameRandom(seed)

        # 游戏状态
        self.turn: int = 1
        self.max_turns: int = MAX_TURNS
        self.game_over: bool = False
        self.winner: Optional[str] = None

        # 模式与时间
        from game.game_mode import GameMode
        from game.season import Season
        self.game_mode: GameMode = GameMode.STANDARD
        self.season: Season = Season.SPRING
        self.year: int = 184  # 黄巾起义起始年
        self.start_year: int = 184

        # 游戏数据
        self.cities: Dict[str, City] = {}
        self.armies: Dict[str, Army] = {}
        self.generals: Dict[str, General] = {}

        # 子系统
        self.map: MapSystem = MapSystem()
        self._city_system: CitySystem = CitySystem()
        self._resource_system: ResourceSystem = ResourceSystem()
        self._general_system: GeneralSystem = GeneralSystem(rng=self.rng)
        self._diplomacy_system: DiplomacySystem = DiplomacySystem(rng=self.rng)
        self._army_movement: ArmyMovementSystem = ArmyMovementSystem()
        self._battle_scheduler: BattleScheduler = BattleScheduler(rng=self.rng)
        self._battle_resolver: BattleResolver = BattleResolver(rng=self.rng)
        self._kingdom_system: Any = None  # 建国系统（init_game 时初始化）

        # Hex Map (loaded in init_game)
        self.hex_map: Optional[Any] = None
        self._influence_system: Optional[Any] = None

        # 事件总线
        self.events: EventBus = EventBus()

        # 日志
        self.turn_logs: List[TurnLog] = []
        self._messages: List[DiplomacyMessage] = []
        self._pending_battles: List[BattleContext] = []
        self._army_counter: int = 0

    # ============================================================
    # 游戏初始化
    # ============================================================

    def init_game(self, data: Dict[str, Any]) -> None:
        """从数据字典初始化游戏

        Args:
            data: 包含 cities, generals, map_topology 的字典
                  格式参考 data/*.json
        """
        # 1. 加载城市
        for city_data in data.get("cities", []):
            city = City(**city_data)
            self.cities[city.id] = city
            self.map.add_city(city)

        # 2. 加载将领
        for gen_data in data.get("generals", []):
            general = General(**gen_data)
            self.generals[general.id] = general

        # 3. 加载地图拓扑（确保双向连接）
        topology = data.get("map_topology", {})
        for city_id, neighbors in topology.items():
            if city_id in self.cities:
                self.cities[city_id].neighbors = list(neighbors)
                # 重新添加到地图以确保双向连接
                self.map.add_city(self.cities[city_id])

        logger.info(
            "游戏初始化完成: %d 城市, %d 将领, %d 势力",
            len(self.cities), len(self.generals), NUM_FACTIONS,
        )

        # 初始化建国系统
        from game.kingdom_system import KingdomSystem
        self._kingdom_system = KingdomSystem()

        # 4. 加载 HexMap（如果地图数据可用）
        self._init_hex_map(data)

    def _init_hex_map(self, data: Dict[str, Any]) -> None:
        """初始化六角格地图"""
        try:
            from game.data_loader import load_hex_map_data
            from game.hex_map import HexMap
            from game.hex_grid import HexCoord
            from game.tile import Tile, TerrainType
            from game.influence_system import InfluenceSystem

            hex_data = load_hex_map_data()
            self.hex_map = HexMap(
                width=hex_data["width"],
                height=hex_data["height"],
            )
            for t in hex_data.get("terrain", []):
                self.hex_map.add_tile(Tile(
                    coord=HexCoord(t["q"], t["r"]),
                    terrain=TerrainType(t["terrain"]),
                    elevation=t.get("elevation", 0),
                    gold_yield=t.get("gold_yield", 0),
                    food_yield=t.get("food_yield", 0),
                    pop_yield=t.get("pop_yield", 0),
                ))

            # 绑定城市位置到 HexMap
            for city_id, pos in hex_data.get("city_positions", {}).items():
                if city_id in self.cities:
                    self.cities[city_id].position = HexCoord(pos["q"], pos["r"])

            # 初始化地块归属和产出
            self._initialize_territories()

            # 初始化影响力系统
            self._influence_system = InfluenceSystem()

            logger.info("HexMap 加载完成: %d 格", len(list(self.hex_map.iter_tiles())))
        except Exception as e:
            logger.warning("HexMap 加载失败: %s，使用降级模式", e)
            self.hex_map = None
            self._influence_system = None

    def _initialize_territories(self) -> None:
        """初始化城市控制区地块的归属和产出"""
        if self.hex_map is None:
            return
        from game.constants import TERRAIN_YIELDS

        for city in self.cities.values():
            territory = self._city_system.get_city_territory(city, self.hex_map)
            for coord in territory:
                tile = self.hex_map.get_tile(coord)
                if tile is not None:
                    tile.owner_city_id = city.id
                    tile.faction = city.faction
                    yields = TERRAIN_YIELDS.get(tile.terrain.value, {})
                    tile.gold_yield = yields.get("gold", 0)
                    tile.food_yield = yields.get("food", 0)
                    tile.pop_yield = yields.get("pop", 0)

    # ============================================================
    # 命令执行
    # ============================================================

    def execute_command(self, command: Command) -> CommandResult:
        """执行一个玩家命令

        Args:
            command: 命令对象

        Returns:
            命令执行结果
        """
        command_type = command.type

        try:
            if command_type == "develop" and isinstance(command, DevelopCommand):
                return self._execute_develop(command)
            elif command_type == "recruit" and isinstance(command, RecruitCommand):
                return self._execute_recruit(command)
            elif command_type == "attack" and isinstance(command, AttackCommand):
                return self._execute_attack(command)
            elif command_type == "reward" and isinstance(command, RewardCommand):
                return self._execute_reward(command)
            elif command_type == "explore" and isinstance(command, ExploreCommand):
                return self._execute_explore(command)
            elif command_type == "message" and isinstance(command, MessageCommand):
                return self._execute_message(command)
            elif command_type == "rumor" and isinstance(command, RumorCommand):
                return self._execute_rumor(command)
            else:
                return CommandResult(
                    success=False,
                    command_type=command_type,
                    description=f"未知命令类型: {command_type}",
                )
        except Exception as e:
            logger.exception("命令执行失败: %s", command)
            return CommandResult(
                success=False,
                command_type=command_type,
                description=f"命令执行异常: {e}",
            )

    def _execute_develop(self, cmd: DevelopCommand) -> CommandResult:
        """执行发展命令"""
        city = self.cities.get(cmd.city)
        if city is None:
            return CommandResult(success=False, command_type="develop",
                                 description=f"城市 {cmd.city} 不存在")
        if city.faction != cmd.faction:
            return CommandResult(success=False, command_type="develop",
                                 description=f"城市 {cmd.city} 不属于 {cmd.faction}")

        result = self._city_system.develop(city, cmd.develop_type)
        return CommandResult(
            success=result.success,
            command_type="develop",
            description=result.description,
            data={"gold_cost": result.gold_cost, "effect": result.effect_value},
        )

    def _execute_recruit(self, cmd: RecruitCommand) -> CommandResult:
        """执行征兵命令"""
        city = self.cities.get(cmd.city)
        if city is None:
            return CommandResult(success=False, command_type="recruit",
                                 description=f"城市 {cmd.city} 不存在")
        if city.faction != cmd.faction:
            return CommandResult(success=False, command_type="recruit",
                                 description=f"城市 {cmd.city} 不属于 {cmd.faction}")

        result = self._city_system.recruit(city, cmd.troops)
        return CommandResult(
            success=result.success,
            command_type="recruit",
            description=result.description,
            data={"troops": result.troops_recruited,
                  "gold_cost": result.gold_cost, "food_cost": result.food_cost},
        )

    def _execute_attack(self, cmd: AttackCommand) -> CommandResult:
        """执行进攻命令"""
        # 验证出发城市
        from_city = self.cities.get(cmd.from_city)
        if from_city is None:
            return CommandResult(success=False, command_type="attack",
                                 description=f"出发城市 {cmd.from_city} 不存在")
        if from_city.faction != cmd.faction:
            return CommandResult(success=False, command_type="attack",
                                 description=f"城市 {cmd.from_city} 不属于 {cmd.faction}")

        # 验证目标城市
        to_city = self.cities.get(cmd.to_city)
        if to_city is None:
            return CommandResult(success=False, command_type="attack",
                                 description=f"目标城市 {cmd.to_city} 不存在")

        # 验证兵力
        if cmd.troops > from_city.garrison:
            return CommandResult(success=False, command_type="attack",
                                 description=f"兵力不足: 需要{cmd.troops}, 仅有{from_city.garrison}")

        # 验证将领
        general = self.generals.get(cmd.general)
        if general is None:
            return CommandResult(success=False, command_type="attack",
                                 description=f"将领 {cmd.general} 不存在")
        if general.location != from_city.id:
            return CommandResult(success=False, command_type="attack",
                                 description=f"将领 {cmd.general} 不在 {cmd.from_city}")

        # 计算距离
        distance = self.map.get_distance(cmd.from_city, cmd.to_city)
        if distance <= 0:
            return CommandResult(success=False, command_type="attack",
                                 description=f"无法到达 {cmd.to_city}")

        # 计算六角格路径（如果 HexMap 可用）
        hex_path: list = []
        if self.hex_map is not None:
            from game.hex_grid import HexCoord
            from_city_pos = self.cities[cmd.from_city].position
            to_city_pos = self.cities[cmd.to_city].position
            hex_path = self.hex_map.find_path(from_city_pos, to_city_pos)
            if not hex_path:
                return CommandResult(success=False, command_type="attack",
                                     description=f"无法从 {cmd.from_city} 行军到 {cmd.to_city}（无可行路径）")

        hex_distance_val = max(1, len(hex_path) - 1) if hex_path else distance

        # 创建军队
        self._army_counter += 1
        army = Army(
            id=f"army_{self._army_counter}",
            faction=cmd.faction,
            general_id=cmd.general,
            soldiers=cmd.troops,
            food=cmd.troops * 3,  # 自带3回合粮草
            food_consumption_per_turn=int(cmd.troops * ARMY_FOOD_COST_PER_SOLDIER),
            morale=80,
            status=ArmyStatus.MARCHING,
            from_city=cmd.from_city,
            to_city=cmd.to_city,
            progress=0.0,
            total_distance=distance if not hex_path else hex_distance_val,
            current_hex=hex_path[0] if hex_path else None,
            path_hexes=hex_path if hex_path else [],
            path_index=0,
        )
        self.armies[army.id] = army

        # 减少城市守军
        from_city.garrison -= cmd.troops

        # 将领出征
        general.location = army.id

        return CommandResult(
            success=True,
            command_type="attack",
            description=f"军队 {army.id} 从 {cmd.from_city} 出发，目标 {cmd.to_city}，距离 {distance} 回合",
            data={"army_id": army.id, "distance": distance},
        )

    def _execute_reward(self, cmd: RewardCommand) -> CommandResult:
        """执行赏赐命令"""
        general = self.generals.get(cmd.general)
        if general is None:
            return CommandResult(success=False, command_type="reward",
                                 description=f"将领 {cmd.general} 不存在")

        # 确定支付赏赐的城市
        city: Optional[City] = None
        if general.location in self.cities:
            city = self.cities[general.location]
        elif general.location.startswith("army_"):
            # 将领随军出征，从军队出发城市支付
            army = self.armies.get(general.location)
            if army:
                city = self.cities.get(army.from_city)

        if city is None:
            return CommandResult(success=False, command_type="reward",
                                 description=f"将领所在位置 {general.location} 无城市")

        result = self._general_system.reward(general, city, cmd.gold)
        return CommandResult(
            success=result.success,
            command_type="reward",
            description=result.description,
            data={"loyalty_change": result.loyalty_change},
        )

    def _execute_explore(self, cmd: ExploreCommand) -> CommandResult:
        """执行探索命令"""
        city = self.cities.get(cmd.city)
        if city is None:
            return CommandResult(success=False, command_type="explore",
                                 description=f"城市 {cmd.city} 不存在")

        result = self._general_system.explore(city)
        if result.found:
            # 创建新将领
            gen_id = f"explored_{len(self.generals) + 1}"
            new_general = General(
                id=gen_id,
                name=result.general_name,
                faction=cmd.faction,
                command=result.general_command,
                politics=result.general_politics,
                bravery=result.general_bravery,
                intelligence=result.general_intelligence,
                loyalty=60,
                location=cmd.city,
            )
            self.generals[gen_id] = new_general
            city.generals.append(gen_id)

            return CommandResult(
                success=True,
                command_type="explore",
                description=result.description,
                data={"general_id": gen_id, "general_name": result.general_name},
            )

        return CommandResult(
            success=True,
            command_type="explore",
            description=result.description,
        )

    def _execute_message(self, cmd: MessageCommand) -> CommandResult:
        """执行外交消息命令"""
        result = self._diplomacy_system.send_message(
            from_faction=cmd.faction,
            to_faction=cmd.to,
            content=cmd.content,
            turn=self.turn,
        )
        return CommandResult(
            success=result.success,
            command_type="message",
            description=result.description,
            data={"message_id": result.message_id},
        )

    def _execute_rumor(self, cmd: RumorCommand) -> CommandResult:
        """执行流言命令"""
        target_general = None
        if cmd.target_general:
            target_general = self.generals.get(cmd.target_general)

        spy_intelligence = 50
        if cmd.spy_general:
            spy = self.generals.get(cmd.spy_general)
            if spy:
                spy_intelligence = spy.intelligence

        result = self._diplomacy_system.spread_rumor(
            target_city_id=cmd.city,
            target_faction="",  # 由 GameEngine 查城市归属
            spy_intelligence=spy_intelligence,
            target_general=target_general,
            turn=self.turn,
        )
        return CommandResult(
            success=result.success,
            command_type="rumor",
            description=result.description,
            data={"loyalty_decrease": result.loyalty_decrease},
        )

    # ============================================================
    # 回合处理
    # ============================================================

    def process_turn(self) -> Dict[str, Any]:
        """处理一个完整的游戏回合

        回合流程：
        1. 资源产出（所有城市）
        2. 行军推进（所有军队）
        3. 战斗检测与结算
        4. 将领忠诚度衰减
        5. 胜利判定
        6. 回合计数递增

        Returns:
            回合处理结果摘要
        """
        result: Dict[str, Any] = {
            "turn": self.turn,
            "cities_updated": 0,
            "armies_moved": 0,
            "battles_fought": 0,
            "game_over": False,
            "winner": None,
        }

        # 更新季节和年份（每 4 回合 = 1 年）
        from game.season import Season
        self.season = Season.from_turn(self.turn)
        self.year = self.start_year + (self.turn - 1) // 4

        # 1. 资源产出
        for city in self.cities.values():
            if self.hex_map is not None:
                # 使用地块产出计算
                territory = self._city_system.get_city_territory(city, self.hex_map)
                tiles = [self.hex_map.get_tile(c) for c in territory]
                tiles = [t for t in tiles if t is not None]
                resource_result = self._resource_system.calculate_resources(
                    city, tiles=tiles, season=getattr(self, 'season', 'spring')
                )
                city.gold += resource_result["gold_change"]
                city.food += resource_result["food_change"]
                city.population += resource_result["population_change"]
                # 确保资源不为负
                city.gold = max(0, city.gold)
                city.food = max(0, city.food)
                city.population = max(0, city.population)
            else:
                self._city_system.update_city(city)
            result["cities_updated"] += 1

        # 影响力扩散
        if self._influence_system is not None and self.hex_map is not None:
            self._influence_system.spread_influence(
                list(self.cities.values()), self.hex_map
            )

        # 2. 行军推进（所有非驻守军队）
        season = getattr(self, 'season', 'spring')
        disbanded_army_ids: List[str] = []
        for army in list(self.armies.values()):
            if army.soldiers <= 0:
                # 全灭的军队清理
                del self.armies[army.id]
                continue
            if self.hex_map is not None:
                move_result = self._army_movement.process_movement(
                    army, hex_map=self.hex_map, season=season,
                    cities=self.cities, generals=self.generals,
                )
            else:
                move_result = self._army_movement.process_movement(
                    army, cities=self.cities, generals=self.generals,
                )
            if move_result.disbanded:
                disbanded_army_ids.append(army.id)
            result["armies_moved"] += 1

        # 清理已并入守军的到达部队
        for army_id in disbanded_army_ids:
            if army_id in self.armies:
                del self.armies[army_id]

        # 3. 将领忠诚度衰减
        for general in self.generals.values():
            self._general_system.process_turn_decay(general)

        # 4. 战斗检测与结算
        battle_contexts = self._battle_scheduler.detect_battles(
            armies=self.armies,
            cities=self.cities,
            map_system=self.map,
            generals=self.generals,
        )

        for ctx in battle_contexts:
            ctx.turn = self.turn
            # 更新上下文中的兵力数据
            ctx.attacker_total_soldiers = sum(
                self.armies[a_id].soldiers
                for a_id in ctx.attacker_armies
                if a_id in self.armies
            )
            ctx.attacker_initial_soldiers = ctx.attacker_total_soldiers

            defender_city = self.cities.get(ctx.defender_city or "")
            if defender_city:
                ctx.defender_total_soldiers = defender_city.garrison
                ctx.defender_initial_soldiers = ctx.defender_total_soldiers
                # 传递实际城墙耐久（攻城战用）
                ctx.wall_hp = defender_city.wall_hp
                ctx.wall_max_hp = defender_city.wall_max_hp

            battle_result = self._battle_resolver.resolve_battle(ctx)
            self._apply_battle_result(ctx, battle_result)

            # 回写城墙耐久与守军数量（攻城战中可能被损坏/消灭）
            if defender_city and ctx.wall_hp >= 0:
                defender_city.wall_hp = ctx.wall_hp
                defender_city.garrison = max(0, ctx.defender_total_soldiers)

            result["battles_fought"] += 1

        # 5. 清理已消灭的军队
        self._cleanup_dead_armies()

        # 6. 胜利判定
        self._check_victory()
        result["game_over"] = self.game_over
        result["winner"] = self.winner

        # 7. 建国检测
        if self._kingdom_system is not None:
            for faction in FACTIONS:
                faction_cities = [c for c in self.cities.values() if c.faction == faction]
                kingdom = self._kingdom_system.check_kingdom_eligibility(faction, list(self.cities.values()))
                if kingdom:
                    logger.info("🏰 %s 称%s！国号【%s】",
                                FACTIONS.get(faction, faction),
                                "帝" if kingdom["type"] == "emperor" else "王",
                                kingdom["name"])

        # 8. 回合递增
        if not self.game_over:
            self.turn += 1

        # 记录日志
        self.turn_logs.append(TurnLog(
            turn=result["turn"],
            events=[result],
        ))

        return result

    # ============================================================
    # 战斗结果应用
    # ============================================================

    def _apply_battle_result(
        self, ctx: BattleContext, result: BattleResult
    ) -> None:
        """应用战斗结果到游戏状态

        Args:
            ctx: 战斗上下文
            result: 战斗结果
        """
        defender_city = self.cities.get(ctx.defender_city or "")

        if result.result == BattleResultType.ATTACKER_WIN:
            # 攻击方胜利：占领城市
            captured_city_id = result.captured_city or ctx.defender_city
            if captured_city_id and captured_city_id in self.cities:
                city = self.cities[captured_city_id]
                city.faction = ctx.attacker_faction
                city.morale = max(20, city.morale - 20)  # 占领后民心下降

                # 合并幸存攻击方兵力入城守军
                surviving_attackers = 0
                for army_id in ctx.attacker_armies:
                    if army_id in self.armies:
                        army = self.armies[army_id]
                        initial_total = max(ctx.attacker_initial_soldiers, 1)
                        loss_ratio = result.attacker_casualties / initial_total
                        army.soldiers = max(0, int(army.soldiers * (1 - loss_ratio)))
                        surviving_attackers += army.soldiers
                        # 将领入驻城市
                        if army.soldiers > 0 and army.general_id in self.generals:
                            self.generals[army.general_id].location = city.id
                        # 标记为可清理
                        army.soldiers = 0
                city.garrison += surviving_attackers

            # 清理攻击方军队（已并入守军或全灭）
            for army_id in list(ctx.attacker_armies):
                if army_id in self.armies:
                    del self.armies[army_id]

        elif result.result == BattleResultType.DEFENDER_WIN:
            # 防守方胜利：攻击方军队撤退或消灭
            for army_id in ctx.attacker_armies:
                if army_id in self.armies:
                    army = self.armies[army_id]
                    initial_total = max(ctx.attacker_initial_soldiers, 1)
                    loss_ratio = result.attacker_casualties / initial_total
                    army.soldiers = max(0, int(army.soldiers * (1 - loss_ratio)))
                    if army.soldiers > 0:
                        army.status = ArmyStatus.RETREATING
                        # 撤回出发城市
                        army.from_city, army.to_city = army.to_city, army.from_city

        elif result.result in (BattleResultType.DRAW, BattleResultType.RETREAT):
            # 平局/撤退
            for army_id in ctx.attacker_armies:
                if army_id in self.armies:
                    army = self.armies[army_id]
                    initial_total = max(ctx.attacker_initial_soldiers, 1)
                    loss_ratio = result.attacker_casualties / initial_total
                    army.soldiers = max(0, int(army.soldiers * (1 - loss_ratio)))
                    if army.soldiers > 0:
                        army.status = ArmyStatus.RETREATING

        # 清理该城市的围城状态
        if defender_city is not None:
            defender_city.is_besieged = False
            defender_city.besieging_armies = []

        # 清理俘虏的将领
        for gen_id in result.captured_generals:
            if gen_id in self.generals:
                gen = self.generals[gen_id]
                self._general_system.process_capture(
                    gen, captor_faction=ctx.attacker_faction, turn=self.turn,
                )

    def _cleanup_dead_armies(self) -> None:
        """清理已消灭的军队"""
        dead_army_ids = [
            aid for aid, army in self.armies.items()
            if army.soldiers <= 0
        ]
        for aid in dead_army_ids:
            army = self.armies[aid]
            # 将领返回原城市
            gen = self.generals.get(army.general_id)
            if gen:
                gen.location = army.from_city
            del self.armies[aid]

    # ============================================================
    # 胜利判定
    # ============================================================

    def _check_victory(self) -> None:
        """检查游戏是否结束

        标准模式：
        - 192回合到达 → 城市最多者胜
        - 某势力无城市 → 该势力出局（其他继续）
        - 只剩一个势力 → 该势力胜

        无限模式：
        - 只剩一个势力 → 统一全国胜利
        - 无回合上限，不因 turn 结束
        """
        if self.game_over:
            return

        # 统计各势力城市数
        city_counts: Dict[str, int] = {}
        for city in self.cities.values():
            city_counts[city.faction] = city_counts.get(city.faction, 0) + 1

        # 检查是否只剩一个势力（其他全灭）
        active_factions = [f for f, c in city_counts.items() if c > 0 and f != "neutral"]
        if len(active_factions) == 1:
            self.game_over = True
            self.winner = active_factions[0]
            return

        # 无限模式：只通过统一全国结束
        from game.game_mode import GameMode
        if self.game_mode == GameMode.INFINITE:
            return

        # 检查是否到达最大回合（排除中立城）
        if self.turn >= self.max_turns:
            self.game_over = True
            active_counts = {f: c for f, c in city_counts.items() if f != "neutral"}
            if not active_counts:
                self.winner = None
                return
            max_count = max(active_counts.values())
            winners = [f for f, c in active_counts.items() if c == max_count]
            self.winner = winners[0] if len(winners) == 1 else None  # 平局

    # ============================================================
    # 观察数据生成
    # ============================================================

    def get_observation(self, faction: str) -> GameObservation:
        """为指定势力生成游戏观察数据

        包含信息迷雾：己方信息完整，敌方信息有限。

        Args:
            faction: 势力名称

        Returns:
            该势力能看到的游戏状态
        """
        own_cities = [
            c for c in self.cities.values() if c.faction == faction
        ]
        own_armies = [
            a for a in self.armies.values() if a.faction == faction
        ]
        own_generals = [
            g for g in self.generals.values()
            if g.faction == faction and not g.is_captured
        ]

        # 敌方城市（有迷雾）
        known_cities = []
        for city in self.cities.values():
            if city.faction != faction:
                from game.models import CityInfo, ArmyInfo
                # 检查是否相邻
                is_neighbor = any(
                    n in [oc.id for oc in own_cities]
                    for n in city.neighbors
                )
                info = CityInfo(
                    id=city.id,
                    name=city.name,
                    faction=city.faction,
                    level=city.level,
                    is_besieged=city.is_besieged,
                )
                if is_neighbor:
                    info.garrison = city.garrison
                    info.morale = city.morale
                    info.wall_hp = city.wall_hp
                known_cities.append(info)

        # 可见敌方军队（信息迷雾）
        visible_armies = []
        own_city_ids = {c.id for c in own_cities}
        own_army_hexes = {a.current_hex for a in own_armies if a.current_hex is not None}
        for army in self.armies.values():
            if army.faction == faction or army.soldiers <= 0:
                continue
            visible = False
            if army.current_hex is not None and army.current_hex in own_army_hexes:
                visible = True
            elif army.to_city in own_city_ids or army.from_city in own_city_ids:
                visible = True
            else:
                # 与城市相邻的敌方军队可见
                for oc in own_cities:
                    if army.to_city in oc.neighbors or army.from_city in oc.neighbors:
                        visible = True
                        break
            if visible:
                soldiers_estimate = "few"
                if army.soldiers >= 3000:
                    soldiers_estimate = "many"
                elif army.soldiers >= 1000:
                    soldiers_estimate = "normal"
                morale_estimate = "low"
                if army.morale >= 70:
                    morale_estimate = "high"
                elif army.morale >= 40:
                    morale_estimate = "normal"
                visible_armies.append(ArmyInfo(
                    id=army.id,
                    faction=army.faction,
                    status=army.status,
                    general_id=army.general_id,
                    soldiers_estimate=soldiers_estimate,
                    morale_estimate=morale_estimate,
                ))

        return GameObservation(
            faction=faction,
            turn=self.turn,
            max_turns=self.max_turns,
            own_cities=own_cities,
            own_armies=own_armies,
            own_generals=own_generals,
            known_cities=known_cities,
            visible_armies=visible_armies,
            map_topology={
                cid: c.neighbors for cid, c in self.cities.items()
            },
            received_messages=self._diplomacy_system.get_messages_for_faction(faction),
            sent_messages=self._diplomacy_system.get_sent_messages(faction),
            recent_events=[
                {"turn": tl.turn, "summary": tl.events[-1] if tl.events else {}}
                for tl in self.turn_logs[-5:]
            ],
        )

    # ============================================================
    # 状态管理
    # ============================================================

    def get_state_snapshot(self) -> GameState:
        """获取当前游戏状态快照

        Returns:
            可序列化的完整游戏状态
        """
        return GameState(
            turn=self.turn,
            seed=self.seed,
            game_over=self.game_over,
            winner=self.winner,
            cities=self.cities,
            armies=self.armies,
            generals=self.generals,
            messages=self._messages,
            turn_logs=self.turn_logs,
        )

    def load_state_snapshot(self, state: GameState) -> None:
        """从快照恢复游戏状态

        Args:
            state: 之前保存的游戏状态
        """
        self.turn = state.turn
        self.seed = state.seed
        self.game_over = state.game_over
        self.winner = state.winner
        self.cities = state.cities
        self.armies = state.armies
        self.generals = state.generals
        self._messages = state.messages
        self.turn_logs = state.turn_logs

        # 重建子系统
        self.rng = GameRandom(self.seed)
        self.map = MapSystem()
        for city in self.cities.values():
            self.map.add_city(city)
