# 美术与 UI 现状审计 + 公开素材落地方案

> 审计对象：`feat/web-frontend` 分支，「LLM 大乱斗围观台」Web 前端
> 审计人：林绘澄（美术 / 视觉 / 可访问性）
> 日期：2026-10-03
> 方法：**实读代码 + Playwright 真机截图取证**（不凭文件名猜）
> 唯一允许写入的文档；本次**未改动任何 `web/src/` 或 `game/` 代码**

---

## 0. 结论速览

**现状评分：4 / 10**

| 维度 | 分 | 说明 |
|---|---|---|
| 地图表现力 | **2** | 陆地整片纯色、地形零区分、势力色像水渍，空海占掉半屏 |
| 信息架构 | 5 | 顶栏/右栏/ticker 框架完整，但第一眼看不出「谁在打谁」 |
| 视觉一致性 | 4 | 有 design token 但组件里全是硬编码色值，两套配色语义打架 |
| 题材契合度 | 3 | 观感是「深色数据看板 + 平涂地图」，三国味只靠势力名和金色 |
| 可访问性 | **1** | 无 reduced-motion、无 focus 态、无高对比/色盲模式 |

**一句话**：这是个**结构完整、能跑起来的工具面板**，但还不是一张「看得下去」的三国地图——最大的问题不是「不够美」，是**地图没有任何信息层次**，观众盯着屏幕看不出战况。

**最刺眼的 3 个问题**
1. **地图是一块平涂色板**：所有地形都渲染成同一个米色 `0xd9c9a3`（`GameMap.tsx:516` `parchmentTint()` 忽略 `terrain` 参数），放大后就是一块没上色的画布（见 `02-map-zoom.png`）。
2. **看/玩割裂，看不懂战况**：战斗发生后地图上只有围城红点脉冲，没有交战方、没有方向、没有战线；要理解「谁在打谁」得切到「战报」tab 读文字（见 `01-overview.png` 底部 ticker）。
3. **中文字面量泄漏到界面**：底部 ticker 与战报显示「汉室称**kingdom**！国号【汉】」（`01`/`05` 图底部），来源 `api/game_manager.py:619` 把 Python 枚举 `'kingdom'/'emperor'` 直接拼进了中文句子。

---

## 1. 现状盘点（实读结果）

### 1.1 `assets/` 素材：192K，**全部未接入前端**

| 路径 | 内容 | 大小 | 授权 |
|---|---|---|---|
| `assets/art/hex/` | Kenney 六角地块 31 个（大地块 + `_full` 变体 + 植被 + 桥） | 124K | **CC0**（可商用、无需署名） |
| `assets/art/icons/` | game-icons.net 图标 16 个 SVG（已去黑底 / `currentColor`） | 64K | **CC BY 3.0**（必须署名） |
| `assets/app_icon.icns` | 应用图标 | 428K | 项目自有 |

🔴 **关键发现：这些素材一个都没被前端用到。**
- `web/src/` 全局搜索无任何 `assets/art` 引用（Grep 0 命中）。
- 构建产物 `web/dist/assets/index-C7iJMBKY.js`（481K）里搜不到 `art/hex` / `art/icons` 字符串 → 打包**从不加载**。
- 但 `web/dist/art/`（188K）确实被复制进了发布目录 → **发布包里躺着 188K 永远不请求的死素材**。
- `web/src/utils/{colors,mapIcons,tiles}.ts`（合计 283 行）无任何组件 import → **死代码**。其中 `mapIcons.ts` 走的是 Font Awesome CDN，跟 `assets/art/icons/` 那 16 个 SVG 不是一回事。

> 结论：素材库已经备好但断线了。用户说「充分利用公开素材」，**第一步不是找新素材，是把已有的 31+16 个接上**。

### 1.2 UI 结构

- 入口 `web/index.html`：字体只引 **Noto Sans SC**（Google Fonts，400/500/700）一套；图标走 **Font Awesome 6.5.1 CDN**。
- `web/src/theme/index.ts` 定义了完整 design token（势力色 `FACTION_COLORS`、地形色 `TERRAIN_COLORS`、UI 色 `UI_COLORS`、阴影、城市/军队矢量形状）。
  - ⚠️ **但组件基本不消费 token**：`#d4a84b` 在 `Panel.tsx`/`App.tsx`/`TopBar.tsx` 里硬编码出现 ~30 次，改一次主色要全局替换。
