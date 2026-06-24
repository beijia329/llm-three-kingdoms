# 六角格地图渲染方案 — 开源项目参考与实现路径

> 版本: v1.0 | 日期: 2026-06-24
> 来源: 多轮深度搜索 + 实际源码阅读（Wesnoth / FreeCiv / Felix Turner WFC / Catlike Coding / Red Blob Games）
> 目标: 为 llm-sanguo 提供从当前实现到 Civ 6 级地图的可行升级路径

---

## 一、核心结论

### 1.1 没有现成开源项目能满足全部需求

| 项目 | 领域 | 可复用部分 | 不可复用部分 |
|------|------|-----------|-------------|
| **Wesnoth** | 回合制 hex 战棋 | 坐标系统、地形数据模型、寻路 | SDL 渲染（CPU 瓶颈）、无 LLM 接口 |
| **FreeCiv** | 4X 策略 | 地图生成管线架构、地形属性系统、公平起始位置 | 算法质量不够（块状大陆、随机河流）、C 语言 |
| **Felix Turner WFC** | Web hex 地图 | Three.js 渲染管线、后处理链、BatchedMesh | 无游戏引擎、纯展示 |
| **Catlike Coding** | Unity hex 地图 | 所有渲染算法（地形/河流/迷雾/道路） | Unity C#，需移植 |

### 1.2 唯一可行路径：分层架构 + 分阶段升级

```
引擎层 (Python)     → 现有资产不动，只增强
  ├── 坐标系统       → 已有 axial 坐标，参考 Wesnoth 补完
  ├── 地图生成       → 参考 FreeCiv 管线架构，替换算法
  ├── 地形数据模型   → 参考 FreeCiv struct terrain 扩展
  └── 河流/资源/起始位 → 分阶段升级

渲染层 (Web)         → 现有 PixiJS 不动，新增 Three.js
  ├── PixiJS         → UI 面板、小地图（保持现有）
  └── Three.js       → 3D 地图渲染（新增，与 PixiJS 共存）
```

---

## 二、本次研究发现的源码级参考

### 2.1 Wesnoth 坐标系统（可以直接用的 Python 代码模板）

**文件**: `src/map/location.hpp` + `location.cpp`

关键设计:
- 偏移坐标 (x, y) + 奇偶列偏移 ← 和现有 axial 坐标等价
- 6方向: `n, ne, se, s, sw, nw`
- `get_direction(dir, n)` — 多步移动
- `distance_between(a, b)` — offset 专用距离公式
- `to_cubic()` / `from_cubic()` — 旋转/环操作时用
- `vector_sum_assign()` — hex 向量加法，含奇偶调整

**你应该直接用的**:
```python
# 你的 hex_grid.py 已有 axial 坐标，这是正确的方向
# 缺少的是：
# 1. get_direction(dir, steps) — 多步偏移
# 2. 方向枚举 + 方向解析（Wesnoth 的 parse_direction）
# 3. 向量运算的奇偶修正
```

### 2.2 FreeCiv 地图生成管线（架构可直接搬）

**文件**: `server/generator/mapgen.c`（~3000 行 C，30 年迭代）

```
map_fractal_generate()
  ├── 高度图生成 (5种算法)     ← 你需要一种即可
  ├── make_land()             ← 海陆划分
  │   ├── make_relief()       ← 山脉/丘陵
  │   ├── make_terrains()     ← 地形扩散放置
  │   ├── make_rivers()       ← 河流生成
  │   └── make_plains()       ← 剩余格填平原
  └── create_start_positions()← 起始位置
```

**核心算法 `place_terrain`**（扩散法，可直接翻译为 Python）:
```c
static void place_terrain(struct tile *ptile, int diff, 
                          struct terrain *pterrain, int *to_be_placed, ...) {
    tile_set_terrain(ptile, pterrain);
    (*to_be_placed)--;
    cardinal_adjc_iterate(&(wld.map), ptile, tile1) {
        int Delta = abs(colatitude_diff) + abs(height_diff);
        if (not_placed(tile1) && tmap_is(tile1, tc) 
            && Delta < diff && fc_rand(10) > 4)
            place_terrain(tile1, diff - 1 - Delta, ...);
    }
}
```

### 2.3 FreeCiv 地形数据模型（数据驱动设计）

**文件**: `common/terrain.h`

```c
struct terrain {
    char identifier;           // 单字符 ID
    enum terrain_class tclass; // TC_LAND / TC_OCEAN
    int movement_cost;         // 移动消耗
    int defense_bonus;         // 防御加成 %
    int output[O_LAST];        // [食物, 生产, 贸易] 产出 ← 和你现有的 TERRAIN_YIELDS 一致
    int property[MG_COUNT];    // 地图生成权重 ← 关键！控制地形分布比例
    struct terrain *transform_result; // 改造后地形链
};
```

