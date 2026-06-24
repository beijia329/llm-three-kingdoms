# AGENTS.md - 乱斗三国项目开发规范

> **重要**：所有参与本项目的AI Agent必须先阅读此文件，遵守所有规范。
> 本文件是项目的"宪法"，所有开发活动以此为准。

---

## 一、项目概述

### 1.1 项目目标
开发一个LLM驱动的多智能体策略对战游戏。12方势力在184年黄巾之乱背景下，于六角格真实中国地图上进行策略对战。

### 1.2 核心价值
- 从PVE评测转向PVP竞技，考察LLM的策略能力
- 六角格地图+真实三国地理（中国省界矢量底图）
- 势力性格系统驱动差异化AI决策
- 通过信使系统考察外交博弈能力
- 支持GUI可视化，便于观察AI决策过程
- 多模式：纯CLI / GUI / 无限模式

### 1.3 非目标（Out of Scope）
- 不做3D画面、精美特效（Pygame 2D足够）
- 不做联网对战（本地单机即可）
- 不做复杂兵种/科技树
- 不做移动端适配

---

## 二、技术栈

### 2.1 核心技术
| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.10+ | 主开发语言 |
| Pygame | 2.5+ | GUI渲染 |
| Pydantic | 2.0+ | 数据校验 |
| pytest | 7.0+ | 测试框架 |
| json-repair | latest | JSON容错解析 |

### 2.2 LLM接入
- 统一通过 OpenRouter API 接入多模型
- 支持模型：Claude、GPT、Gemini、Kimi、Qwen等
- 异步并发调用，设置超时保护

### 2.3 代码风格
- 遵循 PEP 8
- 使用 type hints，所有函数必须有类型注解
- 文档字符串使用 Google 风格
- 缩进：4个空格
- 行宽：120字符

---

## 三、目录结构

```
llm-sanguo/
├── AGENTS.md                    # 本文件，项目总规范
├── README.md                    # 项目说明（给人看的）
├── requirements.txt             # 依赖清单
│
├── game/                        # 游戏引擎核心（纯逻辑，无UI依赖）
│   ├── __init__.py
│   ├── engine.py                # GameEngine主类
│   ├── models.py                # 数据模型定义
│   ├── constants.py             # 常量配置
│   ├── random.py                # 确定性随机数生成器
│   ├── state_manager.py         # 状态快照管理（时间旅行）
│   ├── state_validator.py       # 状态合法性校验
│   ├── game_logger.py           # 游戏日志与回放
│   ├── event_bus.py             # 事件总线
│   │
│   ├── systems/                 # 子系统
│   │   ├── __init__.py
│   │   ├── resource_system.py   # 资源系统
│   │   ├── city_system.py       # 城市系统
│   │   ├── general_system.py    # 将领系统
│   │   ├── diplomacy_system.py  # 外交系统
│   │   └── map_system.py        # 地图系统
│   │
│   └── battle/                  # 战斗系统（独立模块）
│       ├── __init__.py
│       ├── battle_context.py    # 战斗上下文
│       ├── battle_scheduler.py  # 战斗调度
│       ├── army_movement.py     # 行军系统
│       └── battle_resolver.py   # 战斗结算
│
├── players/                     # 玩家抽象层
│   ├── __init__.py
│   ├── base_player.py           # 玩家基类
│   ├── cli_player.py            # CLI玩家
│   ├── gui_player.py            # GUI玩家
│   └── llm/                     # LLM玩家
│       ├── __init__.py
│       ├── llm_player.py        # LLM玩家主类
│       ├── prompt_builder.py    # Prompt构建器
│       ├── output_parser.py     # 输出解析器
│       ├── memory_manager.py    # 记忆管理器
│       └── llm_client.py        # LLM API客户端
│
├── renderer/                    # 渲染层（Pygame GUI）
│   ├── __init__.py
│   ├── game_renderer.py         # 游戏主渲染器
│   ├── map_renderer.py          # 地图渲染
│   ├── ui_panel.py              # UI面板
│   └── replay_player.py         # 回放播放器
│
├── tests/                       # 测试
│   ├── __init__.py
│   ├── unit/                    # 单元测试
│   │   ├── test_engine.py
│   │   ├── test_battle.py
│   │   ├── test_resource.py
│   │   └── ...
│   ├── integration/             # 集成测试
│   │   ├── test_full_game.py
│   │   └── ...
│   └── conftest.py              # pytest配置
│
├── docs/                        # 文档
│   ├── design/                  # 设计文档
│   ├── tasks/                   # 任务清单
│   └── specs/                   # 详细规格
│
├── data/                        # 游戏数据
│   ├── cities.json              # 城市初始数据
│   ├── generals.json            # 将领数据
│   └── map.json                 # 地图拓扑
│
└── main.py                      # 程序入口
```

---

## 四、编码规范