- 布局：左侧地图 `flex:1` + 右侧固定 `300px` 面板（`Panel.tsx:733`）。浮层 `TopBar`(50px) / `LlmSetupBar` / `EventTicker`(36px) / 「下一回合」按钮全部 absolute 定位。
- 组件清单：`TopBar`、`LlmSetupBar`、`GameMap`、`EventTicker`、`Panel`（内含 FactionList / CityDetail / GeneralList / DiplomacyPanel / DataPanel / EventsPanel / EventLog / ReasoningPanel）、`map/CityMarker`、`map/ArmyMarker`。

### 1.3 地图渲染（`GameMap.tsx`，649 行）

- **PixiJS 8** 手绘 `Graphics`，纯色多边形，**无贴图、无 shader、无滤镜**。
- 渲染顺序：地块底色 → 势力色块（alpha 0.42）→ 河流 → 势力边界 → 州郡边界 → 州名/城名。注释里说明「线描山脉在整图缩放下会糊成噪点，暂不绘制」（`:192`）→ **结果是整张地图没有任何地形表达**。
- 城市 / 军队标记是 **DOM overlay**（`CityMarker`/`ArmyMarker` 是 `<div>`，不是 Pixi），随 camera transform 缩放。
- `wall/`、贴图缓存、`computeChinaMask()` 等复杂逻辑已写好但**没有用在地形差异化上**。

### 1.4 真机截图（`docs/art/screenshots/`）

用 Playwright（`chromium.launch({channel:'chrome'})`, 1600×900）打开 `http://127.0.0.1:8020/`，空格推进 8 回合后截取：

| 文件 | 内容 |
|---|---|
| `01-overview.png` | 全屏总览（势力 tab，全图视角） |
| `02-map-zoom.png` | 地图滚轮放大特写 |
| `03-panel-factions.png` | 右侧势力面板 |
| `04-reasoning.png` | 决策 tab（CLI 模式空态） |
| `05-eventlog.png` | 战报 tab（战事置顶 + 建国折叠） |
| `06-data.png` | 数据 tab（武将榜 + 城池统计） |

---

## 2. 视觉问题清单（逐条，附截图位置）

### P0 — 地图没有信息层次

1. **陆地是一整块纯米色，无纸纹无地形**。`parchmentTint()`（`GameMap.tsx:516`）对所有 `terrain` 返回同一个 `0xd9c9a3`。证据：`02-map-zoom.png` 下半部，放大后仍是一块没有任何细节的米色，边缘是硬直六边形锯齿。
2. **地形零区分**：山地 / 森林 / 沙漠 / 雪地在屏幕上同色。观众无法理解「这仗为什么在这打」——而这恰恰是三国博弈的关键信息。
3. **势力色域像水渍**：`alpha 0.42` 的大色块直接叠在米色上，边缘是六边形锯齿（`02` 图左侧紫色块、中部金色块），既无边界线也无归属标注。
4. **空海吃掉半个屏幕**：`01-overview.png` 里陆地只占约 x 170–830 / 1300、y 120–500 / 900；四周大片深青 `#1b3a4b` 空着，视觉焦点被稀释。自动取景（`GameMap.tsx:102`）按整个 hex 矩形（含大量海洋格）fit，没有收紧到陆地包围盒。
5. **城市标记缩到全图就糊**：城市是一个 9–18px 圆点 + 白描边城名；全图视角下中心黄色区域多个城名重叠不可读（`01-overview.png` 中心偏下）。

### P0 — 第一眼看不懂「谁在打谁」

6. **战斗在地图上几乎无表达**：只有 `is_besieged` 的红色脉冲点（`CityMarker.tsx:57`）。没有进攻箭头、没有交战双方旗号、没有战线。看 `01-overview.png`，正在进行的三场战斗在图上完全找不到。
7. **底部 ticker 与推进按钮挤在一行**：`EventTicker` 在 `bottom:14px, right:330px`，「下一回合」按钮在 `right:318px`（`App.tsx:129`），两者相邻，ticker 只滚 4 条且无暂停/回看（`01-overview.png` 底部）。

### P1 — 文字与对比度

8. **`textMuted #5a5a72` 用在 10px 提示文字上**（「点击展开」「已等待 Ns」`Panel.tsx:825`、`LlmSetupBar.tsx:634`）。对 `#121222` 背景实测对比度约 **2.8:1**，远低于 WCAG AA 的 4.5:1，基本看不见。
9. **顶栏第二行势力统计** `#96918a` 11px（`TopBar.tsx:97`）偏暗（`01-overview.png` y≈45 那排「汉室3城 曹操2城…」）。该色对深底约 5.9:1，勉强过 AA，但 11px 小字号下观感吃力。
10. **enum 泄漏**：`汉室称kingdom！国号【汉】`（`01`/`05` 图底部）——`api/game_manager.py:619` / `renderer/game_renderer.py:727` 把 `k['type']`（值 `'kingdom'`/`'emperor'`）直接拼进中文。**后端一行文案问题，但直接破坏「看得下去」。**
11. **8 个 tab 挤在 300px 内**：每格约 37px，图标 12px + 文字 11px（`03-panel-factions.png` 顶部），「外交/事件/战报/决策」识别成本高。

