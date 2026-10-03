# 美术素材来源与授权（assets/art）

> 原则：**不重复造轮子**——美术素材一律采用可商用/开源的第三方资源。
> 更新时间：2026-10-01

## 1. 六角地块 / 植被装饰（`assets/art/hex/`）
- 🔴 **状态：当前未接入（评估后决定不接入，2026-10-03）**。
  实测结论：素材为卡通体素风（65×89，与本作 55.43×64 的 hex 长宽比差 18.6%），与「平涂羊皮纸 + 墨线省界」的古地图定位冲突；
  且整图默认倍率下 1 格仅 8×9 屏幕像素、纹理不可读。详见 `docs/design/art-asset-plan.md` **§7**。
  **本目录仅作素材库保留，请勿按"替换 hex 纯色填充"实施。**
- **来源**：Kenney — *Hexagon Tiles / Hexagon Pack*（https://kenney.nl）
- **下载镜像**：https://github.com/utgarda/kenney-hexagon
- **授权**：**CC0 1.0（公共领域）**—— 可商用、可修改、**无需署名**（署名是礼貌，非义务）
- **已下载 31 个**：
  - 基础地块：`tileGrass` `tileDirt` `tileRock` `tileSand` `tileSnow` `tileStone` `tileWater`（各含 `_full` 变体）
  - 植被：`treeGreen_high/mid/low`、`pineGreen_high/mid/low`、`bushGrass`、`flowerGreen`、`flowerRed`
  - 地形：`hillGrass` `hillSnow` `hillSand`、`rockStone`、`smallRockGrass`
  - 水域/桥：`waveWater`、`tileWood_bridge`、`tileStone_bridge`
- 规格：基础 PNG **65×89**，RGBA；需更大尺寸可用其 SVG/spritesheet 版

## 2. 图标（`assets/art/icons/`）
- **来源**：game-icons.net（作者：Lorc、Delapouite、Skoll 等）
- **下载**：https://github.com/game-icons/icons
- **授权**：**CC BY 3.0 —— 必须署名**
- **已下载 16 个**（已后处理：去黑底、`fill="currentColor"`，可直接用 CSS 改色）：
  `castle` `siege-tower` `siege-ram` `horse-head` `crown` `crossed-swords` `shield`
  `treasure-map` `military-fort` `camping-tent` `gold-stack` `coins` `knight-banner`
  `gate` `scroll-quill` `hill-fort`
- ⚠️ **署名义务**：任何用到这些图标的产物须保留下面这行：
  > Icons made by Lorc, Delapouite, Skoll. Available on https://game-icons.net

## 3. 字体（候选，CDN 引用即可，无需本地打包）
| 字体 | 授权 | 用途 |
|---|---|---|
| 思源宋体 Source Han Serif SC | SIL OFL 1.1 | 标题、势力名（汉风） |
| 霞鹜文楷 LXGW WenKai | SIL OFL 1.1 | 正文、事件流（楷体） |
| Noto Sans SC | SIL OFL 1.1 | 已在用（UI 正文） |

## 4. 地图底图数据
- 阿里云 DataV GeoJSON（中国省界，项目已在用）
- 六角格地图：项目自生成（`data/hex_map.json`）

## 5. UI 面板边框（`web/src/assets/ui/`，2026-10-03 新增）
- 🔴 **状态：已接入**（城池详情卡 `CityCard.tsx` + 快捷键说明面板 `ShortcutHelp.tsx` 的九宫格边框）。
- **来源**：Kenney — *UI Pack*（https://kenney.nl/assets/ui-pack；镜像 https://opengameart.org/content/ui-pack）
- **文件**：`web/src/assets/ui/panel-frame.svg`
  - 由包内 `Vector/Grey/button_rectangle_border.svg` **改色**而来：三档灰（#989AAF/#FFFFFF/#DADCE7）
    替换为本作暗金主题色（#5a4a24/#f0e2b4/#b9974a），并删除原作者用于标注九宫格切片线的两枚 2px 红色
    标记（#FF0000）—— 那两枚标记在 `border-image` 下会在边框中部露出红点。
- **授权**：**CC0 1.0（公共领域）** —— 可商用、可修改、**无需署名**
- **用途**：卡片边框（`border-image: url(panel-frame.svg) 8 / 8px / 0 stretch`）
- **规格 / 体积**：SVG，192×64，**约 1.1 KB**（远低于 300 KB 单文件上限）
- **下载校验**（2026-10-03）：
  - 包文件 `kenney_ui-pack.zip` = **1,229,750 bytes**
  - `file kenney_ui-pack.zip` → `Zip archive data, at least v2.0 to extract, compression method=deflate`
  - 解压后 `file .../button_rectangle_border.svg` → `SVG Scalable Vector Graphics image`
- **署名**：CC0 不要求署名。因本素材现已**真实用于产物**，`AttributionBar.tsx` 亦一并列出 Kenney（礼节性致谢）。

## 6. 评估后「决定不接入」的素材（留档，勿再重复评估）
- **Kenney Cursor Pixel Pack**（https://opengameart.org/content/cursor-pixel-pack，CC0）
  - 下载校验：`kenney_cursor-pixel-pack.zip` = 91,411 bytes；`file` → Zip archive data；含 185 个 PNG。
  - **不接入原因**：全部为**像素风**（Preview 实测为粗像素黑白图形），与本作「平涂羊皮纸 + 墨线省界」的
    平滑古地图定位冲突，用作光标会明显割裂。**证据**：`docs/qa/web-ui-elements-2026-10-03/pixel-cursor-rejected.png`。

---
> 新增素材时，请把「来源 / 授权 / 署名要求」补到本文件，避免授权风险。
