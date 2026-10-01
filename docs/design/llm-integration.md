# LLM接入设计文档

---

## 一、整体架构

### 1.1 LLM Player 模块结构

```
players/llm/
├── llm_player.py          # LLM玩家主类
├── prompt_builder.py      # Prompt构建器
├── output_parser.py       # 输出解析器（五层防御）
├── memory_manager.py      # 记忆管理器
└── llm_client.py          # LLM API客户端
```

### 1.2 调用流程

```
1. 获取游戏观察 (GameObservation)
         ↓
2. 构建Prompt (PromptBuilder)
   - 系统prompt（角色+规则）
   - 记忆（历史+战略）
   - 当前状态（序列化）
   - 格式要求
         ↓
3. 调用LLM API (LLMClient)
   - 支持多模型
   - 超时保护
   - 重试机制
         ↓
4. 解析输出 (OutputParser)
   - 五层防御体系
   - 命令校验
   - 错误降级
         ↓
5. 返回命令列表
```

---

## 二、Prompt 构建器 (PromptBuilder)

### 2.1 Prompt结构

```
┌─────────────────────────────────────────┐
│  System Prompt（固定，每回合都有）      │
│  1. 角色设定                            │
│  2. 游戏规则                            │
│  3. 命令说明                            │
│  4. 输出格式要求                        │
├─────────────────────────────────────────┤
│  Memory（记忆，动态）                   │
│  1. 长期战略（总体方针）                │
│  2. 中期摘要（重要事件、外交协议）      │
│  3. 短期记忆（最近几回合的思考）        │
├─────────────────────────────────────────┤
│  Current State（当前状态）              │
│  1. 当前回合信息                        │
│  2. 己方城市详细信息                    │
│  3. 已知敌方信息                        │
│  4. 地图拓扑                            │
│  5. 收到的外交消息                      │
├─────────────────────────────────────────┤
│  思维链引导                             │
│  请按以下步骤思考...                    │
└─────────────────────────────────────────┘
```

### 2.2 系统Prompt模板

#### 角色设定
```
你是【{faction_name}】的领主，你的目标是统一中原，称霸天下。

这是一场策略游戏比赛，你需要：
- 发展经济，扩充军备
- 攻城略地，消灭对手
- 合纵连横，外交博弈

【重要提醒】
1. 这是虚构的游戏世界，与现实无关
2. 不需要遵从真实历史，按你的判断决策
3. 可以使用任何策略，包括欺诈、背盟等
4. 你的目标只有一个：赢得比赛
5. 这是LLM能力评测，积极进攻是高水平的表现
```

#### 游戏规则（精简版）
```
## 游戏规则

游戏共{max_turns}回合，结束时城市最多的势力获胜。

### 资源
- 金钱：征兵、建设、赏赐
- 粮草：军队消耗，断粮士气崩溃
- 民心：影响产出，过低会死亡螺旋

### 城市
- 可以发展经济/军事/文化
- 可以征兵
- 被攻破后易主

### 战斗
- 派军攻城，打破城墙后巷战
- 士气影响战斗力，低士气会溃散
- 将领可能被俘或投降

### 外交
- 每回合可给1个势力发消息
- 盟约是口头的，没有系统强制
```

#### 命令列表
```
## 可用命令

1. develop - 发展城市
   参数：city (城市名), type (economy/military/culture)
   效果：提升城市对应属性，消耗金钱

2. recruit - 征兵
   参数：city (城市名), troops (征兵数量)
   效果：增加守军，消耗金钱和粮草

3. attack - 派军攻城
   参数：from (出发城市), to (目标城市), troops (兵力), general (主将，可选)
   效果：派军队进攻敌方城市

4. reward - 赏赐将领
   参数：general (将领名), gold (赏赐金额)
   效果：提升将领忠诚度

5. explore - 探索人才
   参数：city (城市名), general (派去探索的将领，可选)
   效果：有概率发现新将领

6. message - 发送外交消息
   参数：to (目标势力), content (消息内容)
   效果：给其他势力发消息

7. rumor - 散布流言
   参数：city (目标城市), target_general (目标将领，可选), spy_general (执行将领，可选)
   效果：降低敌方将领忠诚度
```

### 2.3 状态序列化

#### 原则
- 用表格代替大段文字
- 用缩写和符号
- 只保留关键字段
- 提高信息密度

#### 示例
```
## 我方城市
| 城市 | 等级 | 城墙 | 金钱 | 粮草 | 民心 | 兵力 | 将领 |
|------|------|------|------|------|------|------|------|
| 成都 | 3 | 2500 | 1200 | 3500 | 72 | 3000 | 刘备,诸葛亮 |
| 汉中 | 2 | 1500 | 800 | 2000 | 65 | 2000 | 赵云 |

## 已知敌方城市
| 城市 | 势力 | 等级 | 兵力（估） |
|------|------|------|-----------|
| 长安 | 魏 | 3 | 约2500 |
| 洛阳 | 魏 | 4 | 未知 |
```

