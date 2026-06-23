# 文明风格六角格真实地图实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 LLM三国志从 15 城节点图升级为六角格真实三国地图，支持地形、地块资源、民心/影响力 Buff、季节效果和无限模式。

**Architecture:** 新增 `HexMap` + `Tile` 层位于现有 `MapSystem` 之下；`GameEngine` 通过 `HexMap` 管理地理；`ResourceSystem` 和 `CitySystem` 扩展为按城市控制地块计算产出；`ArmyMovementSystem` 改用 A* 六角格路径；`InfluenceSystem` 只提供 Buff/Debuff 不策反；Renderer 新增 `HexMapRenderer` 绘制六角格、地形、边界与影响力云图。

**Tech Stack:** Python 3.10+, Pydantic 2.x, Pygame 2.6+, pytest

**分工说明：** 标注 **(Kimi)** 的任务涉及复杂视觉/渲染难题，由 Kimi 处理；其余任务由 DeepSeek 施工。

---

## 文件结构总览

### 新增文件

- `game/hex_grid.py` — 六角格坐标转换、邻居计算、距离
- `game/hex_map.py` — HexMap 主类，管理 Tile 集合
- `game/tile.py` — Tile 数据模型
- `game/influence_system.py` — 影响力扩散与 Buff/Debuff 计算
- `game/season.py` — Season 枚举与季节效果配置
- `game/game_mode.py` — GameMode 枚举（STANDARD/INFINITE）
- `data/hex_map.json` — 真实三国六角格地图数据
- `data/terrain_colors.json` — 地形颜色配置
- `tests/unit/test_hex_grid.py`
- `tests/unit/test_hex_map.py`
- `tests/unit/test_influence_system.py`
- `tests/unit/test_season.py`
- `renderer/hex_map_renderer.py` — 六角格地图渲染器
- `renderer/camera.py` — 相机/视口（Kimi）

### 修改文件

- `game/constants.py` — 新增六角格、地形、季节、影响力常量
- `game/models.py` — City.position 改为 HexCoord；Army 增加当前格字段
- `game/engine.py` — 加载 HexMap、季节推进、影响力扩散、胜利条件适配
- `game/systems/resource_system.py` — 按控制地块计算产出
- `game/systems/city_system.py` — 城市控制区计算
- `game/battle/army_movement.py` — 六角格路径与移动
- `game/battle/battle_scheduler.py` — 围城检测改为城市邻格
- `game/data_loader.py` — 加载 hex_map.json
- `renderer/game_renderer.py` — 接入 HexMapRenderer
- `renderer/map_renderer.py` — 适配或弃用
- `renderer/ui_panel.py` — 显示地块/季节/游戏模式信息
- `main.py` — 支持 `--mode infinite` 等参数

---

## Phase 1: 六角格基础设施

### Task 1: HexCoord 与坐标转换

**Files:**
- Create: `game/hex_grid.py`
- Test: `tests/unit/test_hex_grid.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_hex_grid.py
from game.hex_grid import HexCoord, hex_distance, hex_neighbors


def test_hex_coord_creation():
    coord = HexCoord(q=2, r=-1)
    assert coord.q == 2
    assert coord.r == -1
    assert coord.s == -1


def test_hex_distance():
    a = HexCoord(0, 0)
    b = HexCoord(3, -2)
    assert hex_distance(a, b) == 3


def test_hex_neighbors():
    center = HexCoord(1, 1)
    neighbors = hex_neighbors(center)
    assert len(neighbors) == 6
    assert HexCoord(2, 1) in neighbors
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
cd /Users/dongsheng/Documents/llm-sanguo-project
python3 -m pytest tests/unit/test_hex_grid.py -v
```

Expected: 失败，模块未找到

- [ ] **Step 3: 实现 HexCoord**

```python
# game/hex_grid.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class HexCoord:
    """六角格轴向坐标"""

    q: int
    r: int

    @property
    def s(self) -> int:
        return -self.q - self.r

    def __add__(self, other: HexCoord) -> HexCoord:
        return HexCoord(self.q + other.q, self.r + other.r)

    def __sub__(self, other: HexCoord) -> HexCoord:
        return HexCoord(self.q - other.q, self.r - other.r)

    def to_tuple(self) -> Tuple[int, int]:
        return (self.q, self.r)


HEX_DIRECTIONS = [
    HexCoord(1, 0), HexCoord(1, -1), HexCoord(0, -1),
    HexCoord(-1, 0), HexCoord(-1, 1), HexCoord(0, 1),
]


def hex_distance(a: HexCoord, b: HexCoord) -> int:
    """计算两个六角格的距离"""
    diff = a - b
    return max(abs(diff.q), abs(diff.r), abs(diff.s))


def hex_neighbors(center: HexCoord) -> List[HexCoord]:
    """获取相邻的 6 个格子"""
    return [center + d for d in HEX_DIRECTIONS]


def axial_to_pixel(coord: HexCoord, size: float) -> Tuple[float, float]:
    """轴向坐标转屏幕像素（pointy-topped）"""
    import math
    x = size * (math.sqrt(3) * coord.q + math.sqrt(3) / 2 * coord.r)
    y = size * (3.0 / 2 * coord.r)
    return (x, y)


def pixel_to_axial(x: float, y: float, size: float) -> HexCoord:
    """屏幕像素转轴向坐标"""
    import math
    q = (math.sqrt(3) / 3 * x - 1.0 / 3 * y) / size
    r = (2.0 / 3 * y) / size
    return hex_round(q, r)


def hex_round(q: float, r: float) -> HexCoord:
    """浮点六角坐标取整"""
    s = -q - r
    rq, rr, rs = round(q), round(r), round(s)
    dq, dr, ds = abs(rq - q), abs(rr - r), abs(rs - s)
    if dq > dr and dq > ds:
        rq = -rr - rs
    elif dr > ds:
        rr = -rq - rs
    return HexCoord(int(rq), int(rr))
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python3 -m pytest tests/unit/test_hex_grid.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add game/hex_grid.py tests/unit/test_hex_grid.py
git commit -m "feat(hex): add HexCoord and coordinate conversions"
```

---

### Task 2: Tile 数据模型

**Files:**
- Create: `game/tile.py`
- Modify: `game/models.py`（可选，若决定合并则跳过）
- Test: `tests/unit/test_tile.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_tile.py
from game.tile import Tile, TerrainType
from game.hex_grid import HexCoord


def test_tile_creation():
    tile = Tile(coord=HexCoord(0, 0), terrain=TerrainType.PLAIN)
    assert tile.coord == HexCoord(0, 0)
    assert tile.terrain == TerrainType.PLAIN
    assert tile.faction is None


def test_tile_yields_default():
    tile = Tile(coord=HexCoord(0, 0), terrain=TerrainType.PLAIN)
    assert tile.gold_yield >= 0
    assert tile.food_yield >= 0
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python3 -m pytest tests/unit/test_tile.py -v
```

