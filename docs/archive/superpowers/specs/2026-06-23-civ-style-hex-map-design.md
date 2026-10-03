> ⚠️ **本文档为历史记录（归档于 2026-10）。**
> 其中**部分结论已被后续版本推翻**，引用前必须以**当前代码**为准。
> 已确认失效：① 早期"每回合=1 个月 / 24 回合"设定 → 现为**每季度 1 回合 / 默认上限 192**；② 地形/影响力等实现细节以 `game/tile.py` / `game/constants.py` / `game/influence_system.py` 为准。

# LLM三国志：文明风格六角格真实地图设计 spec

> 版本：v2.2  
> 日期：2026-06-23  
> 范围：方案二（六角格真实地图 + 地块资源 + 民心/影响力）+ 无限模式  
> 后续施工：主要由 DeepSeek 执行，Kimi 仅负责 DeepSeek 无法解决的视觉/渲染难题

---

## 一、设计目标

把现有 LLM三国志从"15 城节点对战"升级为具有《文明》风格的策略沙盒：

1. **真实三国地理**：用六角格地图承载真实地形（山脉、河流、平原、森林），城市按真实历史位置摆放。
2. **地块资源系统**：城市控制周边地块，地块产出金钱、粮草、人口、特殊资源。
3. **民心与影响力**：民心是城市稳定度，影响力是势力文化辐射，二者按六角格距离传播。
4. **时间感与无限模式**：标准模式保持 24 回合快节奏；无限模式取消回合上限，以统一全国等战略目标为胜利条件。

---

## 二、非目标（本次不做）

- 不改 3D、不做联网对战、不做复杂兵种科技树（与 AGENTS.md 一致）
- 不做工人单位/地块改良设施（文明式 worker/improvement）
- 不做多单位战术战斗（保持现有攻城战抽象模型）
- 不引入特殊资源（马匹/铁矿/盐/丝绸等），只保留金钱、粮草、人口三种基础资源
- 季节效果只影响资源产出和移动力，不引入复杂气候事件链

---

## 三、核心设计

### 3.1 地图坐标系：六角格（Hex Grid）

采用**轴向坐标（axial coordinates）**：每个格子用 `(q, r)` 表示，第三维 `s = -q - r` 隐式推导。

相邻 6 个方向：

```python
HEX_DIRECTIONS = [
    (1, 0), (1, -1), (0, -1),
    (-1, 0), (-1, 1), (0, 1)
]
```

渲染时把 `(q, r)` 转为屏幕像素 `(x, y)`：

```python
x = size * (sqrt(3) * q + sqrt(3)/2 * r)
y = size * (3./2 * r)
```

### 3.2 地图尺寸与真实地理映射

- 地图范围：覆盖东汉末年至三国时期的广阔疆域，**包含中原、巴蜀、江东、辽东以及西域东部地区**，东西约 3500km，南北约 2800km。
- 六角格边长 `HEX_SIZE = 32` 像素。
- 地图格子数：约 120 × 90（可调整）。
- 真实经纬度 → 轴向坐标：先归一化到地图边界，再取最近六角格。
- 数据来源：基于公开历史地理资料（如谭其骧《中国历史地图集》三国时期分册、OpenStreetMap 地形参考），由网络搜索整理主要城市经纬度与山脉河流走向。

### 3.3 地形类型（TerrainType）

| 地形 | 移动消耗 | 资源产出 | 防御加成 | 视觉颜色 |
|------|---------|---------|---------|---------|
| 平原 | 1 | 粮食 ++ | 0% | 浅绿 #7cb342 |
| 森林 | 1.5 | 粮食 + | +10% | 深绿 #33691e |
| 丘陵 | 2 | 金钱 + | +20% | 土黄 #a1887f |
| 山脉 | 不可通行 | 无 | +40% | 灰褐 #757575 |
| 河流 | 2（渡河） | 粮食 + | 0% | 蓝色 #4fc3f7 |
| 沙漠 | 1.5 | 资源 - | -10% | 沙黄 #e6c075 |
| 城市格 | 1 | 商业 ++ | +30% | 势力色 |

移动消耗：军队每回合可移动 `ARMY_MARCH_SPEED / terrain_cost` 格。

### 3.4 地块（Tile）数据模型

