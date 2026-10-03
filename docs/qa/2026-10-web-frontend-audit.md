# Web 前端审计报告（虚有其表 / 交互问题）

日期：2026-10-03 · 范围：`web/src/`（React + PixiJS）· 方法：逐控件读代码 + 起服务实测 `/api/state`

## 结论先行

1. **没有一处 `onClick={() => {}}` / TODO / "暂未实现"**——问题不在"空函数"，而在**接线后不可达、或只改本地 state、或数据根本没下发**。典型三例：外交「发送」tab（`human_faction` 恒 null，入口整个是死的）、季节显示（后端从不返回 `season`）、势力卡点击（只做高亮）。
2. **"交互像一摊烂泥"有可量化主因**：每次 WS `state` 都携带 **2.58 MB 的 `hex_map`（24000 格，占 payload 约 100%）**，而 `GameMap` 每次 state 更新都**全量销毁重建**整层 Pixi 图形。自动推进 800 ms/回合 → 每 0.8 s 重解析 2.3 MB 并重画 24000 格，这是缩放/平移"不跟手"和卡顿的直接来源。
3. **多个已下发字段前端零使用**：`game_over`、`winner`、`is_alive` 后端都返回，前端没有任何组件引用 → 没有胜负结算界面、没有"已出局"标识。
4. **断线不重连、窗口不 resize、地图上的军队完全点不了**——战旗游戏最基本的三层（选中高亮、单位详情、悬浮提示）整体缺失。

---

## §1 虚有其表清单

| 组件:行号 | 控件 | 问题 | 证据 |
|---|---|---|---|
| TopBar.tsx:21-28 | 顶部"N回合 \| Y年 季" | 季节恒为空，只有"184年" | 实测 `/api/state` 的 payload **无 `season` 键**；`game/models.py` 的 `GameState` 无该字段 |
| DiplomacyPanel.tsx:174,245 | 外交「发送」tab（下拉+文本+按钮） | 默认永不可达，恒显示"观战模式下无法发送" | `state.human_faction` 实测为 `null`；前端 grep 无任何设置人类势力的入口；`run_web.py` 也不传 |
| Panel.tsx:321,333-337 | 武将 tab 每方列表 | 硬编码 `slice(0,5)`，"还有 N 人"是**不可点的纯文字** → 第 6 名后永远看不到 | 无 onClick；数据 `generals` 有 53 人 |
| Panel.tsx:103 | 势力卡 | 点击只 `setSelectedFaction`，仅用于本卡高亮；不影响地图/其他 tab | `selectedFaction` 仅出现在 `:93/:100` 的样式判断 |
| LlmSetupBar.tsx:71-77 | 参战势力预选 | CLI 下 `llm_factions` = 全部 12 方，首屏即预选 12 方；切到 LLM 直接"12 方 ≈120s/回合" | 实测 `llm_factions` 返回 12 条；`game_manager.py:379` = `self._players.keys()`（CLI 时就是 12） |
| LlmSetupBar.tsx:104-116 | 「重开一局」 | 无二次确认，直接 `POST /api/reset` 清空进度 | 确认文案只在 `title`（`:342`）里 |
| App.tsx:94-99 | 「自动推进中」指示条 | 无 onClick；开启 auto 后「下一回合」被 `disabled`（:80）→ 界面无"停止"按钮，只能按 `A` | autoIndicator 是纯 div |
| types.ts:167-168 | `game_over` / `winner` | 后端返回、前端**零处引用** → 无胜负/结算界面 | grep 全前端仅出现在 types.ts |
| types.ts:74 | `is_alive` | 后端返回、前端**零处引用** → 出局势力仍按普通卡片列 | grep 仅 types.ts |
| EventTicker.tsx:13 | 底部事件流 | 只取 `slice(-4)`，无展开/暂停/点击 | 固定 4 条 |
| GameMap.tsx:297-310 | 地图城名 | Pixi `Text` 画一次城名，DOM `CityMarker` 又画一次 → 重复标签 | 两处均无条件渲染 |
| Panel.tsx:145-255 | 城市详情卡 | 纯只读，无任何可执行操作（征兵/发展/出征） | 整卡无 button |

**死代码（"画了没接线"的旁证）**：`GameMap.tsx:613 computeChinaMask` 定义后无引用；`theme` 的 `TERRAIN_COLORS`/`CITY_STYLES`/`ARMY_STYLES`/`FACTION_IDS` 无引用；`useGame.ts:140-166 sendCommand`/`reset` 返回但 App 未解构；`types.ts:6 Tile` 无引用。

## §2 前后端契约不一致

| 前端字段 | 后端是否返回 | 实测结果 |
|---|---|---|
| `season`（types.ts:166） | **否** | `'season' in payload == False`；GameState 模型无此字段 → 顶部恒空 |
| `Tile.gold_yield/food_yield/pop_yield`（types.ts:6-14） | **否** | hex tile 实测只有 `q/r/terrain/faction/owner_city_id/province_id` |
| `BattleReport.defender_general_name`（types.ts:118） | **否** | `game_manager.py:690-706` 未打包 → 恒 `undefined`（前端已容错隐藏，符合注释） |
| `FactionStat.model` | 仅 LLM 激活时 | CLI 恒 `""` → 势力卡 `modelTag` 永不显示（实测 caocao.model=""） |
| `llm_factions` 语义 | 返回 12 条 | 实为 `self._players` 键（CLI 也是 12），非"LLM 参战势力"；前端当"实际参战势力"用（LlmSetupBar:63） |
| `GameState` 缺少声明 | 后端多返回 | City 返回 `province_id/generals/neighbors/economic_bonus`；General 返回 `personality/is_injured/captor_faction` 等 → 类型不完整（未致错） |
| `faction_models`（多模型） | REST 支持 / **WS init 丢** | `server.py:241-257` 构造 GameConfig 时未透传 `faction_models`。当前前端走 REST `/api/reset` 规避，`reset()`（WS init）未被调用 → 隐患 |
| `/api/state?reasoning_limit` | 支持 | 前端从不调用；每次 `state` 全量下发 `reasoning` |