- [ ] **Step 3: 实现 Tile 模型**

```python
# game/tile.py
from __future__ import annotations

from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, Field, ConfigDict

from game.hex_grid import HexCoord


class TerrainType(str, Enum):
    PLAIN = "plain"
    FOREST = "forest"
    HILL = "hill"
    MOUNTAIN = "mountain"
    RIVER = "river"
    DESERT = "desert"


class Tile(BaseModel):
    """六角格地块"""

    coord: HexCoord = Field(description="六角格坐标")
    terrain: TerrainType = Field(description="地形类型")
    elevation: int = Field(default=0, ge=0, description="海拔")

    owner_city_id: Optional[str] = Field(default=None, description="归属城市ID")
    faction: Optional[str] = Field(default=None, description="实际控制势力")

    gold_yield: float = Field(default=0.0, ge=0, description="金钱产出")
    food_yield: float = Field(default=0.0, ge=0, description="粮草产出")
    pop_yield: float = Field(default=0.0, ge=0, description="人口产出")

    development_level: int = Field(default=0, ge=0, description="开发等级")
    influence: Dict[str, float] = Field(default_factory=dict, description="势力影响力")
    morale: int = Field(default=50, ge=0, le=100, description="本地民心")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def is_passable(self) -> bool:
        return self.terrain != TerrainType.MOUNTAIN
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python3 -m pytest tests/unit/test_tile.py -v
```

- [ ] **Step 5: Commit**

```bash
git add game/tile.py tests/unit/test_tile.py
git commit -m "feat(tile): add Tile data model for hex grid"
```

---

### Task 3: HexMap 主类

**Files:**
- Create: `game/hex_map.py`
- Test: `tests/unit/test_hex_map.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_hex_map.py
from game.hex_map import HexMap
from game.hex_grid import HexCoord
from game.tile import Tile, TerrainType


def test_hex_map_create_and_get():
    hm = HexMap(width=5, height=5)
    tile = hm.get_tile(HexCoord(0, 0))
    assert tile is not None
    assert tile.terrain == TerrainType.PLAIN


def test_hex_map_out_of_bounds():
    hm = HexMap(width=3, height=3)
    assert hm.get_tile(HexCoord(10, 10)) is None


def test_hex_map_distance():
    hm = HexMap(width=10, height=10)
    path = hm.find_path(HexCoord(0, 0), HexCoord(2, 0))
    assert len(path) == 3
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python3 -m pytest tests/unit/test_hex_map.py -v
```

- [ ] **Step 3: 实现 HexMap**

```python
# game/hex_map.py
from __future__ import annotations

import heapq
from typing import Dict, List, Optional, Tuple

from game.hex_grid import HexCoord, hex_distance, hex_neighbors
from game.tile import Tile, TerrainType


class HexMap:
    """六角格地图

    管理所有 Tile，提供坐标查询、路径计算、范围查询。
    """

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self._tiles: Dict[Tuple[int, int], Tile] = {}

    def add_tile(self, tile: Tile) -> None:
        """添加或覆盖一个地块"""
        self._tiles[tile.coord.to_tuple()] = tile

    def get_tile(self, coord: HexCoord) -> Optional[Tile]:
        """获取指定坐标地块"""
        return self._tiles.get(coord.to_tuple())

    def get_neighbors(self, coord: HexCoord) -> List[Tile]:
        """获取相邻且存在的地块"""
        result = []
        for n in hex_neighbors(coord):
            tile = self.get_tile(n)
            if tile is not None:
                result.append(tile)
        return result

    def iter_tiles(self):
        """迭代所有地块"""
        return iter(self._tiles.values())

    @staticmethod
    def terrain_move_cost(terrain: TerrainType) -> float:
        """地形移动消耗"""
        costs = {
            TerrainType.PLAIN: 1.0,
            TerrainType.FOREST: 1.5,
            TerrainType.HILL: 2.0,
            TerrainType.RIVER: 2.0,
            TerrainType.DESERT: 1.5,
            TerrainType.MOUNTAIN: float("inf"),
        }
        return costs.get(terrain, 1.0)

    def find_path(
        self,
        start: HexCoord,
        goal: HexCoord,
    ) -> List[HexCoord]:
        """A* 寻路"""
        if self.get_tile(start) is None or self.get_tile(goal) is None:
            return []

        open_set = [(0, 0, start)]
        came_from: Dict[HexCoord, HexCoord] = {}
        g_score: Dict[HexCoord, float] = {start: 0.0}
        counter = 0

        while open_set:
            _, _, current = heapq.heappop(open_set)
            if current == goal:
                return self._reconstruct_path(came_from, current)

            for neighbor in hex_neighbors(current):
                tile = self.get_tile(neighbor)
                if tile is None or not tile.is_passable():
                    continue
                cost = self.terrain_move_cost(tile.terrain)
                tentative = g_score[current] + cost
                if neighbor not in g_score or tentative < g_score[neighbor]:
                    counter += 1
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative
                    f = tentative + hex_distance(neighbor, goal)
                    heapq.heappush(open_set, (f, counter, neighbor))

        return []

    @staticmethod
    def _reconstruct_path(
        came_from: Dict[HexCoord, HexCoord],
        current: HexCoord,
    ) -> List[HexCoord]:
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        return list(reversed(path))
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python3 -m pytest tests/unit/test_hex_map.py -v
```

- [ ] **Step 5: Commit**

```bash
git add game/hex_map.py tests/unit/test_hex_map.py
git commit -m "feat(hex): add HexMap with A* pathfinding"
```

---

## Phase 2: 地形与真实地图数据

### Task 4: 地形与资源常量

**Files:**
- Modify: `game/constants.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_constants.py 中新增
from game.constants import TERRAIN_MOVE_COST, SEASON_FOOD_BONUS


def test_terrain_constants():
    assert TERRAIN_MOVE_COST["plain"] == 1.0
    assert TERRAIN_MOVE_COST["mountain"] == float("inf")


def test_season_constants():
    assert "spring" in SEASON_FOOD_BONUS
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python3 -m pytest tests/unit/test_constants.py -v
```

- [ ] **Step 3: 添加常量**