```python
class Tile(BaseModel):
    q: int
    r: int
    terrain: TerrainType
    elevation: int              # 海拔，影响河流流向与防御
    owner_city_id: Optional[str]  # 归属城市
    faction: Optional[str]        # 实际控制势力
    gold_yield: float = 0.0
    food_yield: float = 0.0
    pop_yield: float = 0.0
    development_level: int = 0    # 开发等级（未来扩展）
    influence: Dict[str, float]   # {faction: 影响力值}
    morale: int = 50              # 本地民心
```

### 3.5 城市控制区（City Territory）

每个城市有一个**控制半径**，由城市等级决定：

```python
CITY_TERRITORY_RADIUS = {1: 1, 2: 2, 3: 2, 4: 3, 5: 3}
```

控制规则：
- 城市所在格及半径内所有可通行格归该城所有。
- 控制区边缘与其他城市重叠时，按城市等级/民心/驻军比拼决定归属。
- 城市被占领后，控制区内地块 faction 切换为新势力。

### 3.6 地块资源产出（Resource System 扩展）

**本次只实现基础资源**：金钱、粮草、人口。特殊资源（马匹、铁矿、盐、丝绸等）在后续版本加入。

城市每回合资源产出 = 基础产出 + 控制地块产出总和。

```python
def produce_resources(city: City, tiles: List[Tile], season: Season) -> ResourceDelta:
    base = city_level_config[city.level]
    tile_gold = sum(t.gold_yield for t in tiles)
    tile_food = sum(t.food_yield for t in tiles)
    tile_pop = sum(t.pop_yield for t in tiles)
    # 民心倍率保留现有逻辑
    morale_factor = compute_morale_factor(city.morale)
    # 季节倍率
    season_factor = SEASON_FOOD_BONUS.get(season, 1.0)
    return ResourceDelta(
        gold=(base.gold + tile_gold) * morale_factor,
        food=(base.food + tile_food) * morale_factor * season_factor,
        population=(base.pop_growth + tile_pop) * morale_factor,
    )
```

### 3.7 民心（Morale）与影响力（Influence）

#### 民心
- 民心仍绑定到城市，取值 0–100。
- 新增：城市周边地块民心 = 城市民心的衰减值。
- 民心低于 30 的城市控制区可能叛乱（地块 faction 不变，但产出下降）。

#### 影响力（本次简化为 Buff/Debuff，不策反）
- 影响力绑定到格子和势力，表示某势力在该格的文化/政治渗透。
- 每回合从每个城市向其周边扩散：
  - 基础影响力 = 城市等级 × 10 + 民心 / 10
  - 每向外一格衰减 40%
  - 与敌对势力影响力在格子内竞争，高者占主导
- **影响力只产生 Buff/Debuff，不改变地块 faction**：
  - 若某地块被 A 势力控制，且 A 在该格影响力最高：该格产出 +5%，防守战斗 +5% 防御。
  - 若某地块被 A 势力控制，但 B 在该格影响力显著更高（≥2 倍）：该格产出 -10%，防守战斗 -10% 防御，军队经过时移动力额外 -1（敌方民心不稳）。
- 地块 faction 只随城市占领而改变，避免不可控的边界变化。

### 3.8 军队移动适配

现有 `ArmyStatus.MARCHING` 从"沿城市路径推进"改为"沿六角格路径推进"。

- 出征时计算从 `from_city` 到 `to_city` 的 A* 路径（考虑地形消耗）。
- 军队有当前格子和目标格子，`progress` 表示在相邻两格之间的进度。
- 每回合移动 `speed / terrain_cost` 距离。
- 进入敌方城市邻格即视为"围城"，触发围城战。

### 3.9 时间感与无限模式

#### 回合 = 时间
- 标准模式：每回合 = 1 个月，24 回合 = 2 年，保持快节奏。
- 无限模式：每回合 = 1 个月，每 12 回合推进 1 年，显示年份（如建安元年、建安二年）。

#### 季节效果
每 12 回合为一个年份循环，每 3 回合切换一个季节：

| 季节 | 回合 | 效果 |
|------|------|------|
| 春 | 1–3 | 粮食产出 +10%，人口增长 +5% |
| 夏 | 4–6 | 粮食产出 +5%，军队行军消耗粮草 +10% |
| 秋 | 7–9 | 粮食产出 +15%（丰收） |
| 冬 | 10–12 | 军队移动速度 -20%，围城消耗增加 |

