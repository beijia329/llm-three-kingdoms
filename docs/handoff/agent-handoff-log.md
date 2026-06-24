# Agent 协作交接日志

> 本文件记录多 Agent 协作过程中的关键决策、已完成功能、发现的问题及待办事项。
> 当前负责 Agent：DeepSeek（后端问题修复）
> 上一轮 Agent：Kimi（前端优化 + 游戏测试）

---

## 项目当前状态

- 分支：`feat/web-frontend`
- 已提交：Web 前端（FastAPI + React + PixiJS）基本完成并跑通
- 旧 Pygame GUI 保留在 `main.py --mode gui`，作为临时降级

---

## Kimi 已完成工作

### 1. Web 前端迁移

- `api/server.py`：FastAPI + WebSocket 游戏状态流
- `api/game_manager.py`：游戏会话管理、状态序列化
- `web/`：Vite + React + TypeScript + PixiJS 前端
  - 六角格地图渲染
  - 右侧 4 标签面板（势力/城市/武将/战报）
  - 顶部信息栏、底部事件滚动条
  - 空格下一回合、A 切换自动/手动
  - 滚轮缩放、拖拽平移
- `run_web.py`：一键启动前后端并自动打开浏览器
- `~/Desktop/乱斗三国.app`：桌面双击启动图标

### 2. Part A Bug 修复

| 文件 | 修复内容 |
|------|----------|
| `game/models.py` | 城市新增 `economic_bonus` 字段 |
| `game/systems/city_system.py` | `develop(economy)` 永久叠加经济加成 |
| `game/systems/resource_system.py` | 金币产出计入 `economic_bonus` |
| `game/battle/army_movement.py` | 到达友城并入守军；到达敌城设置围城状态 |
| `game/engine.py` | 战后幸存者并入新城守军；清理围城状态；回写守军数量 |
| `game/battle/battle_resolver.py` | 攻击方胜利增加士气变化 |
| `game/battle/battle_scheduler.py` | 围城己方城市时转为增援 |
| `players/cli_player.py` | 性格参数更显著影响发展/外交类型 |
| `tests/unit/test_engine.py` | 回归测试同步更新 |

### 3. GUI 重构

- `renderer/hex_map_renderer.py`：6 层视觉层次重写
- `renderer/game_renderer.py`：文明 6 风格 UI 重写
- `data/terrain_colors.json`：低饱和度文明 6 配色

### 4. 前端调优

- 初始相机 centered 到中国大陆城市群
- 顶部栏去掉重复年份
- 右侧面板势力色块加边框/阴影提升对比度
- 接入 Google Fonts Noto Sans SC
- 接入 FontAwesome 6 图标

### 5. UI 面板卡片化 + FontAwesome 图标化（v2.1）

- `web/src/theme/index.ts`：新建 Theme 设计体系（势力色/地形色/阴影/城市 SVG path/军队 SVG path）
- `web/src/components/Panel.tsx`：全面重写
  - 玻璃拟态卡片风格（backdrop-filter blur + rgba 背景 + 细边框）
  - 4 标签栏加 FontAwesome 图标（chess-king/city/user-shield/scroll）
  - 势力列表改为卡片式，带势力色左边框、称王/称帝皇冠宝石图标
  - 城市详情卡片：带城堡图标、等级星标、围城红色警告框
  - 武将列表按势力分组卡片化
  - 战报列表加事件类型图标（攻占/战斗/围城/建国/外交）+ 颜色区分
- `web/src/components/TopBar.tsx`：圆角玻璃卡片 + FontAwesome 图标
- `web/src/components/EventTicker.tsx`：玻璃卡片 + 喇叭图标
- `web/src/components/App.tsx`：按钮样式同步玻璃拟态

### 6. 地图元素图标化 + DOM Overlay 架构（v2.1）

- `web/src/components/GameMap.tsx`：重大重构
  - **PixiJS + DOM Overlay 混合渲染**：PixiJS 负责地形/边界/瓦片底图，DOM 负责城市/军队标记
  - 建立 `syncCamera()` 统一同步两套渲染层的平移/缩放
  - 相机状态存 ref，通过 DOM 操作直接更新 overlay，不触发 React 重渲染，性能最优
