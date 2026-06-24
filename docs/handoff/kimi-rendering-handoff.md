# Kimi 接手 — 地图渲染层重构指令

> 日期: 2026-06-24
> 交接方: DeepSeek → Kimi
> 分支: feat/web-frontend
> 状态: 后端数据完整，前端渲染颜色混乱需重写

---

## 一、现状

### 已完成的（不要动）
- ✅ `game/map_generator.py` — 中国 GeoJSON 遮罩 + 15 地形生成 + 省界分配
- ✅ `game/constants.py` — 地形常量 + TERRAIN_PROPERTIES + 势力定义
- ✅ `game/engine.py` — MapGenerator 已接入 _init_hex_map()
- ✅ `game/tile.py` — 15 种 TerrainType
- ✅ `game/hex_grid.py` — 坐标系统 + Direction 枚举
- ✅ `data/city_positions.json` — 22 城坐标（200×120 网格）
- ✅ `api/game_manager.py` — 发送 province 元数据

### 需要 Kimi 重写的（仅前端）
- ❌ `web/src/components/GameMap.tsx` — 渲染逻辑混乱
- ❌ `web/src/theme/index.ts` — 颜色需统一

---

## 二、数据流说明

```
MapGenerator.generate(200, 120)
  └→ 每个格子的数据:
       - q, r: 轴向坐标
       - terrain: 15 种之一 (grass/desert/forest/hill/mountain/peak/plain/
                    grassland/dense_forest/marsh/tundra/snow/water/deep_water/river)
       - province_id: 省界内=古州名(sili/yuzhou/...), 水体=null, 境外=null
       - faction: 引擎设置(城市势力范围), 默认 null

API /api/state 返回:
  hex_map: { width, height, tiles: [{q, r, terrain, faction, province_id}] }
  provinces: { "sili": {name:"司隶", color:"#C9A96E"}, ... }
  faction_stats: { "caocao": {name:"曹操"}, ... }
  cities: { "luoyang": {position:{q,r}, name:"洛阳", faction:"han"}, ... }
```

---

## 三、渲染逻辑（核心）

### 每个格子的填充色，按优先级判定：

```
① 有 faction 且 ≠ "neutral" → 势力色（见第四节）
② 有 province_id      → 统一米色 #c8b878（所有中国无主地同色）
③ terrain 是 water/deep_water → 蓝色（见第五节海洋色）
④ 其他（境外陆地）     → 灰色 #999999（未探索）
```

**重要**：不做任何颜色混合、不做亮度偏移、不做 terrain→颜色的映射。纯四色判定。

### 渲染层次（从底到顶）：

```
Layer 0: 虚拟边界灰白雾（网格外 80 格缓冲）
Layer 1: 六角格填充色（按上述逻辑）
Layer 2: 势力边界线（6px 宽，势力色实线，仅在相邻格势力不同时绘制）
Layer 3: 州郡边界线（2.5px 宽，淡金色虚线，仅在相邻格 province_id 不同时绘制）
Layer 4: 州名标注（20px 金色粗体，黑色描边，半透明深色背景板）
Layer 5: 城名标注（14px 白色粗体，🏯图标前缀，黑色描边）
```

---

## 四、势力色板

按 184 年初始政治关系设计，**禁止使用蓝色系**（蓝=海洋）：

```typescript
const FACTION_COLORS: Record<string, string> = {
  // 黄巾叛乱 — 亮金（与全天下对立，最鲜明）
  zhangjiao: '#FFD700',
  // 汉室联盟 — 暖色系
  han: '#DAA520',           // 汉室 — 深金
  caocao: '#6b3020',        // 曹操 — 红褐
  liubei: '#2d7a3a',        // 刘备 — 森林绿
  sunjian: '#8B2020',       // 孙坚 — 暗红
  yuanshao: '#CC7733',      // 袁绍 — 铜橙
  gongsunzan: '#c4b090',    // 公孙瓒 — 米褐
  mateng: '#5a3070',        // 马腾 — 深紫
  // 董卓 — 冷暗（对立阵营）
  dongzhuo: '#3a3040',
  // 中立观望
  liubiao: '#7a6040',       // 刘表 — 棕
  liuyan: '#5a5070',        // 刘焉 — 灰紫
  // 袁术 — 玫红（袁绍之弟/竞争者）
  yuanshu: '#b04060',
  neutral: '#666666',
}
```

---

## 五、海洋色

```typescript
water:      '#4499cc'   // 浅海蓝
deep_water: '#226688'   // 深海蓝
```

---

## 六、需要修改的文件

### `web/src/components/GameMap.tsx`

**重写整个渲染 useEffect**（约 line 82-250）。关键点：
1. 构建 tileMap（q,r → {terrain, faction, province_id}）
2. 构建 coords（所有需要渲染的坐标集合）
3. 按优先级判定填充色（四色逻辑）
4. 绘制虚拟边界灰白雾（80 格外围）
5. 绘制势力边界（6px 实线）
6. 绘制州郡边界（2.5px 虚线，淡金 #c8b878）
7. 绘制州名（20px 金色，带背景板）
8. 绘制城名（14px 白色，🏯前缀）

**修复相机控制**（约 line 290-340）：
- 拖拽用 ref（不用 state）避免闭包过期
- 缩放范围 0.3-1.2
- 相机夹紧到地图四边

**相机初始位置**：`{ x: -2800, y: -400, zoom: 0.45 }`

### `web/src/theme/index.ts`

- 更新 FACTION_COLORS（按第四节）
- 更新 FACTION_GLOW（匹配新色）
- 保持 TERRAIN_COLORS（仅 ocean 颜色会被用到）
- 删除 adjustBrightness / getTerrainBrightness 等混合函数

---

## 七、不要改的文件

- `game/` 下所有文件
- `api/` 下所有文件
- `data/` 下所有文件
- `web/src/utils/hex.ts`
- `web/src/utils/tiles.ts`
- `web/src/types.ts`
- `web/src/components/map/CityMarker.tsx`
- `web/src/components/map/ArmyMarker.tsx`
- `web/src/components/Panel.tsx`
- `web/src/components/TopBar.tsx`

---

## 八、验证方式

```bash
cd llm-sanguo-project
python3 run_web.py --seed 42 --no-browser
# 打开 http://localhost:5173/
```

**预期效果**：
1. 中国版图清晰（米色底+势力色块）
2. 境外=灰色（蒙古/俄国/东南亚等）
3. 东海/南海=蓝色
4. 势力间有明显粗边界线
5. 州郡间有细虚线边界
6. "司隶""益州"等州名大金字可见
7. 洛阳、成都等城名白色可见
8. 滚轮缩放、拖拽平移正常
9. 无法拖出地图边界
10. 边界外有灰色雾

---

## 九、当前 bug 列表

1. 渲染颜色与预期不符（海洋非蓝、境外非灰、杂色多）
2. 相机拖拽偶尔失效（state 闭包问题）
3. 中国境外地形色透出（应为纯灰）

---

> DeepSeek 签名 | 2026-06-24
