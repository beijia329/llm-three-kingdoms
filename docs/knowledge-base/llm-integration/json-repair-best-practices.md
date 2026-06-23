# json_repair 最佳实践

> 来源：The Neural Base, 2026 + 社区实践总结
> 类型：技术最佳实践
> 项目引用：pitfalls.md 坑4.5、llm-integration.md 输出解析

---

## 一、json_repair 是什么

### 1.1 解决什么问题
LLM输出的JSON经常不标准：
- 尾随逗号
- 单引号
- 缺少引号的key
- 被markdown代码块包裹
- 截断的JSON
- 各种语法错误

json_repair可以自动修复这些问题。

### 1.2 修复成功率
| 场景 | 修复成功率 |
|------|-----------|
| 约束输出（明确要求JSON格式） | 70-85% |
| 原始输出（没有格式要求） | 40-60% |
| 浅层语法错误（尾随逗号、单引号） | 95%+ |
| 深层嵌套结构错误 | 30-50% |

---

## 二、json_repair 的能力边界

### 2.1 能修复的（浅层语法错误）
✅ 尾随逗号：`[1, 2, 3,]` → `[1, 2, 3]`
✅ 单引号：`{'key': 'value'}` → `{"key": "value"}`
✅ 缺少引号的key：`{key: "value"}` → `{"key": "value"}`
✅ 被markdown包裹：````json {...} ```` → 提取JSON
✅ 多余的空白和换行
✅ 简单的截断（如果结构完整）

### 2.2 不能修复的（深层语义错误）
❌ 幻觉key（模型编造不存在的字段）
❌ 类型错误（字符串当数字用）
❌ 逻辑错误（值的范围不对）
❌ 结构完全混乱的JSON
❌ 严重截断导致结构不完整

### 2.3 最危险的：假阳性
**现象**：json_repair返回了"成功"，语法是对的，但语义是错的。

**例子**：
```
# LLM输出（有语法错误，还少了一个必填字段）
{
  "type": "attack",
  "target": "洛阳",
  # troops字段被截断了
}

# json_repair修复后（语法正确，但缺少troops字段）
{
  "type": "attack",
  "target": "洛阳"
}
```

**危害**：
- 你以为解析成功了
- 但实际上数据不完整
- 后面的逻辑会出问题
- 而且很难排查

---

## 三、最佳实践

### 3.1 修复优先，不是 try-catch
**错误做法**：
```python
try:
    data = json.loads(text)
except:
    data = json_repair(text)
```

**正确做法**：
```python
# 直接上修复，因为LLM输出大概率有问题
data = json_repair.repair_json(text)
```

**为什么**：
- 修复优先更快（少一次解析尝试）
- 修复成功率更高
- 代码更简单

### 3.2 修复后必须 Schema 校验
json_repair只保证语法正确，不保证语义正确。

```python
# 1. 修复语法
raw_data = json_repair.repair_json(text)

# 2. Schema校验（Pydantic）
try:
    command = AttackCommand(**raw_data)
except ValidationError as e:
    # 字段缺失、类型错误都会在这里被捕获
    log.error(f"Schema校验失败: {e}")
    return None
```

### 3.3 必须记录修复前后的输出
```python
def parse_output(text: str) -> Command:
    logger.debug(f"原始输出: {text}")
    
    repaired = json_repair.repair_json(text)
    
    if repaired != text:
        logger.info(f"JSON被修复了，原始: {text}, 修复后: {repaired}")
    
    # 继续校验...
```

**为什么重要**：
- 出问题时可以排查
- 统计修复率，优化Prompt
- 发现假阳性问题

### 3.4 不要过度依赖 json_repair
json_repair是最后一道防线，不是万能药。

**优先级**：
1. Prompt写好，让模型输出标准JSON
2. 格式约束明确，要求用markdown代码块
3. 智能提取，从废话里找JSON
4. json_repair修复语法
5. Schema校验语义
6. 业务逻辑校验
7. 重试降级

---

## 四、常见问题与解决方案

### 问题1：模型输出太多废话，JSON藏在中间
**解决方案**：用正则提取JSON部分
```python
import re

def extract_json(text: str) -> str:
    # 尝试匹配markdown代码块
    match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
    if match:
        return match.group(1)
    
    # 尝试匹配第一个{到最后一个}
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group(0)
    
    return text
```

### 问题2：模型输出多个JSON
**解决方案**：取第一个，或者取最大的那个
```python
def find_largest_json(text: str) -> str:
    matches = re.findall(r'\{[^{}]+\}', text)
    if matches:
        return max(matches, key=len)
    return text
```

### 问题3：假阳性（语法对，语义错）
**解决方案**：
- Schema校验（Pydantic）
- 业务逻辑校验
- 记录修复日志，统计假阳性率
- 优化Prompt，减少幻觉

---

## 五、对本项目的启示

### 5.1 我们已经做的
✅ 五层防御体系
✅ json_repair容错
✅ Pydantic Schema校验
✅ 命令合法性校验

### 5.2 需要注意的
⚠️ 必须记录修复前后的输出
⚠️ 警惕假阳性问题
⚠️ 修复优先，不是try-catch
⚠️ 统计修复成功率，持续优化Prompt

---

> **文档类型**：知识库参考资料
> **原始来源**：The Neural Base + 社区实践总结
> **整理日期**：2026-06-23
