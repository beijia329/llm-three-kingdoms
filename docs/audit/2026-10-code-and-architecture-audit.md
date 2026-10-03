# 代码与架构可插拔性审计报告

> 审计人：程基岩（engineering-lead）｜分支：`feat/web-frontend`
> 初版核实：2026-10-03，HEAD `eff4c8a` ｜ 入库前复核：2026-10-03，HEAD `ba51e6a`（复核了 EventBus 与死常量清单，结论不变；仅 `CAPTURE_SURRENDER_*` 已随 v4.1 删除，见 A-3）。
> 性质：**只读研究**（本轮未改任何代码；仅另追加独立 commit 做确定性修复，见报告外）。
> 方法：全量实读 `game/`（28 个 .py）、`players/`（含 `llm/`）、`api/`、`renderer/`、`web/src/`（16 个 .ts/.tsx）、根脚本（`main.py`/`run_web.py`），并用 **ripgrep 内核** 复核引用数。
> 🔴 **工具口径**：本机 `rg` 未在 PATH（`which rg` 返回空），全程改用 CodeBuddy 内置 `Grep` 工具（ripgrep 内核，非 BSD grep）。所有「零引用 / N 处引用」结论均来自该工具全仓扫描，报告里给数字。
> ⚠️ **行号时效**：报告中的 `文件:行号` 为核实时的 HEAD（`eff4c8a`）。文件随后有他人提交（文档对齐/地图拓扑/美术），行号可能位移 ±数行——**以符号名与引用数为准，行号仅供定位**。
> 交叉参考：`docs/audit/2026-10-docs-and-gameplay-audit.md`（文策渊：文档/玩法层）、`docs/pitfalls.md`（死常量登记）。本报告不重复文档对账，聚焦**代码本身 + 可插拔性**。

---

## 〇、总体结论（先读这 5 条）

1. **「mod/DLC 式可插拔」目前评 3/10**。原因是：玩法系统没有统一接口与注册表，靠 `engine.py` 手写调用；加一个命令要改 **8 个文件、约 11 处**，其中 4 处是必须手工同步的平行注册表。详见 §②。

2. **最该修、最容易修、收益最大的一处：`EventBus` 是死的。** 定义了 11 个事件类、约 370 行基础设施，全仓**只有 1 处 `publish`**（`game/engine.py:707`），**0 处 `subscribe`**。`ADR-0001` 把「事件驱动、UI 订阅事件」写成 Accepted，实际上前端/API 都在**轮询** `get_state()`。这是原本应该充当「插件钩子」的那条缝——它存在，但没接线。

3. **一条命令类型要改 8 个文件**：`models.py` / `engine.py`（2 处）/ `llm_player.py`（2 张表）/ `output_parser.py`（2 张表）/ `prompt_builder.py` / `game_manager.py` / `web/src/constants/commands.ts`（4 张表）。**加了命令不改引擎是不可能的**——`execute_command` 是 9 分支的硬 `if/elif`。（🔴 批 2 已改（`166acf6`）：`execute_command` 现走注册表，**引擎分发不必再改**；但端到端加一条**可用**命令仍需约 4 处——准确口径见 §2.4bis。）

4. **玩法机制 0% 数据驱动**。`data/*.json` 只放静态内容（城市/将领/州/地形坐标），**所有机制数值在 `constants.py`、所有机制逻辑在 Python**。想「用 JSON 定义一个每回合结算的新机制」，当前**做不到**。

5. **代码里存在多处「同一语义两套实现」，且其中至少 2 处已经跑偏**：跨进程确定性 seed（`game_manager` 用 CRC32 稳、`main.py` 用内置 `hash()` 不稳）、通行判定（`tile.is_passable()` 与 `TERRAIN_MOVE_COST` 两张表）。前者让 CLI 入口复现不了对局，后者让「改一处不生效」。详见 §①-B。

---

## ① 代码问题清单

> 每条：`文件:行号` + 引用数（ripgrep 全仓）+ 影响。凡「零引用」均已用 ripgrep 复核，排除「文件名/注释推断」。

### A. 死代码（定义了但生产路径零调用）

**A-1 顶层符号（函数/类/字段）**