## §3 交互问题清单（按严重度）

1. **每回合全量重建 Pixi + 2.58 MB 地图**：`GameMap.tsx:95-312` 依赖 `[state]`，每次 `camera.removeChildren()` 后重画 24000 格 + 边界 + 州名/城名；实测 `hex_map` 占 `/api/state` **2.58 MB（约 100%）**，总分 2.34 MB。`useGame.ts:161` auto 间隔 800 ms → 卡顿、缩放平移不跟手。
2. **断线不重连**：`useGame.ts:73-112` 无 reconnect，`onclose` 只置 `connected=false`，必须手动刷新。
3. **窗口 resize 不处理**：`GameMap.tsx:52-79` 仅按挂载时 `clientWidth/Height` 初始化，无 `ResizeObserver` → 改窗口后画布错位。
4. **选中城市无地图反馈**：`CityMarker` props 只有 `city/x/y/zoom/onClick`（无 selected），GameMap 无聚焦逻辑 → 点列表城市只切 tab，地图毫无变化。
5. **军队完全不可交互**：`ArmyMarker.tsx:61 pointerEvents:'none'`、无 onClick；Panel 也没有"军队"tab → 地图上部队无法查看。
6. **快捷键无输入框守卫**：`App.tsx:21-48` 监听 window keydown，不判 `e.target` → `<select>` 聚焦时按空格/字母/数字会推进回合、切自动、切 tab。
7. **重开一局无确认**：`LlmSetupBar.tsx:104-116`。
8. **自动推进无法点击停止**：见 §1 第 7 条。
9. **无 hover 提示**：`CityMarker`/`ArmyMarker` 无 `title`；列表项多数无 tooltip。
10. **无加载进度**：hex_map 2.3 MB 解析期间只有 TopBar 一行"加载中"，无进度/骨架屏。
11. **历史被截断且无翻页**：后端 `events` 只留 20 条（`game_manager.py:343`）、`turn_logs` 只留 10 条（`:435`）；前端"战报/事件"tab 无任何"已截断/更早"提示。
12. **错误文案硬编码端口**：`useGame.ts:206` 写死"后端是否在 8000 端口运行"。
13. **auto_loop 阻塞事件循环**（服务端）：`server.py:219-225` 在 async 循环里同步调用 `process_turn()`，LLM 模式下整轮阻塞，期间无法响应其他消息。

## §4 缺失的基本元素（按玩家优先级）

1. **游戏结束/胜负结算界面**（`game_over`/`winner` 已返回却未用）。
2. **军队详情卡 + "军队"面板**（战旗游戏核心；地图上部队点不了）。
3. **单位/城池 hover 悬浮卡**（popover，现无任何 title）。
4. **选中高亮 + 地图自动居中**（点城市/势力 → 地图定位并高亮）。
5. **右键上下文菜单**（攻击/征兵/移动…；现无 `onContextMenu`）。
6. **重要操作确认与撤销**（重开、进攻）。
7. **快捷键帮助面板 + 输入框守卫**（现仅按钮上一行小字提示）。
8. **地图图例 + 缩放控件**（+/-/复位；现只支持滚轮，无按钮）。
9. **回合历史/战报时间轴**（可回看任意回合）。
10. **城池详情卡上的可执行操作**（征兵/发展/出征）。
11. **全局搜索/筛选**（按势力、武将名）。
12. **自动推进的可见开关与节奏控制**。
13. **断线重连提示与重试按钮**。
14. **"已出局"势力标识**（`is_alive` 已返回）。

## §5 建议修复顺序（收益/成本 Top 8）

1. **瘦身并降频 `hex_map`**：静态地图只在开/换局下发一次（或压缩），`GameMap` 只在 hex_map 变化时重建 —— 直治卡顿/不跟手，收益最大。
2. **加胜负结算弹层**：`game_over`/`winner` 现成，几乎零成本。
3. **加"停止自动"按钮 + 选中高亮/地图定位**：修最刺眼的"点了没反应"。
4. **补 `season` 序列化或停止展示该字段**：消除"永久空白"。
5. **军队详情卡 + 军队面板（点亮 ArmyMarker）**：补战旗核心信息层。
6. **重开二次确认 + 断线重连**：防误操作、防白屏。
7. **城市/军队 hover 提示（先用 `title` 起步）**：低成本提升信息可达性。
8. **快捷键输入框守卫 + 快捷键帮助面板**：消除误触、降低上手成本。

---
注：本报告结论均基于源码阅读与 `curl 127.0.0.1:8021/api/state` 实测；测试服务已按端口精确停止。凡未能实测者已标注"未验证"，本报告无此类条目。