```python
# game/constants.py 末尾追加

# ============================================================
# 六角格地图
# ============================================================

HEX_SIZE: int = 32
"""六角格边长（像素）"""

HEX_MAP_WIDTH: int = 120
"""六角格地图宽度"""

HEX_MAP_HEIGHT: int = 90
"""六角格地图高度"""

# ============================================================
# 地形
# ============================================================

TERRAIN_MOVE_COST: Dict[str, float] = {
    "plain": 1.0,
    "forest": 1.5,
    "hill": 2.0,
    "mountain": float("inf"),
    "river": 2.0,
    "desert": 1.5,
}

TERRAIN_DEFENSE_BONUS: Dict[str, float] = {
    "plain": 0.0,
    "forest": 0.10,
    "hill": 0.20,
    "mountain": 0.40,
    "river": 0.0,
    "desert": -0.10,
}

# 基础产出：仅金钱/粮草/人口
TERRAIN_YIELDS: Dict[str, Dict[str, float]] = {
    "plain": {"gold": 0.0, "food": 3.0, "pop": 1.0},
    "forest": {"gold": 0.0, "food": 1.5, "pop": 0.5},
    "hill": {"gold": 1.5, "food": 0.5, "pop": 0.3},
    "mountain": {"gold": 0.0, "food": 0.0, "pop": 0.0},
    "river": {"gold": 0.5, "food": 2.0, "pop": 0.5},
    "desert": {"gold": 0.0, "food": 0.2, "pop": 0.1},
}

CITY_TERRITORY_RADIUS: Dict[int, int] = {
    1: 1,
    2: 2,
    3: 2,
    4: 3,
    5: 3,
}

# ============================================================
# 季节
# ============================================================

SEASON_FOOD_BONUS: Dict[str, float] = {
    "spring": 1.10,
    "summer": 1.05,
    "autumn": 1.15,
    "winter": 0.90,
}

SEASON_MOVEMENT_FACTOR: Dict[str, float] = {
    "spring": 1.0,
    "summer": 1.0,
    "autumn": 1.0,
    "winter": 0.8,
}

# ============================================================
# 影响力
# ============================================================

INFLUENCE_DECAY_PER_HEX: float = 0.4
"""影响力每向外一格衰减比例"""

INFLUENCE_OWN_BUFF_RATE: float = 0.05
"""己方高影响力地块产出加成"""

INFLUENCE_ENEMY_DEBUFF_RATE: float = 0.10
"""敌方高影响力地块产出减成"""

INFLUENCE_ENEMY_DOMINANCE_RATIO: float = 2.0
"""敌方影响力达到己方 2 倍时触发 debuff"""
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python3 -m pytest tests/unit/test_constants.py -v
```

- [ ] **Step 5: Commit**

```bash
git add game/constants.py tests/unit/test_constants.py
git commit -m "feat(constants): add hex terrain, season and influence constants"
```

---

### Task 5: 真实三国地图数据文件

**Files:**
- Create: `data/hex_map.json`
- Create: `data/terrain_colors.json`
- Modify: `data/cities.json`（position 改为 hex coord）

- [ ] **Step 1: 调研真实地理数据**

使用网络搜索获取以下城市的经纬度或相对位置：
- 中原：许昌、洛阳、长安、邺城、陈留、南阳、襄阳
- 巴蜀：成都、汉中、剑阁、白帝、天水
- 江东：建业、柴桑、江陵、合肥、吴郡
- 辽东：襄平
- 西域：武威、敦煌

- [ ] **Step 2: 生成 hex_map.json**

```json
{
  "width": 120,
  "height": 90,
  "hex_size": 32,
  "bounds": {
    "min_lon": 95.0,
    "max_lon": 125.0,
    "min_lat": 22.0,
    "max_lat": 45.0
  },
  "terrain": [
    {"q": 60, "r": 40, "terrain": "plain", "elevation": 1},
    {"q": 55, "r": 35, "terrain": "mountain", "elevation": 5},
    {"q": 70, "r": 50, "terrain": "river", "elevation": 0}
  ],
  "rivers": [
    [{"q": 50, "r": 60}, {"q": 55, "r": 58}, {"q": 60, "r": 55}]
  ],
  "city_positions": {
    "xuchang": {"q": 65, "r": 38},
    "luoyang": {"q": 58, "r": 35},
    "chengdu": {"q": 25, "r": 55},
    "jianye": {"q": 92, "r": 48}
  }
}
```

说明：山脉和河流只需标记关键格子，其余默认平原/森林/丘陵可通过程序化生成或手工补充。

- [ ] **Step 3: 生成 terrain_colors.json**

```json
{
  "plain": {"fill": "#7cb342", "border": "#558b2f"},
  "forest": {"fill": "#33691e", "border": "#1b5e20"},
  "hill": {"fill": "#a1887f", "border": "#6d4c41"},
  "mountain": {"fill": "#757575", "border": "#424242"},
  "river": {"fill": "#4fc3f7", "border": "#0288d1"},
  "desert": {"fill": "#e6c075", "border": "#c19a4b"},
  "fog": {"fill": "#1a1a2e", "border": "#2a2a3e"}
}
```

- [ ] **Step 4: Commit**

```bash
git add data/hex_map.json data/terrain_colors.json data/cities.json
git commit -m "data(map): add hex map data for Three Kingdoms geography"
```

---

### Task 6: 地图数据加载器

**Files:**
- Modify: `game/data_loader.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_data_loader.py 中新增
from game.data_loader import load_hex_map_data


def test_load_hex_map_data():
    data = load_hex_map_data()
    assert "width" in data
    assert "city_positions" in data
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python3 -m pytest tests/unit/test_data_loader.py -v
```

- [ ] **Step 3: 实现加载器**

```python
# game/data_loader.py 中追加
import json
import os
from typing import Any, Dict


def load_hex_map_data(path: str = "") -> Dict[str, Any]:
    """加载六角格地图数据"""
    if not path:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, "data", "hex_map.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python3 -m pytest tests/unit/test_data_loader.py -v
```

- [ ] **Step 5: Commit**

```bash
git add game/data_loader.py tests/unit/test_data_loader.py
git commit -m "feat(data): add hex map data loader"
```

---

## Phase 3: 城市控制区与资源系统

### Task 7: City 模型适配 HexCoord

**Files:**
- Modify: `game/models.py`

- [ ] **Step 1: 更新 City.position 类型**

```python
# game/models.py
from game.hex_grid import HexCoord


class City(BaseModel):
    # 保留所有现有字段不变（id, name, faction, level, wall_hp, wall_max_hp,
    # gold, food, population, morale, garrison, generals, is_besieged 等）
    position: HexCoord = Field(description="六角格坐标")
    neighbors: List[str] = Field(default_factory=list, description="相邻城市ID列表")
```

