# LLM输出解析五层防御体系

> 来源：CSDN博客 + 腾讯云开发者社区 + 行业实践总结
> 类型：技术最佳实践
> 项目引用：llm-integration.md 输出解析、architecture.md 可验证动作协议

---

## 一、为什么需要防御体系

### 1.1 LLM输出的不可靠性
LLM输出不是API，不能指望它每次都返回标准格式：
- 有时候输出废话
- 有时候格式不对
- 有时候字段缺失
- 有时候值的范围不对
- 有时候逻辑错误

### 1.2 防御深度原则
不能只靠一层防御，要多层叠加：
- 每一层都可能漏掉一些问题
- 多层叠加，漏网之鱼就少了
- 某一层失效了，还有下一层兜底

---

## 二、五层防御体系

### 第一层：Prompt 约束
**目标**：从源头减少错误输出。

**方法**：
- 明确告诉模型输出什么格式
- 给出具体的例子
- 强调"只输出JSON，不要其他内容"
- 列出所有合法的命令类型

**效果**：减少60-70%的格式错误

**局限性**：
- 模型不一定听话
- 复杂场景下还是会出错
- 不同模型的听话程度不一样

---

### 第二层：语法约束
**目标**：确保输出是合法的JSON。

**方法**：
- 从废话里提取JSON（正则）
- 修复语法错误（json_repair）
- 处理截断、尾随逗号、单引号等

**效果**：修复70-85%的语法错误

**局限性**：
- 只能保证语法正确
- 不能保证语义正确
- 有假阳性风险（语法对，语义错）

---

### 第三层：Schema 校验
**目标**：确保数据结构正确。

**方法**：
- 用Pydantic/Zod等Schema校验库
- 检查字段是否存在
- 检查字段类型是否正确
- 检查枚举值是否合法

**效果**：捕获90%以上的结构错误

**局限性**：
- 只能检查结构
- 不能检查业务逻辑
- 比如troops=1000000，Schema校验通过，但业务上不合理

---

### 第四层：业务逻辑校验
**目标**：确保命令在游戏中是可行的。

**方法**：
- 检查资源是否足够
- 检查目标是否存在
- 检查距离是否可达
- 检查是否在冷却中
- 等等...

**效果**：捕获大部分逻辑错误

**局限性**：
- 实现成本高
- 可能漏掉一些边缘情况
- 需要游戏逻辑支持

---

### 第五层：重试与降级
**目标**：前面都失败了，也要优雅处理。

**方法**：
- 解析失败，让模型重新输出
- 重试2-3次
- 还是失败，返回默认命令（空操作）
- 记录错误日志，便于排查

**效果**：保证系统不会崩溃

**局限性**：
- 增加延迟（每次重试都要等）
- 增加成本（每次重试都要花钱）
- 降级后AI表现变差

---

## 三、各层详细实现

### 3.1 Prompt约束层
```python
SYSTEM_PROMPT = """
你是三国时期的军师，为你的势力出谋划策。

## 输出格式
你必须只输出一个JSON对象，不要任何其他内容。
JSON格式如下：

{
  "command": "attack",  // 命令类型：develop/recruit/attack/reward/explore/message/rumor
  "params": {
    // 命令参数，根据命令类型不同而不同
  }
}

## 命令说明
- develop: 发展城市，params: { "city": "城市名", "type": "economy/military/culture" }
- recruit: 征兵，params: { "city": "城市名", "troops": 数量 }
- attack: 进攻，params: { "from": "出发城市", "to": "目标城市", "troops": 数量 }
- ...

## 例子
{
  "command": "attack",
  "params": {
    "from": "许昌",
    "to": "洛阳",
    "troops": 5000
  }
}

记住：只输出JSON，不要解释，不要废话。
"""
```

### 3.2 语法约束层
```python
import re
import json_repair

def extract_and_repair(text: str) -> dict:
    # 1. 尝试提取markdown代码块里的JSON
    match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
    if match:
        text = match.group(1)
    
    # 2. 尝试提取第一个{到最后一个}
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        text = match.group(0)
    
    # 3. 修复语法
    return json_repair.repair_json(text)
```

### 3.3 Schema校验层
```python
from pydantic import BaseModel, Field, ValidationError
from enum import Enum

class CommandType(str, Enum):
    DEVELOP = "develop"
    RECRUIT = "recruit"
    ATTACK = "attack"
    # ...

class AttackParams(BaseModel):
    from_city: str = Field(alias="from")
    to_city: str = Field(alias="to")
    troops: int = Field(gt=0, le=100000)

class Command(BaseModel):
    command: CommandType
    params: dict
```

### 3.4 业务逻辑校验层
```python
def validate_command(command: Command, game_state: GameState) -> bool:
    # 检查城市是否存在
    if command.params.get("city") not in game_state.cities:
        return False
    
    # 检查资源是否足够
    if command.type == "recruit":
        cost = command.params.troops * RECRUIT_COST
        if game_state.gold < cost:
            return False
    
    # 检查距离是否可达
    if command.type == "attack":
        distance = get_distance(command.params.from_city, command.params.to_city)
        if distance > MAX_MARCH_DISTANCE:
            return False
    
    return True
```

### 3.5 重试与降级层
```python
def get_command_with_retry(llm_client, prompt, max_retries=3):
    for i in range(max_retries):
        try:
            output = llm_client.call(prompt)
            command = parse_output(output)
            if command is not None:
                return command
        except Exception as e:
            logger.warning(f"第{i+1}次尝试失败: {e}")
    
    # 降级：返回空命令
    logger.error(f"重试{max_retries}次都失败了，返回空命令")
    return EmptyCommand()
```

---

## 四、可验证动作协议（VAP）

### 4.1 什么是VAP
将LLM的自然语言输出，通过多层校验，转化为游戏引擎可以安全执行的指令。

### 4.2 三层校验
1. **语法层**：是不是合法的JSON
2. **Schema层**：字段对不对、类型对不对
3. **业务层**：在当前游戏状态下能不能执行

### 4.3 好处
- 安全：LLM不能执行非法操作
- 稳定：不会因为输出格式错而崩溃
- 可调试：哪一层失败了一目了然
- 可统计：可以统计各层的失败率

---

## 五、对本项目的启示

### 5.1 我们已经做的
✅ 五层防御体系
✅ Prompt约束
✅ json_repair语法修复
✅ Pydantic Schema校验
✅ 命令合法性校验
✅ 重试降级

### 5.2 需要注意的
⚠️ 每一层都要记录日志，便于统计和调试
⚠️ 警惕json_repair的假阳性
⚠️ 业务校验要全面，不仅检查资源，还要检查距离、状态等
⚠️ 重试次数不要太多，避免成本过高

---

> **文档类型**：知识库参考资料
> **原始来源**：CSDN博客 + 腾讯云开发者社区 + 行业实践
> **整理日期**：2026-06-23