### 4.1 命名约定
| 类型 | 风格 | 示例 |
|------|------|------|
| 类名 | PascalCase | `GameEngine`, `City` |
| 函数名 | snake_case | `calculate_damage()`, `get_city()` |
| 变量名 | snake_case | `current_turn`, `total_gold` |
| 常量 | UPPER_SNAKE_CASE | `MAX_TURNS`, `BASE_GOLD_PRODUCTION` |
| 私有成员 | _前缀 | `_internal_state`, `_calculate()` |

### 4.2 类型注解
- 所有函数必须有参数类型和返回值类型
- 使用 `from __future__ import annotations` 支持前向引用
- 复杂类型用 `typing` 模块：`List`, `Dict`, `Optional`, `Tuple`

```python
# 正确示例
def attack_city(
    attacker: Army,
    defender: City,
    rng: GameRandom
) -> BattleResult:
    """计算攻城战结果"""
    pass
```

### 4.3 错误处理
- 使用自定义异常类，不要裸raise Exception
- 预期内的错误用返回值或异常，不要用assert
- 日志使用标准logging模块

```python
class GameError(Exception):
    """游戏基础异常"""
    pass

class InvalidCommandError(GameError):
    """无效命令异常"""
    pass
```

### 4.4 测试要求
- 新功能必须配套单元测试
- 核心逻辑测试覆盖率 > 80%
- 每个bug修复必须加回归测试
- 测试用例要覆盖边界条件

---

## 五、架构原则

### 5.1 三层分离（铁律）
1. **Engine层**：纯游戏逻辑，不依赖任何UI库
2. **Player层**：决策抽象，只通过标准接口和Engine交互
3. **Renderer层**：只读状态，做展示，不修改游戏逻辑

**验证方法**：Engine模块的import里不能出现pygame

### 5.2 确定性
- 所有随机数必须通过统一的GameRandom生成
- 相同seed + 相同输入 = 相同结果
- 禁止使用 `random.random()`、`time.time()` 等非确定性来源

### 5.3 事件驱动
- 状态变更通过事件通知
- UI和日志系统订阅事件
- 不要直接轮询状态

### 5.4 模块解耦
- 高内聚，低耦合
- 每个模块有明确的职责边界
- 通过接口通信，不直接持有引用

---

## 六、开发流程

### 6.1 标准开发工作流（五步曲）
每个任务都遵循以下五步，严格执行，不要跳步：

```
探索 → 规划 → 执行 → 验证 → 提交
```

#### 第一步：探索（Explore）
- 先读相关的设计文档
- 看现有代码的实现模式
- 理解任务要解决什么问题
- 确认依赖是否都已完成

**产出**：对任务的清晰理解，知道要改哪些文件

#### 第二步：规划（Plan）
- 列出要创建/修改的文件
- 设计关键函数的签名
- 考虑边界情况和错误处理
- 规划测试用例

**产出**：清晰的实现计划（可以写在脑子里或简单注释）

#### 第三步：执行（Execute）
- 按计划写代码
- 小步前进，写完一个函数就验证一下
- 遵循编码规范
- 不要做计划外的重构

#### 第四步：验证（Verify）
- 跑单元测试，确保都通过
- 跑相关的集成测试
- 检查代码是否符合规范
- 验证边界情况

**验证不通过就回到第三步修改**

#### 第五步：提交（Commit）
- 确认所有测试通过
- 确认代码符合规范
- 确认没有引入不必要的依赖
- 写清晰的提交信息

### 6.2 测试驱动开发（TDD）
**核心逻辑必须遵循TDD**：先写测试，再写实现。

#### TDD三步循环
```
红 → 绿 → 重构
```

1. **红**：先写测试，运行测试，确认失败（因为还没实现）
2. **绿**：写实现代码，让测试通过
3. **重构**：优化代码，保持测试通过

#### 为什么要TDD
- 保证代码可测试（写不出测试说明设计有问题）
- 减少bug（测试覆盖了各种情况）
- 便于重构（有测试兜底，不怕改坏）
- 文档化（测试就是最好的用法说明）

#### 哪些必须TDD
- 战斗系统（伤害计算、士气、战斗流程）
- 资源系统（产出、消耗、民心计算）
- 命令解析器
- 状态合法性校验
- 所有核心算法

#### 哪些可以不用TDD
- GUI渲染（视觉效果，不好测）
- 简单的胶水代码
- 配置和常量

### 6.3 任务执行原则
1. **小步前进**：每个任务不超过2小时工作量
2. **随时验证**：完成一部分就跑一部分测试
3. **不做重构**：除非明确要求，否则不要重构已有代码
4. **不做计划外的事**：只做任务清单里的内容，不要"顺便"改别的

### 6.4 代码提交前检查清单
提交代码前，逐项检查：

**代码质量**
- [ ] 代码符合PEP 8
- [ ] 所有函数有类型注解
- [ ] 关键函数有文档字符串（Google风格）
- [ ] 没有硬编码的密钥或路径
- [ ] 没有引入不必要的依赖