### P1 — 一致性与配色语义

12. **同一颜色两种含义**：数据面板里「统帅」和「勇武」都用 `#c85046`（`Panel.tsx:634,636`），「政治」蓝、「智力」金（`06-data.png`）；而五行徽章另有一套 `ELEMENT_COLORS`（金木水火土）。观众要学两套颜色规则。
13. **势力色区分度不足**：`FACTION_COLORS` 里多个低饱和「脏色」——曹操 `#6b3020`、公孙瓒 `#c4b090`、董卓 `#3a3040`、刘表 `#7a6040`、刘焉 `#5a5070`——叠在米色羊皮纸上彼此难分（`01-overview.png` 中西部寒色块）。
14. **圆角/间距无刻度**：卡片 10px、chip 6px、命令标签 4px、stats 6px（`Panel.tsx` 内多套 `styles`），没有统一的 spacing/radius scale，拼凑感明显。

### P2 — 可访问性（当前 ≈ 无分级）

15. **无 `prefers-reduced-motion`**：围城脉冲、退却抖动、spinner 常动（`GameMap.tsx:463` 起 3 个 `@keyframes`）。全项目 Grep 0 命中。
16. **无 `:focus` / `:focus-visible` 样式**：键盘 Tab 走查看不到焦点。
17. **无高对比 / 色盲模式**：势力识别**完全依赖颜色**，无色盲安全备选（色 + 图案/纹理）。
18. **全站仅 3 处 `role`/`aria`**（均在 `LlmSetupBar.tsx`：`role="alert"`×2、`role="radiogroup"`）。地图、面板、按钮均无无障碍标注。

### P2 — 交互

19. **要理解「谁在打谁」的步数 ≥ 3**：等 ticker 滚过 → 切「战报」tab → 读文字；且**地图与事件无联动**（点事件不会定位/高亮地图）。
20. **城市无 hover / 选中反馈**：`CityMarker` 只有点击态，鼠标悬停无变化。
21. **无暂停 / 回放 / 时间轴**：「下一回合」是唯一推进方式，围观场景下无法停下来看某一回合。

---

## 3. 与「三国」题材的契合度

现在观感 = **深色数据看板 + 一张平涂的势力色块地图**。三国味只来自：势力名、金色 `#d4a84b`、一个 `🏰` emoji、少量 FA 图标。

**缺**：纸/绢/墨质感、书法或隶楷标题字、朱砂印、旗帜纹章、山形皴法、卷轴式事件流。

对标《三国志12》的「古地图」是四件事：**纸纹 + 山形线描 + 郡界墨线 + 势力色淡染**。本项目做到了第 3 项（州郡墨线）和第 4 项的一半（色淡染但没边界标注），**前两项完全缺失**——所以看起来不像古地图，像没填色的色板。

**可借鉴的成熟做法（学方法，不抄资产）**——以 P 社《十字军之王 3》为例（IGN 评测、PDS 访谈）：
- **按缩放层级切换表达**：高缩放 = 年代感羊皮纸（抽象、看势力），低缩放 = 精细地形特写（看山川/沼泽/森林）。用**缩放**而非离散 map mode 切换信息。
- **嵌套 tooltip**：悬停关键词弹出解释，tooltip 里还有高亮词可继续悬停，等于把 wiki 做进界面 → 缓解「信息密度高但看不懂」。
- **Issues 面板**：常驻提示「你现在能做什么」，本身就是新手引导。
- **提醒**：CK3 也承认信息过载会「让地图只剩邮票大小」，本项目右栏已经固定 300px，**不建议再加常驻面板**，应把信息下沉到地图本身。

---

## 4. 分阶段落地方案

> 设计原则：**先用零成本的 CSS/配置把「可读」做出来（A），再用公开素材补「质感」（B），最后才动渲染重做「表现力」（C）**。每阶段给可验收标准。

### 阶段 A（1–2 天，纯 CSS / 配置，零风险）