| # | 符号 | 位置 | 全仓引用 | 影响 |
|---|---|---|---|---|
| 1 | `TurnResult` dataclass | `game/engine.py:96` | 2（定义 + `main.py:26` 只 import 未用） | 死 import 拖累；`main.py` 顶部 `from game.engine import GameEngine, TurnResult` 里的 `TurnResult` 从未使用 |
| 2 | `load_state_snapshot()` | `game/engine.py:1533` | 1（仅定义；仅 `docs/handoff` 提到） | 「状态回滚/时间旅行」是 `AGENTS.md 7.5` 的设计承诺，实际无恢复入口 → `GameState` 快照只写不读 |
| 3 | `MapRenderer`（整个文件） | `renderer/map_renderer.py:24` | 1（仅自身定义） | **已废弃的 pygame 路径**：`GameRenderer` 用的是 `HexMapRenderer`，全仓无人 import `MapRenderer` |
| 4 | `ReplayPlayer`（整个文件） | `renderer/replay_player.py:24` | 1（仅自身定义） | 回放功能在 `main.py:292` 仍是「尚在开发中」；类已写好但无调用方 |
| 5 | `MovementEvent` dataclass | `game/battle/army_movement.py:68` | 2（定义 + `tests/unit/test_army_movement.py:14` import） | docstring 自述「用于事件总线/日志」，而事件总线是死的；生产从不构造 |
| 6 | `_estimate_wall_hp()` | `game/battle/battle_resolver.py:217` | 1（仅定义；仅注释提及） | v4 改为「城墙为 0 直接进巷战」，该方法废弃但未删 |
| 7 | `_generate_general_name()` | `game/systems/general_system.py:172` | 1（仅定义） | 自述「已废弃，保留以兼容旧引用」——实际零引用（连测试都没有） |
| 8 | `calculate_turns_to_arrive()` | `game/battle/army_movement.py:381` | 3（定义 + 2 处测试） | 生产 0 调用 |
| 9 | `second_general_id` 字段 | `game/models.py:201` | 1（仅字段定义） | 「副将」机制未实现，字段永远 `None` |
| 10 | `killed_generals` 字段 | `game/models.py:556` | 1（仅字段定义） | 将领「阵亡」机制未实现（只被俘，不阵亡），字段永不写入 |
| 11 | `Faction` 枚举 | `game/models.py:21` | 5（定义 + `tests/unit/test_models.py`） | 生产用 `constants.FACTIONS` dict；枚举是**第 2 份势力清单**（见 B-5），只被测试使用 |
| 12 | `Direction` 枚举 + `get_direction()` + `direction_opposite()` + `_DIRECTION_VECTORS` + `_OPPOSITE_DIRECTION` | `game/hex_grid.py:18/121/148/64/74` | 全部：定义 + `tests/unit/test_hex_grid.py` | 一整块 Wesnoth 借鉴代码，**生产 0 调用**（`find_path` 用的是 `hex_neighbors`/`HEX_DIRECTIONS`） |
| 13 | `get_aggression_weight()` | `game/personality.py:362` | 1（仅定义，**连测试都没有**） | 「性格影响进攻权重」的接口写好但没人调 |
| 14 | `get_general_trait()` | `game/personality.py:346` | 1（仅定义） | `prompt_builder` 用的是 `get_general_title()`，不是 `trait`；`trait` 从未进 prompt |
| 15 | `get_tile_modifiers()` | `game/influence_system.py:87` | 6（定义 + `tests/unit/test_influence_system.py`×4 + 1 份 docs 计划） | 🔴 **影响力系统「算了但不生效」**：每回合 `spread_influence` 计算所有地块影响力，但没有任何代码读取 `get_tile_modifiers` 的加成 → 影响力对产出/防御/移动**零影响** |
| 16 | `GENERAL_PERSONALITIES` | `game/personality.py:331` | 1（仅定义 + docstring 自述） | 自述「由 `GENERAL_PROFILES` 派生以兼容旧引用」，实际**无任何引用** |
| 17 | `season_names_zh()` | `game/season.py:50` | 2（定义 + `tests/unit/test_season.py`） | 生产 0 调用（前端有自己的季节中文映射） |
| 18 | `get_all_provinces()` | `game/systems/map_system.py:252` | 1（仅定义） | 0 引用 |
| 19 | `get_province_cities()` | `game/systems/map_system.py:260` | 1（仅定义） | 0 引用 |
| 20 | `get_city_province()` | `game/systems/map_system.py:274` | 1（仅定义） | 0 引用 |
| 21 | `get_city_count()` | `game/systems/map_system.py:70` | 4（定义 + 3 测试） | 生产 0 调用 |
| 22 | `are_adjacent()` | `game/systems/map_system.py:101` | 4（定义 + 3 测试） | 生产 0 调用 |
| 23 | `get_faction_city_counts()` | `game/systems/map_system.py:218` | 2（定义 + 1 测试） | 生产 0 调用（`api/game_manager` 自己重算 city_counts） |
| 24 | `mark_as_read()` | `game/systems/diplomacy_system.py:148` | 2（定义 + 1 测试） | 🔴 生产从不标记已读 → `prompt_builder.build_state_prompt` 每次都把**所有历史外交消息**当成「未读」重复喂给 LLM |
| 25 | `reject_alliance()` | `game/systems/diplomacy_relation.py:208` | 2（定义 + 1 测试） | 0 生产调用 |
| 26 | `is_allied()` / `is_at_war()` / `is_truce()` | `game/systems/diplomacy_relation.py:105/109/113` | 各 2（定义 + 测试） | 生产 0 调用（引擎直接用 `get_status`/`can_attack`） |
| 27 | `set_long_term()` | `players/llm/memory_manager.py:76` | 4（定义 + 3 测试） | 🔴 生产从不设置 `long_term` → `get_context()` 的「## 长期战略」段**永远为空**，记忆分层退化 |
| 28 | `get_cost_summary()` | `players/llm/llm_client.py:303` | 3（定义 + `tests/llm_3p_run.py`×2 + 1 测试） | 生产/前端 0 调用 → token 用量与成本从不被消费（`total_cost` 只在内存累计） |

**A-2 Web 前端（`web/src/`，0 引用的整文件/导出）**

| # | 符号 | 位置 | 引用 | 影响 |
|---|---|---|---|---|
| 29 | `web/src/utils/tiles.ts`（**整文件**：`computeTiles`/`preloadTiles`/`getTileTexture`/`createTileSprite`/`TileInfo`） | 全文 | **0 import**（ripgrep 全 `web/` 仅命中自身） | CartoDB 卫星瓦片底图方案已被「古地图羊皮纸」替换，整文件 128 行死代码 |
| 30 | `web/src/utils/colors.ts`（**整文件**） | 全文 | **0 import** | `FACTION_COLORS`/`FACTIONS`/`TERRAIN_COLORS`/`UI_COLORS`/`hexToNumber` 的**第 3 份**副本 |
| 31 | `web/src/utils/mapIcons.ts`（**整文件**） | 全文 | **0 import** | FontAwesome SVG 纹理加载，已被内联 `<i class="fa-...">` 取代 |
| 32 | `theme/index.ts` 的 `TERRAIN_COLORS`/`UI_COLORS`/`SHADOWS`/`CITY_STYLES`/`ARMY_STYLES`/`hexToRgba` | `web/src/theme/index.ts:61/81/98/106/143/163` | 0（仅自身定义） | 设计 token 模块只用到 `FACTION_COLORS`/`FACTIONS`/`FACTION_GLOW`/`hexToNumber`，其余 6 个导出死 |
| 33 | `computeChinaMask()` | `web/src/components/GameMap.tsx:536` | 1（仅导出定义） | 76 行 flood-fill 版图算法，导出但无调用方 |
| 34 | `KNOWN_COMMAND_CLASS_NAMES` | `web/src/constants/commands.ts:89` | 1（仅导出定义） | 自述「供测试断言映射表覆盖完整」，但 `web/` 下**没有任何 `.test/.spec` 文件**（`find` 返回空），断言不存在 |

**A-3 死常量（`game/constants.py`，生产 0 引用）**

用 ripgrep 逐个复核，以下均在**生产代码 0 引用**（部分仅被 `tests/unit/test_constants.py` 断言）：

