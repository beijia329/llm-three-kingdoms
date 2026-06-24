"""核心数据模型

本文件定义游戏中所有核心数据结构，严格遵循 docs/design/data-models.md。
所有模型使用 Pydantic 进行数据校验。
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict

from game.hex_grid import HexCoord


# ============================================================
# 基础枚举
# ============================================================

class Faction(str, Enum):
    """势力枚举（184年剧本，12方诸侯）"""

    HAN = "han"
    ZHANGJIAO = "zhangjiao"
    DONGZHUO = "dongzhuo"
    YUANSHAO = "yuanshao"
    CAOCAO = "caocao"
    LIUBEI = "liubei"
    SUNJIAN = "sunjian"
    LIUBIAO = "liubiao"
    LIUYAN = "liuyan"
    GONGSUNZAN = "gongsunzan"
    MATENG = "mateng"
    YUANSHU = "yuanshu"


class ArmyStatus(str, Enum):
    """军队状态枚举"""

    MARCHING = "marching"
    BESIEGING = "besieging"
    RETREATING = "retreating"
    GARRISONED = "garrisoned"


class BattleType(str, Enum):
    """战斗类型"""

    SIEGE = "siege"
    FIELD = "field"
    ENCOUNTER = "encounter"


class BattleResultType(str, Enum):
    """战斗结果枚举"""

    ATTACKER_WIN = "attacker_win"
    DEFENDER_WIN = "defender_win"
    DRAW = "draw"
    RETREAT = "retreat"


class BattlePhase(str, Enum):
    """战斗阶段"""

    START = "start"
    SIEGE = "siege"  # 围城阶段
    STREET = "street"  # 巷战阶段
    ENDED = "ended"


class DiplomaticStatus(str, Enum):
    """外交状态枚举"""

    WAR = "war"           # 交战
    NEUTRAL = "neutral"   # 中立
    ALLIANCE = "alliance" # 同盟
    TRUCE = "truce"       # 停战


class FactionRelation(BaseModel):
    """势力关系数据模型

    代表两个势力之间的外交关系状态。
    """

    faction_a: str = Field(description="势力A")
    faction_b: str = Field(description="势力B")
    status: DiplomaticStatus = Field(
        default=DiplomaticStatus.NEUTRAL, description="外交状态"
    )
    trust: int = Field(
        default=50, ge=0, le=100, description="信任度 0-100"
    )
    truce_end_turn: Optional[int] = Field(
        default=None, description="停战结束回合"
    )
    alliance_end_turn: Optional[int] = Field(
        default=None, description="同盟结束回合"
    )


# ============================================================
# 城市模型
# ============================================================

class City(BaseModel):
    """城市数据模型

    代表地图上的一个城市，包含资源、军事、人口等信息。
    """

    # 基础信息
    id: str = Field(description="城市唯一ID")
    name: str = Field(description="城市名称")
    faction: str = Field(description="所属势力")
    level: int = Field(ge=1, le=5, description="城市等级 1-5")

    # 城墙
    wall_hp: int = Field(ge=0, description="城墙当前耐久")
    wall_max_hp: int = Field(gt=0, description="城墙最大耐久")

    # 资源
    gold: int = Field(ge=0, description="金钱")
    food: int = Field(ge=0, description="粮草")
    population: int = Field(ge=0, description="人口")
    morale: int = Field(ge=0, le=100, description="民心 0-100")

    # 发展加成
    economic_bonus: int = Field(default=0, ge=0, description="经济发展带来的每回合金钱产出加成")

    # 军事
    garrison: int = Field(ge=0, description="守军数量")

    # 将领
    generals: List[str] = Field(default_factory=list, description="驻守将领ID列表")

    # 州郡
    province_id: Optional[str] = Field(default=None, description="所属州ID")

    # 地图
    position: HexCoord = Field(description="六角格坐标")
    neighbors: List[str] = Field(default_factory=list, description="相邻城市ID列表")

    # 状态
    is_besieged: bool = Field(default=False, description="是否被围困")
    besieging_armies: List[str] = Field(default_factory=list, description="围城部队ID列表")

    model_config = ConfigDict(arbitrary_types_allowed=True)


class Province(BaseModel):
    """州数据模型

    代表东汉十三州之一，下辖若干城市。
    """

    id: str = Field(description="州唯一ID")
    name: str = Field(description="州名称")
    capital_city_id: Optional[str] = Field(default=None, description="州治城市ID")
    color: str = Field(default="#888888", description="州渲染颜色")
    description: str = Field(default="", description="州简介")
    cities: List[str] = Field(default_factory=list, description="下辖城市ID列表")


class CityInfo(BaseModel):
    """城市简略信息（用于信息迷雾）

    对敌方城市的有限信息视图，比 City 包含更少的字段。
    """

    id: str = Field(description="城市唯一ID")
    name: str = Field(description="城市名称")
    faction: str = Field(description="所属势力")
    level: int = Field(ge=1, le=5, description="城市等级 1-5")
    is_besieged: bool = Field(default=False, description="是否被围困")
    province_id: Optional[str] = Field(default=None, description="所属州ID")

    # 以下字段仅在相邻或可见时填充
    garrison: Optional[int] = Field(None, description="守军数量（仅相邻城市可见）")
    morale: Optional[int] = Field(None, description="民心（仅相邻城市可见）")
    wall_hp: Optional[int] = Field(None, description="城墙耐久（仅相邻城市可见）")


# ============================================================
# 军队模型
# ============================================================

class Army(BaseModel):
    """军队数据模型

    代表一支正在行军、围城或驻守的部队。
    """

    id: str = Field(description="军队唯一ID")
    faction: str = Field(description="所属势力")

    # 将领
    general_id: str = Field(description="主将ID")
    second_general_id: Optional[str] = Field(None, description="副将ID")

    # 兵力
    soldiers: int = Field(ge=0, description="士兵数量")
    casualties: int = Field(default=0, description="累计伤亡")

    # 补给
    food: int = Field(ge=0, description="携带粮草")
    food_consumption_per_turn: int = Field(description="每回合粮草消耗")

    # 状态
    morale: int = Field(ge=0, le=100, default=80, description="部队士气")
    status: ArmyStatus = Field(description="部队状态")

    # 位置
    from_city: str = Field(description="出发城市")
    to_city: str = Field(description="目标城市")
    progress: float = Field(ge=0, le=1, default=0, description="行军进度 0-1")
    total_distance: int = Field(description="总距离（回合数）")

    # 战斗
    is_in_battle: bool = Field(default=False, description="是否正在战斗")
    current_battle_id: Optional[str] = Field(None, description="当前战斗ID")

    # 六角格移动
    current_hex: Optional[HexCoord] = Field(
        default=None, description="当前所在六角格"
    )
    path_hexes: List[HexCoord] = Field(
        default_factory=list, description="行军路径（HexCoord 列表）"
    )
    path_index: int = Field(default=0, description="当前路径索引")


class ArmyInfo(BaseModel):
    """军队简略信息（用于信息迷雾）"""

    id: str = Field(description="军队唯一ID")
    faction: str = Field(description="所属势力")
    status: ArmyStatus = Field(description="部队状态")
    general_id: str = Field(description="主将ID")

    # 仅大致可见
    soldiers_estimate: Optional[str] = Field(None, description="兵力估算（many/normal/few）")
    morale_estimate: Optional[str] = Field(None, description="士气估算（high/normal/low）")


# ============================================================
# 将领模型
# ============================================================

class General(BaseModel):
    """将领数据模型

    代表一个武将，拥有统帅、政治、勇武、智力四维属性。
    """

    id: str = Field(description="将领唯一ID")
    name: str = Field(description="将领姓名")
    faction: str = Field(description="所属势力")

    # 属性
    command: int = Field(ge=1, le=100, description="统帅 影响战斗")
    politics: int = Field(ge=1, le=100, description="政治 影响治理")
    bravery: int = Field(ge=1, le=100, description="勇武 影响单挑")
    intelligence: int = Field(ge=1, le=100, description="智力 影响计谋")

    # 忠诚度
    loyalty: int = Field(ge=0, le=100, default=70, description="忠诚度")
    loyalty_decay_rate: float = Field(default=0.5, description="每回合忠诚衰减")

    # 状态
    location: str = Field(description="所在位置: 城市ID/军队ID")
    is_captured: bool = Field(default=False, description="是否被俘")
    captured_turn: int = Field(default=-1, description="被俘回合")
    captor_faction: Optional[str] = Field(None, description="俘虏方")

    # 状态效果
    is_injured: bool = Field(default=False, description="是否受伤")
    injured_turns_remaining: int = Field(default=0, description="受伤剩余回合")

    # 性格
    personality: str = Field(default="balanced", description="性格类型")


# ============================================================
# 命令模型
# ============================================================

class Command(BaseModel):
    """命令基类

    代表一个玩家的行动指令。所有具体命令通过 type 字段区分。
    """

    type: str = Field(description="命令类型")
    faction: str = Field(description="执行势力")
    turn: int = Field(description="执行回合")
    params: Dict[str, Any] = Field(default_factory=dict, description="命令参数")


class DevelopCommand(Command):
    """发展城市命令"""

    type: str = Field(default="develop", description="命令类型")
    city: str = Field(description="目标城市ID")
    develop_type: str = Field(description="发展类型: economy/military/culture")


class RecruitCommand(Command):
    """征兵命令"""

    type: str = Field(default="recruit", description="命令类型")
    city: str = Field(description="目标城市ID")
    troops: int = Field(gt=0, description="征兵数量")


class AttackCommand(Command):
    """进攻命令"""

    type: str = Field(default="attack", description="命令类型")
    from_city: str = Field(description="出发城市")
    to_city: str = Field(description="目标城市")
    troops: int = Field(gt=0, description="派遣兵力")
    general: str = Field(description="主将ID")


class RewardCommand(Command):
    """赏赐将领命令"""

    type: str = Field(default="reward", description="命令类型")
    general: str = Field(description="将领ID")
    gold: int = Field(gt=0, description="赏赐金额")


class ExploreCommand(Command):
    """探索人才命令"""

    type: str = Field(default="explore", description="命令类型")
    city: str = Field(description="探索城市")
    general: Optional[str] = Field(None, description="执行探索的将领ID")


class MessageCommand(Command):
    """发送外交消息命令"""

    type: str = Field(default="message", description="命令类型")
    to: str = Field(description="目标势力")
    content: str = Field(description="消息内容")


class RumorCommand(Command):
    """散布流言命令"""

    type: str = Field(default="rumor", description="命令类型")
    city: str = Field(description="流言目标城市")
    target_general: Optional[str] = Field(None, description="流言目标将领")
    spy_general: Optional[str] = Field(None, description="执行间谍的将领")


class ProposeAllianceCommand(Command):
    """提出同盟命令"""

    type: str = Field(default="propose_alliance", description="命令类型")
    to: str = Field(description="目标势力")
    duration: int = Field(default=12, description="同盟持续回合数")


class DeclareWarCommand(Command):
    """宣战命令"""

    type: str = Field(default="declare_war", description="命令类型")
    to: str = Field(description="目标势力")
    reason: str = Field(default="", description="宣战理由")


# ============================================================
# 外交模型
# ============================================================

class DiplomacyMessage(BaseModel):
    """外交消息"""

    id: str = Field(description="消息唯一ID")
    from_faction: str = Field(description="发送方")
    to_faction: str = Field(description="接收方")
    content: str = Field(description="消息内容")
    turn: int = Field(description="发送回合")
    is_read: bool = Field(default=False, description="是否已读")


# ============================================================
# 观察数据模型
# ============================================================

class GameObservation(BaseModel):
    """玩家观察数据

    提供给玩家（包括LLM）的游戏状态视图。
    包含信息迷雾：己方信息完整，敌方信息有限。
    """

    # 基本信息
    faction: str = Field(description="当前玩家势力")
    turn: int = Field(description="当前回合")
    max_turns: int = Field(description="最大回合数")

    # 己方信息（完整）
    own_cities: List[City] = Field(description="己方所有城市（完整信息）")
    own_armies: List[Army] = Field(description="己方所有军队")
    own_generals: List[General] = Field(description="己方所有将领")

    # 敌方信息（不完整，有迷雾）
    known_cities: List[CityInfo] = Field(description="已知的敌方城市")
    visible_armies: List[ArmyInfo] = Field(description="可见的敌方军队")

    # 地图
    map_topology: Dict[str, List[str]] = Field(description="地图拓扑")

    # 外交
    received_messages: List[DiplomacyMessage] = Field(
        default_factory=list, description="收到的消息"
    )
    sent_messages: List[DiplomacyMessage] = Field(
        default_factory=list, description="已发送的消息"
    )
    faction_relations: List[FactionRelation] = Field(
        default_factory=list, description="势力外交关系"
    )

    # 历史事件（最近5回合）
    recent_events: List[Dict[str, Any]] = Field(
        default_factory=list, description="最近事件摘要"
    )


# ============================================================
# 战斗模型
# ============================================================

class BattleContext(BaseModel):
    """战斗上下文

    战斗过程中的共享数据，由 BattleScheduler 创建，
    在 BattleResolver 中使用和更新。
    """

    battle_id: str = Field(description="战斗唯一ID")
    turn: int = Field(description="当前回合")

    # 双方信息
    attacker_faction: str = Field(description="攻击方势力")
    defender_faction: str = Field(description="防守方势力")

    # 攻击方
    attacker_armies: List[str] = Field(description="攻击方军队ID列表")
    attacker_total_soldiers: int = Field(default=0, description="攻击方总兵力")
    attacker_initial_soldiers: int = Field(default=0, description="攻击方战斗前初始总兵力")
    attacker_avg_morale: float = Field(default=0.0, description="攻击方平均士气")
    attacker_avg_command: float = Field(default=0.0, description="攻击方平均统帅")
    attacker_avg_bravery: float = Field(default=0.0, description="攻击方平均勇武")

    # 防守方
    defender_city: Optional[str] = Field(None, description="防守城市ID（攻城战）")
    defender_armies: List[str] = Field(default_factory=list, description="防守方军队ID")
    defender_total_soldiers: int = Field(default=0, description="防守方总兵力")
    defender_initial_soldiers: int = Field(default=0, description="防守方战斗前初始总兵力")
    defender_avg_morale: float = Field(default=0.0, description="防守方平均士气")
    defender_avg_command: float = Field(default=0.0, description="防守方平均统帅")
    defender_avg_bravery: float = Field(default=0.0, description="防守方平均勇武")

    # 城墙耐久（攻城战，由 GameEngine 从城市数据填充）
    wall_hp: int = Field(default=0, description="城墙当前耐久")
    wall_max_hp: int = Field(default=0, description="城墙最大耐久")

    # 战斗状态
    battle_type: BattleType = Field(description="战斗类型")
    battle_phase: BattlePhase = Field(default=BattlePhase.START, description="战斗阶段")
    round_count: int = Field(default=0, description="已进行回合数")

    # 建国/称帝加成
    attacker_morale_bonus: int = Field(default=0, description="攻击方建国士气加成")
    defender_morale_bonus: int = Field(default=0, description="防守方建国士气加成")

    # 结果
    result: Optional[BattleResultType] = Field(None, description="战斗结果")
    attacker_casualties: int = Field(default=0, description="攻击方伤亡")
    defender_casualties: int = Field(default=0, description="防守方伤亡")


class BattleResult(BaseModel):
    """战斗结果

    战斗结算完成后返回的完整结果数据。
    """

    battle_id: str = Field(description="战斗ID")
    battle_type: BattleType = Field(description="战斗类型")
    result: BattleResultType = Field(description="战斗结果")

    # 伤亡
    attacker_casualties: int = Field(description="攻击方伤亡")
    defender_casualties: int = Field(description="防守方伤亡")

    # 士气变化
    attacker_morale_change: int = Field(default=0, description="攻击方士气变化")
    defender_morale_change: int = Field(default=0, description="防守方士气变化")

    # 将领
    captured_generals: List[str] = Field(
        default_factory=list, description="被俘将领ID列表"
    )
    killed_generals: List[str] = Field(
        default_factory=list, description="阵亡将领ID列表"
    )

    # 城市
    captured_city: Optional[str] = Field(None, description="被占领的城市ID")

    # 战斗日志
    battle_log: List[str] = Field(default_factory=list, description="战斗日志")


# ============================================================
# 日志与状态管理模型
# ============================================================

class TurnLog(BaseModel):
    """回合日志"""

    turn: int = Field(description="回合数")
    commands: List[Command] = Field(default_factory=list, description="本回合所有命令")
    events: List[Dict[str, Any]] = Field(default_factory=list, description="本回合事件")
    winner: Optional[str] = Field(None, description="本回合结束时获胜方（如有）")


class GameState(BaseModel):
    """完整游戏状态快照

    用于保存/加载游戏状态，支持回滚（借鉴 boardgame.io 设计）。
    """

    turn: int = Field(description="当前回合")
    max_turns: int = Field(default=192, description="最大回合数")
    year: int = Field(default=184, description="当前年份 (AD)")
    seed: int = Field(description="随机种子")
    game_over: bool = Field(default=False, description="游戏是否结束")
    winner: Optional[str] = Field(None, description="获胜方")

    cities: Dict[str, City] = Field(description="所有城市")
    armies: Dict[str, Army] = Field(description="所有军队")
    generals: Dict[str, General] = Field(description="所有将领")

    messages: List[DiplomacyMessage] = Field(
        default_factory=list, description="外交消息"
    )

    turn_logs: List[TurnLog] = Field(default_factory=list, description="回合日志")