| # | 改动 | 位置 | 代价 |
|---|---|---|---|
| A1 | 建立 token 刻度：字号（11/12/13/15/20）、圆角（4/6/8/10）、间距（4/8/12/16），组件改用 token | `theme/index.ts` + 各组件 styles | 低 |
| A2 | 提对比度：`textMuted` `#5a5a72` → `#8a86a0`（对深底 ≥4.5:1）；`textSecondary` 11px 场景提到 12px | `theme` + `Panel.tsx:825` / `LlmSetupBar.tsx:634` | 低 |
| A3 | 统一配色语义：统帅/勇武拆开（统帅用红、勇武用橙），与五行色合并成一套 | `Panel.tsx:634-637` | 低 |
| A4 | 字体层级（零新增体积）：标题/回合数用系统衬线栈 `"Songti SC","STSong","SimSun",serif`，正文保持黑体 | `index.html` + `TopBar` | 低 |
| A5 | 地图视野收紧 + 空海压暗：fit 到陆地包围盒（不用整张 hex 网格）；海色 `#1b3a4b` 加 CSS 多层径向渐变做轻微「海图」层次 | `GameMap.tsx:102` + 容器样式 | 低 |
| A6 | 修 enum 文案：`称{k['type']}` → 映射表 `{'kingdom':'王','emperor':'帝'}` | `api/game_manager.py:619` + `renderer/game_renderer.py:727`（后端，需程基岩确认） | 极低 |
| A7 | 补 `prefers-reduced-motion`：动画在 reduced-motion 下停用 | `GameMap.tsx:463` keyframes | 低 |

**验收标准（A）**
- 用 Playwright 重新截 `01`~`06` 存 `docs/art/screenshots/phase-a/`，与旧图逐张对比；
- 正文文字对比度 ≥ 4.5:1、大字号 ≥ 3:1（用 Lighthouse / `polished` 的 `getContrastRatio` 或 WebAIM 工具核对，把数值写进 PR）；
- 全图视角下陆地占屏宽 ≥ 70%（当前约 50%）；
- 底栏不再出现任何英文 enum 单词。

### 阶段 B（3–5 天，引入公开素材）

| # | 改动 | 来源（URL + 许可，见 §5） | 体积影响 |
|---|---|---|---|
| B1 | 中文 Web 字体：正文/事件流用**霞鹜文楷**，标题用**思源宋体** | LXGW WenKai / Source Han Serif（OFL 1.1） | 用 `cn-fontsource` 分包，按需加载，首屏仅请求用到的分包（每包 ~64–70K），**不增加首屏阻塞** |
| B2 | 把已下的 16 个 game-icons SVG 真正接进城市/军队/事件图标（替换部分 FA 图标，或反向统一到 FA 一套以免风格混） | `assets/art/icons/`（CC BY 3.0，需保留署名行） | 近乎零（矢量） |
| B3 | 地图陆地加**无缝纸纹**（tileable parchment），用 Pixi `TilingSprite` 或 CSS pattern | ambientCG / Poly Haven（CC0） | 单张 512² WEBP 约 100–300K，可接受 |
| B4 | 势力配色重制：明度分层 + 色相均分，出**4 套方案**（含一套色盲安全版） | 自研（用 Lospec 调色板参考） | 零 |
| B5 | 事件流容器换卷轴/绢纹边框（9-slice 或 CSS border-image） | ambientCG CC0 / 自绘 | 小 |

**验收标准（B）**
- 字体：`font-display: swap`，首屏无白屏；Network 面板确认只加载用到的分包；中文字重与现有一致（不跳字）；
- 图标：全站图标描边粗细统一（不要再出现 game-icons 细描边 + FA 粗实心混排）；
- 纸纹：放大到 200% 无缝、无接缝；叠加后地图 fps 不掉；
- 势力色：任意两方在色盲模拟（deuteranopia/protanopia）下仍可区分，附对比图。

### 阶段 C（1 周+，需重做渲染）

| # | 改动 | 说明 |
|---|---|---|
| C1 | **地形分层渲染**：`parchmentTint` 改为按 `terrain` 返回不同纸色 + 用 Pixi 画「山形皴法」线描（分层：底纸色 → 山脉线描 → 河流 → 郡界 → 势力淡染 → 城市/军队） | 当前 `:192` 注释因「缩放糊成噪点」放弃了山脉；正解是**按缩放 LOD**：整图不画、放大才画（学 CK3） |
| C2 | **战斗可视化**：进攻箭头（Pixi 动画）、交战点冲击波、行军路径虚线；战报事件 ↔ 地图高亮联动（点事件定位） | 直接解决 P0-6 |
| C3 | **势力旗号/纹章**：12 方各一面矢量旗，城市标记换成「旗 + 城名」 | 解决「归属一目了然」 |
| C4 | 地图信息层级：缩放驱动 LOD（远 = 羊皮纸势力图，近 = 地形特写）+ 城名标签避让 | 解决 P0-5 |

**验收标准（C）**
- 单场战斗能**只看地图**看懂「从哪打到哪、谁赢」（去掉文字仍可复述）；
- 地图在 60fps 目标下 ≥ 55fps（Chrome DevTools Performance）；
- 全图视角城名不重叠（标签避让生效）；
- 缩放跨级时无闪烁、无贴图接缝。

