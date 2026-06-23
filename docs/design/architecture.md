# 架构设计文档

## 一、整体架构

### 1.1 三层架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        Player 层                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  LLMPlayer  │  │  GUIPlayer  │  │  CLIPlayer  │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                │                │                 │
│         └────────────────┼────────────────┘                 │
│                          ▼                                   │
│              BasePlayer 抽象接口                             │
│              - get_commands(obs) -> List[Command]           │
│              - receive_message(from, content)               │
└──────────────────────────┬──────────────────────────────────┘
                           │ 标准命令接口
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                        Engine 层                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                     GameEngine                        │  │
│  │                                                       │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐     │  │
│  │  │ 城市系统    │  │ 资源系统    │  │ 将领系统    │     │  │
│  │  └────────────┘  └────────────┘  └────────────┘     │  │
│  │                                                       │  │
│  │  ┌──────────────────────────────────────────────┐    │  │
│  │  │              战斗系统                         │    │  │
│  │  │  调度器 / 行军 / 结算 / 上下文                │    │  │
│  │  └──────────────────────────────────────────────┘    │  │
│  │                                                       │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐     │  │
│  │  │ 外交系统    │  │ 地图系统    │  │ 事件总线    │     │  │
│  │  └────────────┘  └────────────┘  └────────────┘     │  │
│  └───────────────────────────────────────────────────────┘  │
│                          ▲                                   │
│                          │ 状态快照接口                       │
└──────────────────────────┼──────────────────────────────────┘
                           │ 只读访问
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                       Renderer 层                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ 地图渲染     │  │ UI面板       │  │ 回放系统     │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 核心设计原则

| 原则 | 说明 | 验证方法 |
|------|------|---------|
| **Engine纯逻辑** | 不依赖任何UI框架 | engine目录下不能import pygame |
| **Player无状态感知** | 只通过观察接口获取信息 | Player不能直接访问GameEngine内部状态 |
| **Renderer只读** | 只读取状态，不修改逻辑 | Renderer不能调用Engine的修改方法 |
| **确定性** | 相同输入=相同输出 | 用固定seed跑两次，结果完全一致 |
| **事件驱动** | 状态变化通过事件通知 | UI不轮询状态，订阅事件即可 |

---

## 二、GameEngine 主类

### 2.1 类定义

```python
class GameEngine:
    """游戏引擎主类"""

    def __init__(self, seed: int = None):
        self.seed = seed or random.randint(0, 1000000)
        self.rng = GameRandom(self.seed)

        # 游戏状态
        self.turn: int = 1
        self.max_turns: int = 24
        self.game_over: bool = False
        self.winner: Optional[str] = None

        # 子系统
        self.cities: Dict[str, City] = {}
        self.armies: Dict[str, Army] = {}
        self.generals: Dict[str, General] = {}
        self.map: MapSystem = None
        self.events: EventBus = EventBus()

        # 外交消息
        self.messages: List[DiplomacyMessage] = []

        # 回合日志
        self.turn_log: List[TurnLog] = []
```

### 2.2 核心方法

| 方法 | 说明 |
|------|------|
| `init_game(map_data, factions)` | 初始化游戏 |
| `execute_commands(faction, commands)` | 执行一个势力的命令 |
| `process_turn()` | 处理一回合的所有逻辑 |
| `get_observation(faction) -> GameObservation` | 获取某个势力的观察数据 |
| `check_victory() -> Optional[str]` | 检查胜利条件 |
| `get_state_snapshot() -> GameState` | 获取完整状态快照 |

### 2.3 回合处理流水线

```python
def process_turn(self):
    """处理一回合"""
    # 1. 处理所有军队行军
    self._process_army_movement()

    # 2. 检测并处理战斗
    self._process_battles()

    # 3. 回合结束处理（资源产出、消耗等）
    self._process_end_of_turn()

    # 4. 检查胜利条件
    self._check_victory()

    self.turn += 1
```

---

## 三、子系统设计

### 3.1 城市系统 (CitySystem)

**职责：**
- 城市发展（经济/军事/文化）
- 征兵
- 城市状态管理

**核心方法：**
- `develop_city(city_id, focus) -> bool`
- `recruit_troops(city_id, amount) -> bool`
- `get_city_info(city_id) -> CityInfo`

### 3.2 资源系统 (ResourceSystem)

**职责：**
- 计算每回合资源产出
- 处理资源消耗
- 民心变化计算

**核心公式：**
```
金钱产出 = 基础产出 × 城市等级 × (1 + 民心系数)
粮草产出 = 基础产出 × 城市等级 × (1 + 民心系数)
民心变化 = f(事件, 治理, 税率)
```

### 3.3 将领系统 (GeneralSystem)

**职责：**
- 将领招募与探索
- 忠诚度管理
- 将领赏赐
- 俘虏与招降