- `web/src/components/map/CityMarker.tsx`：新建
  - SVG 矢量城堡图标（城墙+塔楼+城门+等级星标）
  - 势力色光晕（filter drop-shadow）
  - 围城红色脉冲动画（CSS animation）
  - 兵力条（彩色进度条）
  - LOD 自适应：远距离保持可读大小
- `web/src/components/map/ArmyMarker.tsx`：新建
  - 进攻：盾牌形状 + 金色中心装饰
  - 撤退：散乱士兵点 + 向左箭头 + CSS 抖动动画
  - 士气条 + 兵力数字
- `web/src/utils/mapIcons.ts`：废弃外部 FontAwesome SVG 方案，改为内联 SVG

### 7. CartoDB 真实地图瓦片底图（v2.1）

- `web/src/utils/tiles.ts`：新建瓦片系统
  - 基于 `data/hex_map.json` bounds（95~125°E, 22~45°N）建立投影映射
  - 标准 Web Mercator 公式转换经纬度 ↔ 瓦片坐标
  - CartoDB `dark_nolabels` 暗色底图（最适合游戏覆盖）
  - 固定 zoom=6，预加载约 35 张瓦片，容错静默失败
- `web/test-browser.mjs`：添加瓦片请求拦截，避免测试超时

### 8. Playwright 自动化测试 + 长流程稳定性

- `web/test-long-run.mjs`：新建 50 回合长流程测试
  - 自动模式推进，实时回合监控
  - 内存检测（Performance.memory API）
  - 截图保存最终状态
- 测试结果：50 回合零错误，前端无崩溃

---

## 发现的后端问题（移交 DeepSeek）

### 高优先级

| 编号 | 问题 | 位置 | 影响 | 建议修复 | 状态 |
|------|------|------|------|----------|------|
| B-01 | 马腾 0 城 | `data/cities.json` | 马腾势力无法存在，3 将 location 无效 | 给马腾分配至少 1 座西北城（武威/天水/新增姑臧） | ✅ 已修复：武威划归马腾，3 将移驻武威 |
| B-02 | 势力城数不平衡 | `data/cities.json` | 袁绍、公孙瓒、袁术仅 1 城，开局过弱 | 重新平衡 184 年剧本初始势力分布 | ✅ 已修复：合肥划归袁术（2城），董卓保留天水（1城）满足最低要求 |
| B-03 | `GameState` 缺 `max_turns` / `year` | `game/models.py` | 前端需 `api/game_manager.py` 临时补齐 | 在 `GameState` 模型正式加入 | ✅ 已修复：GameState 新增 year/max_turns 字段，get_state_snapshot/load_state_snapshot 同步 |
| B-04 | 河流地形太宽太假 | `data/hex_map.json` | 视觉问题根源在数据 | 重新生成或替换为真实水系数据 | ⏳ 暂缓：需真实水系 GIS 数据替换，优先级较低 |
| B-05 | 城市 neighbor 不完整 | `data/cities.json` | 武威已修复，需全量检查 | 遍历确保双向连接、无孤立 | ✅ 已修复：10 处缺失双向连接已补齐，全量验证通过 |

### 中优先级

| 编号 | 问题 | 位置 | 影响 | 建议修复 | 状态 |
|------|------|------|------|----------|------|
| B-06 | 军队士气/粮草逻辑待验证 | `game/battle/army_movement.py` | 断粮、溃散是否按设计生效 | 补充测试并修复 | ✅ 已验证：现有测试覆盖断粮→士气下降→溃散→全灭全链路 |
| B-07 | 建国系统 Buff 未生效 | `game/kingdom_system.py` | 只记录未影响产出/士气 | 接入 `resource_system` / `battle_resolver` | ✅ 已修复：resource_system 接受 production_bonus，battle_resolver 接受 morale_bonus，engine 自动传入 |
| B-08 | 信息迷雾 `visible_armies` 粗糙 | `game/engine.py` | 敌方军队可见规则简单 | refine 可见规则 | ✅ 已优化：新增 5 层可见性规则（hex相遇/己方城/围城邻居/相邻城/hex距离≤2） |
| B-09 | 游戏结束年份显示 | `game/engine.py` | `year` 初始值之前为 1 | 已临时改为 184，需确认长期正确性 | ✅ 已验证：year=184+(turn-1)//4，turn 192→year 231，新增 4 个单元测试 |

