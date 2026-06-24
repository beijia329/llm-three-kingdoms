# 六角格地图渲染 — 会话交接文档

> 交接给: DeepSeek 执行会话 | 日期: 2026-06-24
> 前置会话: 完成开源项目源码分析（Wesnoth / FreeCiv），确定取其精华方案

---

## 已完成的工作

1. **深度搜索了 4 轮** — 覆盖 Catlike Coding / Red Blob Games / Felix Turner WFC / Nick Chavez 逆向
2. **读了 3 个开源项目的实际源码**:
   - Wesnoth `src/map/location.hpp` — 坐标系统
   - FreeCiv `server/generator/mapgen.c` — 地图生成管线
   - FreeCiv `common/terrain.h` — 地形数据模型
3. **用 CodeGraph 索引了当前项目** — 93 文件, 1723 节点
4. **输出了知识库文档**: `docs/knowledge-base/hex-map-rendering-reference.md`
5. **确定"取其精华"方案** — 见下文"关键决策"

---

## 关键决策：取其精华，不再逆向工程

### 已完成的开源研究足够指导 Phase 1 编码

前置会话已经完成了对 FreeCiv / Wesnoth 的源码级分析，**关键算法和数据模型设计已经被提取到知识库文档中**。完整逆向工程（特别是 FreeCiv 3000 行 C 代码）边际收益极低，原因：

| 项目 | 可复用部分（已提取） | 不可复用部分（无需逆向） |
|------|---------------------|------------------------|
| **Wesnoth** | 坐标系统验证（已有 axial ✅）、方向枚举缺失项 | SDL 渲染、无 LLM 接口 |
| **FreeCiv** | `place_terrain` 扩散法伪代码、`struct terrain` property 权重设计 | 块状大陆算法、C 语言工程 noise、随机河流 |

### Phase 1 取什么精华

**直接可用的研究成果（知识库文档已有）：**
1. **FreeCiv `struct terrain` 数据模型** → 翻译成 Python `TERRAIN_PROPERTIES` Dict
2. **FreeCiv `place_terrain` 扩散法** → 已有 Python 伪代码，补全类型注解即可
3. **Wesnoth 方向枚举** → `game/hex_grid.py` 补 `Direction` enum + `get_direction(dir, steps)`

**按需逆向工程原则：**
- **不预先做完整逆向**：FreeCiv 3000 行 C 代码不逐行翻译
- **遇到具体问题时才去源码里找答案**：比如扩散法参数调不通、地形权重算法有歧义时，回查 `mapgen.c` 对应函数
- **只逆向解决当前问题的最小代码片段**：找到关键 10-20 行 C 逻辑，翻译为 Python，不要连带翻译整个模块

**Phase 1 不碰的内容（Phase 2/3 再考虑）：**
- Voronoi 大陆形状（FreeCiv 里没有，Civ 7 才有）
- 排水盆地河流（Red Blob Games JS 算法，Python 移植需独立研究）
- 连续山脉骨骼线（Catlike Coding Part 3，C# 需独立移植）
- Three.js 渲染叠加层（前端工作，与引擎层无关）

---

## 当前项目状态

```
Python 引擎: 游戏核心已跑通，hex 坐标系统已有 ✅
渲染器:     Pygame + Web 前端 (React+PixiJS) 已有 ✅
Web 前端:   React + PixiJS ✅ + CartoDB 瓦片底图 ✅
地图生成:   ❌ 没有，城市是手动配置的
地形种类:   6 种，Phase 1 扩展到 15 种
河流/迷雾:  ❌ 未实现（Phase 2）
确定性随机: GameRandom ✅（必须用于 MapGenerator）
测试覆盖:   399 passed ✅
```

---

## Phase 1 完整执行方案（DeepSeek 直接从这里开始编码）