| 常量 | 行 | 备注 |
|---|---|---|
| `OVERTIME_EXTRA_SOLDIERS` | 71 | 文件已自标「全仓 0 引用」；加时机制从未实现 |
| `STARTING_CITIES_PER_FACTION` | 59 | 0 引用 |
| `EXPLORE_COOLDOWN_TURNS` | 388 | 文件已自标 0 引用；探索冷却从未实现 |
| `INTELLIGENCE_STRATEGY_SUCCESS_RATE` | 443 | 文件已自标 0 引用；没有「计谋」命令类型可挂 |
| `MORALE_LOSS_GENERAL_DEATH` | 270 | 0 引用（将领不会阵亡） |
| `MORALE_BOOST_OUTNUMBERED` | 276 | 0 引用 |
| `MORALE_LOSS_SURROUNDED` | 282 | 0 引用 |
| `MORALE_LOSS_BESIEGED` | 279 | 🔴 **0 引用，但语义存在**：`city_system.py:377` 直接硬编码 `change -= 3`，改常量无效 |
| `MORALE_ELITE_THRESHOLD`/`HIGH`/`NORMAL`/`LOW`/`CRITICAL` | 286/289/292/295/298 | 5 个士气分档阈值全 0 引用 |
| `INITIAL_GOLD`/`INITIAL_FOOD`/`INITIAL_GENERALS_PER_FACTION` | 533/536/539 | 0 引用（初始值来自 `data/*.json`） |
| `DEBUG_MODE`/`LOG_LEVEL`/`AI_THINKING_TIMEOUT_SECONDS`/`AI_MAX_RETRIES` | 546/549/552/555 | 4 个「开发/调试」常量全 0 引用（超时/重试用的是 `llm_client` 自己的常量） |
| `MIN_DISTANCE_BETWEEN_CITIES` | 526 | 0 引用 |
| `DIPLOMACY_ALLIANCE_COMBAT_BONUS` | 507 | 0 引用（「同盟共同对敌 +10%」未实现） |
| ~~`CAPTURE_SURRENDER_BASE_CHANCE`/`CAPTURE_SURRENDER_LOYALTY_FACTOR`~~ | ~~375/378~~ | **已于 v4.1 删除**（`game/constants.py:375` 仅留「已删除」注释；初版把这两条列为死常量，入库复核时已消失——不追认） |
| `MAX_LOYALTY_FROM_REWARD` | 372 | 0 引用（`general_system.py:221` 硬编码 100） |
| `GENERAL_ATTRIBUTE_MIN`/`GENERAL_ATTRIBUTE_MAX` | 454/457 | 仅 `tests/unit/test_constants.py` 断言，生产 0 |
| `MAP_WIDTH`/`MAP_HEIGHT`/`CITY_RENDER_RADIUS` | 517/520/523 | 仅被 pygame `renderer/`（且 `MapRenderer` 已死）引用；Web 端不用 |

**A-4 死 import**

- `MORALE_COMBAT_BONUS_RATE`（`game/battle/battle_resolver.py:47`）：被 import，但函数体用的是内联 `avg_morale/100.0`，常量从未引用。= 死 import。
- `TurnResult`（`main.py:26`）：见 A-1-1。

---

### B. 矛盾实现（同一语义，两套/多套）

| # | 语义 | 实现 A | 实现 B | 判定 |
|---|---|---|---|---|
| **B-1** | **跨进程确定性：每方玩家 RNG 种子** | `api/game_manager.py:267` 用 `_stable_hash()`（`zlib.crc32`，跨进程恒定，有注释解释为何不用内置 hash） | `main.py:100 / 207 / 256` 用内置 `hash(faction) % 10000` | 🔴 **`main.py` 违反 ADR-0002**。`PYTHONHASHSEED` 随机加盐 → 同一 `--seed` 在 CLI 入口跑出的对局不可复现。修一处漏三处 |
| **B-2** | **地块可否通行** | `tile.is_passable()`（`game/tile.py:73-98`） | `TERRAIN_MOVE_COST`（`game/constants.py:575-598`，`inf`=不可通行） | 两条真值来源，且 `hex_map.find_path` **两个都读**（`hex_map.py:129` 读 `is_passable`，`:131` 读 `terrain_move_cost`）。`constants.py:583-585` 的注释**谎称**「改 `is_passable()` 不生效，因为 `find_path` 走的是本表」——实测 `find_path` 确实调用了 `is_passable()` |
| **B-3** | **六角格距离** | `hex_grid.hex_distance()`（`hex_grid.py:95`） | 内联重复 3 处：`engine._nearest_city`（`engine.py:1261-1265`）、`engine.get_observation` 可见性规则5（`engine.py:1457-1459`）、`GameMap.tsx getFactionAt`（`GameMap.tsx:522-525`） | 4 份实现，改算法要改 4 处 |
| **B-4** | **城市控制区半径** | `CITY_TERRITORY_RADIUS`（`constants.py:664`，被 `CitySystem.get_city_territory` 用） | `engine._expand_territories` 用 `depth = 8 + city.level*2`（`engine.py:383`）；`GameMap.tsx cityRadius()` 用 `1/2/3`（`GameMap.tsx:530-534`） | 🔴 **3 套不同半径**。后端的「领地归属」用 8+level×2、前端「势力边界」用 1/2/3 → 前端画的边界与后端判定的归属**对不上** |
| **B-5** | **势力清单** | `constants.FACTIONS`（`constants.py:78`） | `models.Faction` 枚举（`models.py:21`）、`web/theme FACTIONS`（`theme/index.ts:29`）、`web/utils/colors FACTIONS`（`colors.ts:38`） | 4 份副本 |
| **B-6** | **势力颜色** | `constants.FACTION_COLORS`（`constants.py:93`，如 caocao=`#0055A4`） | `web/theme FACTION_COLORS`（`theme/index.ts:9`，caocao=`#6b3020`） | 取向不同（后端旧色板 vs 前端美术新色板），两套并存 |
| **B-7** | **城市资源/民心每回合更新** | `engine.process_turn` hex 分支：直接调 `ResourceSystem.calculate_resources`（`engine.py:853`），**不做民心自然变化** | `CitySystem.update_city`（`city_system.py:287`）：调 `resource_system.update_city_resources` **并**应用 `_calculate_morale_change` | 🔴 生产走 hex 分支（`hex_map` 成功生成后恒非 None），于是 `CitySystem.update_city` + `_calculate_morale_change`（围城 -3 / 断粮 -5 / 向 50 回归，`city_system.py:358-392`）**在生产路径上是死的**。民心只能靠 `develop(culture)`、人设代价、占城 -20 改变——**「围城掉民心」这条规则事实上没生效** |
| **B-8** | **增援入城（兵力并入守军）** | `army_movement._handle_arrival` 友方分支：`target_city.garrison += army.soldiers`（**无上限**，`army_movement.py:351`） | `engine._disband_army_into_city`：`min(garrison + soldiers, level*GARRISON_CAP_PER_LEVEL)`（**有上限**，`engine.py:1278-1279`） | 两套增援实现，一个封顶一个不封顶 → 守军可被两条代码路径带过上限 |
| **B-9** | **命令 schema** | `engine.execute_command` 的 `if/elif` + `isinstance`（`engine.py:435-452`） | `llm_player.COMMAND_CLASSES`/`PARAM_MAPPING`（`llm_player.py:44/73`）、`output_parser.VALID_COMMAND_TYPES`/`required_params`（`output_parser.py:333/362`）、`game_manager._deserialize_command`（`game_manager.py:450`）、`web commands.ts` 4 张表 | 命令的「类型—字段—必填」定义散落 **6 处**，无单一真源（详见 §②-2.1） |

