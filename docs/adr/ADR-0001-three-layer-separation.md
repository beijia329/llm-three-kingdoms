# ADR-0001 三层架构分离（Engine / Players / Renderer）

- **状态**：Accepted（已落地，AGENTS.md 5.1 列为"铁律"）
- **日期**：2026-06-24（记录于 Phase 5→6 收口）
- **相关**：architecture.md 一/二/五、AGENTS.md 5.1、command-pattern.md 八

---

## 背景（Context）

项目是 LLM 驱动的多智能体策略对战游戏，需要同时支撑多种"决策源"（LLM、CLI、GUI 人控）与多种"展示端"（Pygame 桌面、Web 浏览器），并且游戏逻辑必须可独立测试、可复现、可被评测复用。早期若把渲染/输入与逻辑耦合，会导致：

- 游戏逻辑无法脱离 GUI 跑单测与回放；
- 换一种 LLM 或玩家类型要改逻辑；
- 换一种展示（Web vs Pygame）要重写整局。

因此需要一个强制的分层边界。

---

## 决策（Decision）

采用严格的三层分离：

1. **Engine 层（纯游戏逻辑）**
   - 不依赖任何 UI 框架。验证方法：`game/` 目录下不得出现 `import pygame` / `from pygame`（已用 Grep 全量核查，`game/` 内 **零** pygame 引用，铁律成立）。
   - 持有唯一 `GameRandom(seed)` 与 `EventBus`（见 `game/engine.py`：`from game.event_bus import EventBus`、`from game.random import GameRandom`、`self.rng = GameRandom(seed)`、`self.events = EventBus()`）。

2. **Players 层（决策抽象）**
   - 所有决策源继承 `players/base_player.py` 的 `BasePlayer`，通过标准接口 `get_commands(obs) -> List[Command]` 与 `receive_message(from, content)` 与 Engine 交互。
   - **禁止**直接访问 `GameEngine` 内部状态或调用其修改方法；只能回写 `Command`。
   - 已实现：`LLMPlayer`（players/llm/）、`CLIPlayer`、`GUIPlayer`。

3. **Renderer 层（只读展示）**
   - 只读取 Engine 的状态快照 / 订阅 `EventBus` 事件做展示，**不修改**游戏逻辑。
   - 已实现：`renderer/`（Pygame 桌面）、`web/`（React + PixiJS，经 FastAPI 只读消费，见 ADR-0005）。

4. **状态变更走事件驱动**
   - 所有状态变化经 `EventBus` 广播（`CityCapturedEvent` / `BattleStartedEvent` / `BattleEndedEvent` / `GeneralDefectedEvent` 等不可变数据类），UI 与日志订阅事件，不轮询状态。

5. **子系统归属 Engine 层**
   - `game/systems/`（resource/city/general/diplomacy/map）与 `game/battle/`（battle_scheduler / army_movement / battle_resolver）均属于 Engine，互相通过 `BattleContext` / `GameState` 传数据，**不互相持有引用**。

---

## 后果（Consequences）

**正面**
- Engine 可脱离任何 UI 单独跑测试 / 评测 / 回放。
- 新增决策源只需继承 `BasePlayer`（如后续接入新模型）。
- 新增展示端只需实现"只读 Renderer"，Web 与 Pygame 因此可并存为等价消费端。
- 事件驱动让 UI、日志、回放天然解耦。

**负面**
- Player 无法"走后门"直接改状态，某些联调/调试场景略不便（需经 Command 通道）。
- 事件驱动引入一层间接，渲染端需做防抖/节流避免高频重绘。
- Renderer 与 Engine 状态存在"只读快照 vs 实时状态"的同步语义，需约定刷新时机。

---

## 备选方案（Alternatives Considered）

| 方案 | 结论 |
|------|------|
| 单层脚本式（逻辑+渲染耦合） | 出原型快，但不可测试、不可替换 LLM/渲染，否决 |
| 双层（逻辑+渲染）但不做 Player 抽象 | 不利于多决策源并存，否决 |
| 全命令走网络协议（本地也序列化跨进程） | 过度工程，本地单机不需要，否决 |

---

## 落地核查点

- 提交清单（AGENTS.md 6.4）：`Engine 层没有 import pygame`、`Renderer 层没有修改游戏状态`、`没有破坏确定性`。
- 持续验证：`grep -rn "import pygame" game/` 必须为空。

---

## 落地更新（2026-10，engineering-lead）

本 ADR 第 4 条「状态变更走事件驱动 / UI 与日志订阅事件」长期只是**纸面 Accepted**：
`game/event_bus.py` 定义了 10 类事件，但全仓只有 1 处 `publish`、**生产 0 处 `subscribe`**，
前端 / API 实际一直轮询 `get_state()`（即「假 Accepted」）。2026-10 已做**最小接线**：

- `GameEngine.process_turn` 现在真的广播 `TurnStartedEvent` / `TurnEndedEvent`，
  战斗结算广播 `BattleEndedEvent`，占城广播 `CityCapturedEvent`（`DiplomacyMessageSentEvent` 沿用既有产生点）。
- `api/game_manager.py` 成为**第一个真实订阅者**：订阅 `TurnEndedEvent`，据此产生
  「建国/称王」「战斗」事件记录（取代原先 `process_turn` 末尾两段手写 `_add_event`；
  订阅者若失效，这些记录会立刻消失——已验证其「承重」）。
- 删除 5 个**无任何产生点**的事件类（`BattleStartedEvent` / `ArmyCreatedEvent` /
  `GeneralRecruitedEvent` / `GeneralDefectedEvent` / `GameOverEvent`）。
- 约束：`GET /api/state` 的 `events` 字段与接线前**逐字节一致**（已快照比对）；
  `tests/integration/test_api_endpoints.py` 22 项全绿。

仍未做（后续任务，另行排期）：把 `_add_event` 的其余调用也迁移为订阅驱动；
前端改为消费事件流（需 `web/` 侧配合）。