---

## 5. 素材清单（URL + 许可，均已联网核实）

> 核实时间：2026-10-03。**只有明确可商用 / 可署名授权的才列入**。

### 5.1 已在项目里、可继续用

| 名称 | 来源 URL | 许可 | 商用 | 署名 | 备注 |
|---|---|---|---|---|---|
| Kenney 素材 | https://kenney.nl | **CC0 1.0** | ✅ | 不要求 | 官网 Support 页确认「all game assets… public domain licensed (CC0)」，可商用、无需署名 |
| game-icons.net | https://game-icons.net | **CC BY 3.0** | ✅ | **必须** | 官网 about/faq 确认；建议署名行 `Icons made by {作者}. Available on https://game-icons.net`；2026-09 站点约 4,180 图标 |
| Font Awesome Free 6.5.1 | https://fontawesome.com/license/free | 图标 **CC BY 4.0** / 字体 **OFL 1.1** / 代码 **MIT** | ✅ | 文件内已内嵌署名，正常使用无需额外操作 | 项目已在用 CDN；勿移除文件内注释 |

### 5.2 阶段 B 计划引入

| 名称 | 来源 URL | 许可 | 商用 | 署名 | 体积 / 注意 |
|---|---|---|---|---|---|
| 霞鹜文楷 LXGW WenKai | https://github.com/lxgw/LxgwWenKai（最新 v1.522） | **SIL OFL 1.1** | ✅ | 保留 OFL 声明、不改名冒用 | 全量 TTF **约 24–27MB**（Light/Medium/Regular），**必须分包/子集化**后再上 Web |
| 思源宋体 Source Han Serif SC | https://github.com/adobe-fonts/source-han-serif | **SIL OFL 1.1** | ✅ | 同上 | 单字重 TTF **约 8–13MB**，同样需 WOFF2 + 子集 |
| 中文网字计划（CN fontsource） | https://github.com/KonghaYao/chinese-free-web-font-storage ｜ 站点 https://chinese-font.netlify.app/zh-cn/ | 只收免费可商用字体，逐字体标注 | ✅ | 按字体 | 用 `cn-font-split` 分包：每个 woff2 片段 ~64–70K，靠 `unicode-range` 按需加载；NPM 包 `@chinese-fonts/lxgwwenkai` |
| ambientCG 纸纹/材质 | https://ambientcg.com （Paper / Cardboard 分类） | **CC0 1.0** | ✅ | 不要求 | 2000+ PBR 材质，JPG/PNG、多分辨率；已确认「CC0，商用免费，无需署名」 |
| Poly Haven 纹理 | https://polyhaven.com | **CC0** | ✅ | 不要求 | HDRI / Textures / Models 均 CC0 |

### 5.3 明确**不推荐**（版权风险）

- ❌ **光荣《三国志》系列**的任何立绘、地图、UI、字体 —— 均为版权素材，**不能抄资产**；只可学其「信息层次」方法。
- ❌ **影视剧照、游戏角色立绘、ACG 同人图** —— 权属复杂，不碰。
- ❌ 任何「免费但仅个人非商用」的字体/素材站下载物 —— 上线即侵权。
- ⚠️ **旗号 / 纹章**：无可靠 CC0 三国纹章库，建议**自绘矢量**（简单几何：圆形/方形底 + 势力色 + 单字/简笔图案），或用 game-icons.net 的现成符号组合。

---

## 6. 可访问性分级建议（供 UX 规格引用）

当前项目 **无分级**。建议**至少定到 Standard**，并纳入 `design/accessibility-requirements.md`：

| 分级 | 本项目应含 | 现状 |
|---|---|---|
| Basic | 键盘可达、focus 可见、对比度 AA、`prefers-reduced-motion` | ❌ 全缺 |
| **Standard（建议目标）** | Basic + 色盲模式（势力配色安全版 + 图案辅助）+ 文本缩放 200% 不破版 | ❌ |
| Comprehensive | Standard + 字幕/事件流朗读 + 高对比主题 + 输入重映射 | ❌ |
| Exemplary | 全特性 + 完整屏幕阅读器支持（Pixi 地图加 ARIA 描述层） | ❌ |

> 注：**UX 规格（文策渊产）须引用此分级**。地图类内容的屏幕阅读器支持是长期项，建议先做 Basic + 色盲模式落地。

---

## 7. 待用户决策项