---

### C. 隐性耦合（跨模块直访内部状态）

> 判据：不应触及的 `_私有` 成员，或利用「共享可变对象」绕过接口。

| # | 位置 | 直访对象 | 影响 |
|---|---|---|---|
| C-1 | `api/game_manager.py:378-379` | `self.engine._diplomacy_relation_system` | API 层深入引擎私有子系统取关系状态 |
| C-2 | `api/game_manager.py:404` | `self.engine._messages` | 同上（外交消息私有列表） |
| C-3 | `api/game_manager.py:616` | `getattr(self.engine, '_kingdom_system', None)` | 用 `getattr` 兜底访问引擎私有建国系统 |
| C-4 | `api/game_manager.py`（多处：297/312-313/335/361-362/368/415/701/728/791） | `engine.cities/armies/generals/provinces/hex_map/turn_logs/turn` | API **绕过 `get_state_snapshot()` 接口**直接遍历引擎内部集合序列化前端状态。引擎内部结构一变，API 静默出错 |
| C-5 | `renderer/game_renderer.py:480` | `self.engine._diplomacy_relation_system` | pygame 渲染器同样直访私有 |
| C-6 | `renderer/game_renderer.py` / `ui_panel.py`（十余处） | `engine.cities/generals/armies/turn_logs` | 渲染层直读引擎内部集合 |
| C-7 | `engine._execute_attack`（`engine.py:552-556`） | 直接改**另一座城**的 `city.generals` 列表 | 为满足 `battle_scheduler`（`battle_scheduler.py:206-209` 直接读 `target_city.generals` 算守方统帅）而手写维护两份城的 `generals`。引擎自己在该处注释里标「🔴 必须同步维护……否则守城将领名单错乱」——**已知的脆弱耦合**，靠人工维持不变量 |
| C-8 | `players/cli_player.py` | `observation.*` | ✅ 走的是标准观察接口，**合规**（作为反例列出，说明「Player 层解耦」这一条是达标的） |
| C-9 | `tests/unit/test_engine.py:150/167` 等 | `engine._diplomacy_relation_system` | 测试直访私有（可接受但脆） |

---

### D. 重复逻辑

| # | 逻辑 | 副本 |
|---|---|---|
| D-1 | 每方 RNG 种子派生 | 2 份（见 B-1） |
| D-2 | 六角格距离 | 4 份（见 B-3） |
| D-3 | 领地半径 | 3 份（见 B-4） |
| D-4 | 命令类型/参数 schema | 6 份（见 B-9） |
| D-5 | 势力清单/颜色 | 3–4 份（见 B-5/B-6） |
| D-6 | 增援入城 | 2 份（见 B-8） |
| D-7 | hex 颜色解析 | Python 3 处（`map_renderer._hex_to_rgb`、`game_renderer.hex_to_rgb`、`hex_map_renderer._hex_to_rgb`）+ Web 2 处（`theme.hexToNumber`、`utils/colors.hexToNumber`）+ `GameMap.darken` |
| D-8 | 「势力城数统计」 | `engine._check_victory`（`engine.py:1334-1336`）、`api/game_manager.get_state`（`:296-297`）、`MapSystem.get_faction_city_counts`（死）、前端 `Panel.FactionList` 各自统计一遍 |

---

### E. 可疑写法

| # | 位置 | 问题 | 影响 |
|---|---|---|---|
| E-1 | `engine.execute_command`（`engine.py:434-465`） | `try/except Exception` 把**整个命令分发**包住，任何异常都变成「成功= False 的 `CommandResult`」 | 真实 bug（如 `KeyError`）被静默降级为「命令失败」，只写 `logger.exception` → 排查成本高 |
| E-2 | `engine._init_hex_map`（`engine.py:305-308`） | `except Exception` → 静默「降级模式」（`hex_map=None`） | 地图生成失败会把整局退回 legacy 路径（连带触发 B-7 的分叉），但只 `logger.warning` |
| E-3 | `players/llm/output_parser.py:311/324` | `except Exception: pass` ×2 | json_repair 失败被完全吞掉，无日志 |
| E-4 | `engine.py:854/876` | `getattr(self, 'season', 'spring')` | `season` 在 `__init__`（`engine.py:139`）恒已设置，`getattr` 是防御噪声，掩盖「以为自己可能没初始化」的错觉 |
| E-5 | `engine.py:738` | `_execute_rumor` 传 `target_faction=""`，注释写「由 GameEngine 查城市归属」，**但后文无任何回填**（`engine.py:736-742` 全文实读） | 注释撒谎：流言不校验目标城归属 |
| E-6 | `battle_resolver.process_aftermath`（`battle_resolver.py:545-548`） | 形参 `defender_city_owner` 接收后**函数体从未使用**（`:566-604` 实读） | 死参数；调用点 `:164` 还专门传 `""` |
| E-7 | `models.CityInfo`（`models.py:178`） | 声明 `province_id` 字段，但 `engine.get_observation` 构造 `CityInfo` 时（`engine.py:1410-1416`）**不设置** → 恒为 None | 类型/字段存在但语义空转 |
| E-8 | `models.General.loyalty_decay_rate`（`models.py:270`） | 字段自述「v4.0 起仅作展示，实际由 loyalty_baseline 回归驱动」 | 死字段（保留展示但无代码读） |
| E-9 | `renderer/ui_panel.py:37-45` | `UIPanel.__init__(self, engine, renderer)` 持有 `renderer` 引用并回读 `renderer.auto_advance`（`:387`） | 渲染器内部双向引用，违反 ADR-0001「Renderer 只读」精神（虽在 Engine 之外） |

