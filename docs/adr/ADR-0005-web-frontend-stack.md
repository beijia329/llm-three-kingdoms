# ADR-0005 Web 前端技术栈（React + PixiJS + TS + Vite + FastAPI + WebSocket）

- **状态**：Accepted（已实现，待合入 `main` 分支；当前在 `feat/web-frontend`）
- **日期**：2026-06-24（记录于 Phase 5→6 收口）
- **相关**：web/package.json (v2.2.0)、api/server.py (v2.2.0)、run_web.py、AGENTS.md 5.1（Renderer 只读）

---

## 背景（Context）

需要在**不改动纯逻辑 Engine** 的前提下，提供一个浏览器可访问的实时对战/观战界面，且要与既有 Pygame 桌面渲染并存。关键约束：

- Engine 必须保持框架无关（ADR-0001：Engine 不依赖 UI）。
- Web 不能引入"第二套游戏状态"或绕开命令通道直接改逻辑。
- 需支持实时状态流（自动推进/单步）与端到端自动化测试。

---

## 决策（Decision）

**前端栈**（`web/package.json`，version `2.2.0`）：
- React `^18.2` + PixiJS `^8`（地图/精灵渲染）+ TypeScript `^5.4` + Vite `^5.1`
- E2E 测试：Playwright `^1.61`

**后端桥接**（`api/server.py`，FastAPI `version="2.2.0"`）：
- REST：`/api/state`、`/api/command`、`/api/next-turn`、`/api/reset`
- WebSocket：`/ws/game` 实时状态流（客户端发 `init/command/next_turn/auto`，服务端回 `state/event/error`）
- CORS 放开（`allow_origins=["*"]`）用于本地开发；生产构建由 `StaticFiles` 托管 `web/dist`

**边界规则**：
- `api/game_manager.py` 的 `GameManager` 作为**单例**包裹 Engine，是唯一把 Engine 暴露给 Web 的边界。
- Web（前端 + `api/`）**不 import 游戏逻辑**，只通过 REST/WS 收发命令与状态。
- Web 与 Pygame 是**等价只读消费端**：都只读 Engine 状态 + 回写 `Command`，共享同一 Engine / `EventBus` / `GameRandom`，不复制游戏状态。

---

## 后果（Consequences）

**正面**
- 浏览器可玩/观战，Engine 零改动。
- 与 Pygame 并存为双渲染通道；类型安全（TS）；热更新（Vite）；可自动化 E2E（Playwright）。
- 单例 `GameManager` 让"本地单机一局"模型清晰。

**负面**
- 多维护一套渲染栈（人力成本）。
- FastAPI + WebSocket 引入异步边界：`auto_loop` 在 WS 协程内串行 `process_turn`，需确保 Engine 单线程推进不被并发 REST 调用重入（见"待确认"）。
- CORS 放开仅适合本地；部署需收紧。
- 当前为单 `GameManager` 单局，**不含**多房间/在线对战——与 AGENTS.md 1.3"非目标：不做联网对战"一致，但文档需明确"Web 是本地单机浏览器展示，非多人在线"。

---

## 备选方案（Alternatives Considered）

| 方案 | 结论 |
|------|------|
| 仅保留 Pygame | 无浏览器可达性，否决 |
| Pygame 编译到 WebAssembly | 复杂、生态不成熟，否决 |
| 纯 Canvas/DOM 无 PixiJS | 地图大量精灵性能差，否决 |
| 前端直连 Engine（不经 FastAPI） | 破坏分层，Web 需装 Python 逻辑，否决 |

---

## 待确认（需主理人/架构师拍板）

1. **并发模型**：`/ws/game` 的 `auto_loop` 与 REST `/api/next-turn`/`/api/command` 是否共享同一推进锁？需确认没有重入 `process_turn` 导致状态竞争（建议补读 `api/game_manager.py` 并加并发测试）。
2. **多房间/对战大厅**：当前单例，若后续要做需重构 `GameManager` 为房间表；本期按"非目标"处理。
3. **分支合入**：当前实现在 `feat/web-frontend`（最近提交 2026-06-24），收口时应合入 `main` 并同步 README/AGENTS/MAINTENANCE 的技术栈描述（见 doc-reconciliation.md 类别 2）。
