# 数据模型设计文档

> 本文档定义游戏中所有核心数据结构。所有开发必须严格遵循此定义。

---

## 一、基础类型定义

### 1.1 势力枚举
```python
from enum import Enum

class Faction(str, Enum):
    WEI = "wei"      # 魏国
    SHU = "shu"      # 蜀国
    WU = "wu"        # 吴国
    NEUTRAL = "neutral"  # 中立
```

### 1.2 城市等级
```python
CITY_LEVELS = {
    1: {"name": "小城", "base_gold": 50, "base_food": 80, "max_population": 10000},
    2: {"name": "中城", "base_gold": 100, "base_food": 150, "max_population": 30000},
    3: {"name": "大城", "base_gold": 200, "base_food": 250, "max_population": 60000},
    4: {"name": "重镇", "base_gold": 350, "base_food": 400, "max_population": 100000},
    5: {"name": "都城", "base_gold": 500, "base_food": 500, "max_population": 150000},
}
```

---

## 二、城市模型

### 2.1 City 数据类
```python
from pydantic import BaseModel, Field
from typing import List, Optional

class City(BaseModel):
    """城市数据模型"""

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

    # 军事
    garrison: int = Field(ge=0, description="守军数量")

    # 将领
    generals: List[str] = Field(default_factory=list, description="驻守将领ID列表")

    # 地图
    position: tuple = Field(description="地图坐标 (x, y)")
    neighbors: List[str] = Field(default_factory=list, description="相邻城市ID列表")

    # 状态
    is_besieged: bool = Field(default=False, description="是否被围困")
    besieging_armies: List[str] = Field(default_factory=list, description="围城部队ID列表")
```

### 2.2 初始值配置

| 等级 | 城墙耐久 | 初始金钱 | 初始粮草 | 初始人口 | 初始民心 | 初始守军 |
|------|---------|---------|---------|---------|---------|---------|
| 1级 | 500 | 200 | 300 | 5000 | 70 | 500 |
| 2级 | 1000 | 400 | 600 | 15000 | 70 | 1000 |
| 3级 | 2000 | 800 | 1000 | 30000 | 70 | 2000 |
| 4级 | 3500 | 1500 | 1800 | 60000 | 70 | 3500 |
| 5级 | 5000 | 2500 | 2500 | 100000 | 70 | 5000 |

---

## 三、军队模型

### 3.1 Army 数据类
```python
class Army(BaseModel):
    """军队数据模型"""

    id: str = Field(description="军队唯一ID")
    faction: str = Field(description="所属势力")

    # 将领
    general_id: str = Field(description="主将ID")
    second_general_id: Optional[str] = Field(None, description="副将ID")

    # 兵力
    soldiers: int = Field(gt=0, description="士兵数量")
    casualties: int = Field(default=0, description="累计伤亡")

    # 补给
    food: int = Field(ge=0, description="携带粮草")
    food_consumption_per_turn: int = Field(description="每回合粮草消耗")

    # 状态
    morale: int = Field(ge=0, le=100, default=80, description="部队士气")
    status: str = Field(description="状态: marching/besieging/retreating/garrisoned")

    # 位置
    from_city: str = Field(description="出发城市")
    to_city: str = Field(description="目标城市")
    progress: float = Field(ge=0, le=1, default=0, description="行军进度 0-1")
    total_distance: int = Field(description="总距离（回合数）")

    # 战斗
    is_in_battle: bool = Field(default=False, description="是否正在战斗")
    current_battle_id: Optional[str] = Field(None, description="当前战斗ID")
```

### 3.2 军队状态枚举
- `marching` - 行军中
- `besieging` - 围城中
- `retreating` - 撤退中
- `garrisoned` - 驻守中（已入城）

---

## 四、将领模型

### 4.1 General 数据类
```python
class General(BaseModel):
    """将领数据模型"""

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
```

### 4.2 属性说明

| 属性 | 影响范围 | 计算公式 |
|------|---------|---------|
| **统帅** | 部队战斗力、士气 | 攻击加成 = command / 100 |
| **政治** | 资源产出、民心恢复 | 产出加成 = politics / 200 |
| **勇武** | 单挑、冲锋 | 暴击概率 = bravery / 200 |
| **智力** | 计谋、识破 | 计谋成功率 = intelligence / 150 |

### 4.3 忠诚度影响

| 忠诚度 | 效果 |
|--------|------|
| 90-100 | 死忠，不可能投降，战斗力+10% |
| 70-89 | 忠诚，很难投降 |
| 50-69 | 一般，有概率投降 |
| 30-49 | 不稳，容易投降，战斗力-10% |
| 0-29 | 危险，随时可能叛变，战斗力-20% |

---

## 五、战斗模型

