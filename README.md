# 乱斗三国 - 多模型策略对战平台

> 184年黄巾之乱，12方诸侯逐鹿中原——大语言模型们，谁才是真正的"天命之子"

> 最后更新：2026-10-01 | 版本：v2.3

---

## 项目简介

这是一个LLM驱动的多智能体策略对战游戏。12个势力（汉室/张角/董卓/袁绍/曹操/刘备/孙坚/刘表/刘焉/公孙瓒/马腾/袁术）在六角格真实中国地图上策略对战。

### 核心特性
- 🗺️ **六角格真实地图**：120×90 格，覆盖中国全境，带省界矢量底图
- ⚔️ **12方势力**：184年黄巾之乱全剧本，每方有独特性格参数
- 🏙️ **22座城池**：经纬度精确投影，地形/资源/控制区系统
- 🔄 **192回合制**：每回合=1季度，184年→232年完整三国形成期
- 🤝 **外交博弈**：信使系统 + 口头盟约 + 流言策反
- 👑 **建国机制**：控3城称王、5城称帝，历史国号 + Buff/Debuff
- 🧠 **性格驱动AI**：aggression/diplomacy/expand 权重影响决策
- 🎥 **相机系统**：WASD平移、滚轮缩放、势力边界渲染
- 📊 **完整回放**：可复现的确定性随机 + 结构化日志

### 技术栈
- **后端**：Python 3.12+
- **游戏引擎**：纯 Python（无 UI 依赖），Pydantic 2.0+ 数据校验
- **GUI（降级 / 调试通道）**：Pygame 2.6+
- **Web 前端（一等公民渲染通道）**：React 18 + PixiJS 8 + TypeScript 5 + Vite 5
- **Web 后端桥接**：FastAPI + WebSocket（桥接单局 GameManager）
- **E2E 测试**：Playwright
- **测试**：pytest（504 tests）
- **LLM**：默认 DeepSeek（api.deepseek.com/v1），可经 OpenRouter / OpenAI 封装切换；密钥用环境变量 `LLM_API_KEY`（兼容旧名 `OPENROUTER_API_KEY`）
- **地图数据**：阿里云 DataV GeoJSON + 六角格投影

---

## 快速开始

```bash
pip install -r requirements.txt

# GUI 模式（六角格地图 + 12方自动对战）
python3 main.py --mode gui --seed 42

# 纯CLI对战
python3 main.py --mode ai-vs-ai --seed 42 --max-turns 30

# 无限模式
python3 main.py --mode infinite --seed 42

# 扮演指定势力
python3 main.py --mode gui --faction caocao

# GPU操作：WASD平移 | 滚轮缩放 | 空格推进 | A自动 | ESC退出
```

---

## 项目结构

```
llm-sanguo/
├── game/                    # 游戏引擎（纯逻辑，无pygame依赖）
│   ├── engine.py            # GameEngine 主类
│   ├── models.py            # Pydantic 数据模型
│   ├── constants.py         # 全局常量配置
│   ├── hex_grid.py          # 六角格坐标系统 (HexCoord)
│   ├── hex_map.py           # 六角格地图 (A* 寻路)
│   ├── tile.py              # 地块数据模型 (Tile/TerrainType)
│   ├── season.py            # 季节枚举
│   ├── game_mode.py         # 游戏模式枚举
│   ├── personality.py       # 性格/战略倾向系统
│   ├── kingdom_system.py    # 建国称王系统
│   ├── influence_system.py  # 影响力扩散系统
│   ├── random.py            # 确定性随机数
│   ├── event_bus.py         # 事件总线
│   ├── data_loader.py       # 数据加载器
│   ├── systems/             # 子系统
│   │   ├── resource_system.py
│   │   ├── city_system.py
│   │   ├── general_system.py
│   │   ├── diplomacy_system.py
│   │   └── map_system.py
│   └── battle/              # 战斗系统
│       ├── battle_scheduler.py
│       ├── battle_resolver.py
│       └── army_movement.py
│
├── players/                 # 玩家层
│   ├── base_player.py
│   ├── cli_player.py        # 性格驱动CLI AI
│   └── llm/                 # LLM玩家
│       ├── llm_player.py
│       ├── prompt_builder.py
│       └── ...
│
├── renderer/                # Pygame 渲染层
│   ├── game_renderer.py     # 主窗口/循环
│   ├── hex_map_renderer.py  # 六角格地图 + 省界 + 势力边界
│   ├── map_renderer.py      # 旧版地图（fallback）
│   ├── camera.py            # 2D相机（平移/缩放）
│   ├── ui_panel.py          # 侧边栏面板
│   └── replay_player.py
│
├── data/                    # 游戏数据
│   ├── hex_map.json         # 120×90 六角格地图
│   ├── china_provinces.json # 中国34省GeoJSON边界
│   ├── cities.json          # 22城配置
│   ├── generals.json        # 47名将
│   └── terrain_colors.json  # 地形颜色
│
├── tests/                   # 399 tests
└── main.py                  # 入口
```

---

## 184年剧本：12方诸侯

| 势力 | 君主 | 城池 | 性格 |
|------|------|------|------|
| 汉室 | 汉灵帝/何进 | 洛阳、长安 | 谨慎 |
| 张角 | 张角 | 巨鹿、南阳 | 激进 |
| 董卓 | 董卓 | 天水 | 激进 |
| 袁绍 | 袁绍 | 邺城 | 野心 |
| 曹操 | 曹操 | 陈留、许昌 | 野心 |
| 刘备 | 刘备 | 剑阁、白帝 | 外交 |
| 孙坚 | 孙坚 | 长沙、柴桑 | 激进 |
| 刘表 | 刘表 | 襄阳、江陵 | 谨慎 |
| 刘焉 | 刘焉 | 成都、汉中 | 谨慎 |
| 公孙瓒 | 公孙瓒 | 蓟 | 激进 |
| 马腾 | 马腾 | 武威 | 激进 |
| 袁术 | 袁术 | 寿春、合肥 | 野心 |

---

## 版本

**v2.3** — 收口质量门修复：API key 变量改名 `LLM_API_KEY`（兼容 `OPENROUTER_API_KEY`）、文档一致性（12方/192回合/22城/胜利条件）、renderer 字体缺陷修复（FONT_CJK_XS）、依赖补 numpy

**v2.2** — 马腾+武威、袁术+合肥、GameState字段补齐、建国Buff接入、信息迷雾优化

**v2.1** — Web 前端（FastAPI + React + PixiJS）、玻璃拟态 UI、Playwright 测试

**v2.0** — 六角格地图 + 12方势力 + 性格系统 + 建国机制

---

> MIT License | 仅供研究和学习
