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
    NATURE_STRAIN_MORALE_PENALTY,
    CITY_LOSS_LOYALTY_PENALTY,
)
from game.event_bus import (
    BattleEndedEvent,
    CityCapturedEvent,
    EventBus,
    TurnEndedEvent,
    TurnStartedEvent,
)
from game.turn_phase import TurnPhase, register_phase_hook, run_phase_hooks
from game.command_registry import get_handler, register_command
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
    ProposeAllianceCommand,
    DeclareWarCommand,
    DiplomacyMessage,
    DiplomaticStatus,
    General,
    GameObservation,
    GameState,
    Province,
    TurnLog,
)
from game.random import GameRandom
from game.personality import FACTION_PERSONALITY, get_general_profile
from game.systems.city_system import CitySystem, GARRISON_CAP_PER_LEVEL
from game.systems.diplomacy_system import DiplomacySystem
from game.systems.diplomacy_relation import DiplomacyRelationSystem
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
        self.provinces: Dict[str, Province] = {}

        # 子系统
        self.map: MapSystem = MapSystem()
        self._city_system: CitySystem = CitySystem()
        self._resource_system: ResourceSystem = ResourceSystem()
        self._general_system: GeneralSystem = GeneralSystem(rng=self.rng)
        self._diplomacy_system: DiplomacySystem = DiplomacySystem(rng=self.rng)
        self._diplomacy_relation_system: Optional[DiplomacyRelationSystem] = None
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

        # v4.0：本回合各势力实际发出的命令类型 (faction, cmd_type)
        # 用途见 _apply_nature_strain：判断该势力本回合的抉择是否违背其君主本性
        self._turn_actions: List[Tuple[str, str]] = []
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
            # v4.0：把开局忠诚度固化为该将领的「忠诚基准」
            # 忠诚度每回合向基准回归（而非单向衰减到 0），
            # 使赏赐/被俘/失城造成的偏离会自动缓慢回归人物本性。
            if general.loyalty_baseline is None:
                general.loyalty_baseline = general.loyalty
            # v4.0：从人设档案回填性格。
            # data/generals.json 里没有 personality 字段（全为 None → 默认 balanced），
            # 原 GENERAL_PERSONALITIES 的 key 又与数据 ID 对不上（17/19 失配），
            # 所以性格此前从未真正进入过游戏。
            profile = get_general_profile(general.id)
            if profile is not None:
                general.personality = profile["personality"]
            self.generals[general.id] = general

        # 3. 加载州数据
        for prov_data in data.get("provinces", []):
            province = Province(**prov_data)
            self.provinces[province.id] = province
            self.map.add_province(province)

        # 填充每个州的城市列表
        for city in self.cities.values():
            if city.province_id and city.province_id in self.provinces:
                if city.id not in self.provinces[city.province_id].cities:
                    self.provinces[city.province_id].cities.append(city.id)

        # 4. 将领分配到城市（填充 city.generals）
        for general in self.generals.values():
            loc = general.location
            if loc in self.cities:
                if general.id not in self.cities[loc].generals:
                    self.cities[loc].generals.append(general.id)

        # 5. 加载地图拓扑（确保双向连接）
        topology = data.get("map_topology", {})
        for city_id, neighbors in topology.items():
            if city_id in self.cities:
                self.cities[city_id].neighbors = list(neighbors)
                # 重新添加到地图以确保双向连接
                self.map.add_city(self.cities[city_id])

        logger.info(
            "游戏初始化完成: %d 城市, %d 将领, %d 州, %d 势力",
            len(self.cities), len(self.generals), len(self.provinces), NUM_FACTIONS,
        )

        # 初始化建国系统
        from game.kingdom_system import KingdomSystem
        self._kingdom_system = KingdomSystem()

        # 初始化外交关系系统
        from game.constants import FACTIONS
        self._diplomacy_relation_system = DiplomacyRelationSystem(list(FACTIONS.keys()))

        # 4. 加载 HexMap（如果地图数据可用）
        self._init_hex_map(data)

    def _init_hex_map(self, data: Dict[str, Any]) -> None:
        """初始化六角格地图（使用 MapGenerator 程序化生成）

        使用 MapGenerator 生成完整六角格地图（15 种地形），
        城市坐标仍从 hex_map.json 读取（Phase 2 再做公平起始位置分配）。
        """
        try:
            from game.map_generator import MapGenerator
            from game.hex_map import HexMap
            from game.hex_grid import HexCoord
            from game.tile import Tile, TerrainType
            from game.influence_system import InfluenceSystem

            from game.constants import HEX_MAP_WIDTH, HEX_MAP_HEIGHT

            # 使用 MapGenerator 程序化生成地形
            map_gen = MapGenerator(rng=self.rng)
            self.hex_map = map_gen.generate(
                width=HEX_MAP_WIDTH,
                height=HEX_MAP_HEIGHT,
            )

            # [修复 2026-10-01] 不再用 hex_map.json 的 city_positions 覆盖城市坐标：
            # 那份坐标属于 120×90 / 95-125°E·22-45°N 的旧地图空间，而运行时地图是
            # 200×120 / 73-136°E·16-54°N → 覆盖后城池会落到海里/错位。
            # data/cities.json 中每个城市自带的 position 才是与新地图匹配的坐标。

            # [修复 2026-10-01] 城市地块强制可通行（山/峰 → PLAIN），**不再挪动城市**。
            # 原实现遇到不可通行地形会把城市搬到最近可通行格 → 13 座城偏离真实地理 1~4 格。
            for city in self.cities.values():
                tile = self.hex_map.get_tile(city.position)
                if tile is None:
                    nearest = self._find_nearest_passable(city.position)
                    if nearest is not None:
                        city.position = nearest
                    continue
                if not tile.is_passable():
                    logger.info(
                        "城市 %s 所在格地形 %s 不可通行 → 就地改为 PLAIN（保持真实定位）",
                        city.id, tile.terrain.value,
                    )
                    tile.terrain = TerrainType.PLAIN

            # 初始化地块归属和产出
            self._initialize_territories()

            # 初始化影响力系统
            self._influence_system = InfluenceSystem()

            logger.info("HexMap 生成完成: %d 格", len(list(self.hex_map.iter_tiles())))
        except Exception as e:
            logger.warning("HexMap 生成失败: %s，使用降级模式", e)
            self.hex_map = None
            self._influence_system = None

    def _find_nearest_passable(self, coord: 'HexCoord') -> 'Optional[HexCoord]':
        """从给定坐标开始 BFS 搜索最近的可通行地块

        用于城市位置落入水/山/峰时，自动修正到最近的可通行格。

        Args:
            coord: 原始坐标

        Returns:
            最近的可通行格坐标，未找到则返回 None
        """
        from collections import deque
        from game.hex_grid import HexCoord, hex_neighbors

        if self.hex_map is None:
            return None

        visited: set = {coord.to_tuple()}
        queue: deque = deque([coord])

        while queue:
            current = queue.popleft()
            tile = self.hex_map.get_tile(current)
            if tile is not None and tile.is_passable():
                return current
            for neighbor in hex_neighbors(current):
                key = neighbor.to_tuple()
                if key not in visited:
                    visited.add(key)
                    tile = self.hex_map.get_tile(neighbor)
                    if tile is not None:
                        queue.append(neighbor)
        return None

    def _initialize_territories(self) -> None:
        """初始化城市控制区地块的归属和产出"""
        if self.hex_map is None:
            return
        # [领地 2026-10-01] 归属统一交给 _expand_territories()（全量重划，先到先得）。
        self._expand_territories()

    def _expand_territories(self) -> None:
        """全量重划领地：清空所有地块归属，再从每座**有主城**做多源 BFS，先到先得。

        [领地 2026-10-01] 这是**唯一**的领地划分入口，开局与"占领后"都调用它，
        保证边界永远一致、无交叉、无残留（占领时不再需要手动转移领地）。
        - 源点：所有 faction != neutral 的城市
        - 扩张：深度 = 8 + level×2，避水/避峰，限中国境内（province_id 非空）
        - 先到先得 → 相邻势力自然形成边界
        """
        if self.hex_map is None:
            return
        from collections import deque
        from game.tile import TerrainType
        from game.hex_grid import HexCoord
        from game.constants import TERRAIN_YIELDS

        # 1. 清空所有地块归属
        for tile in self.hex_map.iter_tiles():
            tile.owner_city_id = None
            tile.faction = None

        blocked = {TerrainType.WATER, TerrainType.DEEP_WATER, TerrainType.PEAK}
        queue: deque = deque()
        assigned: set = set()

        # 2. 以所有有主城为源点
        for city in self.cities.values():
            if city.faction == "neutral":
                continue
            start = city.position
            if self.hex_map.get_tile(start) is None:
                continue
            depth = 8 + city.level * 2
            assigned.add((start.q, start.r))
            st = self.hex_map.get_tile(start)
            st.owner_city_id = city.id
            st.faction = city.faction
            queue.append((start.q, start.r, city.id, depth))

        dirs = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]
        while queue:
            q, r, city_id, depth = queue.popleft()
            if depth <= 0:
                continue
            for dq, dr in dirs:
                nq, nr = q + dq, r + dr
                if (nq, nr) in assigned:
                    continue
                tile = self.hex_map.get_tile(HexCoord(nq, nr))
                if tile is None:
                    continue
                if tile.terrain in blocked:
                    continue
                if not tile.province_id:
                    continue
                assigned.add((nq, nr))
                tile.owner_city_id = city_id
                tile.faction = self.cities[city_id].faction
                yields = TERRAIN_YIELDS.get(tile.terrain.value, {})
                tile.gold_yield = yields.get("gold", 0)
                tile.food_yield = yields.get("food", 0)
                tile.pop_yield = yields.get("pop", 0)
                queue.append((nq, nr, city_id, depth - 1))

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

        # v4.0：记录本回合各势力实际发出的命令类型，供「人设代价」判定使用。
        # 放在最前面记录（无论成败），因为"想做什么"比"做成了什么"更能体现本性。
        self._turn_actions.append((command.faction, command_type))

        try:
            # 命令分发走注册表（game/command_registry.py）——单一扩展点。
            # 新增命令只需 register_command(...)，**本函数不再枚举命令类型**。
            entry = get_handler(command_type)
            if entry is None:
                return CommandResult(
                    success=False,
                    command_type=command_type,
                    description=f"未知命令类型: {command_type}",
                )
            expected_cls, handler = entry
            # 保留原语义：type 命中但命令类不匹配（isinstance 失败）也按「未知命令」处理
            if not isinstance(command, expected_cls):
                return CommandResult(
                    success=False,
                    command_type=command_type,
                    description=f"未知命令类型: {command_type}",
                )
            return handler(self, command)
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

        # [G 解将荒 2026-10-0X v4.0] 放宽将领校验：原实现硬要求
        # `general.location == from_city.id`，导致「无驻将的城市」永久无法出征 ——
        # 出征胜后将领驻留新占城（见本函数占领分支 `general.location = city.id`），
        # 不回原城，终局约 48% 城市无本地将领 → 地图约第 26~31 回合彻底冻结。
        # 现允许调度**位于己方任意城市**的空闲将领随军出征，引擎自动「调将前来领兵」。
        dispatch_note = ""
        if general.location != from_city.id:
            is_dispatchable = (
                general.faction == cmd.faction
                and not general.is_captured
                and general.location in self.cities
                and self.cities[general.location].faction == cmd.faction
            )
            if not is_dispatchable:
                return CommandResult(success=False, command_type="attack",
                                     description=f"将领 {cmd.general} 不在 {cmd.from_city}")
            # 🔴 必须同步维护两座城的 city.generals 列表：
            # battle_scheduler.stationed_generals 直接读 target_city.generals 计算守方
            # 平均统帅/勇武/智力并生成 defender_general_ids，不维护会让守城将领名单错乱，
            # 隐性影响战斗结算与俘虏判定。把该将领 id 从旧城移除、加入出发城。
            old_city = self.cities[general.location]
            if general.id in old_city.generals:
                old_city.generals.remove(general.id)
            if general.id not in from_city.generals:
                from_city.generals.append(general.id)
            dispatch_note = f"（自 {old_city.id} 调将 {general.name} 前来领兵）"

        # 计算距离
        distance = self.map.get_distance(cmd.from_city, cmd.to_city)
        if distance <= 0:
            return CommandResult(success=False, command_type="attack",
                                 description=f"无法到达 {cmd.to_city}")

        # 外交检查：不能攻击同盟或停战中的势力
        if self._diplomacy_relation_system is not None:
            if not self._diplomacy_relation_system.can_attack(cmd.faction, to_city.faction):
                status = self._diplomacy_relation_system.get_status(cmd.faction, to_city.faction)
                return CommandResult(
                    success=False, command_type="attack",
                    description=f"无法攻击: 与 {to_city.faction} 处于 {status.value} 状态",
                )

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
            description=f"军队 {army.id} 从 {cmd.from_city} 出发，目标 {cmd.to_city}，距离 {distance} 回合{dispatch_note}",
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
                # v4.0：忠诚度与基准都用人才池中的史实值（原为硬编码 60）
                loyalty=result.general_loyalty or 70,
                loyalty_baseline=result.general_loyalty or 70,
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

        # 更新外交信任度
        if self._diplomacy_relation_system is not None:
            self._diplomacy_relation_system.on_message_sent(
                cmd.faction, cmd.to, is_positive=True
            )

        # 发布外交消息事件
        from game.event_bus import DiplomacyMessageSentEvent
        self.events.publish(
            DiplomacyMessageSentEvent(
                message_id=result.message_id,
                from_faction=cmd.faction,
                to_faction=cmd.to,
                content=cmd.content,
                turn=self.turn,
            )
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

    def _execute_propose_alliance(self, cmd: ProposeAllianceCommand) -> CommandResult:
        """执行提出同盟命令"""
        if cmd.to not in FACTIONS:
            return CommandResult(
                success=False,
                command_type="propose_alliance",
                description=f"目标势力 {cmd.to} 不存在",
            )
        if cmd.to == cmd.faction:
            return CommandResult(
                success=False,
                command_type="propose_alliance",
                description="不能与自己结盟",
            )

        # 史实硬约束（v4.1.2）：宿敌组合直接拒绝，不进入任何概率判定。
        # 为什么设硬规则而不是"降低概率"：玩家实测反馈
        # 「曹操、刘备、孙坚居然互相都结盟，破坏历史沉浸感」——
        # 单靠提示词与信任度只能让荒谬结盟变少，不能保证不发生；
        # 而「汉室与黄巾结盟」「袁绍与袁术结盟」这类是**史实上不可能**的，
        # 必须由代码兜底（对照：P 社/三国志系列同样用硬门槛 + 数值双层）。
        from game.personality import can_ally, relation_stance

        if not can_ally(cmd.faction, cmd.to):
            stance = relation_stance(cmd.faction, cmd.to)
            return CommandResult(
                success=False,
                command_type="propose_alliance",
                description=(
                    f"与 {FACTIONS.get(cmd.to, cmd.to)} 为{stance}，"
                    "史实上不可能结盟"
                ),
            )

        # 信任度门槛（v4.1.2）：让 `trust` 从"只显示的数字"变成真正的判据。
        # 在此之前 trust 从不参与任何决策（只被增减与展示），属于装饰。
        # 🔴 读当前值而非初始值——玩家可以用信使往来把它抬上来。
        from game.constants import DIPLOMACY_TRUST_MIN_FOR_ALLIANCE

        current = self._diplomacy_relation_system.get_relation(cmd.faction, cmd.to)
        current_trust = current.trust if current is not None else 0
        if current_trust < DIPLOMACY_TRUST_MIN_FOR_ALLIANCE:
            return CommandResult(
                success=False,
                command_type="propose_alliance",
                description=(
                    f"与 {FACTIONS.get(cmd.to, cmd.to)} 的信任度仅 {current_trust}，"
                    f"不足以结盟（需 {DIPLOMACY_TRUST_MIN_FOR_ALLIANCE}）。"
                    "可先遣使通信以积累信任。"
                ),
            )

        rel = self._diplomacy_relation_system.set_status(
            cmd.faction, cmd.to, DiplomaticStatus.ALLIANCE, turn=self.turn
        )
        return CommandResult(
            success=True,
            command_type="propose_alliance",
            description=f"与 {FACTIONS.get(cmd.to, cmd.to)} 结为同盟（信任度: {rel.trust}）",
            data={"trust": rel.trust, "alliance_end_turn": rel.alliance_end_turn},
        )

    def _execute_declare_war(self, cmd: DeclareWarCommand) -> CommandResult:
        """执行宣战命令"""
        if cmd.to not in FACTIONS:
            return CommandResult(
                success=False,
                command_type="declare_war",
                description=f"目标势力 {cmd.to} 不存在",
            )
        if cmd.to == cmd.faction:
            return CommandResult(
                success=False,
                command_type="declare_war",
                description="不能向自己宣战",
            )

        rel = self._diplomacy_relation_system.set_status(
            cmd.faction, cmd.to, DiplomaticStatus.WAR, turn=self.turn
        )
        return CommandResult(
            success=True,
            command_type="declare_war",
            description=f"向 {FACTIONS.get(cmd.to, cmd.to)} 宣战！（信任度: {rel.trust}）",
            data={"trust": rel.trust},
        )

    # ============================================================
    # 回合处理
    # ============================================================

    def _run_phase_hooks(self, phase: TurnPhase, result: Dict[str, Any]) -> None:
        """执行指定相位的注册钩子（回合相位扩展点，见 game/turn_phase.py）。

        新机制只需 `register_phase_hook(...)`，无需改动 process_turn 本体。
        钩子抛异常按「记录 + 继续」处理（见 turn_phase 模块 docstring）。
        """
        run_phase_hooks(self, phase, result)

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
        # v4.0：本回合命令记录清零（execute_command 会往里追加）
        self._turn_actions = []

        result: Dict[str, Any] = {
            "turn": self.turn,
            "cities_updated": 0,
            "armies_moved": 0,
            "battles_fought": 0,
            "game_over": False,
            "winner": None,
        }

        # 事件总线：回合开始广播（订阅者据此感知新回合）
        self.events.publish(
            TurnStartedEvent(turn=self.turn, faction_order=list(FACTIONS.keys()))
        )

        # 更新季节和年份（每 4 回合 = 1 年）
        from game.season import Season
        self.season = Season.from_turn(self.turn)
        self.year = self.start_year + (self.turn - 1) // 4

        # 相位钩子：回合开始
        self._run_phase_hooks(TurnPhase.TURN_START, result)

        # 0. 外交关系到期检查
        if self._diplomacy_relation_system is not None:
            expired = self._diplomacy_relation_system.update_turn(self.turn)
            for fa, fb, new_status in expired:
                logger.info("外交状态变更: %s <-> %s -> %s", fa, fb, new_status.value)

        # 1. 资源产出
        for city in self.cities.values():
            # 获取建国生产加成
            production_bonus = 0.0
            if self._kingdom_system is not None:
                production_bonus = self._kingdom_system.get_production_bonus(city.faction)

            if self.hex_map is not None:
                # 使用地块产出计算
                territory = self._city_system.get_city_territory(city, self.hex_map)
                # 🔴 确定性：territory 是 set，迭代序随 PYTHONHASHSEED 变化；
                # 而下面 ResourceSystem 用 `sum(t.gold_yield ...)` 等浮点求和，
                # 浮点加法不满足结合律，求和顺序不同可能产生 1-ULP 差异 →
                # int() 截断后产出差 1，进而使整局分叉。按 (q, r) 排序锁定顺序（ADR-0002）。
                tiles = [
                    self.hex_map.get_tile(c)
                    for c in sorted(territory, key=lambda h: (h.q, h.r))
                ]
                tiles = [t for t in tiles if t is not None]
                resource_result = self._resource_system.calculate_resources(
                    city, tiles=tiles, season=getattr(self, 'season', 'spring'),
                    production_bonus=production_bonus,
                    generals=self.generals,
                )
                city.gold += resource_result["gold_change"]
                city.food += resource_result["food_change"]
                city.population += resource_result["population_change"]
                # 确保资源不为负
                city.gold = max(0, city.gold)
                city.food = max(0, city.food)
                city.population = max(0, city.population)
            else:
                self._city_system.update_city(city, generals=self.generals)
            result["cities_updated"] += 1

        # 相位钩子：资源产出之后（影响力扩散已迁移为此相位的钩子，见文件底部注册）
        self._run_phase_hooks(TurnPhase.AFTER_PRODUCTION, result)

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

        # 2.5 收容"走投无路"的撤退军队（v4.0）
        self._sweep_stranded_armies()

        # 相位钩子：行军之后（人设代价已迁移为此相位的钩子，见文件底部注册）
        self._run_phase_hooks(TurnPhase.AFTER_MOVEMENT, result)

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

            # 设置建国/称帝士气加成
            if self._kingdom_system is not None:
                ctx.attacker_morale_bonus = self._kingdom_system.get_morale_bonus(ctx.attacker_faction)
                ctx.defender_morale_bonus = self._kingdom_system.get_morale_bonus(ctx.defender_faction)

            # 🔴 战斗快照：必须在 _apply_battle_result **删除攻方军队之前**捕获
            # （攻方胜利会把 attacker_armies 从 self.armies 移除）。
            # attacker_from_cities 用 sorted(set(...)) 去重+排序，避免集合迭代序非确定性。
            attacker_from_cities = sorted({
                self.armies[a_id].from_city
                for a_id in ctx.attacker_armies
                if a_id in self.armies
            })
            lead_general_id = next(
                (self.armies[a_id].general_id
                 for a_id in ctx.attacker_armies if a_id in self.armies),
                "",
            )
            attacker_general_name = (
                self.generals[lead_general_id].name
                if lead_general_id in self.generals else ""
            )
            wall_hp_before = ctx.wall_hp
            attacker_soldiers_snapshot = ctx.attacker_initial_soldiers
            defender_soldiers_snapshot = ctx.defender_initial_soldiers

            battle_result = self._battle_resolver.resolve_battle(ctx)
            self._apply_battle_result(ctx, battle_result)

            # 事件总线：战斗结束广播（每场一次；含战斗可见性所需字段）
            self.events.publish(BattleEndedEvent(
                battle_id=ctx.battle_id,
                result=battle_result.result.value if battle_result.result else "",
                attacker_faction=ctx.attacker_faction,
                defender_faction=ctx.defender_faction,
                attacker_casualties=battle_result.attacker_casualties,
                defender_casualties=battle_result.defender_casualties,
                captured_city=battle_result.captured_city,
                turn=self.turn,
                defender_city=ctx.defender_city,
                attacker_from_cities=attacker_from_cities,
                attacker_soldiers=attacker_soldiers_snapshot,
                defender_soldiers=defender_soldiers_snapshot,
                wall_hp_before=wall_hp_before,
                wall_hp_after=ctx.wall_hp,
                attacker_general_name=attacker_general_name,
            ))

            # 回写城墙耐久与守军数量（攻城战中可能被损坏/消灭）
            if defender_city and ctx.wall_hp >= 0:
                defender_city.wall_hp = ctx.wall_hp
                defender_city.garrison = max(0, ctx.defender_total_soldiers)

            result["battles_fought"] += 1

        # 5. 清理已消灭的军队
        self._cleanup_dead_armies()

        # 相位钩子：战斗结算之后
        self._run_phase_hooks(TurnPhase.AFTER_RESOLUTION, result)

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

        # 相位钩子：回合结束（写日志/广播回合结束之前）
        self._run_phase_hooks(TurnPhase.TURN_END, result)

        # 记录日志
        self.turn_logs.append(TurnLog(
            turn=result["turn"],
            events=[result],
        ))

        # 事件总线：回合结束广播（放在最后——此时 turn 已递增、日志已落，
        # 使订阅者拿到的 self.engine.turn 与「原先在 process_turn 之后手写」一致）。
        self.events.publish(TurnEndedEvent(
            turn=result["turn"],
            summary={
                "battles_fought": result["battles_fought"],
                "armies_moved": result["armies_moved"],
                "cities_updated": result["cities_updated"],
                "game_over": self.game_over,
                "winner": self.winner,
            },
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
                old_faction = city.faction
                city.faction = ctx.attacker_faction
                # 占领后民心下降
                city.morale = max(20, city.morale - 20)

                # 事件总线：城市被占领广播
                self.events.publish(CityCapturedEvent(
                    city_id=city.id,
                    city_name=city.name,
                    attacker_faction=ctx.attacker_faction,
                    defender_faction=old_faction,
                    turn=self.turn,
                ))

                # v4.0：失城打击 —— 原主其余将领忠诚度下降。
                # 这让忠诚度不再是一个恒等于初始值的静止数字：
                # 局势恶化会真实动摇人心，低忠诚将领被俘后更容易投降，
                # 从而把「失城 → 人心浮动 → 将领投降 → 敌方得将」串成闭环。
                if old_faction != ctx.attacker_faction:
                    for g in self.generals.values():
                        if g.faction == old_faction and not g.is_captured:
                            g.loyalty = max(
                                0, g.loyalty - CITY_LOSS_LOYALTY_PENALTY
                            )

                # [领地 2026-10-01] "占城即夺地"：占领后全量重划领地。
                # 该城已成为新势力的源点，重划后其周边地块自然归入新势力，边界自动更新。
                self._expand_territories()

                # 外交影响：占领城市降低信任度，双方变为交战状态
                if self._diplomacy_relation_system is not None and old_faction != ctx.attacker_faction:
                    self._diplomacy_relation_system.on_city_captured(ctx.attacker_faction, old_faction)
                    self._diplomacy_relation_system.set_status(
                        ctx.attacker_faction, old_faction,
                        DiplomaticStatus.WAR, turn=self.turn
                    )

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
                        # v4.0：掉头回城（含重算回程路径），不再是"只对调 from/to"
                        self._redirect_army_home(army)

        elif result.result in (BattleResultType.DRAW, BattleResultType.RETREAT):
            # 平局/撤退
            for army_id in ctx.attacker_armies:
                if army_id in self.armies:
                    army = self.armies[army_id]
                    initial_total = max(ctx.attacker_initial_soldiers, 1)
                    loss_ratio = result.attacker_casualties / initial_total
                    army.soldiers = max(0, int(army.soldiers * (1 - loss_ratio)))
                    if army.soldiers > 0:
                        # v4.0：原实现只把状态置为 RETREATING，既不换向也不重算路径，
                        #       军队会沿去程路径继续走到敌方城下，然后永久卡死。
                        self._redirect_army_home(army)

        # 清理该城市的围城状态
        if defender_city is not None:
            defender_city.is_besieged = False
            defender_city.besieging_armies = []

        # 清理俘虏的将领
        # v4.0：这里才真正被执行（此前 captured_generals 恒为空，见 battle_resolver 注释）
        captured_city_id = result.captured_city or ctx.defender_city
        captured_city = self.cities.get(captured_city_id) if captured_city_id else None
        for gen_id in result.captured_generals:
            if gen_id not in self.generals:
                continue
            gen = self.generals[gen_id]
            capture_result = self._general_system.process_capture(
                gen, captor_faction=ctx.attacker_faction, turn=self.turn,
            )
            if capture_result.surrendered:
                # 归顺：改属攻方（process_capture 已改 faction）并留在这座城里
                if captured_city is not None:
                    gen.location = captured_city.id
                    if gen_id not in captured_city.generals:
                        captured_city.generals.append(gen_id)
            else:
                # 宁死不降：转入关押，不再担任该城守将
                if captured_city is not None and gen_id in captured_city.generals:
                    captured_city.generals.remove(gen_id)

    def _apply_nature_strain(self, result: Dict[str, Any]) -> None:
        """违背君主本性的抉择带来轻微、可逆的人心代价（v4.0）

        ## 为什么这么设计（回应「人设是否限制 LLM 智能」）

        人设在这里是**倾向**，不是枷锁。LLM 完全可以违背本性去下好棋——
        世界只回馈一点点代价。这个代价刻意设计得很轻且完全可逆，
        目的是让"像不像自己"成为一个**真实的决策维度**，而不是
        强迫模型去演角色的紧箍咒：违背一次损失 1 点民心，
        而 1 点民心远不足以让一步好棋变坏棋。

        代价只落在「民心」上，**不动将领忠诚度** —— 因为忠诚度会直接
        改变战斗力，那会变成"限制智能"；民心只影响产出，属于"呈现代价"。

        当前只覆盖两条语义最清晰的规则：
        - cautious（谨慎型君主）主动进攻 → 文官集团不满
        - aggressive（激进型君主）整回合无任何军事行动 → 主战派躁动

        Args:
            result: 回合结果字典（会写入 nature_strain 统计）
        """
        actions_by_faction: Dict[str, set] = {}
        for faction, cmd_type in self._turn_actions:
            actions_by_faction.setdefault(faction, set()).add(cmd_type)

        strained = 0
        for faction, actions in actions_by_faction.items():
            style = FACTION_PERSONALITY.get(faction, {}).get("style", "balanced")
            violated = False

            if style == "cautious" and "attack" in actions:
                violated = True
            elif style == "aggressive" and not (actions & {"attack", "recruit", "develop"}):
                violated = True

            if not violated:
                continue

            for city in self.cities.values():
                if city.faction == faction:
                    city.morale = max(0, city.morale - NATURE_STRAIN_MORALE_PENALTY)
            strained += 1

        result["nature_strain"] = strained

    def _redirect_army_home(self, army: Army) -> None:
        """让战败/撤退的军队掉头撤回出发城市（v4.0 新机制）

        🔴 为什么必须有这个函数：
        原实现在战斗失败时只做 `army.from_city, army.to_city = army.to_city, army.from_city`
        （DRAW/RETREAT 分支甚至连对调都没有），而 **path_hexes 仍是去程路径**：
          1. 军队"撤退"时继续沿去程路径朝敌方城市推进；
          2. 走完路径后因 `_process_hex_movement` 的到达判定只对 MARCHING 生效，
             永远不触发 `_handle_arrival` → 既不能入城归建、也不会被清理；
          3. 于是变成"野外僵尸军队"：不参战、不消失，每回合只能靠断粮
             （士气 -10 → 溃散 -10% 兵力）慢慢掉兵，直至 soldiers=0 凭空蒸发。
        实测（exp11，5 局 48 回合）：155 场战斗中 35 场 RETREAT + 8 场守方胜，
        这些攻方残部全部进入僵尸状态，兵力白白蒸发 → 攻守双方实力同时被消耗，
        这就是"12 方谁也打不完"的直接原因之一。

        本函数做三件事：
          1. 语义换向：to_city ← 自家出发城；
          2. **以当前位置为起点重算回程路径**（这是原实现缺失的关键一步）；
          3. 若回程无路可走（孤岛/城市已易主），残部直接归建，绝不留成僵尸。

        Args:
            army: 需要撤回的军队（会被就地修改）
        """
        home_city = self.cities.get(army.from_city)
        if home_city is None or home_city.faction != army.faction:
            # 出发城已丢失：退回目标城（若仍是己方），否则保持撤退由断粮自然消耗
            alt = self.cities.get(army.to_city)
            if alt is not None and alt.faction == army.faction:
                home_city = alt
            else:
                army.status = ArmyStatus.RETREATING
                return

        # 语义互换：from = 当前所在（原目标城），to = 自家城
        army.from_city, army.to_city = army.to_city, home_city.id

        if self.hex_map is not None:
            start = army.current_hex or home_city.position
            new_path = self.hex_map.find_path(start, home_city.position)
            if new_path:
                army.path_hexes = new_path
                army.path_index = 0
                army.current_hex = new_path[0]
                army.total_distance = max(1, len(new_path) - 1)
                army.progress = 0.0
            else:
                # 无可行回程路径：残部直接归建，避免野外蒸发
                self._disband_army_into_city(army, home_city)
                return

        army.status = ArmyStatus.RETREATING

    def _sweep_stranded_armies(self) -> None:
        """收容已抵达路径终点却无处可去的撤退军队（v4.0）

        🔴 为什么需要：撤退军的目标城可能在撤退途中被敌方占领
        （`_redirect_army_home` 重算路径时 home_city 还属于自己），
        等它走到终点，`_handle_arrival` 发现"撤退 + 非友方城"只能不处理，
        军队便永久停在 progress=1.0 —— 又是一支野外僵尸。

        实测（exp12，5 局 48 回合）：仅靠 `_redirect_army_home` 仍有 6 支军队滞留，
        其中 4 支是 progress=1.0 的 RETREATING 军队，正是本方法要收容的对象。

        策略：抵达终点且目标已非己方城 → 残部直接归建最近的己方城市
        （走不动就不走了，但兵力绝不凭空蒸发）；若该势力已无城 → 军队就地解散。
        """
        for army in list(self.armies.values()):
            if army.status != ArmyStatus.RETREATING:
                continue

            # 是否已抵达路径终点
            arrived = army.progress >= 1.0 or (
                bool(army.path_hexes)
                and army.path_index >= len(army.path_hexes) - 1
            )
            if not arrived:
                continue

            target = self.cities.get(army.to_city)
            if target is not None and target.faction == army.faction:
                # 仍是己方城：交给 _handle_arrival 走正常入城流程
                continue

            own_cities = [c for c in self.cities.values() if c.faction == army.faction]
            if not own_cities:
                # 势力已无城可回 → 残部就地解散（将领下野）
                gen = self.generals.get(army.general_id)
                if gen is not None:
                    gen.is_captured = False
                army.soldiers = 0
                self.armies.pop(army.id, None)
                continue

            self._disband_army_into_city(army, self._nearest_city(army, own_cities))

    def _nearest_city(self, army: Army, candidates: List[City]) -> City:
        """按六角格直线距离找最近的候选城市

        刻意不寻路：本方法在每回合的军队巡检里调用，若逐城跑 A* 会带来
        不必要的开销，而"最近的己方城"用直线距离足够（只用于残部归建）。

        Args:
            army: 军队（用其当前所在格为起点）
            candidates: 候选城市列表（应为非空）

        Returns:
            距离最近的城市
        """
        start = army.current_hex
        if start is None:
            return candidates[0]

        def hex_distance(city: City) -> int:
            dq = abs(start.q - city.position.q)
            dr = abs(start.r - city.position.r)
            ds = abs((-start.q - start.r) - (-city.position.q - city.position.r))
            return max(dq, dr, ds)

        return min(candidates, key=hex_distance)

    def _disband_army_into_city(self, army: Army, city: City) -> None:
        """把军队残部并入城市守军并解散该军队（将领回城）

        用于撤退军队无法走回城市时的兜底，保证兵力不凭空消失。

        Args:
            army: 要解散的军队
            city: 接收残部的己方城市
        """
        cap = city.level * GARRISON_CAP_PER_LEVEL
        city.garrison = min(city.garrison + army.soldiers, cap)
        gen = self.generals.get(army.general_id)
        if gen is not None:
            gen.location = city.id
        army.soldiers = 0
        self.armies.pop(army.id, None)

    def _cleanup_dead_armies(self) -> None:
        """清理已消灭的军队"""
        dead_army_ids = [
            aid for aid, army in self.armies.items()
            if army.soldiers <= 0
        ]
        for aid in dead_army_ids:
            army = self.armies[aid]
            # 将领返回己方城市。
            # 🔴 原实现直接 `gen.location = army.from_city`，但撤退时 from_city
            # 已被互换为**敌方城市**，会把将领"送进"敌人城里（下回合该城若被
            # 己方攻击，这名将领就会被当作守方将领处理）。改为优先落到己方城。
            gen = self.generals.get(army.general_id)
            if gen:
                for cid in (army.from_city, army.to_city):
                    c = self.cities.get(cid)
                    if c is not None and c.faction == army.faction:
                        gen.location = c.id
                        break
                else:
                    fallback = next(
                        (c.id for c in self.cities.values() if c.faction == army.faction),
                        None,
                    )
                    if fallback is not None:
                        gen.location = fallback
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
            if len(winners) == 1:
                self.winner = winners[0]
            else:
                # 并列最多城 → 次级指标决胜，保证唯一胜者（确定性）
                def tiebreak(f):
                    fac_cities = [c for c in self.cities.values() if c.faction == f]
                    garri = sum(c.garrison for c in fac_cities)
                    pop = sum(c.population for c in fac_cities)
                    gold = sum(c.gold for c in fac_cities)
                    return (garri, pop, gold, f)
                self.winner = sorted(
                    sorted(winners, key=lambda f: f),            # ④ faction 字典序（稳定兜底）
                    key=lambda f: tiebreak(f)[:3], reverse=True  # ① 守军 ② 人口 ③ 总gold 降序
                )[0]

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
        # 己方城市相邻城市集合（用于可见性判断）
        neighbor_city_ids: set = set()
        for c in own_cities:
            neighbor_city_ids.update(c.neighbors)
        # 己方城市 hex 坐标集合（用于 hex 距离判断）
        own_city_hexes: set = set()
        if self.hex_map is not None:
            for c in own_cities:
                own_city_hexes.add(c.position)

        for army in self.armies.values():
            if army.faction == faction or army.soldiers <= 0:
                continue
            visible = False

            # 规则1: 同一 hex 上相遇必定可见
            if army.current_hex is not None and army.current_hex in own_army_hexes:
                visible = True
            # 规则2: 目标或来源为己方城市
            elif army.to_city in own_city_ids or army.from_city in own_city_ids:
                visible = True
            # 规则3: 正在围城己方相邻城市的军队（敌方围城己方邻居，必然可见）
            elif army.status == ArmyStatus.BESIEGING and army.to_city in neighbor_city_ids:
                visible = True
            # 规则4: 来源或目标为己方相邻城市（经过己方势力范围的军队）
            elif army.to_city in neighbor_city_ids or army.from_city in neighbor_city_ids:
                visible = True
            # 规则5: Hex 距离判断（如果 hex_map 可用，在己方城市 hex 距离 ≤2 格内的军队可见）
            elif self.hex_map is not None and army.current_hex is not None and own_city_hexes:
                for own_hex in own_city_hexes:
                    dq = abs(own_hex.q - army.current_hex.q)
                    dr = abs(own_hex.r - army.current_hex.r)
                    ds = abs((-own_hex.q - own_hex.r) - (-army.current_hex.q - army.current_hex.r))
                    if max(dq, dr, ds) <= 2:
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

        # 外交关系
        faction_relations = []
        if self._diplomacy_relation_system is not None:
            faction_relations = self._diplomacy_relation_system.get_faction_relations(faction)

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
            faction_relations=faction_relations,
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
            max_turns=self.max_turns,
            year=self.year,
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
        """从快照恢复游戏状态 —— 🔴 **本方法当前不可用，调用即抛 `NotImplementedError`**。

        为什么不让它"尽力而为"
        ----------------------
        原实现只重建了 `self.rng` 与 `self.map`，**未恢复**：

        | 缺失项 | 后果 |
        |---|---|
        | `hex_map` | 恢复后为 `None` —— 领地/地块产出、影响力扩散全部失效 |
        | `season` | 恢复为 `SPRING`（季节影响产出） |
        | `_diplomacy_relation_system` | 恢复后为 `None` —— 外交操作在 `None` 上报错 |
        | `_kingdom_system` | 未重建 —— 建国/称帝加成失效 |
        | 各子系统缓存、`loyalty_baseline` | 未重建 |

        🔴 **最危险的是它不报错**：2026-10-03 实测（`tests/balance/exp20_snapshot_restore.py`）：

            原引擎：turn=13  hex_map=已建  season=WINTER  外交关系=69 条
            恢复后：turn=13  hex_map=None  season=SPRING  外交关系=None
            继续推进 12 回合 → "成功"，turn=25
            但后台抛 AttributeError: 'NoneType' object has no attribute 'set_status'
            （被引擎的命令级 try/except 吞掉，表面看一切正常）

        即：它会造出一个**看起来还行、实际静默降级**的引擎。按本项目
        「拒绝静默兜底」的原则，宁可显式不可用，也不留这个陷阱。

        为什么不能"补齐"
        ----------------
        **`GameState` 快照格式缺字段**（2026-10-03 实读 + 实跑）。快照只有 11 个字段：

            turn / max_turns / year / seed / game_over / winner /
            cities / armies / generals / messages / turn_logs

        两样关键东西**都不在**：

        1. **没有任何 hex 地块/领地字段**。而 `hex_map` 由 `init_game(data)`
           依赖**原始地图数据**构建 —— 光凭一份 `GameState` 造不出来。
        2. **没有外交关系字段**，恢复后外交全丢。
           ⚠️ 易混点：`faction_relations` 属于 **`GameObservation`**（喂给 AI 的
           观察），**不是** `GameState`（存档快照）。我第一版判断就把它当成
           快照字段、写成"字段存在但生产端没填"，被实跑纠正 ——
           两者务必分清。

        所以这不是「接线漏了」，而是**存档格式不完整**：要做存档/读档，
        必须先扩 `GameState`，属功能开发，不是修 bug。

        要做的话，建议路径（避免再做半个）
        ----------------------------------
        1. 扩快照格式：加外交关系、加地图/领地（或改存 `seed + data 摘要`
           以便重建 `hex_map`）；
        2. `load_state_snapshot(state, data)` 先走 `init_game(data)` 把地图与
           全部子系统按同一路径建好，再覆盖被存档的实体；
        3. 补一个**等价性验收**：『恢复后继续跑 N 回合』 必须与
           『不中断跑 N 回合』逐回合指纹一致 —— 否则读档会改变对局结果。

        Args:
            state: 之前保存的游戏状态（当前实现不接受）

        Raises:
            NotImplementedError: 总是抛出。原因见上。
        """
        raise NotImplementedError(
            "load_state_snapshot 当前不可用："
            "GameState 快照格式缺两类关键字段（无地图/领地、无外交关系），"
            "且原实现未恢复 hex_map / season / 外交系统，会静默产生降级引擎。"
            "详见本方法 docstring 与 tests/balance/exp20_snapshot_restore.py。"
            "要做存档/读档请先扩 GameState 格式（属功能开发，不是修 bug）。"
        )

    def _load_state_snapshot_legacy(self, state: GameState) -> None:  # pragma: no cover
        """【已停用】原实现留档，供将来做存档功能时参考起点。

        🔴 不要直接调用 —— 它只恢复部分状态，会产出静默降级的引擎
        （见 `load_state_snapshot` 的 docstring）。
        """
        self.turn = state.turn
        self.max_turns = state.max_turns
        self.year = state.year
        self.seed = state.seed
        self.game_over = state.game_over
        self.winner = state.winner
        self.cities = state.cities
        self.armies = state.armies
        self.generals = state.generals
        self._messages = state.messages
        self.turn_logs = state.turn_logs

        # 重建子系统（⚠️ 不全 —— 缺 hex_map / season / 外交 / 建国 / 各子系统）
        self.rng = GameRandom(self.seed)
        self.map = MapSystem()
        for city in self.cities.values():
            self.map.add_city(city)


# ============================================================
# 内置命令注册（命令类型 → 期望命令类 → 处理器方法）
# ============================================================
# 顺序即注册顺序，确定。新增内置命令在此加一行即可（分发逻辑无需改动）；
# 外部/mod 命令调用 game.command_registry.register_command(...) 另行登记。
register_command("develop", DevelopCommand, GameEngine._execute_develop)
register_command("recruit", RecruitCommand, GameEngine._execute_recruit)
register_command("attack", AttackCommand, GameEngine._execute_attack)
register_command("reward", RewardCommand, GameEngine._execute_reward)
register_command("explore", ExploreCommand, GameEngine._execute_explore)
register_command("message", MessageCommand, GameEngine._execute_message)
register_command("rumor", RumorCommand, GameEngine._execute_rumor)
register_command(
    "propose_alliance", ProposeAllianceCommand, GameEngine._execute_propose_alliance
)
register_command("declare_war", DeclareWarCommand, GameEngine._execute_declare_war)


# ============================================================
# 内置回合相位钩子注册
# ============================================================
# 顺序即 (priority, 注册序)，确定。新增「每回合结算」机制在此注册即可，
# process_turn 本体无需改动（见 game/turn_phase.py、ADR-0006）。


def _hook_spread_influence(engine: "GameEngine", result: Dict[str, Any]) -> None:
    """相位钩子（after_production）：扩散影响力。

    自 process_turn 内联逻辑迁移而来，位置与语义不变（资源产出之后、行军之前）。
    """
    if engine._influence_system is not None and engine.hex_map is not None:
        engine._influence_system.spread_influence(
            list(engine.cities.values()), engine.hex_map
        )


register_phase_hook(
    TurnPhase.AFTER_PRODUCTION, _hook_spread_influence,
    priority=100, name="influence_spread",
)


def _hook_nature_strain(engine: "GameEngine", result: Dict[str, Any]) -> None:
    """相位钩子（after_movement）：结算「人设代价」。

    自 process_turn 内联迁移而来，位置不变（行军/收容撤退军之后、忠诚衰减之前）。
    """
    engine._apply_nature_strain(result)


register_phase_hook(
    TurnPhase.AFTER_MOVEMENT, _hook_nature_strain,
    priority=100, name="nature_strain",
)


def _hook_city_morale(engine: "GameEngine", result: Dict[str, Any]) -> None:
    """相位钩子（after_movement）：城市的民心自然变化。

    承载 `CitySystem._calculate_morale_change` 的全部四条自然规则：
      1. 被围困        -3 / 回合
      2. 粮草为 0      -5 / 回合
      3. 粮草充足盈余  +1 / 回合
      4. 民心向 50 回归（>70 微降、<30 微升）—— **全局唯一的自校正项**

    🔴 为什么必须迁到这里（历史缺陷，务必保留本注释）
    -------------------------------------------------
    本机制原在 `CitySystem.update_city` 内，而 `update_city` **只在 `process_turn`
    的资源产出段的「无六角地图」else 分支被调用**（生产恒有 hex_map → 恒走 if 分支
    走 `calculate_resources`）→ 整段逻辑从未执行。`tests/balance/
    exp18_siege_morale_reachability.py`（原名 exp16）实测：修复前 5 局 × 48 回合
    `_calculate_morale_change` 调用数 = **0**；修复后 = 城市数 × 回合数（实测 7440）。
    （同类缺陷还有 `defender_generals`，见 docs/design/modding-guide.md §4 第 5 条。）

    🔴 为什么是 AFTER_MOVEMENT 这个相位
    -----------------------------------
    `is_besieged` 在**行军相位**被写入（`game/battle/army_movement.py:364`，军队抵达敌城），
    在**战斗结算**被清 0（`_apply_battle_result` 内 `defender_city.is_besieged = False`）。
    只有夹在两者之间的相位它才为真 —— 这正是 AFTER_MOVEMENT
    （`tests/balance/exp17_siege_flag_leak.py`（原名 exp15）阳性对照实测该相位峰值有 5–6 座城为真）。
    若放在资源产出相位（更早），则恒为 False。

    遍历按 `city.id` 升序 —— 确定性，绝不依赖 set/dict 迭代序（ADR-0002）。
    """
    if engine._city_system is None:
        return
    for city in sorted(engine.cities.values(), key=lambda c: c.id):
        change = engine._city_system._calculate_morale_change(city)
        if change:
            city.morale = max(0, min(100, city.morale + change))


register_phase_hook(
    TurnPhase.AFTER_MOVEMENT, _hook_city_morale,
    priority=100, name="city_morale",
)

