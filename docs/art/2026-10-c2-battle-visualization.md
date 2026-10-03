# C2 · 战斗可视化（前端呈现层）

> 作者：林绘澄（美术 / 视觉）　日期：2026-10-03
> 上游口径：`docs/design/v4.1-gameplay-gaps.md` §4「缺口 3：战斗在界面上不可见」
> 依赖：后端 `state.recent_battles`（**当前尚未落地**，见 §4）

---

## 1. 验收标准（上游定义，照抄）

> **单场战斗，观众只看地图、不看文字，3 秒内能复述三件事。**

1. **谁在打谁** —— 进攻方 → 防守方；
2. **打的什么结果** —— 城被攻下 / 守住了 / 攻方溃退；
3. **从哪来、打向哪** —— 进攻箭头，起点 = 攻方出发城，终点 = 目标城。

---

## 2. 已实现

| 验收项 | 实现 |
|---|---|
| 从哪来、打向哪 | `BattleOverlay` 画**世界坐标箭头**：**每个出发城各一条** → 目标城（多线汇聚）；SVG **二次贝塞尔** path + 箭头 marker |
| 谁在打谁 | 箭头**颜色 = 攻方势力色**；**粗细 = 兵力比**（攻方占比，屏幕 4–9px 量级）；残留箭保留颜色 |
| 打的什么结果 | 三态徽标：`attacker_win`→**占领**（金）/ `defender_win`→**守住**（绿）/ `retreat`→**溃退**（褐）/ `draw`→相持（灰） |
| 回放节奏 | 回合推进后对**最近 ≤3 场**逐场短回放（每场 **1.5s**），`battle_id` 保序；结束后留残留箭 + 700ms 淡出 |
| 加分项 | 回放标签带**双方兵力与总伤亡**（`2,100 ⚔ 3,800 −2,800`）+ 主将名；多出发城时显示 **`×N路`**；**城防条**（`城防 8000 → 6200`，色随剩余比例） |
| 色盲友好 | 标签里的势力标识用**单字徽标 + 名称**（不是纯色块）——复用阶段B 的 `FACTION_GLYPH` |
| 地图认人 | `CityMarker` 加**势力单字小徽标**（放大到一定程度才显示，避免全图糊） |

> ⚠️ **出发城是复数**（`attacker_from_cities: string[]`）。一场战斗常有多支来自不同城的攻方部队被合并
> （`battle_scheduler._group_by_target`，实测 **15%** 的战斗如此）。所以前端**对每个出发城各画一条箭头**——
> 单起点会漏画其余进攻线、指向错误（这直接违反 §4.2 的验收标准）。依据见设计文档 §4.3.1 更正。

### 技术选型
**DOM + SVG 叠加层**，复用 `GameMap` 已有的世界坐标 overlay `transform`。
- 不引入 PixiJS ticker 动画系统：改动小、风险低、几场战斗无性能压力；
- 所有尺寸除以 `zoom`（`inv = 1/zoom`），保证观感不随地图缩放变化；
- 回放由 React state + 50ms 步进驱动，**不触发 Pixi 层重建**（Pixi 渲染 effect 只依赖 `state`/`pixiReady`）。

### 文件
- `web/src/components/map/BattleOverlay.tsx`（新增）：箭头 + 回放标签 + 三态徽标
- `web/src/components/GameMap.tsx`：回放序列状态机 + 挂载叠层
- `web/src/components/map/CityMarker.tsx`：势力单字徽标
- `web/src/types.ts`：`BattleReport` + `GameState.recent_battles`

---

## 3. 数据契约（消费上游 §4.3 的 DTO）

```ts
interface BattleReport {
  battle_id: string
  turn: number
  attacker_faction: string
  defender_faction: string
  attacker_from_cities: string[]      // 出发城 id **列表**（复数）—— 画箭头必须
  defender_city: string | null        // 城市 id
  attacker_soldiers: number
  defender_soldiers: number
  attacker_casualties: number
  defender_casualties: number
  result: string                      // attacker_win|defender_win|draw|retreat
  wall_hp_before?: number
  wall_hp_after?: number
  attacker_general_name?: string
}
```

前端是**纯只读消费方**：`recent_battles` 缺省时整个叠层不渲染（优雅降级）。

---

## 4. 🔴 后端依赖尚未落地（阻塞「真实数据」）

实读结论（非推测）：

| 检查 | 结果 |
|---|---|
| `recent_battles` 在代码库里？ | ❌ 只在设计文档中出现 |
| `event_bus.py` 定义 `BattleEndedEvent` / `CityCapturedEvent`？ | ✅ `:78` / `:57` |
| 有 `publish(...)`？ | ❌ `engine.py` 搜不到 |
| `game_manager.py` 订阅？ | ❌ 只 `subscribe("turn_ended", ...)`（`:187`） |

**需要工程侧补（约 60 行，字段见 §3）**：
1. `engine.py` `_apply_battle_result` 内 `publish(BattleEndedEvent(...))`，占领时 `publish(CityCapturedEvent(...))`；
2. `game_manager.py` 订阅并累积 `recent_battles`（近 N 场，带上限，参考 `MAX_EVENTS_KEPT`）；
3. `get_state()` 序列化 `recent_battles` → WebSocket 推给前端。

落地后**前端无需改动**，直接生效。

### 曲线与回放的两个实现要点
- **贝塞尔曲线**：单路带固定侧偏（轻弧，不死板）；**多路按出发城序号在中点两侧扇形错开曲率**，
  避免多条线叠成一条看不清。
- **回放时「线从起点长到终点」**：不能直接截断终点画 `Q`（形状会不对）。二次贝塞尔的子曲线仍是
  二次贝塞尔——用 **De Casteljau 在 t=progress 处切分取左半段**：
  控制点 = `(P0, lerp(P0,C,p), lerp(lerp(P0,C,p), lerp(C,P2,p), p))`。

### 本文档截图的验证方式
后端字段还没落地（见 §4），所以用 **Playwright 拦截 WebSocket**：拉真实 `state` → 注入合成的
**3 场战斗**（占领/守住/溃退各一；其中一场是 **3 路合攻**）→ 推给页面 → 连拍。
**这证明渲染链路可用，不代表真实数据已通**（mock 不算验收，见 §5）。

截图：`docs/art/screenshots/phase-c2-battle/01-replay.png`、`02-replay.png`、`03-replay.png`
（01 可见 3 路合攻的**扇形贝塞尔**与「汉室⚔黄巾 / 守住」+ 城防条；03 为回放结束后的残留箭）。

---

## 5. 已知限制 / 后续

- **真实数据未通**（见 §4）——这是唯一阻塞项，属工程侧（任务 #33）。
- 🔴 **mock 截图不算验收**：真实数据通了以后要重做「**只看地图、不看文字**，说出谁打谁/结果/从哪来」的 3 秒自测。
- **没有独立的战斗时间轴控件**（暂停/重播某场）——当前是「回合推进即自动回放」。若观众反馈想回看，再加。
- 未做**多场同回合的排序可视化**（当前按 `battle_id` 顺序逐场播）。
- 箭头是贝塞尔曲线但**不绕地形**（会横穿山脉/海域）——若后续觉得别扭，可做避让（成本中）。
- 城防条只在 `wall_hp_before/after` 都有值时显示（缺字段时自动隐藏，不报错）。