- [ ] **Step 2: 更新 data/cities.json 中 position 字段**

每个城市从 `[x, y]` 改为 `{"q": int, "r": int}`。

- [ ] **Step 3: 运行模型测试**

```bash
python3 -m pytest tests/unit/test_models.py -v
```

- [ ] **Step 4: Commit**

```bash
git add game/models.py data/cities.json
git commit -m "refactor(models): City.position uses HexCoord"
```

---

### Task 8: 城市控制区计算

**Files:**
- Modify: `game/systems/city_system.py`
- Test: `tests/unit/test_city_system.py`（扩展）

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_city_system.py
from game.systems.city_system import CitySystem
from game.hex_grid import HexCoord
from game.hex_map import HexMap
from game.tile import Tile, TerrainType
from game.models import City


def test_city_territory_radius_2():
    city = City(
        id="test", name="测试", faction="wei", level=2,
        wall_hp=100, wall_max_hp=100, gold=100, food=100,
        population=1000, morale=50, garrison=100,
        position=HexCoord(5, 5),
    )
    hm = HexMap(width=20, height=20)
    for q in range(20):
        for r in range(20):
            hm.add_tile(Tile(coord=HexCoord(q, r), terrain=TerrainType.PLAIN))

    system = CitySystem()
    territory = system.get_city_territory(city, hm)
    assert len(territory) > 1
    assert HexCoord(5, 5) in territory
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python3 -m pytest tests/unit/test_city_system.py::test_city_territory_radius_2 -v
```

- [ ] **Step 3: 实现控制区方法**

```python
# game/systems/city_system.py 中追加
from typing import List, Set

from game.hex_grid import HexCoord, hex_distance
from game.hex_map import HexMap
from game.constants import CITY_TERRITORY_RADIUS


def get_city_territory(self, city: City, hex_map: HexMap) -> Set[HexCoord]:
    """获取城市控制区坐标集合"""
    radius = CITY_TERRITORY_RADIUS.get(city.level, 1)
    center = city.position
    territory: Set[HexCoord] = set()
    for q in range(-radius, radius + 1):
        for r in range(-radius, radius + 1):
            coord = HexCoord(center.q + q, center.r + r)
            if hex_distance(center, coord) <= radius:
                if hex_map.get_tile(coord) is not None:
                    territory.add(coord)
    return territory
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python3 -m pytest tests/unit/test_city_system.py -v
```

- [ ] **Step 5: Commit**

```bash
git add game/systems/city_system.py tests/unit/test_city_system.py
git commit -m "feat(city): add city territory calculation on hex grid"
```

---

### Task 9: 资源系统按地块计算产出

**Files:**
- Modify: `game/systems/resource_system.py`
- Test: `tests/unit/test_resource_system.py`（扩展）

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_resource_system.py
def test_calculate_gold_with_tiles():
    rs = ResourceSystem()
    city = make_test_city(level=2)
    tiles = [make_plain_tile() for _ in range(7)]
    delta = rs.calculate_resources(city, tiles, season="spring")
    assert delta["gold_change"] >= 0
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python3 -m pytest tests/unit/test_resource_system.py -v
```

- [ ] **Step 3: 重构 ResourceSystem**

```python
# game/systems/resource_system.py
from typing import List

from game.tile import Tile
from game.constants import TERRAIN_YIELDS, SEASON_FOOD_BONUS


def calculate_resources(
    self,
    city: City,
    tiles: List[Tile],
    season: str = "spring",
) -> Dict[str, Any]:
    """根据城市和控制地块计算本回合资源变化"""
    gold_change = self.calculate_gold_production(city, tiles)
    food_change = self.calculate_food_production(city, tiles, season)
    pop_change = self.calculate_population_growth(city, tiles)
    food_consumption = self.calculate_food_consumption(city)

    return {
        "gold_change": gold_change,
        "food_change": food_change - food_consumption,
        "population_change": pop_change,
    }


def calculate_gold_production(self, city: City, tiles: List[Tile]) -> int:
    if city.morale < MIN_MORALE_FOR_PRODUCTION:
        return 0
    level_config = CITY_LEVELS[city.level]
    base = level_config["base_gold"]
    population_output = city.population * GOLD_PER_POPULATION
    tile_gold = sum(t.gold_yield for t in tiles)
    total = base + population_output + tile_gold
    multiplier = self._get_morale_multiplier(city.morale, MORALE_GOLD_PENALTY)
    return int(total * multiplier)


def calculate_food_production(
    self, city: City, tiles: List[Tile], season: str
) -> int:
    if city.morale < MIN_MORALE_FOR_PRODUCTION:
        return 0
    level_config = CITY_LEVELS[city.level]
    base = level_config["base_food"]
    population_output = city.population * FOOD_PER_POPULATION
    tile_food = sum(t.food_yield for t in tiles)
    total = base + population_output + tile_food
    multiplier = self._get_morale_multiplier(city.morale, MORALE_FOOD_PENALTY)
    season_factor = SEASON_FOOD_BONUS.get(season, 1.0)
    return int(total * multiplier * season_factor)


def calculate_population_growth(self, city: City, tiles: List[Tile]) -> int:
    if city.population <= 0:
        return 0
    level_config = CITY_LEVELS[city.level]
    max_population = level_config["max_population"]
    if city.population >= max_population:
        return 0

    tile_pop = sum(t.pop_yield for t in tiles)
    morale_factor = city.morale * POPULATION_GROWTH_MORALE_FACTOR
    growth_rate = POPULATION_GROWTH_BASE + morale_factor
    growth_rate = min(growth_rate, MAX_POPULATION_GROWTH_RATE)
    growth = int(city.population * growth_rate) + int(tile_pop)

    if growth > 0:
        growth = min(growth, max_population - city.population)
    elif growth < 0:
        growth = max(growth, -int(city.population * 0.1))
    return growth
```

同时保留旧的 `update_city_resources(city)` 接口，内部调用新的 `calculate_resources` 并传入空 tiles，避免破坏既有调用方。

- [ ] **Step 4: 运行测试，确认通过**

```bash
python3 -m pytest tests/unit/test_resource_system.py -v
```

- [ ] **Step 5: Commit**

```bash
git add game/systems/resource_system.py tests/unit/test_resource_system.py
git commit -m "feat(resource): calculate production from controlled tiles"
```

---

## Phase 4: 影响力 Buff/Debuff