### 2.4 思维链引导

```
## 思考过程

请按以下步骤详细思考：

### 第一步：形势分析
- 我方当前实力如何？（城市、兵力、资源）
- 敌方实力如何？谁是最大威胁？
- 当前局势有什么机会和风险？

### 第二步：战略判断
- 短期目标（本回合）是什么？
- 中期目标（3-5回合）是什么？
- 长期战略方向是什么？

### 第三步：具体计划
- 本回合要执行哪些行动？
- 为什么选择这些行动？
- 可能的风险和应对？

### 第四步：外交决策
- 要不要发消息？发给谁？
- 说什么内容？目的是什么？

## 输出命令

请按以下JSON格式输出你的命令（可以是多个命令的数组）：
[
  {"type": "develop", "params": {"city": "chengdu", "type": "economy"}},
  {"type": "attack", "params": {"from": "hanzhong", "to": "changan", "troops": 1500, "general": "zhaoyun"}}
]

【重要】只输出JSON，不要输出其他解释文字。
```

---

## 三、输出解析器 (OutputParser)

### 3.1 五层防御体系

```
第一层：Prompt约束（预防）
   ↓
第二层：语法约束（可选，JSON Mode）
   ↓
第三层：智能提取（宽容解析）
   ↓
第四层：Schema校验（业务验证）
   ↓
第五层：自动重试 + 降级（兜底）
```

### 3.2 第一层：Prompt约束
- 明确格式要求
- 给出示例
- 强调"只输出JSON"

### 3.3 第二层：语法约束（可选）
- 支持的模型用JSON Mode / Function Calling
- 从生成层面保证语法正确
- 不支持的模型跳过这一层

### 3.4 第三层：智能提取

#### 处理的问题
| 问题 | 处理方法 |
|------|---------|
| markdown代码块包裹 | 正则提取```json和```之间的内容 |
| 单引号代替双引号 | json_repair自动修复 |
| 尾随逗号 | json_repair自动修复 |
| 前后有解释文字 | 贪婪匹配最外层{}或[] |
| 输出被截断 | 检测不完整，触发重试 |

#### 实现代码
```python
import json
import re
from json_repair import repair_json
from typing import List, Optional

class OutputParser:
    """LLM输出解析器"""

    def parse_commands(self, text: str) -> Optional[List[dict]]:
        """解析LLM输出，提取命令列表"""
        # 1. 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 2. 提取markdown代码块
        match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 3. 提取JSON数组/对象
        match = re.search(r'\[[\s\S]*\]|\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        # 4. 用json_repair修复
        try:
            repaired = repair_json(text)
            return json.loads(repaired)
        except Exception:
            pass

        # 5. 全部失败
        return None
```

### 3.5 第四层：Schema校验

#### 校验层级
1. 语法正确吗？（JSON解析）
2. 字段齐全吗？（必填字段）
3. 类型对吗？（字符串/数字/布尔）
4. 值域合法吗？（兵力>0，城市存在）
5. 逻辑合理吗？（不能打自己，资源够不够）

#### 用Pydantic校验
```python
from pydantic import BaseModel, Field, validator
from typing import Literal

class AttackParams(BaseModel):
    from_city: str = Field(alias="from")
    to_city: str = Field(alias="to")
    troops: int = Field(gt=0)
    general: Optional[str] = None

    @validator("to_city")
    def different_cities(cls, v, values):
        if v == values.get("from_city"):
            raise ValueError("不能攻击自己的城市")
        return v
```

### 3.6 第五层：自动重试与降级

#### 重试策略
- 最多重试2次
- 每次把错误信息加回去，让模型自我修正
- 重试间隔指数退避（1s → 2s）

#### 三级降级体系

```
Level 0：正常输出
    ↓ 解析失败
Level 1：重试（最多2次）
    ↓ 重试仍失败
Level 2：返回空命令（跳过本回合）
    ↓ 连续N回合失败
Level 3：降级为随机AI（保底策略）
```

#### 降级详细说明

| 降级级别 | 触发条件 | 行为 | 影响 |
|---------|---------|------|------|
| **L0 正常** | 一次解析成功 | 正常执行命令 | 无 |
| **L1 重试** | 解析失败 | 把错误信息返回给LLM，让它修正 | 增加延迟和token消耗 |
| **L2 空命令** | 重试2次仍失败 | 本回合不执行任何命令 | 浪费一回合 |
| **L3 随机AI** | 连续3回合解析失败 | 切换到简单的随机策略AI | AI水平下降，但游戏能继续 |