1. **是否引入新中文字体？** 引入会多出分包请求（每包 ~64–70K，按需加载，首屏通常只 2–4 包 ≈ 200–300K）。**收益**：标题/正文有汉风层级，是「三国味」成本最低的一招。要不要做？
2. **图标风格统一到哪一套？** (a) 全用已下的 game-icons（16 个不够覆盖，需再补下载）；(b) 全用 FA（现成但偏现代）；(c) 混合（需统一描边）。倾向 (a) 或 (c)，因为 game-icons 更「游戏/古风」。
3. **地图重做深度到哪（阶段 C 范围）？** C1 地形分层 / C2 战斗可视化 / C3 旗号纹章 三件哪几件进本轮？建议 C2 优先（直接解决「看不懂战况」），C1 次之。
4. **势力配色重制要不要连历史考据一起做？**（如按汉/魏/蜀/吴传统色）还是只按「区分度 + 色盲安全」优化？
5. **是否接受阶段 A 先落 1–2 天验证效果**，再决定投入阶段 B/C？

---

## 8. 阻塞项 / 风险

- 🔴 **`kingdom` 文案在后端**（`api/game_manager.py` / `renderer/`），属程基岩 / 文策渊范围；我只能在本文档记录，**需主理人派单修复**。
- 🟡 **`parchmentTint` 忽略地形** 是渲染层问题，阶段 C1 才动；阶段 A 无法靠 CSS 解决地形区分。
- 🟡 **字体体积**：思源宋体/霞鹜文楷**必须分包**，直接引全量会在慢网下阻塞——**不可裸引**。需程基岩确认 Vite 侧接入方式（`vite-plugin-font` 或预生成分包）。
- 🟡 **可访问性评级为空**：UX 规格目前无分级可引用，需与文策渊对齐后再写 UX 文档。
- 🟢 素材**已备好但断线**——阶段 B 接上的成本极低，是本轮性价比最高的动作。

---

*附：截图见 `docs/art/screenshots/`（01–06），阶段A 改造后见 `docs/art/screenshots/phase-a/`。*

---

# 附：阶段 A 执行记录（2026-10-03）

> 依据本文档 §4 阶段 A 清单执行；team-lead 已批准，并把「接入已有素材」从阶段 B 提前到 A。

## 已落地的改动

| 项 | 改动 | 文件 |
|---|---|---|
| A1 token | 新增 `SPACE`/`RADIUS`/`FONT_SIZE`/`FONT_STACK` 令牌；`UI_COLORS` 提亮 | `theme/index.ts` |
| A2 对比度 | `textMuted #5a5a72`（2.8:1）→ `#8a86a0`（≈5.3:1）；`textSecondary #96918a` → `#a8a29a`（≈7.3:1）；同步替换 `TopBar`/`Panel`/`LlmSetupBar`/`EventTicker` 里的旧值 | 多处 |
| A3 语义色 | 「统帅」「勇武」拆分：新增 `STAT_COLORS`（统帅朱 `#e0705a` / 勇武橙 `#d99a3c` / 政治蓝 / 智力金 / 忠诚绿） | `theme` + `Panel.tsx` |
| A4 字体层级 | 标题/回合数/城名用系统衬线栈 `.font-serif`（零体积） | `index.html` + `TopBar.tsx` + `Panel.tsx` |
| A5 地图取景 | 取景由「整张 200×120 网格」改为**陆地包围盒**（按 `province_id`），陆地横向占比 **50.4% → 87.0%** | `GameMap.tsx` |
| A5 地形 | `parchmentTint()` 不再对所有地形返回同色，改查 `TERRAIN_PARCHMENT` 表 → 山地/森林/沙漠/雪地/草原可区分（修复 P0-1） | `theme` + `GameMap.tsx` |
| A6 enum | `称kingdom！` → `称王！`（team-lead 已在 HEAD `1ee105a` 修复） | 后端 |
| A7 reduced-motion | 全局 `@media (prefers-reduced-motion: reduce)` 关停动画；并补 `:focus-visible` 焦点样式 | `index.html` |
| 素材接入 | 10 个 game-icons（gate/military-fort/castle/hill-fort/crown/siege-tower/crossed-swords/horse-head/shield/scroll-quill）经 Vite 引入，CSS mask 着色：城池按等级换剪影 + 都城加冕 + 围城攻城塔，军队按状态换剪影，事件流用卷轴 | `CityMarker.tsx` / `ArmyMarker.tsx` / `EventTicker.tsx` + `src/assets/icons/` |
| 死代码 | 删除 `utils/colors.ts`（**与 theme 冲突的旧配色副本，真正的雷**）、`utils/tiles.ts`（远程 CartoDB 底图，已废）、`utils/mapIcons.ts`（FA CDN 纹理，未用），共 283 行 | — |
| 死素材 | 删除 `web/public/art/`（47 个素材，Vite 原样复制进 dist = 188K 死体积）；改用 `web/src/assets` + Vite import，**只发布被引用的**，且自动 hash 缓存 | — |

