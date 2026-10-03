# 归档区说明（docs/archive/）

> 本目录存放**不再代表当前系统**的历史文档。它们仍有方法论价值，但**结论可能已被后续版本推翻**。

## 归档标准

一份文档被移入本目录，通常满足以下之一：

- 它所描述的阶段/任务/缺陷**已完成或已修复**（如 `handoff/`、`tasks/`、`design/v31-*`）。
- 它的口径**已被新的权威文档取代**（如 `施工指南.md` 被 `design/concept.md` + 实际代码取代）。
- 它是**过程记录**而非长期事实源（协作日志、执行提示词、更名记录）。

仍作为事实源的文档**不会**进这里，见 `docs/design/`、`docs/specs/`、`docs/adr/`、`README.md`、`AGENTS.md`。

## 失效标注约定

归档文档**顶部必须带「失效横幅」**，格式：

```markdown
> ⚠️ **本文档为历史记录（归档于 2026-10）**。
> 其中**部分结论已被后续版本推翻**，引用前必须以**当前代码**为准。
> 已确认失效的结论示例：<2-3 条最易被误引的，带 file:line 指向现行实现>
```

横幅里必须给出**现行实现的位置**（`文件:行号`），让读者能立刻核对，而不是只能相信一句话。

## 🔴 规矩：引用归档文档前，必须 rg 复核当前代码

**本项目的已知高发事故**：拿历史报告的结论当现状引用。

- 例 1：`design/v31-generals-audit.md` 曾断言「`LOYALTY_COMBAT_*` 零引用、忠诚不影响战力」——
  v4.0 已接线（`game/systems/general_system.py:360` `loyalty_combat_factor`）。
- 例 2：`qa/doc-reconciliation.md` 曾断言「文档写统一 OpenRouter」——
  实际 `AGENTS.md:44` 等早已是「默认 DeepSeek」。

因此：**任何来自 `docs/archive/` 的结论，写进新文档或作为决策依据前，先 `Grep`/`rg` 到当前代码核对一遍。**
归档只是挪了位置，文件内容仍可能被搜索命中、被误当成现行事实。

## 目录

```
docs/archive/
├── README.md              # 本文件
├── 施工指南.md             # v2.0/v2.3 阶段进度（历史）
├── LLM三国志施工手册（已过时）.md  # 旧三方设计手册
├── build_app.sh           # 被 build_release.sh 取代的旧构建脚本
├── design/                # v31-* 审计报告（部分结论被 v4 推翻）
├── handoff/               # Kimi/DeepSeek 多 Agent 交接记录
├── tasks/                 # 阶段性任务清单与完成记录
└── superpowers/           # 六角格地图早期 spec/plan/prompt
```
