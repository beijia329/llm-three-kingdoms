# Command 模式数据模型

> 本文档详细定义游戏中的命令模式（Command Pattern）。
> 所有玩家操作都封装为Command对象，可序列化、可校验、可回放。
> 参考：architecture.md 第九章 命令模式与可验证动作协议

---

## 一、设计思想

### 1.1 为什么用 Command 模式

| 好处 | 说明 |
|------|------|
| **可序列化** | 命令可以转成JSON，保存到日志或通过网络传输 |
| **可校验** | 执行前可以校验命令是否合法 |
| **可回放** | 记录所有命令，可以重放整局游戏 |
| **可撤销** | 理论上可以支持Undo（第一版可能不实现） |
| **解耦** | 玩家决策和游戏执行解耦，中间通过Command传递 |
| **审计** | 所有操作都有记录，便于调试和分析 |

### 1.2 三层校验（VAP）
每个命令执行前都要经过三层校验：

```
1. 语法层：JSON格式对不对？
   ↓
2. Schema层：字段对不对？类型对不对？枚举值对不对？
   ↓
3. 业务层：当前状态下能不能执行？资源够不够？目标存在吗？
```

### 1.3 命令执行流程

```
玩家决策 → 生成Command对象 → Schema校验 → 业务校验 → 执行 → 记录日志
                                                                 ↓
                                                              触发事件
```

---

## 二、Command 基类

### 2.1 基类定义
所有命令都继承自BaseCommand。

```python
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, Dict, Any

class CommandType(str, Enum):
    """命令类型枚举"""
    DEVELOP = "develop"      # 发展城市
    RECRUIT = "recruit"      # 征兵
    ATTACK = "attack"        # 进攻
    REWARD = "reward"        # 赏赐将领
    EXPLORE = "explore"      # 探索人才
    MESSAGE = "message"      # 发送外交消息
    RUMOR = "rumor"          # 散布流言

class BaseCommand(BaseModel):
    """命令基类"""
    type: CommandType                    # 命令类型
    faction: str                         # 执行方势力
    turn: int                            # 执行回合
    params: Dict[str, Any] = Field(default_factory=dict)  # 命令参数
```

### 2.2 命令结果
每个命令执行后返回CommandResult。

```python
class CommandResult(BaseModel):
    """命令执行结果"""
    success: bool                        # 是否成功
    command: BaseCommand                 # 原始命令
    message: str = ""                    # 结果说明
    data: Dict[str, Any] = Field(default_factory=dict)  # 额外数据
    events: List[GameEvent] = Field(default_factory=list)  # 触发的事件
```

---

## 三、各命令详细定义

### 3.1 Develop（发展城市）
提升城市的经济、军事或文化。

**参数**：
```python
class DevelopParams(BaseModel):
    city: str                           # 城市名称
    type: str                           # 发展类型：economy / military / culture
```

**效果**：
- **economy（经济）**：提升金钱产出，消耗金钱
- **military（军事）**：提升城墙和守军上限，消耗金钱和粮草
- **culture（文化）**：提升民心增长速度，消耗金钱

**合法性校验**：
- 城市必须存在
- 城市必须属于己方
- 资源必须足够
- 城市等级未达上限

**示例**：
```json
{
  "type": "develop",
  "faction": "wei",
  "turn": 5,
  "params": {
    "city": "许昌",
    "type": "economy"
  }
}
```

---

### 3.2 Recruit（征兵）
在城市征募士兵。

**参数**：
```python
class RecruitParams(BaseModel):
    city: str                           # 城市名称
    troops: int = Field(gt=0)           # 征兵数量
```

**效果**：
- 增加城市守军
- 消耗金钱和粮草
- 消耗人口

**合法性校验**：
- 城市必须存在且属于己方
- 征兵数量 > 0
- 资源必须足够
- 人口必须足够
- 不超过城市守军上限

**示例**：
```json
{
  "type": "recruit",
  "faction": "wei",
  "turn": 5,
  "params": {
    "city": "许昌",
    "troops": 2000
  }
}
```

---

### 3.3 Attack（进攻）
派遣军队进攻敌方城市。

**参数**：
```python
class AttackParams(BaseModel):
    from_city: str = Field(alias="from")  # 出发城市
    to_city: str = Field(alias="to")      # 目标城市
    troops: int = Field(gt=0)             # 出征兵力
    general: Optional[str] = None         # 主将（可选，默认选最好的）
```