### Task 10: InfluenceSystem

**Files:**
- Create: `game/influence_system.py`
- Test: `tests/unit/test_influence_system.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_influence_system.py
from game.influence_system import InfluenceSystem
from game.hex_grid import HexCoord
from game.hex_map import HexMap
from game.tile import Tile, TerrainType
from game.models import City


def test_influence_spreads_from_city():
    hm = HexMap(width=10, height=10)
    for q in range(10):
        for r in range(10):
            hm.add_tile(Tile(coord=HexCoord(q, r), terrain=TerrainType.PLAIN))
    city = City(
        id="c", name="C", faction="wei", level=2,
        wall_hp=100, wall_max_hp=100, gold=0, food=0,
        population=1000, morale=80, garrison=100,
        position=HexCoord(5, 5),
    )
    sys = InfluenceSystem()
    sys.spread_influence([city], hm)
    tile = hm.get_tile(HexCoord(5, 5))
    assert tile.influence.get("wei", 0) > 0
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python3 -m pytest tests/unit/test_influence_system.py -v
```

- [ ] **Step 3: 实现 InfluenceSystem**

```python
# game/influence_system.py
from __future__ import annotations

from typing import List

from game.constants import (
    INFLUENCE_DECAY_PER_HEX,
    INFLUENCE_OWN_BUFF_RATE,
    INFLUENCE_ENEMY_DEBUFF_RATE,
    INFLUENCE_ENEMY_DOMINANCE_RATIO,
)
from game.hex_grid import HexCoord, hex_distance
from game.hex_map import HexMap
from game.models import City
from game.tile import Tile


class InfluenceSystem:
    """影响力系统

    只提供 Buff/Debuff，不策反地块。
    """

    def spread_influence(
        self,
        cities: List[City],
        hex_map: HexMap,
    ) -> None:
        """每回合扩散影响力"""
        # 先清空
        for tile in hex_map.iter_tiles():
            tile.influence.clear()

        for city in cities:
            self._spread_from_city(city, hex_map)

    def _spread_from_city(self, city: City, hex_map: HexMap) -> None:
        radius = 5
        center = city.position
        base = city.level * 10 + city.morale / 10
        for q in range(-radius, radius + 1):
            for r in range(-radius, radius + 1):
                coord = HexCoord(center.q + q, center.r + r)
                dist = hex_distance(center, coord)
                if dist > radius:
                    continue
                tile = hex_map.get_tile(coord)
                if tile is None:
                    continue
                value = base * ((1 - INFLUENCE_DECAY_PER_HEX) ** dist)
                tile.influence[city.faction] = tile.influence.get(
                    city.faction, 0
                ) + value

    @staticmethod
    def get_tile_modifiers(tile: Tile, controlling_faction: str) -> dict:
        """获取某地块在当前控制势力下的 Buff/Debuff"""
        own = tile.influence.get(controlling_faction, 0)
        max_enemy = 0.0
        for faction, value in tile.influence.items():
            if faction != controlling_faction and value > max_enemy:
                max_enemy = value

        production_mod = 0.0
        defense_mod = 0.0
        movement_mod = 0.0

        if own > 0 and own >= max_enemy:
            production_mod += INFLUENCE_OWN_BUFF_RATE
            defense_mod += INFLUENCE_OWN_BUFF_RATE
        if max_enemy > 0 and max_enemy >= own * INFLUENCE_ENEMY_DOMINANCE_RATIO:
            production_mod -= INFLUENCE_ENEMY_DEBUFF_RATE
            defense_mod -= INFLUENCE_ENEMY_DEBUFF_RATE
            movement_mod -= 1.0

        return {
            "production": production_mod,
            "defense": defense_mod,
            "movement": movement_mod,
        }
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python3 -m pytest tests/unit/test_influence_system.py -v
```

- [ ] **Step 5: Commit**

```bash
git add game/influence_system.py tests/unit/test_influence_system.py
git commit -m "feat(influence): add influence spread and buff/debuff system"
```

---

## Phase 5: 军队移动适配

### Task 11: Army 模型增加当前格

**Files:**
- Modify: `game/models.py`

- [ ] **Step 1: 更新 Army 模型**

```python
# game/models.py
class Army(BaseModel):
    # 保留所有现有字段不变（id, faction, general_id, second_general_id,
    # soldiers, casualties, food, food_consumption_per_turn, morale, status,
    # from_city, to_city, progress, total_distance, is_in_battle, current_battle_id）
    current_hex: Optional[HexCoord] = Field(
        default=None, description="当前所在六角格"
    )
    path_hexes: List[HexCoord] = Field(
        default_factory=list, description="行军路径（HexCoord 列表）"
    )
    path_index: int = Field(default=0, description="当前路径索引")
```

- [ ] **Step 2: Commit**

```bash
git add game/models.py
git commit -m "feat(army): add current_hex and path_hexes fields"
```

---

### Task 12: 出征命令创建军队时计算 Hex 路径

**Files:**
- Modify: `game/engine.py` 中 `_execute_attack`

- [ ] **Step 1: 修改军队创建逻辑**

```python
# game/engine.py _execute_attack 中
from game.hex_grid import HexCoord

# 计算 Hex 路径
from_pos = self.hex_map.get_tile(self.cities[cmd.from_city].position)
to_pos = self.hex_map.get_tile(self.cities[cmd.to_city].position)
path = self.hex_map.find_path(
    self.cities[cmd.from_city].position,
    self.cities[cmd.to_city].position,
)
if not path:
    return CommandResult(
        success=False, command_type="attack",
        description=f"无法从 {cmd.from_city} 行军到 {cmd.to_city}",
    )

total_distance = max(1, len(path) - 1)

army = Army(
    id=f"army_{self._army_counter}",
    faction=cmd.faction,
    general_id=cmd.general,
    soldiers=cmd.troops,
    food=cmd.troops * 3,
    food_consumption_per_turn=int(cmd.troops * 0.2),
    morale=80,
    status=ArmyStatus.MARCHING,
    from_city=cmd.from_city,
    to_city=cmd.to_city,
    progress=0.0,
    total_distance=total_distance,
    current_hex=path[0],
    path_hexes=path,
    path_index=0,
)
```

- [ ] **Step 2: 运行相关测试**

```bash
python3 -m pytest tests/unit/test_engine.py -v
```

- [ ] **Step 3: Commit**

```bash
git add game/engine.py
git commit -m "feat(engine): create army with hex path"
```

---

### Task 13: ArmyMovementSystem 按格移动

**Files:**
- Modify: `game/battle/army_movement.py`
- Test: `tests/unit/test_army_movement.py`（扩展）