### 执行原则
- **不再做逆向工程**：FreeCiv/Wesnoth 的精华已提取到知识库文档，直接基于已有伪代码编码
- **严格 TDD**：红→绿→重构，每个功能先写测试再实现
- **严格五步曲**：探索→规划→执行→验证→提交，不要跳步
- **小步提交**：每 1-2 个测试通过就 git commit
- **施工日志同步**：每完成一个任务，更新 `施工指南.md` 和 `docs/handoff/agent-handoff-log.md`

---

### 任务 1: 扩展地形数据模型（6 → 15 种）+ terrain property 权重系统

**修改文件**: `game/tile.py`, `game/constants.py`
**测试文件**: `tests/unit/test_tile.py`, `tests/unit/test_constants.py`

#### Step 1.1: 扩展 TerrainType（15 种）

```python
class TerrainType(str, Enum):
    GRASS = "grass"
    GRASSLAND = "grassland"
    PLAIN = "plain"
    FOREST = "forest"
    DENSE_FOREST = "dense_forest"
    HILL = "hill"
    MOUNTAIN = "mountain"
    PEAK = "peak"
    DESERT = "desert"
    MARSH = "marsh"
    TUNDRA = "tundra"
    SNOW = "snow"
    WATER = "water"
    DEEP_WATER = "deep_water"
    RIVER = "river"
```

- `Tile.is_passable()` 更新：MOUNTAIN + PEAK 不可通行；WATER/DEEP_WATER 不可通行（陆地行军视角）；RIVER 可通行但减速
- 保持向后兼容：RIVER 暂时保留为独立地形格（非叠加层简化）

#### Step 1.2: 扩展地形常量（constants.py）

扩展 `TERRAIN_MOVE_COST` / `TERRAIN_DEFENSE_BONUS` / `TERRAIN_YIELDS` 覆盖全部 15 种。

#### Step 1.3: 新增 TERRAIN_PROPERTIES（FreeCiv 精华提取）

仿 FreeCiv `struct terrain` 的 `property[MG_COUNT]`，用 Python Dict 实现：

```python
TERRAIN_PROPERTIES: Dict[str, Dict[str, Any]] = {
    # 4 个生成权重属性，控制地图生成时的分布
    # altitude: "deep" | "low" | "mid" | "high" | "peak"
    # temperature: "tropical" | "temperate" | "cold" | "frozen"
    # humidity: "wet" | "normal" | "dry"
    # vegetation: "none" | "sparse" | "dense"
    "grass":        {"altitude": "low",   "temperature": "temperate", "humidity": "wet",    "vegetation": "dense"},
    "grassland":    {"altitude": "low",   "temperature": "temperate", "humidity": "normal", "vegetation": "sparse"},
    "plain":        {"altitude": "low",   "temperature": "temperate", "humidity": "normal", "vegetation": "none"},
    "forest":       {"altitude": "low",   "temperature": "temperate", "humidity": "wet",    "vegetation": "dense"},
    "dense_forest": {"altitude": "low",   "temperature": "tropical",  "humidity": "wet",    "vegetation": "dense"},
    "hill":         {"altitude": "mid",   "temperature": "temperate", "humidity": "normal", "vegetation": "sparse"},
    "mountain":     {"altitude": "high",  "temperature": "temperate", "humidity": "dry",    "vegetation": "none"},
    "peak":         {"altitude": "peak",  "temperature": "cold",      "humidity": "dry",    "vegetation": "none"},
    "desert":       {"altitude": "low",   "temperature": "tropical",  "humidity": "dry",    "vegetation": "none"},
    "marsh":        {"altitude": "low",   "temperature": "temperate", "humidity": "wet",    "vegetation": "dense"},
    "tundra":       {"altitude": "low",   "temperature": "cold",      "humidity": "normal", "vegetation": "sparse"},
    "snow":         {"altitude": "mid",   "temperature": "frozen",    "humidity": "normal", "vegetation": "none"},
    "water":        {"altitude": "deep",  "temperature": "temperate", "humidity": "wet",    "vegetation": "none"},
    "deep_water":   {"altitude": "deep",  "temperature": "temperate", "humidity": "wet",    "vegetation": "none"},
    "river":        {"altitude": "low",   "temperature": "temperate", "humidity": "wet",    "vegetation": "none"},
}
```