**效果**：
- 从出发城市派出军队
- 军队开始向目标城市行军
- 到达后触发攻城战

**合法性校验**：
- 出发城市必须存在且属于己方
- 目标城市必须存在且不属于己方
- 出征兵力 > 0
- 出发城市守军 >= 出征兵力
- 两城市必须相邻或可达
- 城市不能已经有军队出征

**示例**：
```json
{
  "type": "attack",
  "faction": "wei",
  "turn": 5,
  "params": {
    "from": "许昌",
    "to": "洛阳",
    "troops": 5000,
    "general": "曹操"
  }
}
```

---

### 3.4 Reward（赏赐将领）
赏赐将领，提升忠诚度。

**参数**：
```python
class RewardParams(BaseModel):
    general: str                        # 将领名称
    gold: int = Field(gt=0)             # 赏赐金钱
```

**效果**：
- 消耗金钱
- 提升将领忠诚度
- 忠诚度越高，提升越少（边际递减）

**合法性校验**：
- 将领必须存在且属于己方
- 赏赐金钱 > 0
- 势力金钱必须足够

**示例**：
```json
{
  "type": "reward",
  "faction": "wei",
  "turn": 5,
  "params": {
    "general": "曹操",
    "gold": 500
  }
}
```

---

### 3.5 Explore（探索人才）
在城市探索，有几率发现新将领。

**参数**：
```python
class ExploreParams(BaseModel):
    city: str                           # 在哪个城市探索
    general: Optional[str] = None       # 派去探索的将领（可选，默认随机）
```

**效果**：
- 消耗金钱
- 有几率发现在野将领
- 几率取决于城市等级和民心

**合法性校验**：
- 城市必须存在且属于己方
- 金钱必须足够

**示例**：
```json
{
  "type": "explore",
  "faction": "wei",
  "turn": 5,
  "params": {
    "city": "许昌"
  }
}
```

---

### 3.6 Message（外交消息）
向其他势力发送外交消息。

**参数**：
```python
class MessageParams(BaseModel):
    to: str                             # 接收方势力
    content: str                        # 消息内容
```

**效果**：
- 对方在下回合收到消息
- 每回合只能发1条消息

**合法性校验**：
- 接收方必须存在且不是己方
- 消息内容不为空
- 本回合还没发过消息

**示例**：
```json
{
  "type": "message",
  "faction": "wei",
  "turn": 5,
  "params": {
    "to": "shu",
    "content": "我们联手攻打吴国如何？"
  }
}
```

---

### 3.7 Rumor（散布流言）
在敌方城市散布流言，降低守将忠诚度。

**参数**：
```python
class RumorParams(BaseModel):
    city: str                           # 目标城市
    target_general: Optional[str] = None  # 目标将领（可选，默认随机）
    spy_general: Optional[str] = None     # 执行流言的将领（可选，影响成功率）
```

**效果**：
- 消耗金钱
- 降低敌方守将忠诚度
- 有几率被识破（反效果）

**合法性校验**：
- 城市必须存在且不属于己方
- 金钱必须足够

**示例**：
```json
{
  "type": "rumor",
  "faction": "wei",
  "turn": 5,
  "params": {
    "city": "成都",
    "target_general": "诸葛亮"
  }
}
```

---

## 四、命令合法性校验

### 4.1 校验层级

#### 第一层：Schema 校验
用Pydantic做结构校验：
- 字段是否存在
- 字段类型是否正确
- 枚举值是否合法
- 数值范围是否合理（比如troops > 0）

#### 第二层：静态业务校验
不依赖游戏状态的校验：
- 命令类型是否存在
- 参数是否完整
- 格式是否正确

#### 第三层：动态业务校验
依赖游戏状态的校验：
- 资源是否足够
- 目标是否存在
- 是否属于己方
- 距离是否可达
- 等等...

### 4.2 校验器实现

```python
class CommandValidator:
    """命令校验器"""
    
    def validate_schema(self, command: BaseCommand) -> bool:
        """Schema校验（Pydantic自动做）"""
        # Pydantic模型实例化时自动校验
        return True
    
    def validate_static(self, command: BaseCommand) -> List[str]:
        """静态业务校验"""
        errors = []
        # 检查命令类型
        # 检查必填参数
        # ...
        return errors
    
    def validate_dynamic(self, command: BaseCommand, game_state: GameState) -> List[str]:
        """动态业务校验"""
        errors = []
        # 检查资源
        # 检查目标
        # 检查状态
        # ...
        return errors
```