**核心方法：**
- `explore_generals(city_id) -> List[General]`
- `reward_general(general_id, gold) -> bool`
- `capture_general(general_id, captor)`
- `try_recruit(general_id) -> bool`

### 3.4 外交系统 (DiplomacySystem)

**职责：**
- 信使系统（发送消息）
- 流言系统
- 关系值管理

**核心方法：**
- `send_message(from_faction, to_faction, content)`
- `spread_rumor(from_faction, target_city, target_general)`

### 3.5 地图系统 (MapSystem)

**职责：**
- 城市拓扑关系
- 行军路线计算
- 距离计算

**数据结构：**
- 邻接表表示城市连接
- 边权重 = 行军时间（回合数）

---

## 四、战斗系统架构

详见 [battle-system.md](./battle-system.md)

### 4.1 模块划分

```
battle/
├── battle_context.py      # 战斗上下文（共享数据）
├── battle_scheduler.py    # 战斗调度（谁和谁打）
├── army_movement.py       # 行军系统
└── battle_resolver.py     # 战斗结算
```

### 4.2 设计原则
- 战斗上下文是纯数据类，不包含逻辑
- 四个子模块互相不持有引用，通过上下文传递数据
- 战斗结果通过事件广播出去

---

## 五、事件总线

### 5.1 设计
- 简单的发布-订阅模式
- 同步执行（游戏是单线程的）
- 事件是不可变的数据类

### 5.2 事件类型

```python
@dataclass
class GameEvent:
    turn: int
    timestamp: float

@dataclass
class CityCapturedEvent(GameEvent):
    city_id: str
    old_faction: str
    new_faction: str

@dataclass
class BattleEndedEvent(GameEvent):
    battle_id: str
    attacker: str
    defender: str
    result: str  # "attacker_win" / "defender_win" / "draw"
    casualties: Dict[str, int]

@dataclass
class GeneralDiedEvent(GameEvent):
    general_id: str
    cause: str

@dataclass
class ResourceChangedEvent(GameEvent):
    faction: str
    resource_type: str
    change: int
    reason: str
```

---

## 六、线程模型

### 6.1 线程划分

| 线程 | 职责 | 说明 |
|------|------|------|
| 主线程 | Pygame渲染 + 事件处理 | 保证60fps |
| 游戏线程 | 游戏逻辑 + LLM调用 | 后台运行，不阻塞UI |

### 6.2 同步机制
- 使用 `threading.Event` 同步
- GUIPlayer通过事件等待玩家操作
- LLM调用使用线程池并发执行

### 6.3 注意事项
- 游戏逻辑是单线程的，避免并发问题
- LLM调用可以并发，但结果收集后串行执行
- 状态修改只能在游戏线程进行

---

## 七、可扩展性设计

### 7.1 扩展点
- **新玩家类型**：继承BasePlayer即可
- **新战斗规则**：替换BattleResolver
- **新胜利条件**：修改check_victory
- **新UI**：实现新的Renderer

### 7.2 配置化
- 游戏参数通过配置文件调整
- 不需要改代码就能平衡数值
- 支持不同的游戏模式（短局/长局/自定义）

---

## 八、状态快照与回滚

### 8.1 设计思想（借鉴 boardgame.io）
游戏状态是不可变的，每次操作产生新的状态快照。所有历史快照都保存，可以随时回退到任意回合。

**核心价值：**
- 支持回放系统（时间旅行）
- 便于调试（出问题可以回退看之前的状态）
- 支持Undo/Redo
- 可以做状态哈希校验

### 8.2 GameState 快照结构

```python
@dataclass
class GameState:
    """游戏状态快照（不可变）"""
    turn: int
    seed: int
    rng_state: tuple  # 随机数生成器状态

    # 游戏数据
    cities: Dict[str, City]
    armies: Dict[str, Army]
    generals: Dict[str, General]
    messages: List[DiplomacyMessage]

    # 游戏状态
    game_over: bool
    winner: Optional[str]

    # 元数据
    state_hash: str  # 状态哈希，用于校验
```

### 8.3 快照管理

```python
class StateManager:
    """状态管理器"""

    def __init__(self):
        self.history: List[GameState] = []  # 历史快照

    def save_snapshot(self, engine: GameEngine):
        """保存当前状态快照"""
        state = engine.get_state_snapshot()
        self.history.append(state)

    def load_snapshot(self, turn: int) -> GameState:
        """加载指定回合的状态"""
        return self.history[turn - 1]

    def rollback(self, turn: int):
        """回滚到指定回合"""
        # 清空该回合之后的历史
        self.history = self.history[:turn]
```

### 8.4 状态哈希校验
每个状态快照计算一个哈希值，用于：
- 检测状态是否被意外修改
- 回放时验证结果一致性
- 调试时快速定位差异