#### Step 1.4: TDD 顺序
1. 先写 `test_tile.py` 扩展测试（15 种地形枚举、is_passable 新规则）→ 红
2. 修改 `tile.py` → 绿 → `git commit -m "feat(tile): expand TerrainType to 15 kinds"`
3. 写 `test_constants.py` 扩展测试 → 红
4. 修改 `constants.py` → 绿 → `git commit -m "feat(constants): add 15-terrain yields, costs, defense and property weights"`

---

### 任务 2: 实现 MapGenerator（取其精华：FreeCiv 扩散法 + 自研噪声）

**新建文件**: `game/map_generator.py`
**测试文件**: `tests/unit/test_map_generator.py`

#### 核心设计

```python
class MapGenerator:
    """六角格地图生成器

    生成管线（参考 FreeCiv mapgen.c 架构）：
    1. 多八度 value noise 生成高度图（自研，不引入外部依赖）
    2. 海陆划分（海拔阈值）
    3. 纬度→温度带映射 + 海拔修正
    4. 扩散法地形放置（FreeCiv place_terrain 精华提取）
    5. 深海标记 + 未分配填充

    所有随机数通过 GameRandom，保证确定性。
    """

    def __init__(self, rng: GameRandom) -> None: ...
    def generate(self, width: int, height: int) -> HexMap: ...
```

#### 管线详解

**Step 2.1: `_generate_height_map(width, height) -> List[List[float]]`**
- 用 `GameRandom` 实现多八度 value noise（2-3 个八度，振幅逐次减半）
- **不要引入 opensimplex/perlin-noise 等外部依赖！** 用 GameRandom + 插值即可
- 输出归一化到 `[0.0, 1.0]`

**Step 2.2: `_make_land(height_map, sea_level=0.35) -> List[List[bool]]`**
- 高度 < sea_level = 水（False），否则陆地（True）
- sea_level 可调，控制水陆比例

**Step 2.3: `_assign_temperature_band(height_map, land_mask) -> List[List[str]]`**
- 按纬度（r 坐标）分带：北部= cold/frozen, 中部= temperate, 南部= tropical
- 海拔越高温度越低：PEAK 总是 frozen

**Step 2.4: `_place_terrain(height_map, land_mask, temp_map) -> HexMap`**
- 先标记所有水格为 WATER / DEEP_WATER（深海：height < sea_level - 0.1）
- 陆地上按 "海拔+温度+湿度" 组合确定候选地形：
  - high altitude + any temp → MOUNTAIN / PEAK
  - low + tropical + dry → DESERT
  - low + tropical + wet → DENSE_FOREST / MARSH
  - low + temperate + wet → GRASS / FOREST
  - low + temperate + normal → GRASSLAND / PLAIN
  - low + cold → TUNDRA
  - mid + cold → SNOW
- **扩散法聚集**（FreeCiv `place_terrain` 精华，知识库文档已有伪代码）：
  - 从种子格开始，向邻居扩散
  - 扩散概率受高度差和温度差惩罚：`diff = abs(dH) + abs(dT)`
  - 使用 `GameRandom` 做随机判断

**Step 2.5: `_fill_unassigned(hex_map) -> None`**
- 任何未分配的地块填为 GRASSLAND 或 PLAIN

#### TDD 顺序
1. 写 `test_map_generator.py`（6 项测试，见下）→ 全部红
2. 新建 `map_generator.py` → 逐项绿
3. `git commit -m "feat(mapgen): add MapGenerator with 15 terrain types and climate zones"`

---

### 任务 3: TDD 验证（6 项测试）

新建 `tests/unit/test_map_generator.py`：

