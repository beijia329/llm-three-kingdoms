# ADR-0003 LLM 输出五层防御（解析与校验）

- **状态**：Accepted（已落地，players/llm/output_parser.py 实现）
- **日期**：2026-06-24（记录于 Phase 5→6 收口）
- **相关**：llm-integration.md 第三章、command-pattern.md 四、players/llm/output_parser.py、players/llm/llm_player.py

---

## 背景（Context）

LLM 输出不可控：可能包裹 markdown 代码块、用单引号代替双引号、留尾随逗号、前后夹解释文字、被截断、字段缺失/类型错、甚至逻辑非法（攻击自己的城市、资源不足还征兵）。系统必须"尽量从垃圾输出中提取有效命令"，且**非法命令绝不能污染游戏状态**。

设计目标（llm-integration.md 3.7）：无论 LLM 多低能，游戏必须正常进行到结束。

---

## 决策（Decision）

采用**五层防御管线**（`players/llm/output_parser.py` 的 `parse_commands` / `validate_command` / `filter_commands`）：

| 层 | 机制 | 实现位置 |
|----|------|---------|
| L1 Prompt 约束（预防） | 强调"只输出 JSON"、给示例 | `prompt_builder.py` |
| L2 语法约束 | `json.loads` 直接解析 → 提取 ```json 代码块 → 正则提取最外层 `[]`/`{}` | `output_parser.py` |
| L3 智能提取 | `json_repair.repair_json` 修复单引号/尾随逗号/注释 | `output_parser.py` |
| L4 Schema 校验 | 检查命令类型合法、必填参数齐全、数值 > 0、`develop type` 枚举合法 | `OutputParser.validate_command` |
| L5 重试+降级 | 解析失败把错误回灌 LLM 重试（最多 2 次）；仍失败则空命令/随机 AI | `llm_player.py`（见 ADR-0004） |

- **多命令"部分通过"**：`filter_commands` 只保留合法命令，非法丢弃并记日志，合法命令照常执行（不因一条坏命令丢弃整批）。
- **与 VAP 三层校验对齐**：L2–L4 对应命令模式里的"语法层 → Schema 层 → 业务层"；但**深层业务合法性**（资源够不够、城市存不存在、是否打自己）由 Engine 在 `execute_commands` 时做最终拦截，不在 Parser 内完成。

---

## 后果（Consequences）

**正面**
- 解析成功率目标 >95%；非法输出被隔离，游戏状态不被污染。
- 宽容解析兼容主流模型的各种"啰嗦"输出；降级可控（ADR-0004）。

**负面**
- `json_repair` 可能把截断文本"修出"一个语义错误的合法 JSON（如补默认值时方向跑偏），需依赖 L4 + Engine 业务校验兜底。
- 重试增加 token 成本与单回合延迟（指数退避 1s→2s）。
- L4 仅做结构/枚举校验，深层业务合法性仍依赖 Engine，两层命名需对开发者清晰（见下"术语缺口"）。

---

## 备选方案（Alternatives Considered）

| 方案 | 结论 |
|------|------|
| 强制 JSON Mode / Function Calling | 更稳，但绑定特定模型，不支持的模型要跳过（已作为 L2 可选增强，非唯一路径） |
| `eval` / `ast.literal_eval` 直接执行 | 高危注入，否决 |
| 解析失败即崩溃 | 违反 LLM 游戏容错铁律，否决 |

---

## 术语缺口（待统一，建议并入文档对账）

- `command-pattern.md` 把 VAP 写成"语法层 / 业务静态层 / 业务动态层"，而 `llm-integration.md` 用"五层防御"。两者描述的是同一套校验但**命名体系不一致**，易让新成员困惑。建议在某一文档/ADR 中明确映射：五层防御（L2–L4）= VAP 的语法+Schema 层，业务动态层 = Engine 执行期校验。
