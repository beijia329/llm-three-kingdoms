# 2026-10 质量审计（精简版）

- 审计分支：`feat/web-frontend`　审计起点提交：`5d3aa4e`
- 说明：审计期间该分支被其他成员持续提交（HEAD 已推进到 `3b3d97c`，工作区含他人未提交改动）。
  有测试文件的目录亦在增加。**下述覆盖率为 `5d3aa4e` 时点快照**，结论均以代码静态判读 + 实测为准。
- 范围：`tests/unit` + `tests/integration`；只读代码，仅新增本文件。

## 1. 覆盖率

命令：`SDL_VIDEODRIVER=dummy python3 -m pytest tests/unit --cov=game --cov-report=term-missing -q`

- **总覆盖率 90%**（3305 语句，319 未覆盖）；**583 passed**；耗时 21m16s。

覆盖最低的 5 个模块（按覆盖率升序，含未覆盖行数）：

| 模块 | 覆盖率 | 未覆盖行 |
|---|---|---|
| `game/engine.py` | **76%** | **178** |
| `game/personality.py` | 79% | 6 |
| `game/data_loader.py` | 81% | 12 |
| `game/systems/city_system.py` | 83% | 23 |
| `game/systems/map_system.py` | 88% | 11 |

补充：`game/map_generator.py` 覆盖率 90% 但**未覆盖 46 行**，绝对缺口仅次于 `engine.py`。
`engine.py` 是唯一「既大又漏」的模块——178 行未覆盖，且下列全部高危盲区都在其中。

## 2. 最危险的 3 个盲区

判定标准：**坏了测试也抓不到（无断言 / 无覆盖）且影响大**。

| # | 位置 | 为什么危险（一句话） | 现有测试 |
|---|---|---|---|
| 1 | `game/battle/battle_resolver.py:175` → `game/engine.py:1176-1193` | 战后俘虏链唯一入口：此行不传 `defender_generals` → `captured_generals` 恒空 → `process_capture` 零调用 → 俘虏/投降/降将转投整条链静默断裂 | **无（假绿）**。唯一相关单测 `test_battle_resolver.py:410` **直接给 `process_aftermath` 传参**，绕过生产链；`engine.py:1178,1185-1188` 覆盖率缺失 |
| 2 | `game/engine.py:1144-1165`（`_redirect_army_home`） | 攻方战败/平局/撤退后掉头回城；返程路径若坏，败军会沿去程走到敌城下**永久卡死** | **无**。全 `tests/` 无任何测试引用 `_redirect_army_home`；`engine.py:1144-1152` 覆盖率缺失 |
| 3 | `game/engine.py:1623-1645`（`load_state_snapshot`） | `GameState` 快照「只写不读」——设计承诺的状态回滚/时间旅行**无恢复入口**；即便接上，恢复不全也无测试能发现 | **无**。`test_engine.py:416` 只测 `get_state_snapshot()` 序列化，不测恢复；`1629-1645` 覆盖率缺失 |

盲区 #1、#2 都属同一缺陷族：**「生产调用链断裂 / 死代码，而单测因绕过调用链而全绿」**——
这是本仓库最反复出现的失效形态。

## 3. 「故意改坏」验证

- **改坏内容**：注释掉 `game/battle/battle_resolver.py:175` 的 `defender_generals=list(context.defender_general_ids),`
- **运行**：`SDL_VIDEODRIVER=dummy pytest tests/unit tests/integration -q`
- **结果**：**653 passed，0 failed**（耗时 11m26s）→ 🔴 **没有任何测试失败**。

**这说明了什么**：
把生产链上唯一一处 `defender_generals=` 接线摘掉后，整套 unit + integration **全绿**。
即：`resolve_battle → process_aftermath → captured_generals → engine.process_capture`
这条**俘虏 / 投降 / 降将转投**链路，在自动化测试里**没有任何保护**——它在生产环境静默断裂，
CI 不会报警。`battle_resolver.py:174` 的注释声称「由 `tests/integration/test_battle_report.py`
在生产链路上断言锁定」，但实测该文件只测 `BattleReport` / `recent_battles` 字段契约，
**不含任何** `defender_generals` / `process_capture` / `captured_generals` 断言——
**该注释是一处失真的「已保护」声明**，应随补测一并更正。

改坏行已立即还原：`git diff game/battle/battle_resolver.py` 为空。