```python
def calculate_state_hash(state: GameState) -> str:
    """计算状态哈希"""
    # 序列化所有关键数据，计算SHA256
    # 注意：要保证相同状态=相同哈希
    pass
```

---

## 九、命令模式与可验证动作协议

### 9.1 设计思想
所有玩家操作都封装为Command对象，而不是直接调用方法。

**好处：**
- 可以序列化（存日志、网络传输）
- 可以回放
- 可以撤销
- 可以校验（执行前检查是否合法）
- 统一的错误处理

### 9.2 Command 基类

```python
class Command(BaseModel):
    """命令基类"""
    type: str = Field(description="命令类型")
    faction: str = Field(description="执行势力")

    def validate(self, engine: GameEngine) -> ValidationResult:
        """执行前校验（可选，子类可重写）"""
        return ValidationResult(valid=True)

    def execute(self, engine: GameEngine) -> CommandResult:
        """执行命令"""
        pass
```

### 9.3 可验证动作协议（VAP）
参考行业最佳实践，LLM输出的命令需要经过三层校验：

| 层级 | 校验内容 | 执行者 |
|------|---------|--------|
| 第一层 | 语法正确（JSON格式） | OutputParser |
| 第二层 | Schema正确（字段齐全、类型对） | Pydantic |
| 第三层 | 业务合法（资源够、城市存在、不是打自己） | Command.validate() |

只有三层都通过，命令才会被执行。

### 9.4 命令执行结果

```python
@dataclass
class CommandResult:
    success: bool
    message: str  # 成功或失败的原因
    events: List[GameEvent]  # 触发的事件
```

---

## 十、状态合法性校验

### 10.1 为什么需要
游戏系统复杂，很容易出现状态不一致：
- 军队出发了，守军没减少
- 将领被俘了，还在城市里
- 资源变成负数
- 民心超过100

### 10.2 校验时机
- 每回合结束后
- 每个命令执行后（开发模式）
- 加载存档后

### 10.3 校验规则

```python
def validate_state(engine: GameEngine) -> List[str]:
    """校验游戏状态合法性，返回错误列表"""
    errors = []

    # 城市校验
    for city in engine.cities.values():
        if city.gold < 0:
            errors.append(f"城市{city.name}金钱为负：{city.gold}")
        if city.food < 0:
            errors.append(f"城市{city.name}粮草为负：{city.food}")
        if city.population < 0:
            errors.append(f"城市{city.name}人口为负：{city.population}")
        if not (0 <= city.morale <= 100):
            errors.append(f"城市{city.name}民心越界：{city.morale}")
        if city.garrison < 0:
            errors.append(f"城市{city.name}守军为负：{city.garrison}")

    # 军队校验
    for army in engine.armies.values():
        if army.soldiers <= 0:
            errors.append(f"军队{army.id}兵力非正：{army.soldiers}")
        if not (0 <= army.morale <= 100):
            errors.append(f"军队{army.id}士气越界：{army.morale}")

    # 将领校验
    for general in engine.generals.values():
        if not (0 <= general.loyalty <= 100):
            errors.append(f"将领{general.name}忠诚越界：{general.loyalty}")

    # 一致性校验
    # 将领位置是否存在
    # 军队的将领是否存在
    # 等等...

    return errors
```

### 10.4 开发模式 vs 生产模式
- **开发模式**：每个命令后都校验，发现错误立刻断言失败
- **生产模式**：每回合结束校验，记录错误日志，尽量继续运行

---

## 十一、游戏日志系统

### 11.1 日志类型

| 类型 | 内容 | 用途 |
|------|------|------|
| **命令日志** | 玩家输入的所有命令 | 回放、调试 |
| **事件日志** | 游戏中发生的所有事件 | UI展示、统计 |
| **状态快照** | 每回合结束时的完整状态 | 时间旅行、校验 |
| **LLM日志** | LLM的输入输出 | 调试AI行为、Prompt优化 |

### 11.2 回合日志结构

```python
@dataclass
class TurnLog:
    turn: int

    # 各方命令
    commands: Dict[str, List[Command]]

    # 发生的事件
    events: List[GameEvent]

    # 状态快照（可选，节省空间可以不存）
    state_snapshot: Optional[GameState] = None
```

### 11.3 回放文件格式
```json
{
  "version": "1.0",
  "seed": 42,
  "players": {
    "wei": {"type": "llm", "model": "claude-sonnet"},
    "shu": {"type": "llm", "model": "gpt-4o"},
    "wu": {"type": "llm", "model": "gemini-pro"}
  },
  "turns": [
    {
      "turn": 1,
      "commands": {...},
      "events": [...]
    }
  ],
  "winner": "shu",
  "total_turns": 24
}
```

---

## 十二、G与ctx分离思想