```python
# 测试 1: 生成有效 HexMap
def test_generate_creates_valid_hex_map():
    rng = GameRandom(seed=42)
    gen = MapGenerator(rng)
    hex_map = gen.generate(30, 20)
    assert hex_map is not None
    assert len(list(hex_map.iter_tiles())) == 30 * 20

# 测试 2: 有水有陆地
def test_map_has_both_land_and_water():
    rng = GameRandom(seed=42)
    gen = MapGenerator(rng)
    hex_map = gen.generate(60, 40)
    terrains = {t.terrain for t in hex_map.iter_tiles()}
    assert any(t in (TerrainType.WATER, TerrainType.DEEP_WATER) for t in terrains)
    land_terrains = {TerrainType.GRASS, TerrainType.PLAIN, TerrainType.FOREST, ...}
    assert any(t in land_terrains for t in terrains)

# 测试 3: 气候带存在（南部热带、北部寒带）
def test_climate_zones_present():
    rng = GameRandom(seed=42)
    gen = MapGenerator(rng)
    hex_map = gen.generate(60, 40)
    # 南部行应有 tropical 类
    # 北部行应有 cold/frozen 类
    # 通过 TERRAIN_PROPERTIES 反查 temperature 验证

# 测试 4: 相同 seed 确定性
def test_deterministic_with_same_seed():
    rng1 = GameRandom(seed=42)
    rng2 = GameRandom(seed=42)
    gen1 = MapGenerator(rng1)
    gen2 = MapGenerator(rng2)
    hm1 = gen1.generate(30, 20)
    hm2 = gen2.generate(30, 20)
    for t1, t2 in zip(sorted(hm1.iter_tiles(), key=lambda t: t.coord.to_tuple()),
                      sorted(hm2.iter_tiles(), key=lambda t: t.coord.to_tuple())):
        assert t1.terrain == t2.terrain

# 测试 5: 深海存在
def test_deep_water_exists():
    rng = GameRandom(seed=42)
    gen = MapGenerator(rng)
    hex_map = gen.generate(60, 40)
    terrains = [t.terrain for t in hex_map.iter_tiles()]
    assert TerrainType.DEEP_WATER in terrains

# 测试 6: 高海拔有山/峰
def test_mountain_peak_at_high_elevation():
    rng = GameRandom(seed=42)
    gen = MapGenerator(rng)
    hex_map = gen.generate(60, 40)
    terrains = [t.terrain for t in hex_map.iter_tiles()]
    assert TerrainType.MOUNTAIN in terrains or TerrainType.PEAK in terrains
```

---

## 施工日志要求（DeepSeek 必须执行）

每完成一个任务，更新以下文件：

1. **`施工指南.md`** — 在"施工日志"节添加条目，格式：
   ```
   ### 2026-06-24 Phase 1: 地形扩展 + 地图生成器（会话 X）
   **做了什么**：...
   **关键决策**：...
   **测试结果**：pytest ... passed
   **下阶段**：...
   ```

2. **`docs/handoff/agent-handoff-log.md`** — 在"DeepSeek 本轮工作"节追加条目

3. **git commit** — 每 1-2 个测试通过就 commit，信息清晰

---

## 参考代码位置

| 参考 | 本地路径 | 说明 |
|------|---------|------|
| 现有 hex 坐标 | `game/hex_grid.py` | axial 坐标，已有 |
| 现有地形 | `game/tile.py` | 6 种，需扩展 |
| 当前常量 | `game/constants.py` | 地形常量，需扩展 |
| 确定性随机 | `game/random.py` | GameRandom，MapGenerator 必须用 |
| HexMap 主类 | `game/hex_map.py` | MapGenerator 输出目标 |
| 知识库文档 | `docs/knowledge-base/hex-map-rendering-reference.md` | 开源精华提取 |
| 现有测试 | `tests/unit/test_hex_map.py` | 参考测试风格 |
| 开发规范 | `AGENTS.md` | 五步曲 + TDD + 编码规范 |
| 常见坑 | `docs/pitfalls.md` | 坑 5（随机数）、坑 16（三层分离）特别相关 |

---

## 投入新会话的提示词

见下方独立代码块（由当前会话输出）。
