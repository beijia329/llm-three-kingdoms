# DeepSeek 执行提示词

> 用途：投入新会话，让 deepseek-v4-pro 执行后端修复任务
> 协作方：Kimi（前端），通过 docs/handoff/agent-handoff-log.md 同步

---

## 项目位置

`/Users/dongsheng/Documents/llm-sanguo-project`

## 你的角色

你负责**后端修复**，专注修复交接日志中列出的 B-01 ~ B-09。
前端/视觉工作由 Kimi 负责，你不碰前端代码。

## 必读文件（按顺序）

1. `AGENTS.md` — 项目宪法
2. `MAINTENANCE.md` — 架构速览、已知技术债
3. `docs/handoff/agent-handoff-log.md` — 交接日志（最重要的上下文）
4. `docs/pitfalls.md` — 常见坑与避坑指南

## 当前分支说明

| 分支 | 内容 | 你操作吗？ |
|------|------|-----------|
| `main` | 完整游戏引擎 + Pygame GUI | ✅ 你的工作基座 |
| `feat/web-frontend` | main + Web 前端（Kimi 的领地） | ❌ 不要碰 |

你的修复在 `main` 分支上做。如果修复涉及 feat/web-frontend 也改了的文件，在两个分支都修。

## 后端 Bug 清单（按优先级）

### B-01 [高] 马腾 0 城
- **现状**：`data/cities.json` 中没有任何城市的 `faction` 是 `mateng`
- **后果**：3 名马腾将领（马腾/马超/庞德）location=changan 但 changan 属 han，开局马腾势力无城可用
- **修复**：给马腾分配至少 1 座西北城池（武威/天水，或新增姑臧），设置 faction=mateng
- **注意**：同时更新将领的 location

### B-02 [高] 势力城数不平衡
- **现状**：汉室/张角/董卓/曹操/刘备/孙坚/刘表/刘焉 各 2 城，袁绍/公孙瓒/袁术 各 1 城，马腾 0 城
- **修复**：调整为各势力至少 2 城（或更符合 184 年历史分布的配置）
- **注意**：更新 generals.json 中将领的 location，更新 hex_map.json 中的 city_positions

### B-03 [高] GameState 缺字段
- **现状**：`game/models.py:GameState` 没有 `max_turns` 和 `year` 字段（当前是 engine 实例属性而非模型字段）
- **修复**：在 GameState 中加入 `max_turns: int` 和 `year: int`，确保序列化/反序列化时包含

### B-04 [中] 河流地形太宽太假
- **现状**：`data/hex_map.json` 中河流数据不真实
- **修复**：替换或重新生成真实水系数据

### B-05 [中] 城市 neighbor 不完整
- **现状**：武威已修复，但其他城市可能也有单向/缺失连接
- **修复**：遍历 `data/cities.json`，确保所有 `neighbors` 双向连接、无孤立城市

### B-06 [中] 军队士气/粮草逻辑待验证
- **位置**：`game/battle/army_movement.py`
- **修复**：验证断粮、溃散是否按设计生效，补测试

### B-07 [中] 建国系统 Buff 未生效
- **位置**：`game/kingdom_system.py`
- **现状**：`get_production_buff()` 和 `get_morale_buff()` 已实现但未接入 `game/systems/resource_system.py` 和 `game/battle/battle_resolver.py`
- **修复**：在资源产出和战斗结算中调用 kingdom buff

### B-08 [低] 信息迷雾粗糙
- **位置**：`game/engine.py` 中 `visible_armies` 逻辑
- **修复**：细化可见规则（如只有相邻城市/己方军队附近可见）

### B-09 [低] 游戏结束年份显示
- **位置**：`game/engine.py`
- **现状**：`year` 初始值已临时改为 184
- **修复**：确认长期正确性

## 已知技术债（有余力时处理）

详见 `MAINTENANCE.md`「已知技术债」章节，重点关注：
- `renderer/replay_player.py` 回放系统未完成
- `OXERTIME_EXTRA_SOLDIERS` 已导入未使用
- `players/llm/memory_manager.py` 无法跨回合记住外交消息
- 部分数值硬编码未收敛到 `game/constants.py`

## 协作规范

1. 每次完成一个 bug 修复就 `git commit`，提交信息格式：`fix: B-0X 简短描述`
2. 如果修复过程中发现 Kimi 的前端依赖了某个后端接口，在交接日志中追加说明
3. 更新 `docs/handoff/agent-handoff-log.md` 中的「发现的后端问题」表格（状态改为已修复）
4. 如果发现新的后端问题，追加到表格末尾

## 工作原则

- **别闭门造车**：多读现有代码理解设计意图，不要按自己想象重写
- **小步提交**：每个 bug 一个 commit，方便 Kimi 同步
- **TDD 优先**：修 bug 前先写回归测试，确保修复可验证
- **先读后写**：改代码前先读相关文件完整内容，理解上下文

## 验收标准

```bash
python3 -m pytest tests/ -q       # 全部通过
python3 main.py --mode ai-vs-ai --seed 42 --max-turns 30   # 能跑完整局
bash verify.sh                     # 全量验证通过
```

## 绝对禁止

- 不要修改 `web/` 目录下的任何文件（Kimi 的领地）
- 不要修改 `api/server.py` 和 `api/game_manager.py`
- 不要修改 `renderer/hex_map_renderer.py`（Kimi 负责）
- 不要动 Pygame GUI 渲染逻辑
- 不要重构计划外的代码
- 不要一次改太多文件