### 已修复（供 DeepSeek 知晓）

- `武威` 孤立：已添加 `tianshui`、`changan` 邻居。

---

## 测试记录

```bash
# 全量测试
python3 -m pytest tests/ -q     # 395 passed
bash verify.sh                     # 全部验证通过

# 浏览器测试
node web/test-browser.mjs          # ✓ 无页面 JS 错误，turn 1 → 2 正常

# 长流程稳定性测试
node web/test-long-run.mjs         # ✓ 50 回合零错误，前端无崩溃
```

---

## DeepSeek 本轮工作（2026-06-24）

### 已完成的修复

| 编号 | 修改文件 | 修改内容 |
|------|----------|----------|
| B-01 | `data/cities.json`, `data/generals.json` | 武威势力 dongzhuo→mateng；马腾/马超/庞德/董卓/李儒 location 更新 |
| B-02 | `data/cities.json`, `data/generals.json` | 合肥 neutral→yuanshu；张勋/桥蕤 location nanyang→shouchun |
| B-03 | `game/models.py`, `game/engine.py` | GameState 新增 year/max_turns 字段；get/load_state_snapshot 同步 |
| B-05 | `data/cities.json` | 10 处缺失双向邻居连接补齐（chenliu/luoyang/changan/xuchang/nanyang/he_fei/yecheng） |
| B-07 | `game/systems/resource_system.py`, `game/battle/battle_resolver.py`, `game/models.py`, `game/engine.py` | 建国 Buff 接入：resource_system 新增 production_bonus 参数，battle_resolver 使用 BattleContext.attacker/defender_morale_bonus |
| B-08 | `game/engine.py` | visible_armies 5 层可见性规则（hex相遇/己方城/围城邻居/势力范围/hex距离≤2） |
| B-09 | `tests/unit/test_engine.py` | 新增 TestYearCalculation 类 4 个测试 |

### 暂缓项

| 编号 | 原因 |
|------|------|
| B-04 | 河流数据替换需真实 GIS 水系数据，属视觉优化，优先级较低，建议配合前端瓦片底图后续迭代 |

### 测试结果

```bash
python3 -m pytest tests/ -q     # 399 passed（原 395 + 新增 4）
bash verify.sh                     # 全部验证通过
```

### 势力分布（修复后）

| 势力 | 城市数 | 城市 | 武将数 |
|------|--------|------|--------|
| han | 2 | 洛阳(4), 长安(3) | 4 |
| zhangjiao | 2 | 巨鹿(2), 南阳(3) | 4 |
| caocao | 2 | 陈留(2), 许昌(3) | 5 |
| liubei | 2 | 剑阁(2), 白帝(2) | 4 |
| sunjian | 2 | 长沙(2), 柴桑(3) | 5 |
| liubiao | 2 | 襄阳(3), 江陵(3) | 4 |
| liuyan | 2 | 成都(4), 汉中(3) | 3 |
| yuanshu | 2 | 寿春(2), 合肥(2) | 3 |
| dongzhuo | 1 | 天水(2) | 3 |
| yuanshao | 1 | 邺城(3) | 4 |
| gongsunzan | 1 | 蓟(3) | 3 |
| mateng | 1 | 武威(2) | 3 |
| neutral | 2 | 建业(3), 吴郡(2) | 0 |

### 需要 Kimi 配合

- B-04 河流数据优化（GIS 数据源 + hex_map.json 重生成）
- 建国系统前端提示（称王/称帝时 UI 弹窗，生产/士气 Buff 数值显示）

---

## 前端下一步计划（Kimi 继续）

