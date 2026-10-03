# Web 前端「战旗基本交互元素」补齐报告

日期：2026-10-03 · 范围：`web/src/**`、`web/public/**`、`web/src/assets/**`、`assets/art/`、`docs/**`
输入：`docs/qa/2026-10-web-frontend-audit.md` §3/§4
提交人：ui-elements

---

## 0. 头号纪律的执行结果

**本轮新增的每一个控件都可用；做不到的明确置灰并注明原因，没有「点了没反应」的控件。**

关键证据：城市详情卡的「征兵 / 发展 / 出征」不是占位按钮 —— 它们走**真实后端命令通道**
（WebSocket `{type:"command"}` → `api/game_manager.execute_command` → `game/engine.execute_command`），
实测回执（截图 `05-recruit-result.png` / `06-attack-result.png`）：

- 征兵 → `成功征兵100人，消耗100金钱、200粮草`（洛阳守军 3500 → 3600，金钱同步减少）
- 出征 → `军队 army_1 从 luoyang 出发，目标 chenliu，距离 1 回合`（地图上真出现 600 兵的行军部队）

> 说明：Web 端 `human_faction` 恒为 `null`（纯观战）。命令以**该城所属势力**的名义下发，
> 属观战者人为干预。详情卡顶部已用醒目提示写明这一点，**不假装是"你的回合"**。

---

## 1. 新增元素（每项附截图路径）

| # | 元素 | 实现位置 | 截图 |
|---|---|---|---|
| A1 | **城池详情卡**（等级/守军/城墙/民心/金钱/粮草/人口/州郡/经济加成/驻守武将 + 可执行操作 + 相邻敌城跳转） | `web/src/components/CityCard.tsx`（新） | `02-city-card.png`、`06-attack-result.png` |
| A2 | **hover 悬浮提示**（城池/军队/资源数字） | `web/src/components/Tooltip.tsx`（新）+ `map/CityMarker.tsx`、`map/ArmyMarker.tsx`、`Panel.tsx` | `03-city-hover.png`、`04-stat-hover.png`、`07-army-card.png` |
| A3 | **选中高亮 + 地图自动居中**（金色脉冲环、放大、镜头居中；列表行同步高亮） | `map/CityMarker.tsx`、`GameMap.tsx`（聚焦 effect）、`Panel.tsx` | `02-city-card.png`、`03-city-hover.png` |
| A4 | **快捷键说明面板**（「? / H」调出；Esc 关闭） | `web/src/components/ShortcutHelp.tsx`（新）+ `App.tsx` | `08-shortcut-panel.png` |
| A5 | **加载 / 等待态**（① 未拿到状态时的「载入地图」全屏层；② 回合推进的全局「AI 思考中 Ns」条；③ 命令执行时按钮转圈 + 回执） | `GameMap.tsx`、`App.tsx`、`CityCard.tsx` | `00-loading.png`、`09-thinking.png`、`05-recruit-result.png` |

### 附带修正（本轮实测中发现并修掉的真实缺陷）
- **「主将」下拉曾出现"选了必失败"的选项**：正在带兵的将领（`location` = army id）不在任何城中，
  引擎会拒绝（`将领 he_jin 不在 luoyang`）。已在候选里滤掉「非己方城池」的将领（`CityCard.tsx`）。
  这是实测跑出来的，不是推测 —— 见下节验证记录。
- **`Panel` 城市 tab 的只读详情卡**（审计 §1）被移除：详情+操作统一收敛到地图浮层 `CityCard`，
  避免「两处详情、一处只读」。

---

## 2. 引入的素材

| 素材 | 文件 | 体积 | 来源 URL | 许可 | 署名要求 |
|---|---|---|---|---|---|
| Kenney UI Pack — 面板九宫格边框（改色） | `web/src/assets/ui/panel-frame.svg` | **约 1.1 KB** | https://kenney.nl/assets/ui-pack （镜像 https://opengameart.org/content/ui-pack） | **CC0 1.0** | **无需署名**（已在 `AttributionBar` 礼节性列出） |