- [ ] **Step 1: 重构 process_movement**

```python
# game/battle/army_movement.py
from game.constants import SEASON_MOVEMENT_FACTOR
from game.hex_map import HexMap


def process_movement(
    self,
    army: Army,
    hex_map: HexMap,
    season: str = "spring",
) -> MovementResult:
    """处理一回合的军队移动"""
    result = MovementResult()
    if army.status not in (
        ArmyStatus.MARCHING,
        ArmyStatus.RETREATING,
        ArmyStatus.BESIEGING,
    ):
        return result

    # 移动力预算
    base_speed = 2.0 if army.status == ArmyStatus.RETREATING else 1.0
    season_factor = SEASON_MOVEMENT_FACTOR.get(season, 1.0)
    movement_budget = base_speed * season_factor

    old_index = army.path_index

    # 沿路径推进
    if (
        army.status in (ArmyStatus.MARCHING, ArmyStatus.RETREATING)
        and army.path_hexes
    ):
        while movement_budget > 0 and army.path_index < len(army.path_hexes) - 1:
            next_hex = army.path_hexes[army.path_index + 1]
            tile = hex_map.get_tile(next_hex)
            if tile is None:
                break
            cost = HexMap.terrain_move_cost(tile.terrain)
            if cost == float("inf"):
                break
            if movement_budget < cost:
                break
            movement_budget -= cost
            army.path_index += 1
            army.current_hex = next_hex

        total_steps = max(1, len(army.path_hexes) - 1)
        army.progress = army.path_index / total_steps
        result.progress_made = (army.path_index - old_index) / total_steps

    # 粮草消耗
    result.food_consumed = self._consume_food(army)

    # 断粮判定
    if army.food <= 0:
        result.starvation = True
        self._apply_starvation(army)

    # 溃散判定
    if army.morale <= MORALE_BREAK_THRESHOLD:
        soldiers_lost = self._apply_rout(army)
        result.routing = soldiers_lost > 0
        result.soldiers_lost_to_rout = soldiers_lost

    # 到达判定
    if army.status == ArmyStatus.MARCHING and army.path_index >= len(army.path_hexes) - 1:
        army.progress = 1.0
        arrival_result = self._handle_arrival(army)
        result.arrived = arrival_result["arrived"]
        result.arrival_type = arrival_result["type"]
        result.status_changed = arrival_result["status_changed"]

    return result
```

- [ ] **Step 2: 更新测试并运行**

```bash
python3 -m pytest tests/unit/test_army_movement.py -v
```

- [ ] **Step 3: Commit**

```bash
git add game/battle/army_movement.py tests/unit/test_army_movement.py
git commit -m "feat(movement): army moves along hex path with terrain cost"
```

---

### Task 14: GameEngine 传入 HexMap 到 Movement

**Files:**
- Modify: `game/engine.py`

- [ ] **Step 1: 更新 process_turn 中的行军调用**

```python
# game/engine.py process_turn
for army in list(self.armies.values()):
    if army.soldiers <= 0:
        del self.armies[army.id]
        continue
    self._army_movement.process_movement(army, self.hex_map, self.season)
    result["armies_moved"] += 1
```

- [ ] **Step 2: Commit**

```bash
git add game/engine.py
git commit -m "feat(engine): pass hex_map and season to movement system"
```

---

## Phase 6: 季节与无限模式

### Task 15: Season 与 GameMode 枚举

**Files:**
- Create: `game/season.py`
- Create: `game/game_mode.py`

- [ ] **Step 1: 实现枚举**

```python
# game/season.py
from enum import Enum


class Season(str, Enum):
    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"

    @classmethod
    def from_turn(cls, turn: int) -> "Season":
        month = ((turn - 1) % 12) + 1
        if month <= 3:
            return cls.SPRING
        elif month <= 6:
            return cls.SUMMER
        elif month <= 9:
            return cls.AUTUMN
        else:
            return cls.WINTER
```

```python
# game/game_mode.py
from enum import Enum


class GameMode(str, Enum):
    STANDARD = "standard"
    INFINITE = "infinite"
```

- [ ] **Step 2: 写测试**

```python
# tests/unit/test_season.py
from game.season import Season


def test_season_from_turn():
    assert Season.from_turn(1) == Season.SPRING
    assert Season.from_turn(4) == Season.SUMMER
    assert Season.from_turn(13) == Season.SPRING
```

- [ ] **Step 3: Commit**

```bash
git add game/season.py game/game_mode.py tests/unit/test_season.py
git commit -m "feat(season): add Season and GameMode enums"
```

---

### Task 16: GameEngine 支持季节与无限模式

**Files:**
- Modify: `game/engine.py`

- [ ] **Step 1: 添加字段**

```python
# game/engine.py __init__
from game.season import Season
from game.game_mode import GameMode

self.game_mode: GameMode = GameMode.STANDARD
self.season: Season = Season.SPRING
self.year: int = 1
self.start_year: int = 190  # 东汉末年，建安元年 = 196，可配置
```

- [ ] **Step 2: 更新 process_turn**

```python
# game/engine.py process_turn
self.season = Season.from_turn(self.turn)
self.year = self.start_year + (self.turn - 1) // 12

# 影响力扩散
self._influence_system.spread_influence(
    list(self.cities.values()), self.hex_map
)

# 资源计算时传入 season
for city in self.cities.values():
    territory = self._city_system.get_city_territory(city, self.hex_map)
    tiles = [self.hex_map.get_tile(c) for c in territory]
    tiles = [t for t in tiles if t is not None]
    result = self._resource_system.calculate_resources(
        city, tiles, self.season.value
    )
    city.gold += result["gold_change"]
    city.food += result["food_change"]
    city.population += result["population_change"]
    # 民心、资源下限等逻辑保留
```

- [ ] **Step 3: 适配胜利判定**

```python
# game/engine.py _check_victory
if self.game_mode == GameMode.INFINITE:
    # 无限模式：只剩一个势力或统一全国才结束
    active = [f for f, c in city_counts.items() if c > 0]
    if len(active) == 1:
        self.game_over = True
        self.winner = active[0]
    return

# 标准模式保持原逻辑（不变）
# 统计各势力城市数 -> 只剩一个势力则结束
# 到达 max_turns 后按城市最多者判定胜负/平局
self._check_standard_victory(city_counts)
```

- [ ] **Step 4: 运行测试**

```bash
python3 -m pytest tests/unit/test_engine.py tests/integration/test_full_game.py -v
```

- [ ] **Step 5: Commit**