#### 无限模式规则
- `max_turns = None` 或一个极大值（如 9999）。
- 胜利条件可选：
  - **统一全国**：占领所有城市。
  - **文化胜利**：影响力覆盖全图 60% 以上地块。
  - **经济胜利**：总金钱/粮草达到阈值。
  - **生存模式**：坚持不被灭国。
- 回合递增不再触发强制结束，只触发年份/季节显示更新。

### 3.10 真实三国地图数据

新建 `data/hex_map.json`：

```json
{
  "width": 80,
  "height": 60,
  "hex_size": 32,
  "terrain": [
    {"q": 10, "r": 20, "terrain": "mountain", "elevation": 5},
    {"q": 11, "r": 20, "terrain": "plain", "elevation": 1, "resource": "grain"}
  ],
  "rivers": [
    [(10, 20), (11, 20), (12, 21), ...]
  ],
  "city_positions": {
    "xuchang": {"q": 45, "r": 25},
    "luoyang": {"q": 40, "r": 22},
    "chengdu": {"q": 20, "r": 45},
    "jianye": {"q": 60, "r": 35}
  }
}
```

城市仍保留 `data/cities.json`，但 `position` 字段从 `[x, y]` 像素坐标改为 `{"q": int, "r": int}`。

---

## 四、架构改动

### 4.1 新增模块

```
game/
  map_system.py          # 保留，但内部改用 HexMap
  hex_map.py             # 六角格地图核心（新增）
  tile.py                # Tile 模型（新增）
  influence_system.py    # 影响力扩散（新增）
  systems/
    resource_system.py   # 扩展地块产出
    city_system.py       # 扩展控制区计算
```

```
renderer/
  hex_map_renderer.py    # 六角格地图渲染（新增）
  map_renderer.py        # 逐步替换或适配
  ui_panel.py            # 扩展地块信息面板
```

### 4.2 改动模块

| 模块 | 改动 |
|------|------|
| `game/models.py` | 新增 `Tile`, `TerrainType`, `ResourceType`, `InfluenceSnapshot`；`City.position` 改为 `HexCoord` |
| `game/engine.py` | 初始化时加载 `HexMap`；回合流程加入影响力扩散 |
| `game/systems/resource_system.py` | `produce_resources` 接收城市控制地块 |
| `game/systems/city_system.py` | 城市升级时扩大控制区 |
| `game/battle/army_movement.py` | 路径计算改用 HexMap A* |
| `game/battle/battle_scheduler.py` | 检测围城基于城市邻格而非城市距离 |
| `renderer/game_renderer.py` | 窗口可缩放，右侧面板支持地块详情 |
| `renderer/map_renderer.py` | 改为渲染六角格（或新建 `hex_map_renderer.py` 替代） |

### 4.3 保持不变的模块

- `players/llm/`：LLM 玩家通过 observation 获取信息，observation 屏蔽底层是城市网络还是六角格。
- `game/battle/battle_resolver.py`：战斗结算公式不变，只改触发条件。
- `game/event_bus.py`：事件总线不变，新增 `TILE_INFLUENCE_CHANGED` 等事件。

---

## 五、GUI 渲染要点（Kimi 负责视觉难题）

### 5.1 DeepSeek 可完成的基础渲染

- 六角格地图底色、地形颜色区分
- 城市位置标记（圆形/六边形高亮）
- 势力边界线（按地块 faction 绘制）
- 影响力云图（半透明色块叠加）
- 右侧信息面板：城市/地块详情

### 5.2 Kimi 负责的视觉难题

1. **六角格点击命中检测**：精确的点到六边形距离判断，包括屏幕缩放/平移后的坐标变换。
2. **地形纹理与高度可视化**：山脉、河流、森林在六角格上的美观渲染，避免纯色块。
3. **势力边界平滑绘制**：地块 faction 交界处的抗锯齿边界线，而不是锯齿状。
4. **影响力渐变热图**：多势力影响力叠加时的颜色混合，避免脏色。
5. **军队动画在城市格间平滑移动**：行军单位沿六角格路径的插值动画。
6. **大地图相机系统**：支持缩放（滚轮）、拖拽平移、小地图/鹰眼。
7. **战斗/占领视觉反馈**：短暂动画或粒子效果（如城市变色、旗帜切换）。

---

## 六、数据与配置

### 6.1 新增配置项（constants.py）