**下载后实际校验（非只看 HTTP 200）**：
- `kenney_ui-pack.zip` = 1,229,750 bytes
- `file kenney_ui-pack.zip` → `Zip archive data, at least v2.0 to extract, compression method=deflate`
- 解压后 `file Vector/Grey/button_rectangle_border.svg` → `SVG Scalable Vector Graphics image`

**改动**：三档灰 → 暗金主题色；删除原作者的两枚 2px 红色九宫格切片标记（`#FF0000`），
否则 `border-image` 下边框中部会露红点。

**用途**：`CityCard` 与 `ShortcutHelp` 的 `border-image` 边框（这才是"战旗面板"该有的样子，
纯 Web 圆角卡片读起来像后台表单）。

**登记**：已写入 `assets/art/ATTRIBUTION.md` §5；同步在 `web/src/components/AttributionBar.tsx`
的 CREDITS 与页脚摘要中加入 Kenney（CC0，非强制，属致谢）。

---

## 3. 评估后**放弃**的素材（附原因）

| 素材 | 体积 | 许可 | 放弃原因 |
|---|---|---|---|
| Kenney Cursor Pixel Pack | 91,411 bytes（zip，185 个 PNG） | CC0 | 全部为**粗像素黑白**风格，与本作「平涂羊皮纸 + 墨线省界」的平滑古地图定位割裂。用作光标会明显破坏一致性。证据图：`pixel-cursor-rejected.png`（原始 Preview）。已留档于 `ATTRIBUTION.md` §6，勿重复评估。 |

**未采用的候选**：ambientCG 羊皮纸纹理（需 1K 以上、体积偏大，且暗色玻璃卡片上叠加亮色纸纹会与
现有 `rgba(16,16,30,0.94)` 面板底色冲突，反不如现在干净）；Kenney 六角地块（此前已评估不接入，
见 `docs/design/art-asset-plan.md` §7）。

---

## 4. 验证记录（可复现）

- 命令：`cd web && npx tsc --noEmit` → 退出码 **0**
- 服务：`/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m uvicorn api.server:app --port 8023`
  （前端 `web/dist` 由后端同源托管，WS 指向同源 8023）
- 浏览器：Playwright + 系统 Chrome（headless）
- 一次干净对局（先 `POST /api/reset`）下的断言全部通过，**页面错误数 = 0**：

```
✓ 加载态可见（未拿到状态时显示「正在连接后端并载入地图」）
✓ 页面加载：地图标记已渲染
✓ 快捷键入口按钮存在
✓ 城池详情卡已弹出（含「可执行操作」）
✓ 城池 hover 悬浮卡出现：「洛阳 · 汉室 / 等级 4 · 守军 3,500 / 城墙 3,500 / 3,500 / 民心 70 / 单击查看详情」
✓ 资源数字 hover 说明出现
✓ 征兵命令真实执行：「成功征兵100人，消耗100金钱、200粮草」
✓ 出征命令真实执行：「军队 army_1 从 luoyang 出发，目标 chenliu，距离 1 回合」
✓ 军队详情卡已弹出（军队可点击）
✓ 快捷键说明面板内容完整
✓ Esc 可关闭快捷键面板
✓ 回合推进有全局等待条（AI 思考中 Ns）
页面错误数：0
```

- 服务已按端口精确停止：`lsof -ti tcp:8023 | xargs kill`

---

## 5. 未完成 / 已知边界

1. **观战者干预的语义**：命令以 AI 势力名义下发，会改变对局。这是"能接到后端"的必然结果，
   已用提示标注，但**没有做权限门**（后端本就允许任意 `faction` 的命令）。
2. **未做**（审计 §4 中未列入本轮"至少覆盖"清单，故未纳入）：右键上下文菜单、地图图例/缩放按钮、
   回合历史时间轴、全局搜索。
3. **相邻敌城**只列非本势力相邻城；同势力相邻城的跳转未提供。
4. 同一格叠多支部队时，标记会重叠（点击取最上层）；未做扇形散开。