---

## ② 🔴 架构可插拔性评估（本轮重点）

### 2.0 现状：引擎长什么样

`GameEngine`（`game/engine.py`，**1556 行**）是一个「上帝对象」：

- 持有全部状态：`cities` / `armies` / `generals` / `provinces` / `hex_map` / `turn_logs` / `_messages`。
- 在 `__init__` 里**硬编码 new 出 9 个子系统**（`engine.py:150-159`），又在 `init_game` 里 new 出 3 个（`kingdom_system`/`diplomacy_relation`/`influence_system`，`engine.py:245-250/302`）。
- `process_turn`（`:804-981`）是**写死的 8 步流水线**，注释编号 0/1/2/2.5/2.6/3/4/5/6/7/8；每一步直接调具体子系统的具体方法。
- 子系统**没有基类、没有统一接口、没有生命周期**。它们是普通 class，方法名由引擎逐处手写调用（`self._city_system.develop(...)`、`self._general_system.process_capture(...)`…）。

「玩法系统 = 一个 class + 引擎里若干处 `self._xxx_system.yyy(...)` 调用」——这就是当前的扩展模型。

### 2.1 一个玩法系统「插进来」要改几处（3 个真实例子）

#### 例 1：加入一个新命令类型（取文档已立项的「计谋 `scheme`」，见 `docs/design/v31-generals-audit.md` I-3）

必须改 **8 个文件、约 11 处**：

| 步 | 文件 | 改动 |
|---|---|---|
| 1 | `game/models.py`（命令段，`:298-383`） | 新增 `SchemeCommand(Command)` 类 |
| 2 | `game/engine.py:39-64` | import 新命令类 |
| 3 | `game/engine.py:435-452` | `execute_command` 的 `if/elif` 加一个分支（**注意：这是硬编码分支，不能只加数据**） |
| 4 | `game/engine.py` | 新增 `_execute_scheme()` 方法（约 20+ 行） |
| 5 | `players/llm/llm_player.py:44` | `COMMAND_CLASSES` 加一项 |
| 6 | `players/llm/llm_player.py:73` | `PARAM_MAPPING` 加一项 |
| 7 | `players/llm/output_parser.py:333` | `VALID_COMMAND_TYPES` 加一项 |
| 8 | `players/llm/output_parser.py:362` | `required_params` 加一项 |
| 9 | `players/llm/prompt_builder.py:161-197` | `build_commands_help` 文本加一段（否则 LLM 根本不知道有这条命令） |
| 10 | `api/game_manager.py:450-506` | `_deserialize_command` 加一个 `elif` |
| 11 | `web/src/constants/commands.ts:16/31/44/57` | **4 张表**各加一项（`COMMAND_LABELS`/`COMMAND_TYPE_LABELS`/`COMMAND_ICONS`/`COMMAND_TYPE_ICONS`） |
| 12 | （工程惯例）`tests/unit/` | 新增单测 |

**结论**：命令是「数据类」，但**分发是硬编码**。步 3、5、6、7、8、10、11 是 7 处**平行注册表**，任何一处漏改都造成「后端认、前端不认」或「LLM 不知道」的不一致。

#### 例 2：加入一个新胜利条件（如「占领洛阳并守住 N 回合」）

| 步 | 文件 | 改动 |
|---|---|---|
| 1 | `game/engine.py:1318-1372` | 改 `_check_victory`——**单函数混装**了「只剩一方」「到回合上限」「并列 tiebreak」三套逻辑，新增条件只能继续往里塞分支 |
| 2 | `game/game_mode.py` | 若作为新 `GameMode`，加枚举值 |
| 3 | `game/engine.py:_check_victory` & `process_turn` | 针对新模式的 `if` |
| 4 | `api/server.py:48-63` + `api/game_manager.py:173-176` | 新模式要在 env 校验、`_init_engine` 里各加分支 |
| 5 | `main.py:47-51` | 命令行 `choices` 加选项 |
| 6 | `web/src`（TopBar 显示模式等） | 前端展示 |

**结论**：胜利逻辑**没有策略接口**，`GameMode` 只是一个 2 值枚举 + 一处 `if`（`engine.py:1347`），不是可插拔的策略对象。加 1 个胜利条件牵动 5–6 个文件。

#### 例 3：加入一个「每回合结算」的新机制（如「天灾/蝗灾，每 N 回合触发一次」）

| 步 | 文件 | 改动 |
|---|---|---|
| 1 | `game/engine.py:process_turn` | 在写死的 8 步流水线里插一步（改核心循环） |
| 2 | `game/constants.py` | 加数值常量 |
| 3 | `game/models.py` | 若需新状态字段（如 `city.disaster_turns`） |
| 4 | `api/game_manager.py`（`get_state`） | 新状态要序列化给前端 |
| 5 | `web/src/types.ts` + 某面板 | 前端展示 |
| 6 | 事件上报 | EventBus 是死的 → 只能去 `game_manager._add_event(...)` 手写一条（`game_manager.py:783`），无法「订阅广播」 |

**结论**：新机制必须**改引擎主循环**。没有「系统注册表 + 生命周期钩子」可挂。

### 2.2 当前扩展点盘点

