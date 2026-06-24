# 知识库 - 乱斗三国项目

> 本文件夹收录了项目开发过程中参考的所有行业资料、最佳实践和技术文档。
> 所有设计决策都有对应的参考依据，不是凭空捏造。

---

## 📚 知识库结构

```
knowledge-base/
├── README.md              # 本文件，总索引
├── references.md          # 参考文献总列表（含引用标注）
│
├── ai-development/        # AI辅助开发方法论
│   ├── vibe-coding-sdlc.md
│   └── agents-md-best-practices.md
│
├── game-architecture/     # 游戏架构设计
│   ├── boardgame-io-architecture.md
│   ├── deterministic-game-design.md
│   └── event-driven-architecture.md
│
├── llm-integration/       # LLM集成技术
│   ├── json-repair-best-practices.md
│   └── llm-output-parsing-defense.md
│
├── testing/               # 测试与平衡性
│   ├── monte-carlo-balance-testing.md
│   └── game-balance-methodology.md
│
└── multi-agent/           # 多智能体系统
    └── multi-agent-architecture.md
```

---

## 🎯 如何使用知识库

### 1. 想了解某个设计决策的依据
先看 `references.md`，搜索相关关键词，找到对应的参考资料。

### 2. 想深入学习某个领域
直接进入对应的子目录，阅读完整的参考资料摘要。

### 3. 想复核设计是否合理
对比参考资料中的最佳实践，检查我们的设计是否符合行业标准。

---

## 📋 核心参考来源

| 领域 | 核心参考 | 对项目的影响 |
|------|---------|-------------|
| AI辅助开发 | Vibe Coding SDLC Framework | 开发工作流、AGENTS.md规范 |
| 游戏架构 | boardgame.io | 状态快照、纯函数逻辑、确定性 |
| LLM集成 | json_repair 最佳实践 | 五层防御体系、假阳性问题 |
| 游戏测试 | 蒙特卡洛平衡性测试 | 数值调优、胜率统计方法 |
| 多智能体 | 三层协同架构（感知/认知/行动） | Player层设计、VAP协议 |

---

## ⚠️ 使用原则

1. **参考不是照搬**：所有资料都是参考，需要结合本项目实际情况调整
2. **标注来源**：如果在设计文档中引用了某个观点，记得在 references.md 中标注
3. **持续更新**：发现新的好资料随时加入知识库
4. **摘要为主**：保存核心观点和关键信息，不保存完整原文（避免版权问题）

---

> **知识库版本**：v2.2
> **创建日期**：2026-06-23
> **维护者**：项目架构师