---

## 五、命令执行器

### 5.1 执行器接口

```python
class CommandExecutor:
    """命令执行器"""
    
    def execute(self, command: BaseCommand, game_state: GameState) -> CommandResult:
        """执行命令"""
        # 1. 校验
        errors = self.validator.validate_dynamic(command, game_state)
        if errors:
            return CommandResult(success=False, message="; ".join(errors))
        
        # 2. 执行
        handler = self._get_handler(command.type)
        result = handler(command, game_state)
        
        # 3. 记录日志
        self.logger.log_command(command, result)
        
        # 4. 触发事件
        for event in result.events:
            self.event_bus.publish(event)
        
        return result
```

### 5.2 各命令的Handler
每个命令类型对应一个handler函数：
- `handle_develop(command, state) -> CommandResult`
- `handle_recruit(command, state) -> CommandResult`
- `handle_attack(command, state) -> CommandResult`
- ...

---

## 六、命令序列化

### 6.1 转 JSON
```python
command = AttackCommand(
    faction="wei",
    turn=5,
    params={"from": "许昌", "to": "洛阳", "troops": 5000}
)

json_str = command.model_dump_json()
```

### 6.2 从 JSON 解析
```python
def parse_command(json_str: str) -> BaseCommand:
    """从JSON解析命令"""
    # 1. 先解析成dict
    data = json_repair.repair_json(json_str)
    
    # 2. 根据type选择具体的命令类
    command_type = data.get("type")
    command_class = COMMAND_CLASSES.get(command_type)
    
    if not command_class:
        raise ValueError(f"未知命令类型: {command_type}")
    
    # 3. 实例化（自动Schema校验）
    return command_class(**data)
```

### 6.3 命令注册表
```python
COMMAND_CLASSES = {
    CommandType.DEVELOP: DevelopCommand,
    CommandType.RECRUIT: RecruitCommand,
    CommandType.ATTACK: AttackCommand,
    CommandType.REWARD: RewardCommand,
    CommandType.EXPLORE: ExploreCommand,
    CommandType.MESSAGE: MessageCommand,
    CommandType.RUMOR: RumorCommand,
}
```

---

## 七、命令日志

### 7.1 日志结构
每回合的命令日志：

```python
class TurnLog(BaseModel):
    turn: int                            # 回合数
    commands: List[BaseCommand]          # 本回合执行的命令
    results: List[CommandResult]         # 执行结果
    events: List[GameEvent]              # 触发的事件
    state_snapshot: GameState            # 回合结束时的状态快照
```

### 7.2 完整游戏日志
```python
class GameLog(BaseModel):
    game_id: str                         # 游戏ID
    seed: int                            # 随机种子
    players: Dict[str, str]              # 势力 -> 玩家/模型
    turns: List[TurnLog]                 # 每回合日志
    winner: Optional[str] = None         # 获胜方
    end_reason: Optional[str] = None     # 结束原因
```

### 7.3 用途
- **回放**：可以从日志重放整局游戏
- **调试**：出问题时可以复盘
- **分析**：统计AI的决策模式
- **评测**：用于模型评测的数据收集

---

## 八、与其他系统的关系

### 8.1 和 Engine 的关系
- Engine是命令的执行者
- Engine不关心命令是谁发的，只负责执行
- 所有状态变更都通过命令触发

### 8.2 和 Player 的关系
- Player是命令的生产者
- Player根据观察数据做出决策，生成命令
- Player不直接修改状态，只能发命令

### 8.3 和 日志系统 的关系
- 所有命令都被记录到日志
- 日志可以用来回放
- 日志可以用来分析

### 8.4 和 校验系统 的关系
- 命令执行前必须通过校验
- 校验失败返回错误，不执行
- 校验保证游戏状态的合法性

---

> **文档版本**：v2.2
> **创建日期**：2026-06-23
> **最后更新**：2026-06-24
> **相关文档**：data-models.md, architecture.md
> **v2.2更新**：势力枚举3方→12方，命令示例 faction key 更新
> **v1.1更新**：补充Explore的general参数和Rumor的spy_general参数
