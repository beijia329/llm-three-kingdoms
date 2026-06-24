# Kimi 接手 — 地图渲染层 + 数据层完整重构指令

> 日期: 2026-06-24 | 分支: feat/web-frontend
> 状态: 后端数据已完整，前端渲染 + 城市 + 边界需全面重做

---

## 一、项目背景

乱斗三国：LLM 驱动的 12 方势力六角格策略对战游戏。184 年黄巾之乱，中国真实地图（200×120 六角格），13 个古州郡。

---

## 二、完整需求清单

### 需求 1：地图范围
- 六角格：200 列 × 120 行 = 24,000 格
- 地理覆盖：73°E–136°E, 16°N–54°N（囊括全中国 + 东海 + 南海）
- 中国版图：用 `data/china_provinces.json`（34 省级行政区 GeoJSON）做遮罩
- 境外：蒙古、俄罗斯、朝鲜、东南亚、印度等陆地 → 灰色未探索
- 海洋：东海、南海、太平洋 → 蓝色

### 需求 2：地形系统（15 种）
中国境内 10 种陆地地形：grass(草地) / desert(沙漠) / grassland(草原) / dense_forest(密林) / hill(丘陵) / plain(平原) / peak(山峰) / tundra(冻土) / mountain(山脉) / snow(雪地)
海洋 2 种：water(浅海) / deep_water(深海)
外加 river(河流)、marsh(沼泽)

### 需求 3：颜色体系（核心）
**颜色只用来区分势力**，不用来区分地形或州郡。四层判定：

```
判定顺序（优先级从高到低）：

第 1 层 — 势力领土
  条件：tile.faction 存在且 ≠ "neutral"
  颜色：纯势力色（不混合地形色、不混合州郡色）
  说明：同一势力的所有领土统一着色

第 2 层 — 中国境内无主地
  条件：tile.faction 为空/null，且 tile.province_id 存在
  颜色：统一米色 #c8b878
  说明：全部中国无主土地同一颜色，不按地形区分

第 3 层 — 海洋水域
  条件：tile.province_id 为空，且 terrain 为 "water" 或 "deep_water"
  颜色：**全部浅蓝色 #4499cc**（不区分浅海深海）

第 4 层 — 境外未探索陆地
  条件：以上都不满足（即 province_id 为空、非水域）
  颜色：灰色 #999999
  说明：蒙古、俄国、朝鲜、东南亚等
```

**绝对禁止**：
- 不要用地形色（TERRAIN_COLORS）给陆地着色
- 不要做任何颜色混合、亮度偏移、alpha 叠加
- 势力领土必须是纯势力色

### 需求 4：势力色板（按 184 年初关系）
色系逻辑：汉室联盟=暖色系，董卓=冷色对立，黄巾=亮色突出。**禁止使用蓝色**（蓝=海洋）。

```
zhangjiao: '#FFD700'    // 黄巾 — 亮金（与全天下对立）
han:       '#DAA520'    // 汉室 — 深金（宗主）
caocao:    '#6b3020'    // 曹操 — 红褐（嫡系）
liubei:    '#2d7a3a'    // 刘备 — 森林绿（仁德）
sunjian:   '#8B2020'    // 孙坚 — 暗红（勇猛）
yuanshao:  '#CC7733'    // 袁绍 — 铜橙（盟主）
gongsunzan:'#c4b090'   // 公孙瓒 — 米褐（北疆）
mateng:    '#5a3070'    // 马腾 — 深紫（西凉）
dongzhuo:  '#3a3040'    // 董卓 — 暗灰（对立阵营）
liubiao:   '#7a6040'    // 刘表 — 棕（中立）
liuyan:    '#5a5070'    // 刘焉 — 灰紫（中立）
yuanshu:   '#b04060'    // 袁术 — 玫红（袁绍之弟/竞争者）
neutral:   '#666666'
```

### 需求 5：边界线体系（三层，从粗到细）

**5a. 势力国界线**（最粗，最明显）
- 条件：相邻两格 faction 值不同（且都不为 neutral/null）
- 样式：势力色实线，宽度 6px，alpha 0.9
- 位置：两格之间的边线中点，垂直于连线

**5b. 州郡边界线**（中等）
- 条件：相邻两格 province_id 值不同
- 样式：淡金色 #c8b878 虚线，宽度 2.5px，alpha 0.85
- 虚线：每条边分成 3 段，每段占 60%

**5c. 六角格线**（不要画）
- 同州同势力内不画格子线，让州郡形成统一板块