## 验收结果

| 标准 | 结果 |
|---|---|
| `npx tsc --noEmit` | ✅ 通过 |
| `npm run build` | ✅ 通过（769 模块） |
| 正文对比度 ≥4.5:1 | ✅ `textMuted` ≈5.3:1、`textSecondary` ≈7.3:1 |
| 陆地占屏宽 ≥70% | ✅ **87.0%**（改造前 50.4%，脚本量化） |
| 底栏无英文 enum | ✅ 截图 `phase-a/05-eventlog.png` 无英文 |
| `web/dist` 无未引用素材 | ✅ `dist/art` 已消失；`dist` 756K（原含 art 约 940K）；图标被 Vite 内联进 JS |
| 前后截图对比 | ✅ `docs/art/screenshots/`（前） vs `phase-a/`（后），6 张 |

## 关于六角地块（31 个 Kenney）——未接入，理由

实测 `assets/art/hex/*.png` 全部为 **65×89 六角蒙版**（四角透明，不透明占比 81.18%，即六边形面积比）。结论：
1. **不能当无缝背景纹理**——六角蒙版平铺会露缝；`_full` 变体与基础版蒙版一致，并非方形满铺。
2. **当逐格贴图**需 ~24000 个 Sprite（其中 16970 是海），且 Kenney 是卡通体素风，会推翻现有「平涂羊皮纸 + 墨线」的古地图定位，风格冲突 + 性能风险。
→ 故**不发布**（已从 `web/public/art/` 移除）。原始素材仍完整保留在 `assets/art/hex/` 作为素材库。若阶段 C 决定改走「地块浮雕」路线（C1），再评估接入。

## 遗留 / 待办

- ⚠️ **署名可见性**：现已在 `web/index.html` 加入署名注释，但 CC BY 3.0 要求在**产物中可见**。建议后续加「关于/素材」入口做可见署名（需文策渊/程基岩配合定位置）。
- `zhangjiao #FFD700` 与 `han #DAA520` 两色过近、多个低饱和「脏色」——属 §4 阶段 B4（势力配色重制），本轮**未动**（team-lead 决策：考据暂不做）。
- 地图第一屏仍是「色块为主」；地形已可区分，但「更有古地图味」的纸纹/山形线描属阶段 C1。
- 战斗可视化（进攻箭头/交战双方）属阶段 C2，本轮未做——「看不懂战况」的根因仍在。

---

## 附二：阶段 A 追加（署名 + 势力配色微调，2026-10-03）

> team-lead 二次决策后追加。截图见 `docs/art/screenshots/phase-a-final/`。

### 1. 可见素材署名（CC BY 法律义务）

新增 `web/src/components/AttributionBar.tsx`，并在 `App.tsx` 把布局改为 `列[ 行[地图, 面板], 署名条 ]`：

- **始终可见**的一行页脚（22px）：`素材署名：game-icons.net（CC BY 3.0）· Font Awesome（CC BY 4.0）· Noto Sans SC（OFL）· Kenney（CC0）` + 「详情」按钮。
- 点「详情」展开完整署名：作者名 + 许可 + 官方链接 + 指向 `assets/art/ATTRIBUTION.md`。
- 组件内是 `CREDITS[]` 数组，**新增素材必须同步加一条**（避免变成「写了没接线」的假署名）。

覆盖到的实际素材：game-icons.net（10 个图标，CC BY 3.0 **必须署名**）、Font Awesome Free 6.5.1（UI 图标，CC BY 4.0 **必须署名**）、Noto Sans SC（OFL 1.1）、Kenney（CC0，当前未发布，列出备查）。

### 2. 势力配色「最小区分度」微调

只修**过近色对**，不做考据重制（team-lead 限定范围）。用 CIELAB ΔE 量化：

| 指标 | 现状 | 调整后 |
|---|---|---|
| 最小两两 ΔE | **17.2**（dongzhuo×liuyan） | **28.4** |
| 对羊皮纸底最小 ΔE | **9.2**（gongsunzan 几乎隐形） | **35** |
| 红绿色盲模拟最小 ΔE | **1.0**（caocao×sunjian 完全同色） | **6.8** |