### 12.1 借鉴 boardgame.io
boardgame.io 有一个很重要的设计思想：
- **G**：游戏状态（开发者管理，包含所有游戏数据）
- **ctx**：框架元数据（框架管理，只读，包含回合数、当前玩家等）

### 12.2 我们的对应
- **G ≈ GameState**：城市、军队、将领、资源等游戏数据
- **ctx ≈ GameContext**：回合数、seed、游戏是否结束、胜利者

### 12.3 好处
- 游戏逻辑只关心G，不关心框架元数据
- 框架可以统一处理回合切换、胜利判定等
- 状态更清晰，职责更明确

---

## 十三、容错与兜底机制

### 13.1 设计原则

**核心原则：游戏必须能运行到结束，任何组件失败都不能导致整个游戏崩溃。**

这是LLM驱动游戏的特殊要求——LLM的输出是不可控的，网络可能不稳定，API可能宕机。游戏架构必须能优雅地处理所有这些异常。

### 13.2 多层容错体系

```
┌─────────────────────────────────────────┐
│         游戏层（GameEngine）            │
│  状态校验、异常隔离、最大回合数保证      │
├─────────────────────────────────────────┤
│         玩家层（Player）                │
│  超时保护、重试、降级、空命令兜底        │
├─────────────────────────────────────────┤
│         LLM层（LLMClient）              │
│  网络重试、超时、错误处理                │
└─────────────────────────────────────────┘
```

### 13.3 各层容错详细说明

#### LLM层容错
- **超时保护**：每个请求30秒超时，不会无限等待
- **网络重试**：网络错误自动重试2次，指数退避
- **错误处理**：API返回错误不崩溃，记录日志后降级
- **速率限制**：自动处理429错误，等待后重试

#### 玩家层容错
- **解析容错**：五层防御体系，尽量从垃圾输出中提取有效命令
- **重试机制**：解析失败时，把错误返回给LLM让它修正
- **空命令兜底**：实在解析不出来，返回空命令（跳过本回合）
- **连续失败降级**：连续3回合失败，降级为随机AI
- **异常隔离**：一个玩家出错，不影响其他玩家的决策

详见 [llm-integration.md](./llm-integration.md) 第三章。

#### 游戏层容错
- **状态合法性校验**：每回合结束校验状态，发现异常记录日志
- **尽量继续运行**：非致命错误不中断游戏，记录后继续
- **命令合法性校验**：所有命令执行前经过三层校验（语法→Schema→业务）
- **部分执行**：一回合多个命令，只丢弃非法的，合法的照常执行
- **最大回合数**：24回合强制结束，不会无限循环

### 13.4 最坏情况分析

| 场景 | 结果 | 游戏是否能继续 |
|------|------|--------------|
| 一个模型输出格式错误 | 重试 → 空命令 → 随机AI | ✅ 能 |
| 一个模型API完全挂了 | 超时 → 降级为随机AI | ✅ 能 |
| 两个模型都挂了 | 两个都降级为随机AI | ✅ 能 |
| 三个模型都挂了 | 全部随机AI，纯随机对战 | ✅ 能 |
| 游戏状态出现异常 | 记录日志，尽量修复后继续 | ✅ 大部分情况能 |
| 游戏逻辑出现致命bug | 崩溃，记录错误栈 | ❌ 不能（但这是bug，不是LLM的问题） |

### 13.5 为什么选择"降级为随机AI"而不是"跳过"？

**原因**：
1. **平衡性**：三方对战少了一方，剩下两方的平衡会被打破
2. **游戏节奏**：空命令等于挂机，游戏会变得很无聊
3. **评测公平性**：模型A崩溃了直接判负，和模型B打了20回合才输，没有可比性
4. **数据完整性**：随机AI至少能产生完整的游戏数据，便于分析

**随机AI的设计原则**：
- 策略简单但合法（不会犯低级错误）
- 有基本的发展和进攻逻辑
- 强度适中，不会太强也不会太弱
- 作为"基准线"，衡量LLM比随机强多少

### 13.6 异常监控与日志

- **所有异常都必须记录**：包括解析失败、API错误、降级事件
- **降级事件要标红**：在日志中用WARNING级别，便于排查
- **游戏结束后输出统计**：每个玩家的降级次数、空命令次数
- **评测报告中标注异常**：如果模型出现过降级，在报告中说明

### 13.7 开发模式 vs 生产模式

| 模式 | 异常处理 | 适用场景 |
|------|---------|---------|
| **开发模式** | 异常立刻断言失败，暴露问题 | 开发、调试 |
| **生产模式** | 记录日志，尽量继续运行 | 正式评测、运行 |

开发模式下，我们希望尽早发现问题；生产模式下，我们希望游戏能跑完。

---

> **文档版本**：v1.1
> **最后更新**：2026-06-23
> **更新内容**：补充状态快照、命令模式、状态校验、日志系统、容错与兜底机制