| 扩展点 | 能否「加而不改引擎」 | 实据 |
|---|---|---|
| **`Command` 体系** | ❌ 不能。命令类可加，但 `execute_command` 的 9 分支 `if/elif`（`engine.py:435-452`）是硬编码分发 | 见 2.1 例 1 |
| **`EventBus`** | ❌ **没被真正使用**。11 个事件类、约 370 行；全仓 `publish`×1（`engine.py:707` 仅 `DiplomacyMessageSentEvent`）、`subscribe`×0。`GameOverEvent`/`CityCapturedEvent`/`BattleEndedEvent` 等**定义了但从不发布**；没有任何订阅者（前端状态来自 `GameManager` 轮询，不是事件） | ripgrep 全仓：`\.publish(` 生产仅 1 处；`\.subscribe` 生产 0 处 |
| **`GameEngine` 硬编码分支** | — 现状量化：`execute_command` **9 个 `elif`**；`process_turn` **8 个固定步骤**（编号 0–8）；`_check_victory` 内嵌 3 套逻辑；`_apply_nature_strain` 内嵌 2 条「人设规则」的字符串判断（`engine.py:1134-1137`） | 见文件 |
| **`GameMode` 机制** | ❌ 不通用。`GameMode` 是 `STANDARD`/`INFINITE` 两值枚举（`game_mode.py:8-15`），只在 `_check_victory`（`:1347`）与 `game_manager._init_engine`（`:173-176`）各用一次；不是策略对象 | 见文件 |
| **`data/*.json`** | ❌ 只能定义**静态内容**（城市/将领/州/地图坐标），**不能定义机制**。机制数值全在 `constants.py`、逻辑全在 Python | `game/data_loader.py` 只读 `cities/generals/provinces/hex_map/china_provinces` |

### 2.3 数据与逻辑的边界（现状）

| 维度 | 现状 | 能不能靠数据定？ |
|---|---|---|
| 静态内容（城市/将领/地形坐标） | `data/*.json` ✅ | 能（已是） |
| 地形/城市数值表 | `constants.py`（`CITY_LEVELS`/`TERRAIN_*`）❌ 硬编码 Python dict | 能（本该数据化，尚未） |
| 人设档案（53 将） | `personality.py` Python dict ❌ | 能（本该数据化） |
| 国号/称王参数 | `kingdom_system.py` 硬编码 ❌ | 能 |
| 机制（战斗/忠诚/外交/流水线） | 全部 Python ❌ | **当前完全不能** |

即：**项目是「内容数据驱动 + 逻辑硬编码」**。要「用一份 JSON 定义一个新机制并让它跑起来」——今天做不到。

### 2.4 改造方案

#### 档 A：最小可行（**1–2 天**，低风险）

目标：把「加系统」从「改引擎」变成「注册」。做 4 件事：

1. **命令处理器注册表**。把 `execute_command` 的 `if/elif` 换成字典查表：
   ```python
   # game/commands/registry.py
   HANDLERS: dict[str, Callable[[GameEngine, Command], CommandResult]] = {}
   def register(cmd_type: str): ...        # 装饰器注册
   ```
   各 `_execute_*` 改为 `@register("develop")` 等注册；`execute_command` 变成 `HANDLERS[command.type](self, command)`。→ **引擎分发代码不再需要枚举命令类型**（这是原先最大的一处耦合）。⚠️ 但这**不等于**"只改 1 个文件"——准确口径见 §2.4bis。**顺带把 4 张平行表改为从注册表派生**（`COMMAND_CLASSES`/`VALID_COMMAND_TYPES`/`required_params`/`_deserialize_command` 由「命令元数据」单点生成），前端 `commands.ts` 通过 `/api/commands` 端点拉取，消灭另 4 处硬表。
2. **真正接线 `EventBus`**：在 `process_turn` 的关键点 `publish`（`TurnStartedEvent`/`TurnEndedEvent`/`CityCapturedEvent`/`BattleEndedEvent`）；让 `GameManager` 的 `_events` 与日志改为**订阅**事件；pygame/Web 的展示也走订阅。→ 这是给未来 mod 的**第一根钩子**。
3. **引入 `System` 协议 + `SystemRegistry`**：定义 `class System(Protocol): def on_turn_start(ctx): ...; def on_turn_end(ctx): ...; def on_event(evt): ...`，`process_turn` 改成「遍历注册过的系统按声明顺序调钩子」。先把 `influence_system`、`kingdom_system`、`nature_strain` 从引擎里搬进系统，验证这条缝能用。
4. **落 ADR**：`ADR-0006-command-handler-registry`、`ADR-0007-system-lifecycle`、`ADR-0008-eventbus-wired`。

代价/风险：改动核心循环，**必须保持确定性顺序**（系统注册顺序要固定且可序列化）；`event_bus` 接错会改变现有轮询语义 → 需回归 `tests/integration` + 一局确定性对照（同 seed 逐位一致）。收益：把「加命令」的**引擎侧**耦合从「必改」降为「不必改」；但端到端仍约 4 处，**不是**「降到 1 个文件」（准确口径见 §2.4bis）。

#### 档 B：理想架构（**1–2 周**，高风险）

在档 A 基础上，做到「像《钢铁雄心》一样发 DLC」：

1. **插件包格式**：`plugins/<name>/manifest.json`（name/version/depends/core_version）+ `plugin.py`，暴露 `register_commands(ctx)` / `register_systems(ctx)` / `register_victory(ctx)` / `register_events(ctx)` / `load_data(ctx)`。启动时 `PluginLoader` 扫描目录并加载。
2. **胜利条件策略化**：`VictoryCondition` 协议 + 注册表，`_check_victory` 变为「遍历已注册条件」。
3. **机制数据化**：定义 JSON schema（效果/事件卡/数值），把 `constants` 中「机制数值」下沉到 `data/`；系统从数据构造规则。
4. **系统生命周期 + 确定性相位**：系统声明 phase（`pre_turn`/`settle`/`post_turn`），注册表按固定序执行，保证「插件数量变化不影响既有系统的随机流」（需 per-system RNG 或相位隔离）。
5. **存档兼容**：`GameState` 加 `plugins`/`core_version`，插件卸载后旧存档可降级加载。

代价/风险：**最高风险在确定性与存档兼容**——本项目对「同 seed 逐位一致」有硬要求（`tests/balance/pacing_lib`）；插件任意插入随机调用会破坏它。且需要一个稳定的「核心数据契约」，现在还没有。**不建议现在做。**

### 2.4bis 更新：批 2 已实施（2026-10）——「加命令」的准确成本口径

