# 事件驱动游戏架构

> 来源：Game Design Patterns + Generalist Programmer
> 类型：架构设计参考
> 项目引用：architecture.md 第五章 事件总线

---

## 一、什么是事件驱动架构

### 1.1 核心思想
组件之间不直接调用，而是通过事件通信。
- 发布者：发出事件，不知道谁会接收
- 订阅者：监听事件，不知道谁发出的
- 事件总线：中间传递消息

### 1.2 为什么用事件驱动

| 好处 | 说明 |
|------|------|
| **解耦** | 组件之间不直接依赖，改一个不影响另一个 |
| **可扩展** | 增加新功能只要订阅事件，不用改现有代码 |
| **可测试** | 组件可以单独测试，mock起来方便 |
| **异步** | 发布者不用等订阅者处理完 |
| **可观测** | 所有事件都可以记录和回放 |

### 1.3 什么时候不用
- 简单的小游戏，不需要这么复杂
- 对性能要求极高的场景（事件传递有开销）
- 调用关系非常明确且固定的场景

---

## 二、事件驱动的核心概念

### 2.1 事件（Event）
事件是发生了什么事的通知，是不可变的数据对象。

**特点**：
- 过去式命名：SomethingHappened
- 不可变：创建后不能修改
- 包含上下文：事件发生时的相关数据

**例子**：
```python
class CityCapturedEvent(GameEvent):
    """城市被占领事件"""
    turn: int
    city: str
    old_faction: str
    new_faction: str
    captured_general: Optional[str] = None
```

### 2.2 事件总线（Event Bus）
负责事件的发布和订阅。

**核心功能**：
- subscribe(event_type, handler)：订阅事件
- publish(event)：发布事件
- unsubscribe(event_type, handler)：取消订阅

**实现方式**：
- 简单的字典映射：事件类型 → 处理器列表
- 同步或异步
- 支持优先级

### 2.3 处理器（Handler）
处理事件的函数或方法。

**特点**：
- 接收一个事件参数
- 不返回值（或者返回不重要）
- 不应该抛出异常（异常要自己处理）

---

## 三、游戏中的典型事件

### 3.1 游戏流程事件
- GameStartedEvent：游戏开始
- TurnStartedEvent：回合开始
- TurnEndedEvent：回合结束
- GameEndedEvent：游戏结束

### 3.2 城市相关事件
- CityDevelopedEvent：城市被发展
- CityRecruitedEvent：城市征兵
- CityCapturedEvent：城市被占领
- CityLostEvent：城市丢失

### 3.3 军事相关事件
- ArmyMarchedEvent：军队出发
- ArmyArrivedEvent：军队到达
- BattleStartedEvent：战斗开始
- BattleEndedEvent：战斗结束
- GeneralCapturedEvent：将领被俘

### 3.4 资源相关事件
- GoldChangedEvent：金钱变化
- FoodChangedEvent：粮草变化
- MoraleChangedEvent：士气变化

### 3.5 外交相关事件
- MessageSentEvent：消息发送
- MessageReceivedEvent：消息接收
- RumorSpreadEvent：流言散布

---

## 四、实现模式

### 4.1 简单实现
```python
class EventBus:
    def __init__(self):
        self._handlers: Dict[Type[GameEvent], List[Callable]] = defaultdict(list)
    
    def subscribe(self, event_type: Type[GameEvent], handler: Callable):
        self._handlers[event_type].append(handler)
    
    def publish(self, event: GameEvent):
        for handler in self._handlers[type(event)]:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"事件处理器出错: {e}")
```

### 4.2 注意事项

#### 事件顺序
- 同一事件的多个处理器，执行顺序不保证
- 如果有顺序依赖，要显式处理

#### 异常处理
- 一个处理器出错不应该影响其他处理器
- 每个处理器都要catch异常
- 记录错误日志

#### 无限循环
- 事件处理器不要发布同类型的事件，可能造成死循环
- 如果需要，加个深度限制

#### 性能
- 事件太多会有性能开销
- 注意事件的粒度，不要太细也不要太粗

---

## 五、在我们项目中的应用

### 5.1 哪些地方用事件

#### 日志系统
- 订阅所有事件
- 记录到日志文件
- 用于回放和调试

#### UI渲染
- 订阅状态变化事件
- 更新界面显示
- 播放动画效果

#### 成就/统计
- 订阅关键事件
- 统计数据
- 解锁成就

#### AI记忆
- 订阅重要事件
- 更新AI的记忆
- 影响后续决策

### 5.2 哪些地方不用事件

#### 核心游戏逻辑
- 战斗结算直接调用，不用事件
- 资源计算直接修改，不用事件
- 原因：核心逻辑要简单直接，事件会增加复杂度

#### 同步调用
- 需要返回值的调用
- 需要等待结果的调用
- 原因：事件是异步的，不适合需要立即返回的场景

---

## 六、事件驱动的坑

### 坑1：事件泛滥
**现象**：什么都做成事件，系统里有几百种事件。

**后果**：
- 没人记得清有哪些事件
- 不知道某个功能会触发哪些事件
- 调试困难

**避坑**：
- 事件粒度要适中
- 不要为了"可能以后有用"就加事件
- 定期清理没用的事件

### 坑2：顺序依赖
**现象**：处理器A必须在处理器B之前执行，但事件总线不保证顺序。

**后果**：
- 有时候正常，有时候不正常
- 很难调试

**避坑**：
- 尽量不要有顺序依赖
- 如果必须有，用优先级或者合并成一个处理器

### 坑3：调试困难
**现象**：出了问题不知道是哪个事件触发的。

**后果**：
- 排查问题困难
- 不知道事件的传递路径

**避坑**：
- 所有事件都打日志
- 记录事件的发布者和处理器
- 有事件追踪工具

### 坑4：性能问题
**现象**：事件太多，处理不过来。

**后果**：
- 游戏卡顿
- 延迟增加

**避坑**：
- 不要什么都做成事件
- 高频事件可以合并
- 异步处理不紧急的事件

---

## 七、对本项目的启示

### 7.1 我们已经做的
✅ 事件总线设计
✅ 事件类型定义
✅ 发布-订阅模式

### 7.2 需要注意的
⚠️ 事件粒度要适中，不要太细也不要太粗
⚠️ 核心逻辑不用事件，保持简单直接
⚠️ 所有事件都要记录日志，便于调试
⚠️ 注意异常处理，一个处理器出错不影响其他

---

> **文档类型**：知识库参考资料
> **原始来源**：Game Design Patterns + Generalist Programmer
> **整理日期**：2026-06-23