```python
HEX_SIZE: int = 32
HEX_MAP_WIDTH: int = 120
HEX_MAP_HEIGHT: int = 90

TERRAIN_MOVE_COST: Dict[TerrainType, float] = {...}
TERRAIN_DEFENSE_BONUS: Dict[TerrainType, float] = {...}
TERRAIN_YIELDS: Dict[TerrainType, Dict[str, float]] = {...}

SEASON_FOOD_BONUS: Dict[Season, float] = {
    Season.SPRING: 1.10,
    Season.SUMMER: 1.05,
    Season.AUTUMN: 1.15,
    Season.WINTER: 0.90,
}
SEASON_MOVEMENT_FACTOR: Dict[Season, float] = {
    Season.SPRING: 1.0,
    Season.SUMMER: 1.0,
    Season.AUTUMN: 1.0,
    Season.WINTER: 0.8,
}

INFLUENCE_DECAY_PER_HEX: float = 0.4
INFLUENCE_DIPLOMATIC_MESSAGE_BONUS: float = 10.0
CITY_TERRITORY_RADIUS: Dict[int, int] = {...}
```

### 6.2 新数据文件

- `data/hex_map.json`：地形、河流、城市位置。
- `data/terrain_colors.json`：地形颜色与纹理配置（可换肤）。

---

## 七、测试策略

1. **HexMap 单元测试**：坐标转换、邻居计算、A* 路径、地形消耗。
2. **影响力传播测试**：单城扩散、多城竞争、衰减公式。
3. **资源产出测试**：地块产出加总、民心倍率、城市等级影响。
4. **控制区测试**：城市升级扩张、边界重叠判定、占领后切换。
5. **确定性测试**：相同 seed + 相同输入，HexMap 生成结果一致。
6. **渲染测试**：mock pygame surface，验证 `HexMapRenderer.render()` 不抛异常。

---

## 八、施工顺序建议

### 阶段 1：六角格基础设施
1. 实现 `HexCoord`, `Tile`, `HexMap`。
2. 坐标转换与邻居查询。
3. 加载 `data/hex_map.json`。

### 阶段 2：地形与资源
1. 定义 `TerrainType`, `ResourceType`。
2. 扩展 `ResourceSystem` 计算地块产出。
3. 城市控制区计算。

### 阶段 3：影响力与民心
1. 实现 `InfluenceSystem`。
2. 每回合扩散与竞争。
3. 地块策反逻辑。

### 阶段 4：军队移动适配
1. HexMap A* 路径。
2. 军队沿格移动与围城检测。

### 阶段 5：无限模式
1. `GameMode` 枚举（STANDARD/INFINITE）。
2. 可配置胜利条件。
3. 年份显示。

### 阶段 6：GUI 升级
1. 基础六角格渲染（DeepSeek）。
2. 相机/缩放/平移（Kimi）。
3. 边界线/影响力热图（Kimi）。
4. 地块详情面板（DeepSeek）。
5. 战斗/占领反馈（Kimi）。

### 阶段 7：集成与回归
1. 接回放模式。
2. 人机对战适配。
3. 全量测试与 LLM 对战回归。

---

## 九、风险与回退方案

| 风险 | 缓解 |
|------|------|
| HexMap 改动过大影响现有对战 | 保留旧 `MapSystem` 接口，HexMap 内部替换 |
| 真实地图数据复杂导致测试变慢 | 提供小尺寸测试地图 `data/hex_map_test.json` |
| LLM observation 输出变复杂 | observation 中对 LLM 仍使用简化城市网络视图 |
| 渲染性能差 | 只渲染屏幕内格子 + LOD（远格简化） |

---

## 十、已确认决策

1. **真实地图覆盖范围**：包含中原、巴蜀、江东、辽东、西域东部；基于网络公开历史地理资料（如谭其骧《中国历史地图集》三国分册、OpenStreetMap 地形参考）整理城市坐标与地形。
2. **时间粒度**：每回合 = 1 个月；标准模式 24 回合 = 2 年；无限模式保留季节效果（春夏秋冬循环，影响粮食产出与军队移动力）。
3. **资源种类**：本次只实现基础资源（金钱、粮草、人口）；特殊资源留待后续版本。
4. **影响力机制**：本次不落地策反，只作为 Buff/Debuff 系统；地块 faction 只随城市占领改变。

---

> 本 spec 已确认，进入 `writing-plans` 制定详细施工计划。