```bash
git add game/engine.py
git commit -m "feat(engine): integrate season, infinite mode and hex-based resources"
```

---

## Phase 7: GUI 渲染

### Task 17: 基础 HexMapRenderer（DeepSeek）

**Files:**
- Create: `renderer/hex_map_renderer.py`
- Test: `tests/unit/test_hex_map_renderer.py`（mock surface）

- [ ] **Step 1: 实现基础渲染**

```python
# renderer/hex_map_renderer.py
from __future__ import annotations

import math
from typing import Optional

import pygame

from game.hex_grid import HexCoord, axial_to_pixel
from game.hex_map import HexMap
from game.tile import TerrainType


class HexMapRenderer:
    """六角格地图渲染器"""

    def __init__(self, hex_map: HexMap, hex_size: int = 32) -> None:
        self.hex_map = hex_map
        self.hex_size = hex_size
        self.colors = self._load_colors()

    def _load_colors(self) -> dict:
        import json
        import os
        path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "data", "terrain_colors.json"
        )
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def render(self, surface: pygame.Surface, camera_offset=(0, 0)) -> None:
        for tile in self.hex_map.iter_tiles():
            self._draw_hex(surface, tile, camera_offset)

    def _draw_hex(
        self,
        surface: pygame.Surface,
        tile,
        camera_offset: tuple,
    ) -> None:
        x, y = axial_to_pixel(tile.coord, self.hex_size)
        x += camera_offset[0]
        y += camera_offset[1]
        points = self._hex_points(x, y, self.hex_size)
        color = self.colors.get(tile.terrain.value, {}).get("fill", "#888888")
        border = self.colors.get(tile.terrain.value, {}).get("border", "#555555")
        pygame.draw.polygon(surface, self._hex_to_rgb(color), points)
        pygame.draw.polygon(surface, self._hex_to_rgb(border), points, 1)

    def _hex_points(self, x: float, y: float, size: float) -> list:
        import math
        points = []
        for i in range(6):
            angle = math.pi / 3 * i - math.pi / 6
            px = x + size * math.cos(angle)
            py = y + size * math.sin(angle)
            points.append((px, py))
        return points

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> tuple:
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
```

- [ ] **Step 2: 写 mock 测试**

```python
# tests/unit/test_hex_map_renderer.py
import pygame
from renderer.hex_map_renderer import HexMapRenderer
from game.hex_map import HexMap
from game.hex_grid import HexCoord
from game.tile import Tile, TerrainType


def test_hex_map_renderer_smoke():
    pygame.init()
    surface = pygame.Surface((400, 300))
    hm = HexMap(width=5, height=5)
    for q in range(5):
        for r in range(5):
            hm.add_tile(Tile(coord=HexCoord(q, r), terrain=TerrainType.PLAIN))
    renderer = HexMapRenderer(hm)
    renderer.render(surface)
    pygame.quit()
```

- [ ] **Step 3: Commit**

```bash
git add renderer/hex_map_renderer.py tests/unit/test_hex_map_renderer.py
git commit -m "feat(renderer): basic hex map renderer"
```

---

### Task 18: 势力边界与影响力云图渲染（Kimi）

**Files:**
- Modify: `renderer/hex_map_renderer.py`

- [ ] **Step 1: 绘制势力边界**

在 `_draw_hex` 中根据 `tile.faction` 填充势力色（半透明覆盖或替换地形色），并在相邻 faction 不同的边画更粗的边界线。

- [ ] **Step 2: 绘制影响力云图**

为每个地块计算主导势力影响力，用半透明色叠加。多势力时用颜色混合（需 Kimi 处理避免脏色）。

- [ ] **Step 3: Commit**

```bash
git add renderer/hex_map_renderer.py
git commit -m "feat(renderer): faction borders and influence heatmap (Kimi)"
```

---

### Task 19: 相机系统（Kimi）

**Files:**
- Create: `renderer/camera.py`
- Modify: `renderer/game_renderer.py`

- [ ] **Step 1: 实现 Camera 类**

```python
# renderer/camera.py
from __future__ import annotations


class Camera:
    """2D 相机：支持平移、缩放"""

    def __init__(self, x: float = 0, y: float = 0, zoom: float = 1.0) -> None:
        self.x = x
        self.y = y
        self.zoom = zoom
        self.min_zoom = 0.3
        self.max_zoom = 3.0

    def move(self, dx: float, dy: float) -> None:
        self.x += dx / self.zoom
        self.y += dy / self.zoom

    def zoom_at(self, factor: float, screen_x: float, screen_y: float) -> None:
        new_zoom = max(self.min_zoom, min(self.max_zoom, self.zoom * factor))
        # 以鼠标位置为锚点缩放
        wx = (screen_x - self.x) / self.zoom
        wy = (screen_y - self.y) / self.zoom
        self.x = screen_x - wx * new_zoom
        self.y = screen_y - wy * new_zoom
        self.zoom = new_zoom

    def world_to_screen(self, wx: float, wy: float) -> tuple:
        return (
            wx * self.zoom + self.x,
            wy * self.zoom + self.y,
        )

    def screen_to_world(self, sx: float, sy: float) -> tuple:
        return (
            (sx - self.x) / self.zoom,
            (sy - self.y) / self.zoom,
        )
```

- [ ] **Step 2: 接入 GameRenderer**

处理鼠标滚轮缩放、中键拖拽平移、WASD/方向键平移。

- [ ] **Step 3: Commit**

```bash
git add renderer/camera.py renderer/game_renderer.py
git commit -m "feat(renderer): camera pan and zoom (Kimi)"
```

---

### Task 20: 军队与城市在 Hex 上渲染（Kimi）

**Files:**
- Modify: `renderer/hex_map_renderer.py`
- Modify: `renderer/game_renderer.py`

- [ ] **Step 1: 绘制城市**

在 `HexMapRenderer` 中添加 `render_cities`，接收 `engine.cities`，在城市格子上绘制势力色圆点/六边形高亮，显示城市名。

- [ ] **Step 2: 绘制军队**

军队沿 `path_hexes` 插值渲染，在格与格之间平滑移动。显示士气条、兵力、方向箭头。

- [ ] **Step 3: Commit**

```bash
git add renderer/hex_map_renderer.py renderer/game_renderer.py
git commit -m "feat(renderer): render cities and armies on hex grid (Kimi)"
```

---

### Task 21: UI 面板扩展（DeepSeek）

**Files:**
- Modify: `renderer/ui_panel.py`

- [ ] **Step 1: 显示季节/年份/游戏模式**