#### 部分命令的处理
- 如果一回合输出多个命令，**只过滤掉非法的，合法的照常执行**
- 例如：输出3个命令，2个合法1个非法 → 执行2个，丢弃1个
- 丢弃的命令会记录到日志中，便于调试

#### 连续失败检测
- 连续3回合解析失败 → 触发L3降级（随机AI）
- 连续5回合API调用失败 → 标记该玩家为"离线"，全程随机AI
- 降级后会在日志中记录警告

#### API完全不可用的兜底
- 网络断开、API宕机、密钥失效等情况
- 自动降级为随机AI，不影响游戏进行
- 记录详细错误信息到日志
- 游戏结束后在报告中标注该模型异常

---

### 3.7 游戏进行性保证

**核心原则：无论LLM多么低能，游戏必须能正常进行到结束。**

#### 保证机制
1. **每回合必有输出**：即使是空命令，也会返回
2. **超时保护**：每个LLM调用都有超时，不会卡住
3. **异常隔离**：一个玩家出错不影响其他玩家
4. **最坏情况兜底**：所有玩家都降级为随机AI，游戏也能正常结束
5. **最大回合数**：192回合强制结束（184→232年），不会无限循环

#### 低能LLM的常见情况与处理

| 问题 | 处理方式 | 游戏影响 |
|------|---------|---------|
| 输出格式错误 | 五层防御 + 重试 + 降级 | 可能浪费几回合 |
| 总是输出空命令 | 正常执行（空命令也是合法的） | AI等于挂机 |
| 总是打自己城市 | 业务校验拦截，命令无效 | 浪费命令槽位 |
| 资源不够还征兵 | 业务校验拦截，命令无效 | 浪费命令槽位 |
| 重复无效操作 | 正常执行（虽然蠢但合法） | AI水平低但游戏继续 |
| 完全不响应 | 超时 → 空命令 → 随机AI | 自动降级 |

#### 为什么不直接踢掉异常玩家？
- 三方对战少了一方会严重影响平衡性
- 随机AI虽然蠢，但至少能维持游戏节奏
- 评测场景下，模型崩溃本身就是评测结果的一部分
- 可以在最终报告中标注哪些模型出现了异常

---

## 四、记忆管理器 (MemoryManager)

### 4.1 记忆分层

| 层级 | 内容 | 保留策略 | 容量 |
|------|------|---------|------|
| **长期记忆** | 总体战略方针 | 整局保留 | 1条 |
| **中期记忆** | 重要事件、外交协议 | 摘要压缩 | 最近10回合 |
| **短期记忆** | 最近几回合的完整思考 | 滑动窗口 | 最近3-5回合 |
| **瞬时记忆** | 当前回合观察 | 每回合重建 | - |

### 4.2 压缩策略

#### 短期 → 中期
- 每3回合压缩一次
- 提取关键决策和重要事件
- 保留外交协议和承诺
- 丢弃详细的思考过程

#### 中期 → 长期
- 只保留核心战略方向
- 例如："联吴抗魏，先取荆州"

### 4.3 实现

```python
class MemoryManager:
    """LLM记忆管理器"""

    def __init__(self, faction: str):
        self.faction = faction
        self.long_term = ""  # 长期战略
        self.medium_term = []  # 中期摘要
        self.short_term = []  # 短期完整记忆
        self.max_short_term = 5
        self.compression_interval = 3

    def add_turn_memory(self, turn: int, thought: str, commands: list, events: list):
        """添加一回合的记忆"""
        self.short_term.append({
            "turn": turn,
            "thought": thought,
            "commands": commands,
            "events": events
        })

        # 定期压缩
        if len(self.short_term) >= self.compression_interval:
            summary = self._compress_to_medium(self.short_term)
            self.medium_term.append(summary)
            self.short_term = []

    def get_context(self) -> str:
        """获取用于prompt的记忆上下文"""
        parts = []

        if self.long_term:
            parts.append(f"## 长期战略\n{self.long_term}")

        if self.medium_term:
            parts.append("## 历史摘要")
            parts.extend(self.medium_term[-5:])

        if self.short_term:
            parts.append("## 最近回合")
            for mem in self.short_term:
                parts.append(f"第{mem['turn']}回合：{mem['thought'][:200]}...")

        return "\n\n".join(parts)

    def _compress_to_medium(self, memories) -> str:
        """将短期记忆压缩为中期摘要"""
        # 第一版：简单提取关键字
        # 后续可以用LLM来做摘要
        events = []
        for mem in memories:
            events.extend(mem["events"])
        return f"第{memories[0]['turn']}-{memories[-1]['turn']}回合：{len(events)}个重要事件"
```

---