### 需求 6：文字标注体系（三层）

**6a. 州郡名**
- 位置：每个 province 内所有格子的几何中心
- 样式：20px 金色(#FFD700) 粗体，黑色 4px 描边
- 背景：半透明深色底板（矩形，比文字大 8px padding，alpha 0.7）
- 内容：`state.provinces[provId].name`（如"司隶""益州"）

**6b. 城市名**
- 位置：`city.position` 对应像素坐标，向下方偏移 HEX_SIZE * 1.4
- 样式：14px 白色 粗体，黑色 3px 描边
- 图标：🏯 前缀（如"🏯 洛阳"）
- 内容：`city.name`

**6c. 势力名**（可选）
- 如果该城市是势力首府，在城名下方加势力名小字
- 12px 势力色，无描边

### 需求 7：城市系统

**7a. 城市数据**
- 22 座初始城市，坐标在 `data/city_positions.json`
- 城市属性（名称、等级、势力归属）在 `data/cities.json`
- 需要扩展城市数量（至少补到每个州 1-2 座城，总共约 30+ 座）

**7b. 城市渲染**
- 城市图标：`CityMarker` 组件（DOM Overlay，已在 `web/src/components/map/CityMarker.tsx`）
- 城市标注：见需求 6b

### 需求 8：摄像机系统

**8a. 相机约束**
- 四向夹紧，不能拖出地图范围
- 公式：`cxMin = viewW/zoom - (worldW + PAD)`, `cxMax = PAD`（同理 cy）
- PAD = HEX_SIZE × 90（大范围外围缓冲区）

**8b. 地图尺寸计算**
- `worldW = HEX_SIZE × (√3 × (width-1) + √3/2 × (height-1))`
- `worldH = HEX_SIZE × (1.5 × (height-1))`

**8c. 缩放**
- 范围：0.3 – 1.2
- 滚轮：deltaY > 0 → ×0.9，deltaY < 0 → ×1.1
- 缩放以鼠标位置为中心点

**8d. 拖拽**
- 用 useRef 存储拖拽状态（不要用 useState，会闭包过期）
- 初始相机位置：`{ x: -2800, y: -400, zoom: 0.45 }`

### 需求 9：未探索区域（战争迷雾）

**9a. 虚拟格边界**
- 六角格网格之外 80 格宽的虚拟格
- 颜色：灰色 #999999（与境外陆地同色）

**9b. 不需要轮询渲染**
- 虚拟格不需要实时更新，初始绘制即可

### 需求 10：州郡板块化
- 同一 province_id 的格子不画格子线
- 同一 province 形成统一视觉板块
- 省界用虚线区分（见需求 5b）

---

## 三、数据流

```
MapGenerator.generate(200, 120)
  └→ HexMap
       └→ engine._init_hex_map()
            └→ self.hex_map = MapGenerator(rng).generate(200, 120)
            └→ 加载 city_positions.json 绑定城市坐标
            └→ 调用 load_city_positions() 读取城市坐标

API GET /api/state 返回 JSON:
{
  turn: 1, max_turns: 192, year: 184,
  hex_map: {
    width: 200, height: 120,
    tiles: [{q, r, terrain, faction, province_id, ...} × 24000]
  },
  provinces: {
    "sili":    { name: "司隶", color: "#C9A96E", capital_city_id: "luoyang" },
    "yuzhou":  { name: "豫州", color: "#D4A84B", ... },
    ...共 13 个
  },
  cities: {
    "luoyang": { position: {q, r}, name: "洛阳", faction: "han", level: 4, ... },
    ...共 22+ 个
  },
  faction_stats: {
    "caocao": { name: "曹操", cities: 2, garrison: 2000, gold: 1000, ... },
    ...共 12 个
  },
  armies: { ... },
  generals: { ... }
}
```

---

## 四、需要修改的文件

### 文件 1：`web/src/components/GameMap.tsx`（重写渲染 useEffect）

**位置**：约 line 82–260（整个渲染 useEffect）

**需要构建的数据结构**：
```typescript
// tileMap: 坐标 → 格子数据
const tileMap = new Map<string, { terrain, faction, province_id }>()
// coords: 所有需要渲染的坐标
const coords = new Set<string>()
```

**渲染层次（从底到顶，PixiJS Container 按添加顺序渲染）**：

```
Layer 0: 虚拟边界灰白雾
  - 遍历 q ∈ [-80, 280), r ∈ [-80, 200)
  - 仅 q<0 || q≥200 || r<0 || r≥120 的虚拟格
  - 填充 #999999，无边框

Layer 1: 六角格填充
  - 遍历 coords 中每个格子
  - 按优先级判定填充色（见需求 3 四层逻辑）
  - 不画六角格边框线

Layer 2: 势力边界线
  - 遍历 coords，对每个格子检查 6 个邻居
  - 如果本格 faction ≠ 邻居 faction（且都不为 neutral/null）
  - 在两格之间画势力色线段（width: 6, alpha: 0.9）
  - 去重：用 Set 记录已画的边

Layer 3: 州郡边界线
  - 按 province_id 分组所有格子
  - 对每组，遍历每个格子的 6 条边
  - 如果邻居不在同一组 → 画淡金虚线（width: 2.5）
  - 虚线：每条边分成 3 段，每段画 60%

Layer 4: 州名标注
  - 计算每个 province 的几何中心
  - 画半透明背景矩形
  - 画 20px 金色粗体州名

Layer 5: 城名标注
  - 每个 city 在其像素坐标下方 HEX_SIZE*1.4 处
  - 画 14px 白色 🏯前缀城名
```

### 文件 2：`web/src/theme/index.ts`（重写颜色常量）

**需要更新的**：
- FACTION_COLORS：替换为需求 4 的势力色板
- FACTION_GLOW：匹配新势力色

**需要删除的**（如果存在）：
- 任何 adjustBrightness 函数
- 任何 getTerrainBrightness 函数
- 任何 blendColor 函数

**需要保留的**：
- TERRAIN_COLORS（仅 ocean 色会被用到，陆地色保留但渲染时不调用）
- FACTION_COLORS（更新值）
- UI_COLORS、SHADOWS、CITY_STYLES、ARMY_STYLES（不动）

### 文件 3：`data/city_positions.json`（扩充城市）

当前 22 城，需扩充至 30+ 城。每个州 1-2 座城。

当前城市坐标（200×120 网格）：
```json
{
  "luoyang": {"q":124,"r":60}, "xuchang": {"q":129,"r":62},
  "yecheng": {"q":131,"r":56}, "chenliu": {"q":131,"r":60},
  "changan": {"q":113,"r":62}, "chengdu": {"q":98,"r":73},
  "hanzhong": {"q":108,"r":65}, "jian_ge": {"q":104,"r":68},
  "bai_di": {"q":116,"r":72}, "tianshui": {"q":104,"r":60},
  "jianye": {"q":145,"r":68}, "chai_sang": {"q":136,"r":76},
  "jiangling": {"q":124,"r":74}, "he_fei": {"q":140,"r":69},
  "wu_jun": {"q":151,"r":71}, "julu": {"q":133,"r":53},
  "ji": {"q":138,"r":44}, "xiangyang": {"q":124,"r":68},
  "nanyang": {"q":125,"r":65}, "changsha": {"q":126,"r":81},
  "shouchun": {"q":138,"r":67}, "wuwei": {"q":93,"r":50}
}
```

### 文件 4：`data/cities.json`（扩充城市属性）

当前 22 城。需为新增城市添加完整属性（id, name, faction, level, position, province_id 等）。

---

## 五、不要改的文件

```
game/          — 所有引擎代码不动
api/           — 所有 API 代码不动
data/china_provinces.json  — 省界数据不动
web/src/utils/hex.ts  — 坐标工具不动
web/src/types.ts      — 类型定义不动
web/src/components/map/CityMarker.tsx  — 城市图标组件不动
web/src/components/map/ArmyMarker.tsx  — 军队图标组件不动
web/src/components/Panel.tsx / TopBar.tsx / EventTicker.tsx — 不动
```

---

## 六、启动验证

```bash
cd llm-sanguo-project
python3 run_web.py --seed 42 --no-browser
# 浏览器打开 http://localhost:5173/
```

**验证清单**：
- [ ] 中国版图米色底 + 势力色块（金色=汉，红褐=曹，绿=刘，暗红=孙…）
- [ ] 东海/南海 = 蓝色
- [ ] 蒙古/俄国 = 灰色
- [ ] 势力间有明显的粗边界线（6px）
- [ ] 州郡间有细虚线
- [ ] 州名大字可见（司隶、益州…）
- [ ] 城名白字可见（🏯洛阳、🏯成都…）
- [ ] 滚轮缩放正常
- [ ] 拖拽平移正常
- [ ] 不能拖出中国范围
- [ ] 边界外灰色雾可见
- [ ] 无蓝色势力（蓝=海洋）

---

> DeepSeek 签名 | 2026-06-24