```python
# renderer/ui_panel.py _render_turn_info 中
season_names = {"spring": "春", "summer": "夏", "autumn": "秋", "winter": "冬"}
turn_text = f"{self.engine.year}年 {season_names[self.engine.season.value]} 第{self.engine.turn}回合"
```

- [ ] **Step 2: 显示地块详情**

当 `selected_tile_coord` 存在时，显示地形、产出、影响力、控制城市。

- [ ] **Step 3: Commit**

```bash
git add renderer/ui_panel.py
git commit -m "feat(ui): show season, year, game mode and tile details"
```

---

## Phase 8: 入口与集成

### Task 22: main.py 支持新模式

**Files:**
- Modify: `main.py`

- [ ] **Step 1: 添加参数**

```python
# main.py parse_args
parser.add_argument(
    "--mode",
    choices=["ai-vs-ai", "human-vs-ai", "replay", "gui", "infinite"],
    default="ai-vs-ai",
    help="运行模式",
)
parser.add_argument("--start-year", type=int, default=190, help="起始年份")
```

- [ ] **Step 2: 删除死代码**

删除 `run_gui_mode` 中 `renderer.run()` 之后的死代码块（第 212–227 行）。

- [ ] **Step 3: 实现无限模式入口**

```python
# main.py
def run_infinite_mode(
    seed: int = 42,
    use_llm: bool = False,
    model: str = "deepseek-v4-flash",
    api_key: str = "",
    start_year: int = 190,
) -> None:
    """运行无限模式"""
    from game.game_mode import GameMode

    engine = GameEngine(seed=seed)
    engine.game_mode = GameMode.INFINITE
    engine.max_turns = 9999
    engine.start_year = start_year

    data = load_game_data()
    engine.init_game(data)

    players = {}
    for faction in FACTIONS:
        if use_llm and faction == "wei":
            llm_client = LLMClient(provider="deepseek", model=model, api_key=api_key)
            players[faction] = LLMPlayer(faction=faction, llm_client=llm_client)
        else:
            players[faction] = CLIPlayer(
                faction=faction,
                rng=GameRandom(seed + hash(faction) % 10000),
            )

    from renderer.game_renderer import GameRenderer
    renderer = GameRenderer(engine, title="LLM三国志 - 无限模式")
    renderer.run(players=players, auto_run=True)
```

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "feat(main): support infinite mode and clean dead code"
```

---

### Task 23: 数据加载器集成 HexMap

**Files:**
- Modify: `game/engine.py`

- [ ] **Step 1: 在 init_game 中加载 HexMap**

```python
# game/engine.py
from game.hex_map import HexMap
from game.tile import Tile, TerrainType
from game.data_loader import load_hex_map_data


def init_game(self, data: Dict[str, Any]) -> None:
    # 加载城市、将领、地图拓扑（保留现有旧逻辑不变）
    self._load_cities(data)
    self._load_generals(data)
    self._load_map_topology(data)

    # 加载 HexMap
    hex_data = load_hex_map_data()
    self.hex_map = HexMap(
        width=hex_data["width"],
        height=hex_data["height"],
    )
    for t in hex_data.get("terrain", []):
        self.hex_map.add_tile(Tile(
            coord=HexCoord(t["q"], t["r"]),
            terrain=TerrainType(t["terrain"]),
            elevation=t.get("elevation", 0),
            gold_yield=t.get("gold_yield", 0),
            food_yield=t.get("food_yield", 0),
            pop_yield=t.get("pop_yield", 0),
        ))

    # 绑定城市位置到 HexMap 城市坐标
    for city_id, pos in hex_data.get("city_positions", {}).items():
        if city_id in self.cities:
            self.cities[city_id].position = HexCoord(pos["q"], pos["r"])

    # 初始化地块归属和产出
    self._initialize_territories()
```

- [ ] **Step 2: 实现 _initialize_territories**

```python
def _initialize_territories(self) -> None:
    for city in self.cities.values():
        territory = self._city_system.get_city_territory(city, self.hex_map)
        for coord in territory:
            tile = self.hex_map.get_tile(coord)
            if tile is not None:
                tile.owner_city_id = city.id
                tile.faction = city.faction
                # 应用地形基础产出
                yields = TERRAIN_YIELDS.get(tile.terrain.value, {})
                tile.gold_yield = yields.get("gold", 0)
                tile.food_yield = yields.get("food", 0)
                tile.pop_yield = yields.get("pop", 0)
```

- [ ] **Step 3: Commit**

```bash
git add game/engine.py
git commit -m "feat(engine): load HexMap and initialize territories"
```

---

### Task 24: 全量回归测试

**Files:**
- All tests

- [ ] **Step 1: 运行全部测试**

```bash
python3 -m pytest tests/ -q
```

- [ ] **Step 2: 修复失败测试**

重点检查：
- `test_engine.py`：City.position 改为 HexCoord 后旧测试可能失败
- `test_full_game.py`：完整对局流程
- 所有使用 `position: [x, y]` 的测试数据

- [ ] **Step 3: Commit 修复**

```bash
git add .
git commit -m "test: fix regressions after hex grid migration"
```

---

### Task 25: 运行一局验证

**Files:**
- `main.py`

- [ ] **Step 1: 运行标准模式**

```bash
python3 main.py --mode gui --seed 42
```

- [ ] **Step 2: 运行无限模式**

```bash
python3 main.py --mode infinite --seed 42
```

- [ ] **Step 3: 观察并记录问题**

- 地图是否正确显示
- 季节是否切换
- 资源产出是否合理
- 军队是否能正常移动和围城
- 是否有异常报错

- [ ] **Step 4: Commit 最终修复**

```bash
git add .
git commit -m "fix: smoke test fixes for hex map and infinite mode"
```

---

## 验收标准

1. `pytest tests/` 全部通过
2. `python3 main.py --mode gui` 能正常显示六角格地图、城市、军队
3. `python3 main.py --mode infinite` 能运行多回合，季节/year 显示正确
4. 地块产出受地形、季节、民心、影响力影响
5. 军队按六角格路径移动，山地不可通行，河流/森林减速
6. 势力边界和影响力 Buff 生效
7. 代码符合 AGENTS.md 规范（类型注解、PEP 8、三层分离、无 pygame import in engine）

---

## 备注

- 所有新增模块必须遵循 AGENTS.md：type hints、Google docstring、自定义异常、不硬编码路径。
- Engine 层严禁 import pygame。
- 确定性：HexMap 生成、A* 路径、影响力扩散必须只依赖 seed，不依赖 `random.random()` 或 `time.time()`。
