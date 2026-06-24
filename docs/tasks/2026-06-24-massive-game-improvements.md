# 2026-06-24 乱斗三国 三大系统全面升级

> 本次升级涉及 4 个提交、~30 个文件修改，覆盖数据层、逻辑层、渲染层、Web 交互层。

---

## 提交记录

| 提交 | 内容 | 文件数 |
|------|------|--------|
| `89271ea` | 游戏更名：LLM三国志 → 乱斗三国 + 图标接入 | 20 |
| `e7c2e45` | 州郡体系+武将修复+地图渲染+外交系统核心 | 21 |
| `6f13333` | Web UI 三大面板（外交/数据/事件） | 6 |
| `5d9216f` | Pygame 面板同步 | 1 |
| `c6a1280` | PixiJS 地图同步（province边界+势力填充+水域） | 3 |

---

## 一、里程碑 1：东汉十三州数据体系

### 新建 `data/provinces.json`
十三州：司隶、豫州、冀州、兖州、徐州、青州、荆州、扬州、益州、凉州、并州、幽州、交州。

### `data/cities.json` 重构
- **新增 `province_id`**：每城归属一州
- **重新计算 neighbors**：基于 hex_distance ≤15 自动生成 + 同州保护（≤20）+ 孤立保护
- 删除了地理荒谬的连接：武威-长安(40格)、天水-长安(14格)、长沙-合肥(17格) 等

### 代码层
- `game/models.py`：新增 `Province` 模型，`City`/`Tile` 添加 `province_id`
- `game/data_loader.py`：加载 `provinces.json`
- `game/systems/map_system.py`：添加 province 查询接口
- `game/engine.py`：`init_game()` 自动填充 province 映射 + city.generals

---

## 二、里程碑 2：城池武将数据修复 + 属性生效

### `data/generals.json` 修复
- **移除儿童武将**：马超（8岁）、孙策（9岁）
- **补充名将**：
  - 曹操：典韦(94勇武)、许褚(96勇武)、郭嘉(96智力)
  - 董卓：徐荣(82统帅)、牛辅(68统帅)
  - 袁绍：沮授(92政治)、审配(85政治)
  - 马腾：韩遂(82勇武)
- **武将总数**：47 → 53 人
- **修复探索池重复**：移除黄盖/马超/严颜，避免再次"发现"

### 武将属性真正生效
| 属性 | 影响 | 文件 |
|------|------|------|
| **政治** | 城市产出加成 `1 + sum(politics) * 0.005` | `game/systems/resource_system.py` |
| **勇武** | 暴击率 `min(0.5, avg_bravery * 0.005)`，暴击伤害 1.5x | `game/battle/battle_resolver.py` |
| **统帅** | 城防驻军使用驻守将军统帅均值，非固定 50 | `game/battle/battle_scheduler.py` |

### city.generals 填充
`engine.init_game()` 中自动将 general 加入其 `location` 对应 city 的 `generals` 列表。

---

## 三、里程碑 3：地图渲染改进

### Pygame 端（`renderer/hex_map_renderer.py`）
- **默认 zoom**：0.3 → 0.6
- **边框**：1px → 2px，颜色加深到 `#3a3a3a`
- **Terrain 颜色**：提升区分度（plain 更绿、desert 更黄、forest 深绿、river 蓝）
- **势力领土填充**：faction 颜色 20% 透明度叠加
- **Province 边界**：同 province hex 外轮廓（逐 tile 邻居检测 + 共线边合并）
- **水域**：空白 hex（tile is None）渲染为 `#1a2a4a`
- **势力边界线宽**：动态调整 `max(2, int(4 * camera_zoom))`

### Web 端（`web/src/components/GameMap.tsx`）
- **默认 zoom**：0.3 → 0.6
- **势力填充 alpha**：0.12 → 0.20
- **边框**：`0x3a3a3a`, width 2
- **Province 边界**：PixiJS Graphics 绘制 hex 外轮廓（淡金色 `#b4aa8c`）
- **水域**：遍历整个 hex_map bounding box，空白格渲染 `#1a2a4a`

### 相机 Bug 修复
`renderer/camera.py`：mousemotion 只在 `pressed[1]`（中键）时返回 `True`，避免吞掉所有鼠标事件。