**测试**
- [ ] 新功能有对应的单元测试
- [ ] 所有单元测试通过
- [ ] 测试覆盖了正常情况和边界情况
- [ ] 核心逻辑测试覆盖率 > 80%

**架构**
- [ ] 没有违反三层分离原则
- [ ] Engine层没有import pygame
- [ ] Renderer层没有修改游戏状态
- [ ] 没有破坏确定性（没用random.random()）

**文档**
- [ ] 公共API有文档字符串
- [ ] 复杂逻辑有注释说明
- [ ] 设计文档有更新（如果改了设计）

### 6.5 遇到问题怎么办
1. 先看 `docs/design/` 里的设计文档
2. 再看现有代码的实现模式
3. 查 `docs/pitfalls.md` 里的常见坑
4. 如果还是不确定，记录问题，继续做确定的部分
5. 不要自己瞎猜设计，不确定的地方标注 `TODO: 待确认`

### 6.6 调试技巧
1. **加日志**：关键节点打日志，看数据流向
2. **写测试**：写个最小测试用例复现问题
3. **回退**：用git bisect找哪个提交引入的bug
4. **状态快照**：出问题时保存状态，便于复现
5. **确定性**：固定seed，确保问题可复现

---

## 七、关键设计决策（已确定）


### 7.1 游戏规则
- 12方势力（184年黄巾之乱），初始22城
- 192回合制（每回合=1季度，184→232年），无限模式可选
- 六角格真实中国地图（120×90），省界矢量底图
- 每回合每方可发1条外交消息
- 控3城称王，5城称帝，历史国号+Buff/Debuff

### 7.2 核心资源
- 金钱、粮草、人口、民心
- 民心是经济的隐性倍率

### 7.3 战斗系统
- 攻城战：围城 → 破墙 → 巷战
- 士气系统：影响战斗力，低士气会溃散
- 将领系统：忠诚度、统帅、政治属性

### 7.4 LLM接入
- Prompt四要素：角色+目标+规则+格式
- 思维链引导：先分析再决策
- 五层输出防御：Prompt约束→语法约束→智能提取→Schema校验→重试降级
- 三级降级体系：重试→空命令→随机AI

### 7.5 状态管理
- 命令模式：所有玩家输入都是Command对象
- 三层校验（VAP）：语法层→Schema层→业务层
- 状态快照：每回合保存完整状态，支持回滚
- 状态合法性校验：每回合验证状态一致性

### 7.6 容错与兜底
- 游戏必须能运行到结束，任何组件失败都不能导致崩溃
- LLM连续失败自动降级为随机AI
- 异常隔离：一个玩家出错不影响其他玩家
- 最大回合数保证：24回合强制结束

### 7.7 日志与回放
- 结构化游戏日志：所有命令和事件都要记录
- 支持完整回放：可以从头到尾复现一局游戏
- LLM输入输出都要记录，便于调试和Prompt优化

---

## 八、相关文档索引

### 设计文档
| 文档 | 位置 | 说明 |
|------|------|------|
| 架构设计 | docs/design/architecture.md | 整体架构设计 |
| 数据模型 | docs/design/data-models.md | 所有数据结构定义 |
| 战斗系统 | docs/design/battle-system.md | 战斗系统详细设计 |
| LLM接入 | docs/design/llm-integration.md | LLM接入详细设计 |
| Command模式 | docs/design/command-pattern.md | 命令模式与VAP协议 |

### 规范与指南
| 文档 | 位置 | 说明 |
|------|------|------|
| 任务清单 | docs/tasks/development-tasks.md | 分阶段任务清单 |
| 测试规范 | docs/specs/testing.md | 测试规范与标准 |
| 部署指南 | docs/specs/deployment-guide.md | 安装与运行指南 |
| Prompt调优 | docs/specs/prompt-tuning-guide.md | Prompt优化指南 |
| 模型评测 | docs/specs/model-evaluation.md | 模型评测标准流程 |
| 里程碑验收 | docs/specs/milestone-acceptance.md | 各阶段验收标准 |

### 其他
| 文档 | 位置 | 说明 |
|------|------|------|
| 常见坑 | docs/pitfalls.md | 常见问题与避坑指南 |
| 知识库 | docs/knowledge-base/ | 行业最佳实践参考资料 |
| 施工指南 | 施工指南.md | 面向人的进度跟踪（给人看的） |

---

> **最后更新**：2026-06-24
> **维护者**：项目架构师
> **版本**：v2.2
> **v2.2更新**：马腾势力修复、势力城数平衡、GameState字段补齐、邻居双向连接、建国Buff接入、信息迷雾优化
> **v2.1更新**：Web前端迁移（FastAPI+React+PixiJS）、玻璃拟态UI、DOM Overlay地图、Playwright测试
> **v2.0更新**：六角格地图+12方势力+184年剧本+性格系统+建国机制+文明风格GUI
> **v1.1更新**：补充状态管理、容错兜底、日志回放等设计决策；更新目录结构；完善文档索引