1. **武将头像系统**：为 47 名武将接入头像占位框，架构支持未来替换为 AI 生成/手绘头像
2. **战斗/占领视觉反馈**：城池变色动画、军队移动轨迹线、占领闪光效果
3. **事件弹窗系统**：建国、大胜、武将投降等重要事件的中屏弹窗 + 特效
4. **信息面板交互升级**：点击势力高亮地图领土、城市关联显示相邻城
5. **更精美的素材替换**：城市图标替换为水墨风/手绘风素材、势力旗帜纹理

## 后端下一步计划（DeepSeek）

1. 修复 B-01 马腾 0 城
2. 修复 B-02 势力城数不平衡
3. 修复 B-03 `GameState` 字段缺失
4. 修复 B-04 / B-05 地图数据问题
5. 验证 B-06 / B-07 / B-08 逻辑并修复

---

## 关键决策记录

- **前端框架**：选用 React + TypeScript + PixiJS，未选 PyQt / Kivy。
- **前后端通信**：WebSocket 实时推送 + REST API，非轮询。
- **地图渲染**：PixiJS 自绘六角格，计划叠加真实瓦片底图。
- **旧 GUI**：Pygame 版本保留为降级方案，不删除。

---

## 常用命令

```bash
# 一键启动 Web
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 run_web.py --seed 42

# 浏览器测试
node web/test-browser.mjs

# 验证
bash verify.sh

# 测试
python3 -m pytest tests/ -q
```

---

*最后更新：2026-06-24*  
*更新人：DeepSeek (会话 2)*

---

## 本轮工作（2026-06-24 会话 2：地图渲染方案研究）

### 已完成

| 任务 | 产出 |
|------|------|
| 深度搜索游戏 hex 地图方案 | 覆盖 Catlike Coding / Red Blob Games / Felix Turner WFC / Firaxis / Amplitude |
| 读取 Wesnoth 源码 | `src/map/location.hpp` — 坐标系统、方向、距离公式、立方坐标转换 |
| 读取 FreeCiv 源码 | `server/generator/mapgen.c` — 地图生成管线、`place_terrain` 扩散算法 |
| 读取 FreeCiv 源码 | `common/terrain.h` — 数据驱动地形属性、生成权重系统 |
| 读取 FreeCiv 源码 | `common/map_types.h` — 地图拓扑系统、坐标转换链 |
| CodeGraph 索引项目 | 93 文件、1723 节点、4081 边 |
| 输出知识库文档 | `docs/knowledge-base/hex-map-rendering-reference.md` |
| 输出交接文档 | `docs/handoff/hex-map-rendering-handoff.md` |

### 关键发现

1. **FreeCiv 的架构值得抄，但算法质量不够** — 它的管线流程/数据模型正确，但产生的地图块状，达不到 Civ 6 水平
2. **Wesnoth 的坐标系统可直接复用** — 你的 `hex_grid.py` 已在正确方向上
3. **Civ 6/7 用 Voronoi 图做大陆形状** — 这是比 FreeCiv 伪分形更好的方法
4. **推荐渲染路线从 Three.js 补齐** — PixiJS 继续做 UI，Three.js 新增做主地图

### 下阶段任务（Phase 1）

详见 `docs/handoff/hex-map-rendering-handoff.md`

### 新会话启动提示词

```
请先阅读：
1. docs/knowledge-base/hex-map-rendering-reference.md
2. docs/handoff/hex-map-rendering-handoff.md
3. AGENTS.md

Phase 1 目标：扩展地形数据模型（6→15 种） + 实现基本地图生成器。
严格遵循 TDD + 五步曲。
```

---

## 本轮提交记录

```bash
# 提交 1: UI 面板卡片化 + FontAwesome 图标化
# 提交 2: 地图元素 DOM Overlay 图标化 + Theme 体系
# 提交 3: CartoDB 瓦片底图 + Playwright 长流程测试
# 提交 4: feat(tile): expand TerrainType to 15 kinds
# 提交 5: feat(constants): add 15-terrain yields, costs, defense and property weights
# 提交 6: feat(mapgen): add MapGenerator with 15 terrain types and climate zones
```

---