### 5.1 BattleContext
```python
class BattleContext(BaseModel):
    """战斗上下文（战斗过程中的共享数据）"""

    battle_id: str
    turn: int

    # 双方信息
    attacker_faction: str
    defender_faction: str

    # 攻击方
    attacker_armies: List[str] = Field(description="攻击方军队ID列表")
    attacker_total_soldiers: int = 0
    attacker_avg_morale: float = 0.0
    attacker_avg_command: float = 0.0

    # 防守方
    defender_city: Optional[str] = Field(None, description="防守城市ID（攻城战）")
    defender_armies: List[str] = Field(default_factory=list, description="防守方军队ID")
    defender_total_soldiers: int = 0
    defender_avg_morale: float = 0.0
    defender_avg_command: float = 0.0

    # 战斗状态
    battle_type: str = Field(description="战斗类型: siege/field")
    battle_phase: str = Field(default="start", description="战斗阶段")
    round_count: int = Field(default=0, description="已进行回合数")

    # 结果
    result: Optional[str] = Field(None, description="战斗结果")
    attacker_casualties: int = 0
    defender_casualties: int = 0
```

### 5.2 战斗结果枚举
- `attacker_win` - 攻击方胜利
- `defender_win` - 防守方胜利
- `draw` - 平局
- `retreat` - 攻击方撤退

---

## 六、命令模型

> **注意**：命令模型的详细设计请参考 [command-pattern.md](./command-pattern.md)
> 本文档只做简要定义，以 command-pattern.md 为准。

### 6.1 命令基类
```python
class BaseCommand(BaseModel):
    """命令基类"""
    type: str = Field(description="命令类型")
    faction: str = Field(description="执行势力")
    turn: int = Field(description="执行回合")
    params: Dict[str, Any] = Field(default_factory=dict, description="命令参数")
```

### 6.2 命令类型与参数

| 命令类型 | 参数字段 | 说明 |
|---------|---------|------|
| **develop** | city, type | 发展城市，type: economy/military/culture |
| **recruit** | city, troops | 征兵，troops为征兵数量 |
| **attack** | from, to, troops, general (可选) | 派军进攻 |
| **reward** | general, gold | 赏赐将领 |
| **explore** | city, general (可选) | 探索人才 |
| **message** | to, content | 发送外交消息 |
| **rumor** | city, target_general (可选), spy_general (可选) | 散布流言 |

### 6.3 命令示例
```json
[
  {"type": "develop", "params": {"city": "chengdu", "type": "economy"}},
  {"type": "attack", "params": {"from": "hanzhong", "to": "changan", "troops": 1500, "general": "zhaoyun"}}
]
```

### 6.4 三层校验（VAP）
所有命令执行前必须经过三层校验：
1. **语法层**：JSON格式正确
2. **Schema层**：字段齐全、类型正确、枚举值合法
3. **业务层**：当前状态下可执行（资源够、目标存在等）

详见 [command-pattern.md](./command-pattern.md) 第四章。

---

## 七、观察数据模型

### 7.1 GameObservation
```python
class GameObservation(BaseModel):
    """玩家观察数据（给LLM/玩家看的）"""

    # 基本信息
    faction: str
    turn: int
    max_turns: int

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
    received_messages: List[Message] = Field(description="收到的消息")
    sent_messages: List[Message] = Field(description="已发送的消息")

    # 历史事件（最近5回合）
    recent_events: List[EventSummary] = Field(description="最近事件摘要")
```

### 7.2 信息迷雾规则
- 己方城市：完整信息
- 敌方城市（相邻）：能看到守军数量、城墙大致情况
- 敌方城市（不相邻）：只能看到归属和名称
- 敌方军队（在己方城市附近）：能看到大致兵力
- 敌方军队（远处）：完全不可见

---

## 八、游戏配置常量

```python
# 游戏规则
MAX_TURNS = 24
NUM_FACTIONS = 3
STARTING_CITIES_PER_FACTION = 5

# 经济
GOLD_PER_POPULATION = 0.01  # 每人每回合产金
FOOD_PER_POPULATION = 0.015  # 每人每回合产粮
MORALE_GOLD_PENALTY = 0.005  # 每点民心影响产出百分比

# 军事
RECRUIT_COST_GOLD = 2  # 每个士兵征兵费
RECRUIT_COST_FOOD = 3  # 每个士兵粮草费
GARRISON_FOOD_COST = 0.1  # 每个守军每回合粮草消耗
ARMY_FOOD_COST = 0.2  # 每个出征士兵每回合消耗

# 战斗
WALL_DAMAGE_PER_TURN = 100  # 每回合攻城对城墙伤害
MORALE_LOSS_PER_CASUALTY = 0.01  # 每损失1%兵力士气下降
MIN_MORALE_FOR_BATTLE = 20  # 低于此士气会溃散

# 将领
LOYALTY_DECAY_PER_TURN = 0.5  # 每回合忠诚衰减
REWARD_LOYALTY_BONUS = 5  # 每100金加多少忠诚
CAPTURE_SURRENDER_BASE = 30  # 投降基础概率(%)
```

---

> **文档版本**：v1.1
> **最后更新**：2026-06-23
> **相关文档**：command-pattern.md, architecture.md
> **v1.1更新**：统一命令模型命名规范，与 command-pattern.md 保持一致