---

## 四、里程碑 4：外交系统核心

### 新建 `game/systems/diplomacy_relation.py`
- `DiplomacyRelationSystem`：维护所有势力对的外交关系
- 状态：WAR / NEUTRAL / ALLIANCE / TRUCE
- 信任度：0-100
- 同盟/停战到期自动处理

### `game/models.py`
- 新增 `DiplomaticStatus` 枚举
- 新增 `FactionRelation` 模型
- `GameObservation` 添加 `faction_relations` 字段

### `game/engine.py` 集成
- 攻击命令检查同盟/停战状态
- 城市占领自动更新外交状态（变为 WAR，信任度 -20）
- 发送 message 自动更新信任度 + 发布 EventBus 事件
- 每回合检查同盟/停战是否到期

### `game/constants.py`
新增外交常量：信任度变化值、同盟/停战持续回合数、同盟战斗力加成 10%。

### 消息推送
`main.py` 和 `renderer/game_renderer.py` 的主循环中，执行 message 命令后调用目标势力的 `player.receive_message()`。

---

## 五、里程碑 5：Web UI 面板

### 后端状态暴露（`api/game_manager.py`）
`get_state()` 新增：
- `faction_relations`：所有势力外交关系
- `messages`：外交消息列表
- `turn_logs`：最近 10 回合日志

### 类型定义（`web/src/types.ts`）
新增 `FactionRelation`、`DiplomacyMessage`、`TurnLog` 接口。

### 新建 `DiplomacyPanel.tsx`
- **关系 Tab**：势力关系列表 + 关系矩阵色块图
- **消息 Tab**：收信/发信消息列表
- **发送 Tab**：选择目标势力 + 输入消息 + 发送（通过 `window.__gameWS`）

### Panel.tsx 扩展
- **DataPanel**：武将排行榜（统/政/武/智 Top 5）、城池统计
- **EventsPanel**：回合事件记录（战斗数/行军数/城陷数）
- Tab 从 4 个扩展到 7 个

### App.tsx / useGame.ts
- 键盘快捷键 1-7 对应 7 个面板
- WebSocket 连接成功后暴露到 `window.__gameWS`

---

## 六、里程碑 6：Pygame UI 同步

`renderer/game_renderer.py`：
- Tab 从 4 个扩展到 7 个（1-7 快捷键 + TAB 循环）
- `_draw_diplomacy_panel`：势力关系矩阵 + 最新消息
- `_draw_data_panel`：武将排行榜 + 城池统计
- `_draw_events_panel`：回合事件日志
- 面板点击处理同步扩展

---

## 验证结果

```bash
# Python 编译全部通过
python3 -m py_compile game/constants.py  # OK
python3 -m py_compile game/engine.py     # OK
python3 -m py_compile game/systems/diplomacy_relation.py  # OK
python3 -m py_compile renderer/hex_map_renderer.py        # OK
python3 -m py_compile renderer/game_renderer.py           # OK

# Web 前端构建通过
cd web && npm run build  # ✓ built in 1.93s

# 运行时验证
python3 -c "
from game.engine import GameEngine
from game.data_loader import load_game_data
engine = GameEngine(seed=42)
engine.init_game(load_game_data())
print('州:', len(engine.provinces))
print('关系:', len(engine._diplomacy_relation_system.get_all_relations()))
print('洛阳 gold:', engine._resource_system.calculate_resources(
    engine.cities['luoyang'], generals=engine.generals)['gold_change'])
"
# → 州: 13, 关系: 66, 洛阳 gold: 1686（政治加成生效）
```

---

## 剩余 TODO（低优先级）

1. **Web 地图进一步优化**：
   - PixiJS 中 province 颜色填充（当前只有边界线）
   - 城市/军队标记与 province 颜色不冲突

2. **外交命令扩展**：
   - `ProposeAllianceCommand`、`DeclareWarCommand` 等正式命令
   - CLI/LLM 玩家对 receive_message 的响应逻辑

3. **测试覆盖**：
   - 外交关系状态机单元测试
   - 武将属性影响战斗的集成测试
   - 州郡数据完整性校验脚本
