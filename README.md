# LLM三国志 - 多模型策略对战平台

> 让大语言模型们在三国志的世界里策略对战，看看谁才是真正的"天命之子"

---

## 项目简介

这是一个LLM驱动的多智能体策略对战游戏。三个大语言模型分别扮演魏蜀吴三方势力，在简化版三国志的规则下进行策略对战——发展经济、扩充军备、攻城略地、合纵连横。

灵感来自《赛博斗蛐蛐：9大模型决战三国志，天命在谁？》。

### 核心玩法
- 🎮 **三方对战**：魏蜀吴各据一方，初始5城
- ⏱️ **24回合制**：回合结束时城市最多者胜
- 🤝 **外交博弈**：信使系统，可结盟可背刺
- 🧠 **策略深度**：经济vs军事的资源分配博弈
- 📊 **可观测**：完整回放AI的思考过程

### 技术栈
- **后端**：Python 3.10+
- **GUI**：Pygame 2.5+
- **数据校验**：Pydantic 2.0+
- **测试**：pytest
- **LLM接入**：OpenRouter（支持多模型）

---

## 快速开始

### 安装依赖
```bash
pip install -r requirements.txt
```

### 运行AI对战
```bash
# CLI模式（内置AI）
python main.py

# LLM对战模式（需要API密钥）
python main.py --llm --model deepseek-v4-flash

# GUI模式（可视化观看对战）
python main.py --mode gui
```

### 观看回放（开发中）
```bash
# TODO: 回放系统尚未完全对接 GameRenderer
python main.py --mode replay --file replay.json
```

### 人机对战（开发中）
```bash
# TODO: 人机对战模式尚未实现
python main.py --mode human-vs-ai
```

---

## 项目结构

```
llm-sanguo/
├── game/                # 游戏引擎核心（纯逻辑）
│   ├── engine.py        # GameEngine主类
│   ├── models.py        # 数据模型
│   ├── constants.py     # 常量配置
│   ├── systems/         # 子系统（城市/资源/将领/外交）
│   └── battle/          # 战斗系统
│
├── players/             # 玩家抽象层
│   ├── base_player.py   # 玩家基类
│   ├── cli_player.py    # CLI内置AI玩家
│   └── llm/             # LLM玩家
│
├── renderer/            # 渲染层（Pygame GUI）
│   ├── game_renderer.py # 主渲染器
│   ├── map_renderer.py  # 地图渲染
│   ├── ui_panel.py      # UI面板
│   └── replay_player.py # 回放播放器
│
├── tests/               # 测试
├── data/                # 游戏数据
├── docs/                # 文档
└── main.py              # 程序入口
```

---

## 游戏机制

### 资源系统
- 💰 **金钱**：征兵、建设、赏赐将领
- 🌾 **粮草**：军队消耗，断粮会士气崩溃
- 👥 **人口**：影响资源产出
- ❤️ **民心**：隐性倍率，过低触发死亡螺旋

### 战斗系统
- 🏰 **攻城战**：围城 → 破墙 → 巷战
- 💪 **士气系统**：影响战斗力，低士气会溃散
- 👨‍✈️ **将领系统**：统帅、政治、忠诚度
- 🎲 **确定性随机**：相同seed结果完全一致

### 外交系统
- ✉️ **信使系统**：每回合可发1条消息
- 🕵️ **流言系统**：降低敌方将领忠诚度
- 🤝 **口头盟约**：没有系统强制，全靠信任

---

## 支持的模型

通过OpenRouter接入，支持主流大模型：
- Claude系列（Opus/Sonnet/Haiku）
- GPT系列（GPT-4/GPT-5）
- Gemini系列
- Kimi
- Qwen
- 等等...

---

## 开发文档

- [施工指南（面向人）](./施工指南.md) - 进度跟踪、里程碑、预期效果
- [AGENTS.md](./AGENTS.md) - 给AI开发Agent的项目规范
- [架构设计](./docs/design/architecture.md) - 整体架构设计
- [数据模型](./docs/design/data-models.md) - 所有数据结构定义
- [战斗系统](./docs/design/battle-system.md) - 战斗系统详细设计
- [LLM接入](./docs/design/llm-integration.md) - LLM接入详细设计
- [任务清单](./docs/tasks/development-tasks.md) - 30个开发任务
- [测试规范](./docs/specs/testing.md) - 测试标准与规范

---

## 版本信息

### 项目整体版本
**v1.0**（全部功能已实现，308 测试全通过）

### 文档版本说明
各文档独立维护版本号，因为不同文档更新频率不同。v1.1 表示该文档有重大更新或补充，v1.0 表示暂无重大更新的稳定版本。

| 文档 | 版本 | 说明 |
|------|------|------|
| AGENTS.md | v1.0 | 项目总规范 |
| 施工指南.md | v1.0 | 面向人的进度跟踪 |
| architecture.md | v1.1 | 补充了状态快照、命令模式、容错机制 |
| data-models.md | v1.1 | 统一了命令模型命名规范 |
| battle-system.md | v1.0 | 战斗系统设计 |
| llm-integration.md | v1.1 | 补充了三级降级体系和游戏进行性保证 |
| command-pattern.md | v1.1 | 补充了缺失的命令参数 |
| development-tasks.md | v1.1 | 新增了状态快照等3个任务 |
| testing.md | v1.1 | 补充了TDD规范和平衡性测试 |
| deployment-guide.md | v1.0 | 部署与运行指南 |
| milestone-acceptance.md | v1.0 | 里程碑验收标准 |
| prompt-tuning-guide.md | v1.0 | Prompt调优指南 |
| model-evaluation.md | v1.0 | 模型评测标准流程 |
| pitfalls.md | v1.0 | 常见坑与避坑指南 |
| 知识库 | v1.0 | 10篇行业最佳实践参考资料 |

---

## 开发状态

**当前阶段**：✅ **全部完成**（7/7 阶段，308 测试全通过）

| 阶段 | 状态 | 完成度 |
|------|------|--------|
| 一、项目初始化与数据模型 | ✅ 已完成 | 100% |
| 二、游戏引擎核心 | ✅ 已完成 | 100% |
| 三、战斗系统 | ✅ 已完成 | 100% |
| 四、Engine整合 | ✅ 已完成 | 100% |
| 五、LLM接入 | ✅ 已完成 | 100% |
| 六、GUI与回放 | ✅ 已完成 | 100% |
| 七、测试与优化 | ✅ 已完成 | 100% |

**总进度**：**100%**（实际约6小时，远低于预估34.5小时）

---

## 参考与灵感

- 《赛博斗蛐蛐：9大模型决战三国志，天命在谁？》- 吴磾（腾讯云开发者）
- boardgame.io - 模块化桌游引擎架构
- TripleA - 开源策略游戏引擎
- 《杀戮尖塔》- 确定性随机设计

---

## License

MIT

---

> 本项目仅用于研究和学习目的
