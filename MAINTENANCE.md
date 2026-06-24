# LLM三国志 v2.2 — 运维与开发指南

> 最后更新：2026-06-24
> 面向后续开发者/维护者
> v2.2更新：马腾+武威、袁术+合肥、GameState字段补齐、10处邻居双向修复、建国Buff接入、信息迷雾5层规则

---

## 快速启动

```bash
pip install -r requirements.txt
python3 main.py --mode gui --seed 42        # GUI六角格地图
python3 main.py --mode ai-vs-ai --max-turns 30  # CLI对战
python3 main.py --mode gui --llm            # 12方全LLM对战
python3 -m pytest tests/ -q                 # 399 tests
```

---

## 架构速览

| 层 | 职责 | 关键文件 |
|----|------|---------|
| **Engine** | 纯游戏逻辑，禁止pygame | `game/engine.py` (主循环), `game/models.py` (数据) |
| **Systems** | 子系统 | `game/systems/` (资源/城市/将领/外交), `game/battle/` (战斗) |
| **Hex Map** | 六角格坐标+地形 | `game/hex_grid.py`, `game/hex_map.py`, `game/tile.py` |
| **Players** | AI决策 | `players/cli_player.py` (性格驱动), `players/llm/` (LLM) |
| **Renderer** | Pygame GUI | `renderer/game_renderer.py` (主), `renderer/hex_map_renderer.py` |
| **Data** | JSON配置 | `data/cities.json` (22城), `data/generals.json` (47将), `data/hex_map.json` |

---

## 势力体系 (12方)

内部key: `han, zhangjiao, dongzhuo, yuanshao, caocao, liubei, sunjian, liubiao, liuyan, gongsunzan, mateng, yuanshu`

显示名和颜色定义在 `game/constants.py` 的 `FACTIONS` 和 `FACTION_COLORS` 字典中。
**不要在其他文件中硬编码势力名或颜色**，统一从 `constants` 导入。

---

## 常见维护操作

### 添加新势力
1. `game/constants.py`: 在 FACTIONS、FACTION_COLORS 中添加
2. `game/models.py`: Faction 枚举添加成员
3. `game/personality.py`: FACTION_PERSONALITY 添加性格
4. `data/cities.json`: 分配城市，设置 faction 字段
5. `data/generals.json`: 添加将领并设置 faction
6. `data/hex_map.json`: 确保城市在 city_positions 中
7. `game/kingdom_system.py`: KINGDOM_NAMES 添加国号

### 添加新城市
1. `data/hex_map.json`: city_positions 添加 {q, r}
2. `data/cities.json`: 添加城市条目
3. `game/constants.py`: TOTAL_CITIES 更新

### 修改回合数
1. `game/constants.py`: MAX_TURNS
2. `game/game_mode.py`: 更新注释
3. `main.py`: --max-turns 默认值（必须同步）

---

## 已知技术债

| 项目 | 位置 | 说明 |
|------|------|------|
| 地图渲染旧版 | `renderer/map_renderer.py` | 旧像素坐标渲染，无中文字体，可考虑移除 |
| 回放系统 | `renderer/replay_player.py` | 未完成，engine从未被填充 |
| 河流地形数据 | `data/hex_map.json` | 水系过宽不够真实，需真实GIS数据替换 (B-04) |
| 常数分散 | 多个文件 | 部分数值硬编码未收敛到 constants.py |
| OVERTIME_EXTRA_SOLDIERS | `constants.py` | 已导入但从未使用 |
| 死代码 | `ui_panel.py` | scroll_offset, _cached_logs 未使用 |
| LLM消息记忆 | `players/llm/memory_manager.py` | 无法跨回合记住外交消息 |
| API key | `main.py` | 环境变量名 OPENROUTER_API_KEY 但实际用DeepSeek |

---

## 测试规范

- 399 tests in `tests/`
- 新增功能必须先写测试（TDD）
- `python3 -m pytest tests/ -q` 必须全部通过
- 测试中避免使用过时的 faction key "wei"/"shu"/"wu"

---

## 部署注意事项

- Python 3.12+
- macOS: pingfang SC 字体默认可用
- Linux: 需安装 Noto Sans CJK 或文泉驿
- Windows: 需安装 SimSun 或微软雅黑
- pygame 2.5+ 需要 SDL 2.0