**地形生成权重系统**:
```
MG_MOUNTAINOUS → 山/丘陵比例
MG_GREEN       → 草原/森林比例
MG_TROPICAL    → 热带比例
MG_TEMPERATE   → 温带比例
MG_COLD        → 寒带比例
MG_DRY/WET     → 湿度
MG_OCEAN_DEPTH → 海洋深度
```

### 2.4 FreeCiv 地图拓扑系统（支持不同投影）

**文件**: `common/map.h`, `common/map_types.h`

```c
struct civ_map {
    int topology_id;   // TF_ISO, TF_HEX 标志
    int wrap_id;       // 地图卷绕方式
    int xsize, ysize;  // 原生坐标尺寸
    struct tile *tiles;// 一维数组存储所有格子
    int num_continents, num_oceans;
    // ...
};
```

坐标转换链: `native ↔ map ↔ natural` — 三层坐标解耦，支持等距/hex/不同投影。

### 2.5 当前项目状态（CodeGraph 索引结果）

```
游戏引擎 (Python 71 文件)
  ├── game/hex_grid.py       ← 已有 axial 坐标系统 ✅
  ├── game/hex_map.py        ← 已有 HexMap + A* 寻路 ✅
  ├── game/tile.py           ← 6 种地形，Pydantic 模型 ✅
  ├── game/constants.py      ← 120×90 地图，32px hex ✅
  ├── game/systems/
  │   ├── map_system.py      ← 城市级邻接，非 hex 级 ❌ 需增强
  │   ├── resource_system.py ← 资源产出计算
  │   ├── city_system.py     ← 城市发展/征兵
  │   ├── diplomacy_system.py← 外交系统
  │   └── general_system.py  ← 将领系统
  ├── game/engine.py         ← 游戏引擎主类
  ├── game/models.py         ← City, Army, Faction 等
  └── game/battle/           ← 战斗系统

渲染层
  ├── renderer/              ← Pygame 渲染器 ❌ 需要 Web 化
  ├── api/                   ← FastAPI 后端 ✅
  └── (Web 前端)              ← React + PixiJS（设计中）
```

---

## 三、与目标（Civ 6 级）的差距分析

| 维度 | 当前水平 | FreeCiv 水平 | Civ 6 水平 | 差距原因 |
|------|---------|-------------|-----------|---------|
| 坐标系统 | ✅ axial | ✅ offset+cube | — | 你已有的已经是正确方向 |
| 地图生成 | ❌ 手配城市 | ⚠️ 伪分形+扩散，能玩但块状 | ✅ Voronoi+侵蚀+战略平衡 | FreeCiv 的算法不够自然 |
| 地形种类 | 6 种 | 15+ 种 | 20+ 种 | 扩展数据即可 |
| 河流 | ❌ 无 | ⚠️ 随机游走，能连海 | ✅ 分水岭→汇流→三角洲 | 需要排水盆地算法 |
| 山脉 | ❌ 无 | ⚠️ 单格随机 | ✅ 连续山脊 | 需要骨骼线+噪声 |
| 大陆形状 | ❌ 无 | ⚠️ 够用 | ✅ Voronoi 图 | 可升级 |
| 迷雾 | ❌ 无 | ⚠️ 简单 | ✅ 多层次迷雾 | 可做 |
| 渲染 | Pygame CPU | SDL CPU | GPU 着色器 | Web 前端解决 |
| 资源平衡 | 手配 | ⚠️ 公平分配 | ✅ 战略平衡 | 可升级 |
| 海拔 | 有字段 | 有 | 3D 渲染 | 数据已有，差渲染 |

### 关键判断

**FreeCiv 的算法质量：能产生"可以玩"的地图，但产生不了"好看"的地图。**

- 它的价值在**架构设计**（管线流程、数据模型、扩展性）
- 它的算法需要换：
  - 大陆形状 → Voronoi 图 + 噪声
  - 河流 → 排水盆地法（Red Blob Games）
  - 山脉 → 连续化算法

---

## 四、推荐实施路径

### Phase 1: 引擎数据层升级（纯 Python，2-3 天）

**当前可立即动手**，不涉及任何前端改动。

```
1. 扩展 terrain.py
   ├── 从 6 种 → 12+ 种 (grass, grassland, plain, forest, dense_forest, 
   │   hill, mountain, peak, desert, marsh, tundra, snow, water, deep_water)
   ├── 加入 terrain property 权重系统 (仿 FreeCiv)
   └── 加入文化/产出/移动消耗

2. 实现基本地图生成器
   ├── OpenSimplex 噪声生成高度图
   ├── 海陆划分（海拔阈值）
   ├── 纬度带→气候带映射
   ├── 扩散法地形放置（翻译 FreeCiv place_terrain）
   └── 输出 JSON 地图数据
```

**验证标准**: 生成的地图有可见的大陆、海洋、不同气候带，前端能显示 12 种颜色。

### Phase 2: 地图质量提升（纯 Python，1 周）