档 A 第 1 条（命令处理器注册表）**已落地**（commit `166acf6`）：`execute_command`
去掉 9 分支 `if/elif`，改为查 `game/command_registry.py` 的注册表分发；替换前后
48 回合逐回合指纹、`exp13` 终局指纹均一致。

**但"加命令从 8 文件降到 1 文件"这个说法是错的（本报告前文已据此更正）。** 准确口径：

| 环节 | 注册表落地后是否仍要改 |
|---|---|
| `game/engine.py`（**分发代码**） | ❌ **不必改**（这是本次最大收益） |
| `game/models.py` 定义命令类 | ✅ 必改（数据模型，无法回避） |
| `game/command_registry.py` 注册一行 | ✅ 1 处 |
| 玩家侧（`cli_player` / `llm/output_parser` / `prompt_builder`） | ✅ 若要让 AI 会发这条命令 |
| 前端 `web/src/constants/commands.ts` | ✅ 若要让前端显示这条命令 |

**准确说法**：「引擎**分发代码**不再需要枚举命令类型（原先 9 分支 if/elif，
是最大的一处耦合），但新增一条**可用**命令仍需同步约 **4 处** —— 收益是
『**核心不用改**』，不是『只改 1 个文件』。」

之所以特别写清：本项目反复栽在「表述比事实乐观」上。若后人照着「只改 1 文件」
去做，会发现还要动 4 处，然后开始不信任这份报告——**报告的准确性比好看重要**。

> **未来路径（属档 B，本轮不做）**：若要让前端也「不改代码」，需让 `/api/commands`
> 返回命令元数据、前端按元数据渲染驱动；同时玩家侧的 3 处清单也需从注册表派生。
> 这属于档 B（插件包/DLC 格式）范围，已定为本轮不做。

### 2.5 现在改 vs 等更多系统写完再改？

**建议：现在就做「档 A 最小可行」，但不要上「档 B」。**理由：

- **改造成本随调用点数量增长**。今天「命令分发」是 4 处平行表、「每回合结算」是 1 个写死循环——尚可一次性收敛。**每多写一个玩法系统（往 `engine.py` 里再加 `_execute_*` 和 `process_turn` 步骤），改动面就多一分**，且新系统会复制当前的反模式（硬编码分支、直访私有），把「脏代码」基数做大。
- **档 A 是「买期权」，很便宜**（1–2 天、不动玩法数值、只重构分发与钩子），却把「加系统 = 改引擎」变成「加系统 = 注册」。**它不锁定任何未来设计**。
- **档 B 现在做是「猜架构」**。项目还没 3 个以上真实的新系统来暴露「插件到底需要哪些钩子」。过早抽象出错的 DLC 契约，比没有契约更贵。**等核心（命令注册表 + 事件总线 + 系统生命周期）稳定、并按该缝写 1–2 个真系统之后再泛化**（Fowler「Rule of Three」）。
- **一个直接的证据**：`ADR-0001` 已经把「事件驱动」写成 Accepted，但 `EventBus` 至今 0 订阅者——说明**「先写抽象、后接线」在这个项目里已经失败过一次**。所以下一步应当「接线已有的缝」，而不是「再画新缝」。

### 2.6 可插拔性评分：**3 / 10**

| 加分项（+） | 扣分项（−） |
|---|---|
| 命令是 Pydantic 数据类，天然可并行化（+） | **命令分发硬编码 9 分支 + 4 处平行注册表**（主因，−3） |
| 三层分离真成立（`game/` 内 0 pygame，ripgrep 复核）（+） | **`EventBus` 完全没接线**（11 类 1 publish 0 subscribe），本应是 mod 钩子的缝是死的（−2） |
| 各玩法已各自成文件/成 class，有「好骨架」（+） | `process_turn` 是写死的 8 步流水线；无 `System` 接口/生命周期（−2） |
| 静态内容已数据驱动（cities/generals/JSON）（+） | **机制 0% 数据驱动**（−1.5） |
| 确定性 RNG 已隔离为 `GameRandom`（+） | 胜利条件无策略接口；`GameMode` 2 值枚举（−0.5） |
| | 引擎上帝对象 1556 行，API/渲染直访私有状态（−1） |

合计：3/10。**「骨架在，缝没接」**——离 mod/DLC 式可插拔的距离，不是「缺框架」，而是「现有框架（EventBus / Command / System 分文件）没被当成扩展点用起来」。

---

## ③ 代码清理清单（可执行，**不执行**）

> 处置：**DELETE**（删）/ **ARCHIVE**（归档到 `docs/archive/` 或备份）/ **WIRE**（保留但接线）/ **KEEP**（保留）。
> 「测试覆盖」列：有=删前有回归、无=删前需人眼确认。测试覆盖用 ripgrep 统计（`tests/` 内命中）。

### 3.1 DELETE（明确死代码，建议直接删）

| 目标 | 位置 | 引用数 | 测试覆盖 | 影响面 |
|---|---|---|---|---|
| `renderer/map_renderer.py`（整文件 462 行） | 全文 | 0 import | 无 | 无（`MapRenderer` 无人调用） |
| `renderer/replay_player.py`（整文件 174 行） | 全文 | 0 import | 无 | 无（回放未实现） |
| `web/src/utils/tiles.ts`（整文件） | 全文 | 0 import | 无（web 无测试） | 无 |
| `web/src/utils/colors.ts`（整文件） | 全文 | 0 import | 无 | 无 |
| `web/src/utils/mapIcons.ts`（整文件） | 全文 | 0 import | 无 | 无 |
| `hex_grid.py` 的 `Direction`/`get_direction`/`direction_opposite`/`_DIRECTION_VECTORS`/`_OPPOSITE_DIRECTION` | `hex_grid.py:18/64/74/121/148` | 生产 0，仅 `test_hex_grid.py` | **有**（9 条测试） | 删符号会挂测试 → 需连带删测试；建议 **KEEP+标注** 更稳妥（见 3.3） |
| `_estimate_wall_hp` | `battle_resolver.py:217` | 0 调用 | 无 | 无 |
| `_generate_general_name` | `general_system.py:172` | 0 | 无 | 无 |
| `MovementEvent` | `army_movement.py:68` | 仅 1 测试 import | **有**（import 行） | 删需同删测试 import |
| `calculate_turns_to_arrive` | `army_movement.py:381` | 仅 2 测试 | **有** | 删需删测试 |
| `get_aggression_weight` | `personality.py:362` | 0（含测试） | 无 | 无 |
| `get_general_trait` | `personality.py:346` | 0 | 无 | 无 |
| `get_all_provinces`/`get_province_cities`/`get_city_province` | `map_system.py:252/260/274` | 0 | 无 | 无 |
| `get_city_count`/`are_adjacent`/`get_faction_city_counts` | `map_system.py:70/101/218` | 仅测试 | **有** | 删需删测试 |
| `season_names_zh` | `season.py:50` | 仅 1 测试 | **有** | 删需删测试 |
| `second_general_id` / `killed_generals` 字段 | `models.py:201/556` | 0 | 无 | 无（Pydantic 可选字段） |
| `KNOWN_COMMAND_CLASS_NAMES` | `web/src/constants/commands.ts:89` | 0 | 无（无 web 测试） | 无 |
| `computeChinaMask` | `GameMap.tsx:536` | 0 | 无 | 无（76 行） |
| `TurnResult` import | `main.py:26` | 0 使用 | — | 无 |
| `MORALE_COMBAT_BONUS_RATE` import | `battle_resolver.py:47` | 0 使用 | — | 无 |