改动（保留原主题意象，只拉开明度/色相）：
- `han #DAA520`（深金，与黄巾撞）→ `#CE2A18` 朱红（汉·火德尚赤）
- `gongsunzan #c4b090`（米褐，ΔE 9.2 隐形于底）→ `#6E8073` 北疆灰绿
- `caocao #6b3020` / `sunjian #8B2020` / `liubiao #7a6040` 三个深暖互相糊 → `#5E3828` / `#8A1A2B` / `#9C7A34`
- `mateng #5a3070` / `liuyan #5a5070` / `dongzhuo #3a3040` 三个深紫近黑 → `#6B3FA0` / `#A99BC4`（提亮）/ `#1D1B24`（压更黑）
- `zhangjiao #FFD700` → `#EFC200`、`yuanshao #CC7733` → `#DB861D`、`yuanshu #b04060` → `#C81E63`（微调）

**顺带修一处「两个事实源」隐患**：`FACTION_GLOW` 原本是手写的、与 `FACTION_COLORS` 脱节的 rgba 副本（改色时必漏改），现改为**从 `FACTION_COLORS` 派生**。

⚠️ 诚实说明：12 方**仅靠颜色无法对色盲完全友好**（模拟下最小 ΔE 仅 6.8）。需要**非颜色线索**（势力旗号/图案/文字标签）才能真正达标——这属阶段 B/C，已在 §6 可访问性分级里列为 Standard 级要求。

---

## 附三：中文字体「体积账」（阶段 B 前置，实测，2026-10-03）

> team-lead 要求：**先出账再决定上不上**；阈值「首屏 >300K 或 FCP 明显变差则不上」。
> 方法：Playwright（Chrome，1600×900，禁用缓存）+ CDP `Network.loadingFinished.encodedDataLength`
> 统计**真实传输字节**；FCP 取 `PerformancePaintTiming`。两组网络：LAN（无节流）与 Fast 3G
> （latency 150ms / 1.6Mbps）。字体用真实分包源：
> `https://cdn.jsdelivr.net/npm/@chinese-fonts/lxgwwenkai@3.0.0/dist/LXGWWenKai-Regular/result.css`
> （cn-font-split 生成，**按 unicode-range 切成 ~1940 个 woff2 分片，浏览器只取用到字的片**）。

### 实测结果

| 方案 | 首屏请求数 | 首屏总传输 | FCP（LAN） | FCP（Fast 3G） |
|---|---|---|---|---|
| 基线（现状，Noto Sans SC 走 Google Fonts） | 22 | **1427K** | 508ms | 3180ms |
| + 霞鹜文楷（CSS **同步**阻塞） | 32 | 1498K | 680ms | 3548ms |
| + 霞鹜文楷（CSS **异步** preload） | 32 | 1498K | 512ms | 3540ms |

**霞鹜文楷自身开销：19 个请求 / 549K**（其中字体 CSS 69K + woff2 分片 ~480K）。

### 关键发现：它主要在「替换」而不是「叠加」

基线那 1427K 里，**本来就有约 500K 是 Noto Sans SC 的中文 woff2**（Google Fonts 按 unicode-range 分包，
首屏中文多，于是拉了一大把分片）。把主字体换成霞鹜文楷后，Noto 的分片基本不再请求
（22 → 13 个非字体请求 + 19 个霞鹜请求）。

→ **净增 ≈ +71K / +10 个请求**，不是 +549K。

### 结论与建议

1. **净增 71K < 300K 阈值**，从体积看不构成否决理由。
2. **必须异步加载字体 CSS**（`rel=preload as=style onload` 或 `media=print/onload`）：
   LAN 下 FCP 影响从 +172ms 降到 **+4ms**（可忽略）。同步 `<link>` 会阻塞渲染。
3. **必须只上需要的字重**。霞鹜文楷有 Light/Regular/Medium（**没有 Bold**）——
   别把 Light/Mono 一起引。UI 里的 `font-weight:700` 会走合成粗体或回退，需设计上接受。
4. **Fast 3G 下 FCP 仍 +360ms**：即使异步，480K 分片仍与小 500K 的 JS 抢带宽。
   若严格要求 FCP 不退化，建议**只在「事件流 / 决策正文」等文本区局部用霞鹜文楷**，
   控件与数据面板保持系统字体，可显著减少首屏用到的不重复汉字数。
5. **更省的替代方案（我更推荐先试这个）**：项目**已经在用 Google Fonts**。
   把标题字体从 `Noto Sans SC` 换成同一家的 **`Noto Serif SC`**（同样是 OFL、同一个 CSS 请求追加一个 family），
   **零新集成、几乎零额外首屏成本**，就能拿到「宋体标题」的汉风层级。
   → 建议阶段 B 先做这条，霞鹜文楷仅用于事件流正文，按需局部引入。

> 🔴 待 team-lead 拍板：方案 (a) 全局霞鹜文楷（净 +71K，Fast3G FCP +360ms）；
> (b) 仅标题换 Noto Serif SC（近零成本）；(c) 先 (b) 再局部 (a)。我建议 (c)。