```
3. Voronoi 大陆形状 (参考 Civ 7 方法)
4. 山脉连续化 (Catlike Part 3)
5. 河流排水盆地 (Red Blob Games 算法)
6. 公平起始位置 (FreeCiv create_start_positions)
7. 地形颜色变体 (同类型多色值)
```

**验证标准**: 连续生成 10 张地图，目测大陆形状自然、河流从高到低、山脉成链。

### Phase 3: 渲染升级（Web 前端，1-2 周，可与 Phase 2 并行）

```
8. 引入 Three.js 叠加层 (与 PixiJS 共存)
9. Hex 坐标 → Three.js BufferGeometry
10. 海拔顶点偏移 → 3D 地形
11. 地形颜色着色器 (纹理采样)
12. 河流 UV 流动着色器
13. 迷雾引用计数系统
```

**验证标准**: 3D 地形有起伏感，视觉效果接近 Civ 5。

### Phase 4: 打磨（持续）

```
14. 后处理 (AO, DOF, 暗角) — 参考 Felix Turner
15. 动态阴影
16. 纹理图集 (不再纯色)
17. 自然纹理混合 (Catlike Part 11)
```

**验证标准**: 接近 Civ 6 视觉效果。

---

## 五、开源代码速查表

| 需要实现的功能 | 参考文件 | 语言 | 关键函数/类 |
|-------------|---------|------|------------|
| Hex 坐标系统 | Wesnoth `location.hpp` | C++ | `map_location`, `get_direction`, `distance_between` |
| 地图数据存储 | Wesnoth `map.hpp` | C++ | `gamemap`, `tiles_`, `get_terrain` |
| 地图生成管线 | FreeCiv `mapgen.c` | C | `map_fractal_generate` |
| 地形分配算法 | FreeCiv `mapgen.c` | C | `place_terrain`, `make_relief`, `make_terrains` |
| 河流生成 | FreeCiv `mapgen.c` | C | `make_river` (9 测试函数) |
| 地形数据模型 | FreeCiv `terrain.h` | C | `struct terrain` |
| 地形权重系统 | FreeCiv `terrain.h` | C | `property[MG_COUNT]` |
| 地图拓扑系统 | FreeCiv `map_types.h` | C | `struct civ_map`, `topology_id` |
| 迷雾系统 | Catlike Part 20 | C# | 引用计数 + 着色器 |
| 河流渲染 | Catlike Part 6 | C# | UV 流动 + 水面网格 |
| 地形颜色变体 | Catlike Part 2 | C# | `(q+r) % N` 色值微调 |
| 3D 渲染管线 | Felix Turner WFC | JS/TS | Three.js + TSL |
| 后处理 | Felix Turner WFC | JS/TS | AO + DOF + 暗角 |
| 排水盆地河流 | Red Blob Games | JS | 后序二叉树遍历 |
| 地域放置 | Red Blob Games | JS | Poisson Disc 采样 |

---

## 六、关键技术决策记录

### 6.1 坐标系统：已确定使用 axial (q, r)

- 当前 `hex_grid.py` 已实现 ✅
- Red Blob Games 标准实现
- Wesnoth 的 offset 坐标可通过 `to_cubic()/from_cubic()` 互转

### 6.2 渲染路线：PixiJS + Three.js 混合

- **PixiJS**: UI 面板、小地图、总览图（保持现有）
- **Three.js**: 主地图渲染（新增）
- 共存方案: PixiJS v8 官方文档有 `resetState()` 交替渲染法

### 6.3 地图生成：Python 引擎层完成

- 地图数据在 Python 端生成
- 输出 JSON 通过 WebSocket 发给前端
- 前端只负责渲染，不负责生成

### 6.4 确定性要求

- 所有随机数通过 GameRandom 生成（已有）
- 相同 seed → 相同地图

---

## 七、需要进一步研究的问题

1. **Voronoi 大陆形状生成** — Civ 7 官方确认使用，Python 端实现参考 scipy.spatial.Voronoi 或自己实现
2. **排水盆地算法** — Red Blob Games 有 JS 实现，Python 移植需要测试性能（~4-7M nodes/sec）
3. **Three.js 与 PixiJS 同画布** — 需要验证实际性能，特别是移动端
4. **中国省界叠加** — 当前 hex_map_renderer.py 已有 GeoJSON 加载，Three.js 版本需要等量实现
5. **mapgen.c 翻译** — FreeCiv 的 ~3000 行 C，核心算法约 500 行，建议只翻译 place_terrain + make_rivers 两个核心

---

## 八、相关文档索引

| 文档 | 位置 | 说明 |
|------|------|------|
| 架构设计 | `docs/design/architecture.md` | 项目整体架构 |
| 数据模型 | `docs/design/data-models.md` | 数据结构定义 |
| 六角格设计 | `docs/design/civ-style-hex-map-design.md` | Civ 风格 hex 地图详细设计 |
| 施工日志 | `施工指南.md` | 进度跟踪 |
| 开源参考 | 本文 | 开源项目源码分析 |
