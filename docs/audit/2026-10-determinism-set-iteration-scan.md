# 集合迭代序确定性扫描清单

> 审计人：程基岩（engineering-lead）｜日期：2026-10-03｜分支：`feat/web-frontend`
> 触发：跨进程确定性（ADR-0002）在三个月内被 3 个人、3 处独立发现坏过（玩家种子 / 地图拓扑 / 外交目标），判定为**系统性模式**而非偶发，故做一次全仓扫描。
> 判据（来自主理人任务书）：**该处迭代序是否进入①随机数消耗序列，或②影响输出的分支**。都不涉及的，迭代序变了也无害，**不过度修改**。

## 一、扫描方法与范围

- 工具：CodeBuddy 内置 `Grep`（ripgrep 内核）。
- 目标模式：`list({...})`、`list(set(...))`、`set(`、`{x for x in ...}`、`for x in <set>`、`sorted(set(...))`。
- 范围：`game/`、`players/`、`api/`。
- 说明：Python 3.7+ **dict 迭代序 = 插入序**，是稳定的；本扫描的「序不稳」来源只针对 `set` / `frozenset`。引擎主循环遍历的 `cities/armies/generals` 均为 dict（插入序稳定），故不在风险之列。

## 二、结论表

| # | 位置 | 模式 | 进入 RNG / 输出？ | 裁定 | 处置 |
|---|---|---|---|---|---|
| 1 | `api/game_manager.py`（玩家种子） vs `main.py:100/207/256` | 内置 `hash()`（受 `PYTHONHASHSEED` 随机加盐） | ✅ 是（每方玩家随机种子） | **修** | 已修（commit `ad0894e`）：抽 `game/random.stable_hash` + main.py 3 处改用 |
| 2 | `game/data_loader.py:77` `map_topology = {cid: set() ...}` | `set` 构造邻接表 | ✅ 是（拓扑 → A* 寻路 → 行军） | **修** | 已修（commit `27a52d3`，队友）：对称化 + `sorted(nbs)` |
| 3 | `players/cli_player.py:87` `enemy_factions = list({...})` | `set → list` 后喂 `self._rng.choice()` | ✅ 是（外交/宣战目标） | **修** | 已修（commit `ad0894e`）：改 `sorted({...})` |
| 4 | `game/systems/city_system.py:348` `get_city_territory` 返回 `set[HexCoord]`，消费点 `game/engine.py:850` 迭代该 set 构造 `tiles` | `set → 迭代 → sum(浮点 tile 产出)` | ✅ 是（金钱/粮草/人口产出） | **修** | 已修（本清单同批）：按 `(q, r)` 排序后再取 tile，锁定求和顺序 |
| 5 | `game/engine.py:374` `_expand_territories` `assigned` | `set` 仅成员判断（`in assigned`），遍历用 deque + 固定 dirs | ❌ 否 | 无害 | 不动 |
| 6 | `game/engine.py:1125-1136` `_apply_nature_strain` `actions_by_faction` | `set` 仅成员 / 交集（`in`、`&`）判断，结果为布尔 | ❌ 否 | 无害 | 不动 |
| 7 | `game/engine.py:1428/1432/1455` `neighbor_city_ids` / `own_city_hexes` | `set` 仅成员判断；规则5 遍历 `own_city_hexes` 但只求「是否存在距离≤2」的布尔 | ❌ 否 | 无害 | 不动 |
| 8 | `players/cli_player.py:86 enemy_ids` / `:148 assigned` / `:282 own_city_ids` | `set` 仅成员判断 | ❌ 否 | 无害 | 不动 |
| 9 | `game/map_generator.py:610 visited` / `:790 assigned` | `set` 仅成员判断；遍历一律是 `for r in range(height): for q in range(width)` 网格序 | ❌ 否 | 无害 | 不动 |
| 10 | `api/game_manager.py:239` `sorted(set(self.llm_model_by_faction.values()))` | 已显式 `sorted()` | — | 无害 | 不动 |

**统计**：需修 4 处（#1–#4，其中 #1 #3 本轮、#2 队友已修、#4 本轮）；判定无害 6 处（#5–#10）。

## 三、#4 的细节（本轮新发现）

- `CitySystem.get_city_territory`（`city_system.py:334`）返回 `set[HexCoord]`，**唯一生产消费点**是 `engine.py:850`（`rg` 复核：其余命中均为测试）。
- 消费链：`territory` → `[hex_map.get_tile(c) for c in territory]` → `ResourceSystem.calculate_resources(tiles=...)` → `sum(t.gold_yield for t in tiles)` / `sum(t.food_yield ...)` / `sum(t.pop_yield ...)`。
- 🔴 **为什么是风险**：`set` 迭代序随 `PYTHONHASHSEED` 变 → 浮点求和的**相加顺序**变 → 浮点加法不满足结合律，可能出现 1-ULP 差异 → 后续 `int(...)` 截断后产出差 1 → 逐回合放大成整局分叉。
- **为什么之前没被实测抓到**：概率性（很多 tile 产出是 0.5/3.0 这类可精确表示的二进制小数，顺序无关）；且 12 回合窗口内未必累积到可见分叉。属**潜在**而非已现。
- **处置**：`engine.py:850` 改为 `sorted(territory, key=lambda h: (h.q, h.r))` 后再取 tile。不改 `get_city_territory` 的返回类型（保持 `set`，测试与签名不变），只在消费点排序——最小改动、零语义变更。

## 四、边界与未覆盖

- 本扫描针对 `set`（Python 唯一「迭代序不稳」的内置容器）；`dict` 迭代序稳定，未逐处列。
- 未穷举 `sorted(key=...)` 之外的二级排序稳定性；若某处对「相等键」的元素依赖原序，理论上仍可能不稳，但本次未发现此类调用。
- 建议以自动化守卫（`tests/integration/test_cross_process_determinism.py`）作为长期防线，而非依赖本清单逐项维护。