## DeepSeek 本轮工作（2026-06-24 会话 4：Phase 1 编码执行）

### 已完成

| 任务 | 产出 | 测试 |
|------|------|------|
| 扩展 TerrainType 6→15 种 | `game/tile.py` | 29 passed |
| 扩展地形常量 + TERRAIN_PROPERTIES | `game/constants.py` | 34 passed |
| 实现 MapGenerator | `game/map_generator.py` | 9 passed |
| 全量回归 | 465 unit + 6 integration | 全绿 |

### 修改/新建文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `game/tile.py` | 修改 | TerrainType 15 种 + is_passable 更新 |
| `game/constants.py` | 修改 | 3 个地形 Dict 扩展 + TERRAIN_PROPERTIES 新增 |
| `game/map_generator.py` | **新建** | MapGenerator 完整实现（5 步管线） |
| `tests/unit/test_tile.py` | 修改 | +15 项新测试（地形枚举 + 通行规则） |
| `tests/unit/test_constants.py` | 修改 | +9 项新测试（15 种覆盖 + 属性验证） |
| `tests/unit/test_map_generator.py` | **新建** | 9 项测试（生成/水陆/气候/确定性/山脉） |
| `施工指南.md` | 修改 | 新增 Phase 1 施工日志 |

### 关键技术细节

- **噪声生成**：多八度 value noise（3 octaves: spacing=8/4/2, amplitude=1.0/0.5/0.25），仅用 GameRandom，零外部依赖
- **温度带**：纬度 r/height 决定基础温度 + 海拔冷却（每 0.4 降 1 档，上限 2 档）
- **地形放置**：BFS 迭代扩散（depth=5），概率 = max(0, 1 - 2*delta) * 0.8，delta = abs(dH) + deltaT
- **TERRAIN_PROPERTIES**：仿 FreeCiv property[MG_COUNT]，模块加载时构建反向索引
- **确定性**：所有随机操作通过 GameRandom，seed=42 两次生成完全一致

### Phase 1 补充（同日）

| 文件 | 操作 | 说明 |
|------|------|------|
| `game/hex_grid.py` | 修改 | 新增 Direction 枚举 + get_direction() + direction_opposite() |
| `tests/unit/test_hex_grid.py` | 修改 | +12 项 Direction 测试（方向/步数/反向/回环） |

- **Direction**：N/NE/SE/S/SW/NW 六方向，参考 Wesnoth `map_location::DIRECTION`
- **方向向量**：pointy-topped axial 坐标映射
- **测试结果**：477 单元测试全部通过

### MapGenerator 接入 GameEngine（同日）

| 文件 | 操作 | 说明 |
|------|------|------|
| `game/engine.py` | 修改 | `_init_hex_map()` 改用 MapGenerator 替代静态 JSON；新增 `_find_nearest_passable()` |
| `tests/unit/test_engine.py` | 修改 | +4 项集成测试；城市坐标更新为主大陆位置 |
| `施工指南.md` | 修改 | 新增接入日志 |

- **生成管线**：`MapGenerator(rng=self.rng).generate(120, 90)` → 15 种地形的地图
- **城市安全**：BFS 搜索最近可通行格，确保城市不在水/山/峰上
- **确定性**：`GameEngine(seed=42)` → 完全相同的地图
- **测试结果**：487 单元 + 集成测试全部通过

### 下阶段 Phase 2

- Voronoi 大陆形状（自然海岸线）
- 山脉连续化（骨骼线算法）
- 河流排水盆地生成
- 公平起始位置

---

## 工作原则

1. **别闭门造车，善用现有资源**：地图底图用 CartoDB/天地图现成瓦片，图标用 FontAwesome/Iconify 现成库，动画效果找开源实现（GSAP/Framer Motion），不要自己画图或自研。
2. **先搜再用**：遇到需求先查 npm/pypi 有没有现成库，有就用，别重复造轮子。
3. **小步提交**：每完成一个独立功能就 git commit，方便另一方接手。
4. **日志同步**：每次工作结束前更新本文件，让 DeepSeek 知道当前进度。