### 3.2 WIRE（保留，但应接线——否则是「算了没用」）

| 目标 | 位置 | 当前 | 建议 |
|---|---|---|---|
| `EventBus` | `game/event_bus.py`（整模块 362 行）+ 11 事件类 | 1 publish / 0 subscribe | **接线**（见 ②-2.4 档 A-2）。不接线则应整体降级为「未使用模块」并删掉无人发布的事件类 |
| `InfluenceSystem.get_tile_modifiers` | `influence_system.py:87` | 每回合算影响力但无人读加成 | 接线到产出/防御，或删 `InfluenceSystem`（当前是纯开销） |
| `mark_as_read` | `diplomacy_system.py:148` | 生产不调用 → prompt 重复喂历史消息 | 引擎在生成观察后标记已读 |
| `set_long_term` | `memory_manager.py:76` | 生产不设置 → 「长期战略」段恒空 | 让 `LLMPlayer` 写入或删记忆分层 |
| `MORALE_LOSS_BESIEGED` | `constants.py:279` | 0 引用，`city_system.py:377` 硬编码 3 | 改读常量（与文策渊 D-4 一致） |
| `reject_alliance`/`is_allied`/`is_at_war`/`is_truce` | `diplomacy_relation.py` | 仅测试 | 接线到外交 AI，或删 |

### 3.3 KEEP 但加注（有测试保护 / 低价值不折腾）

- `hex_grid` 的 `Direction` 系列：有 9 条测试，属「Wesnoth 借鉴预留」——**保留 + 在文件头标「当前无生产调用，勿当接口」**，避免下个 agent 又去猜它是否在用。
- `GENERAL_PERSONALITIES`：docstring 已自述「兼容旧引用」，实际零引用——**删定义 + 改 docstring**，或标注废弃。
- 全部 A-3 死常量：与 `docs/pitfalls.md` 的登记表合并管理；按文策渊 D-4 分「接线 / 保留待实现 / 删定义」三档。

### 3.4 附带：`release/` 目录（本仓内 3.7 MB 旧产物）

- `release/llm-sanguo-v2.2.0/LLM三国志.app/Contents/project/` 内含 **整套 v2.2.0 的源码副本**（与现仓 `game/`/`players/`/`api/` **重名但更旧**）。
- 影响：任何全仓 ripgrep/静态扫描都会命中这份旧副本，**污染「引用计数」与「死代码判定」**（本次审计已手动 `!release/**` 排除）。
- 处置建议：**ARCHIVE**（移出仓库或 `.gitignore`），至少加 `.rgignore`/扫描排除，否则未来每次审计都要额外排除。

---

## 附：本次审计的核实动作

- 实读代码：`game/`（28 .py）、`players/`（含 `llm/`）、`api/`、`renderer/`、`web/src/`（16 .ts/.tsx）、`main.py`、`run_web.py`。
- ripgrep 复核（全部报数）：`EventBus`/`publish`/`subscribe`、`TurnResult`、`load_state_snapshot`、`get_cost_summary`、`set_long_term`、`mark_as_read`、`is_allied`/`is_at_war`/`is_truce`、`reject_alliance`、`get_city_count`/`are_adjacent`/`get_faction_city_counts`/`get_all_provinces`/`get_province_cities`/`get_city_province`、`season_names_zh`、`get_aggression_weight`/`get_general_trait`、`GENERAL_PERSONALITIES`、`_generate_general_name`、`_estimate_wall_hp`、`MovementEvent`、`calculate_turns_to_arrive`、`second_general_id`、`killed_generals`、`Direction`/`get_direction`/`direction_opposite`、`MapRenderer`、`ReplayPlayer`、`mapIcons`/`utils/colors`/`utils/tiles`、`computeChinaMask`、`KNOWN_COMMAND_CLASS_NAMES`、`FACTION_GLOW`/`SHADOWS`/`CITY_STYLES`/`ARMY_STYLES`/`hexToRgba`/`UI_COLORS`/`TERRAIN_COLORS`、`MORALE_COMBAT_BONUS_RATE`、`MORALE_LOSS_BESIEGED` 及 A-3 全部常量、`engine._*`/`engine.cities` 等隐性耦合。
- 测试基线：`/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m pytest --collect-only -q` → **604 tests collected**（与团队口径一致）；`./venv/bin/python -m pytest --collect-only -q` → 582（venv 缺 fastapi，少收 API 相关用例）。
- 排除项：`release/**`（v2.2.0 旧产物）、`venv/**`、`node_modules/**` 全程排除，避免旧副本污染计数。
- 未核实：`hex_map_renderer.py`/`ui_panel.py`/`game_renderer.py` 的**逐行**死代码（本轮只审了 pygame 层入口是否被 `main.py` 引用，未逐函数核）；`web/` 无测试框架（`package.json` 只有 `dev`/`build`/`preview`，无 test 脚本），故前端改动**无自动化回归**。