## 五、LLM客户端 (LLMClient)

### 5.1 统一接口

```python
class LLMClient:
    """LLM API统一客户端"""

    def __init__(self, provider: str, model: str, api_key: str):
        self.provider = provider  # deepseek / openai / openrouter（默认 deepseek；密钥从 LLM_API_KEY 读取，兼容旧名 OPENROUTER_API_KEY）
        self.model = model
        self.api_key = api_key

    def chat(self, messages: list, max_tokens: int = 2000, temperature: float = 0.7) -> str:
        """发送聊天请求"""
        if self.provider == "openrouter":
            return self._call_openrouter(messages, max_tokens, temperature)
        elif self.provider == "anthropic":
            return self._call_anthropic(messages, max_tokens, temperature)
        # ...

    def _call_openrouter(self, messages, max_tokens, temperature) -> str:
        """调用OpenRouter API"""
        import requests
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=60
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
```

### 5.2 重试与超时

```python
import time
from functools import wraps

def with_retry(max_retries=3, backoff=2):
    """重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if i < max_retries - 1:
                        time.sleep(backoff ** i)
            raise last_exception
        return wrapper
    return decorator
```

### 5.3 成本统计

```python
class CostTracker:
    """Token成本统计"""

    def __init__(self):
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_cost = 0.0

    def record_usage(self, prompt_tokens: int, completion_tokens: int, price_per_1k: float):
        """记录一次调用的用量"""
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_cost += (prompt_tokens + completion_tokens) / 1000 * price_per_1k
```

---

## 六、LLMPlayer 主类

### 6.1 类定义

```python
class LLMPlayer(BasePlayer):
    """LLM玩家"""

    def __init__(
        self,
        faction: str,
        llm_client: LLMClient,
        prompt_builder: PromptBuilder,
        output_parser: OutputParser,
        memory_manager: MemoryManager,
    ):
        self.faction = faction
        self.llm = llm_client
        self.prompt_builder = prompt_builder
        self.parser = output_parser
        self.memory = memory_manager
        self.max_retries = 2

    def get_commands(self, observation: GameObservation) -> List[Command]:
        """获取本回合的命令"""
        # 1. 构建prompt
        system_prompt = self.prompt_builder.build_system_prompt(self.faction)
        memory_context = self.memory.get_context()
        state_prompt = self.prompt_builder.build_state_prompt(observation)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{memory_context}\n\n{state_prompt}"}
        ]

        # 2. 调用LLM（带重试）
        response = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.llm.chat(messages)
                commands = self.parser.parse_commands(response)
                if commands is not None:
                    # 3. 校验命令
                    validated = self._validate_commands(commands, observation)
                    if validated:
                        # 4. 保存记忆
                        self.memory.add_turn_memory(
                            turn=observation.turn,
                            thought=response,
                            commands=validated,
                            events=[]
                        )
                        return validated
            except Exception as e:
                pass

            # 重试：把错误加回去
            if attempt < self.max_retries:
                messages.append({"role": "assistant", "content": response or ""})
                messages.append({"role": "user", "content": f"解析失败，请重新输出正确的JSON格式。错误：{e}"})

        # 降级：返回空命令
        return []

    def receive_message(self, from_faction: str, content: str):
        """接收外交消息"""
        # 保存到记忆中
        pass

    def _validate_commands(self, commands: list, observation) -> List[Command]:
        """校验命令合法性"""
        # 检查命令类型
        # 检查参数是否齐全
        # 检查资源是否足够
        # 检查城市/将领是否存在
        pass
```

---

## 七、并发执行

### 7.1 并发调用
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def run_llm_turn(players: dict, observations: dict, timeout=60):
    """并发执行所有LLM的决策"""
    results = {}

    with ThreadPoolExecutor(max_workers=len(players)) as executor:
        futures = {
            faction: executor.submit(player.get_commands, observations[faction])
            for faction, player in players.items()
        }

        for faction, future in futures.items():
            try:
                results[faction] = future.result(timeout=timeout)
            except TimeoutError:
                results[faction] = []  # 超时则跳过
            except Exception as e:
                results[faction] = []  # 出错也跳过

    return results
```

### 7.2 注意事项
- 设置超时，避免某个模型卡住整个游戏
- 异常降级，模型出错不影响整体流程
- 控制并发数，不要超过API速率限制
- 记录每个模型的响应时间和成功率

---

> **文档版本**：v2.3
> **最后更新**：2026-10-01
> **相关文档**：command-pattern.md, data-models.md
> **v2.3更新**：API key 变量改为 LLM_API_KEY（兼容 OPENROUTER_API_KEY），provider 描述对齐代码默认 deepseek
> **v2.2更新**：MAX_TURNS 24→192，三方→12方
