# 乱斗三国 · LLM 大乱斗

[![CI](https://github.com/beijia329/llm-three-kingdoms/actions/workflows/ci.yml/badge.svg)](https://github.com/beijia329/llm-three-kingdoms/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)

> 184 年黄巾之乱，十二路诸侯逐鹿中原——让大语言模型各领一方，谁才是真正的「天命之子」？

一个 **LLM 驱动的多智能体策略对战平台**。把大模型评测从传统的「PVE 刷分」搬进「PVP 竞技」：让不同的大模型扮演三国诸侯，在同一套规则下真刀真枪打一局，看谁更会**推理、规划、合纵连横**。

> 灵感来自腾讯云开发者社区《赛博斗蛐蛐：9大模型决战三国志，天命在谁？》

---

## 🎯 这个项目在做什么

大多数 LLM 评测给出的是一个分数。这个项目想给出的是**一局棋**。

每个势力由一个大模型驱动。它每回合必须先写出**决策理由**，再下达命令；这些理由、外交密信、背盟与结盟的瞬间，全部在围观台上实时可见。你能看到曹操权衡「先取弱城滚雪球还是先稳后方」、刘备以汉室宗亲身份四处结好、黄巾以宗教号召力爆兵——**大模型以「棋手」而非「答题者」的形态出现**。

因此本项目有两个同等重要的目标：

1. **公平**：同一套规则、同一份地图、同一个随机种子，可复现地比出高下
2. **好看**：观众能看懂每一步决策背后的判断，而不只是看结果

---

## ✨ 核心特性

| | |
|---|---|
| 🧠 **LLM 即玩家** | 每方一个 LLM，先出「决策理由」再下命令，主观智能全程可见 |
| 🎭 **角色不是枷锁** | 人设提供**倾向与代价**，而非行动脚本；模型可自由违背本性求胜（[见下文](#-设计立场llm-与角色的关系)） |
| ☯️ **五行相克** | 火(勇武)/土(统帅)/金(智力)/水(政治)/木(忠诚)，相克环 火→金→木→土→水→火，克制 +15% |
| 👤 **53 名武将人设** | 每人有称号、性格、特质与五维；忠诚度会随国势浮动，被俘可能倒戈 |
| ⚔️ **机制闭环** | 攻城→俘将→降将→转投；失城→人心浮动→更容易被策反 |
| 🤝 **外交博弈** | 信使系统、正式盟约、流言策反、背盟欺诈 |
| 🗺️ **真实中国地图** | 六角格 + 省界，古地图美学（羊皮纸 + 墨线 + 半透明势力色域），含黄河/长江/珠江 |
| 🏯 **领地系统** | 以城为源多源扩张，占城即夺地，边界随占领实时重划 |
| 👑 **建国机制** | 控 3 城称王、5 城称帝 |
| 🎥 **Web 围观台** | React + PixiJS，实时看 LLM 勾心斗角（决策理由 / 外交 / 事件流） |
| 🔁 **确定性** | 同 seed 可复现；并发决策也不破坏结果一致性（有测试逐回合证明） |
| 🧩 **可插拔子系统** | 三个扩展点（回合相位钩子 / 命令注册表 / 事件总线），加玩法不改引擎——[写一个 Mod](./docs/design/modding-guide.md) |

---

## 🚀 快速开始

### 环境

- Python 3.12+
- Node.js 18+（仅 Web 前端需要）
- 一个 LLM API key（默认 DeepSeek，兼容任意 OpenAI 格式端点）

### 安装

```bash
git clone git@github.com:beijia329/llm-three-kingdoms.git
cd llm-three-kingdoms
pip install -r requirements.txt
```

### 配置 LLM key

```bash
export LLM_API_KEY="sk-..."        # 推荐
export DEEPSEEK_API_KEY="sk-..."   # 兼容旧名
```

> ⚠️ **不要**把占位符（如 `sk-你的key`）留在 `.env` 里。
> 程序会识别占位符并明确报错——这是 v4.0 的刻意设计，
> 因为静默回退成启发式 AI 会让「决策理由」面板恒空且极难排查。

### 跑一局

```bash
# CLI 纯 AI 对战（启发式 AI，零成本，秒级完成）
python main.py --mode ai-vs-ai --max-turns 48

# 3 方 LLM 对战（DeepSeek 实跑，48 回合约 $0.30）
python tests/llm_3p_run.py --turns 48 --factions caocao,liubei,sunjian
```

**建议回合数**：默认 `48` 回合（= 184–195 年，每回合 1 季度，4 回合 1 年）。
实测 192 回合中第 49 回合起**零战斗发生**，后 144 回合完全是空转且成本翻 4 倍。

### 启动 Web 围观台

```bash
cd web && npm install && npm run build && cd ..

python -m uvicorn api.server:app --host 127.0.0.1 --port 8000
# 打开 http://127.0.0.1:8000
```

在顶部工具栏选择 **LLM 围观** 模式 + 参战势力（建议 3 方）→ 点「重开一局」。
切到「决策」tab 即可看每回合的策略理由。

启动参数（也可由 `run_web.py` 传入）：

```bash
python run_web.py --seed 42 --max-turns 48    # 现在真的生效（v4.0 修复）
```

### LLM 模型说明

- 默认 `deepseek-flash`（推理模型，隐藏思维链计入 `max_tokens`，客户端已按需提升上限）
- 可用 id：`deepseek-flash`、`deepseek-v4-pro`
- 换其它 OpenAI 兼容端点：`LLMClient(provider=..., base_url=...)`

---

## 🎭 设计立场：LLM 与角色的关系

这是本项目的核心设计选择（v4.0 明确收口）：

> **LLM 需要读取角色设定后执行吗？这样会不会限制它的智能？**

**会。** 如果把人设当作必须遵守的行动脚本，模型就会为了「像曹操」而放弃好棋，甚至为圆人设而编造史实——这对一个「比谁更会博弈」的平台是致命的。

**但完全不给角色设定同样不行**，那观众看到的只是一个通用优化器，决策理由千篇一律。

所以本项目走第三条路：

| | 做法 |
|---|---|
| **人设定位** | 提供**视角与偏好**（你是谁的视角、你倾斜于什么），不是行动脚本 |
| **自由边界** | 提示词明确告知：可以为了取胜违背本性，**不会因此判负** |
| **代价来源** | 不来自提示词的警告，而来自**世界机制**：违背本性会有轻微、可逆的人心代价 |
| **代价强度** | 刻意做得很轻（一次只掉 1 点民心），不足以让好棋变坏棋 |

结果是「像不像自己」成为一个**真实的决策维度**而非枷锁：模型可以选择演，也可以选择务实，两种选择都会被观众看见并理解。

配套机制：

- **性格驱动倾向**：君主的性格会影响势力的进攻/外交权重
- **人设的机制后果**：谨慎型君主主动开战、激进型君主整回合避战 → 本势力民心 -1
- **人物在局内可见**：将领表带「称号 + 将道（五行）」，模型能据此做「派谁去打谁」的战术判断

---

## ⚔️ 游戏机制要点

### 五行与相克

| 五行 | 对应属性 | 定位 |
|---|---|---|
| 火 | 勇武 | 猛将：正面冲杀、破城 |
| 土 | 统帅 | 统帅：阵战、守御 |
| 金 | 智力 | 谋士：攻城器械、计谋 |
| 水 | 政治 | 能臣：经营、外交 |
| 木 | 忠诚 | 忠臣：死守、抚民 |

相克环 **火 → 金 → 木 → 土 → 水 → 火**：克制方伤害 +15%，被克方 -15%。

将领五行取其加权最高的一项（忠诚加权 0.8，避免因忠诚普遍偏高导致全员判为「木」）。

### 攻城与忠诚

- 城墙完好时守方有防御加成，**城墙一破加成即消失**，转入势均力敌的巷战
- 兵力达守军 **1.25 倍**以上时攻城胜率极高；低于 **0.75 倍**基本必败
- 忠诚 ≥90 的将领所部 +10% 战力；跌破 30 则 -20%（随时哗变）
- 将领被俘后按忠诚分档决定是否投降（0% / 5% / 25% / 50% / 75%）
- 丢失城池会让原主其余将领忠诚度下降——国势受挫，人心浮动

---

## 🧩 可插拔：加玩法不改引擎

加一个新玩法，不该意味着去改 `process_turn`。本项目为此留了三个扩展点：

| 扩展点 | 用途 | 关键文件 |
|---|---|---|
| **回合相位钩子** | 挂「每回合自动结算」的被动机制 | `game/turn_phase.py` |
| **命令注册表** | 加一条玩家/LLM 可下发的主动命令 | `game/command_registry.py` |
| **事件总线** | 事后广播已发生的事，供 UI/日志订阅 | `game/event_bus.py` |

五个相位（`TURN_START` / `AFTER_PRODUCTION` / `AFTER_MOVEMENT` / `AFTER_RESOLUTION` / `TURN_END`）覆盖了回合内所有「新机制可能想挂的位置」。钩子按 `(priority, 注册序)` 双键排序执行，不依赖容器迭代序；钩子抛异常会被记录进 `result["hook_errors"]` 并继续执行——一个 mod 的 bug 不该让整局崩，但必须可观测。

这不是预留的架子，引擎自己在用：`influence_spread`（影响力扩散）与 `nature_strain`（人设代价）两个既有机制已从内联逻辑迁移为钩子，语义与位置不变。

完整签名、纪律与一个可运行的示例 mod 见 **[写一个 Mod](./docs/design/modding-guide.md)**；
示例源码在 `examples/mods/harvest_festival.py`，验收脚本 `examples/run_mod_demo.py`。

> 诚实说明：引擎侧的**命令分发**已是单一扩展点，但一条新命令仍需同步
> `llm_player.COMMAND_CLASSES`、`output_parser.VALID_COMMAND_TYPES`、
> `game_manager._deserialize_command`、前端 `commands.ts` 四处清单。
> 收口进度见 modding-guide 的「已知待办」一节。

---

## 🧪 测试与实验

```bash
python -m pytest tests/ -q          # 单元 + 集成 + 平衡实验
```

全量用例由 CI 在每次推送与 PR 时执行（见顶部 CI 徽章）。
这里刻意不写死用例数量——写死的数字必然随迭代失真，本项目已有过
「旧结论被当现状」的教训（见 `docs/pitfalls.md`）。要拿当前真实数量：

```bash
python -m pytest tests/ --collect-only -q | tail -1
```

**平衡实验**（`tests/balance/`，约 400 局 headless 对照模拟，全部可复现）：

```bash
PYTHONHASHSEED=0 ./venv/bin/python tests/balance/exp11_siege_anatomy.py --games 5 --turns 48
PYTHONHASHSEED=0 ./venv/bin/python tests/balance/exp12_unification_check.py --games 5 --turns 48
PYTHONHASHSEED=0 ./venv/bin/python tests/balance/exp13_parallel_determinism.py --turns 12
PYTHONHASHSEED=0 ./venv/bin/python tests/balance/exp14_general_system_audit.py --games 3 --turns 48
PYTHONHASHSEED=0 ./venv/bin/python tests/balance/exp17_siege_flag_leak.py --games 5 --turns 48
PYTHONHASHSEED=0 ./venv/bin/python tests/balance/exp18_siege_morale_reachability.py --games 5 --turns 48
PYTHONHASHSEED=0 ./venv/bin/python tests/balance/exp19_diplomacy_reachability.py --games 5 --turns 48
```

实验遵循三条纪律：**一变量一改**、**每次至少 5 局**、**必须设对照组**。
`PYTHONHASHSEED=0` 是必须的——引擎内部有依赖集合迭代顺序的逻辑。

零观测（"某机制从未发生"）的结论**必须先跑阳性对照**再下，否则无法区分
"真的没发生"与"探针没跑起来"。`exp18`/`exp19` 都内置了阳性对照与探针有效性判定。
历史教训见 `docs/pitfalls.md`。

---

## 📁 项目结构

```
game/       游戏引擎（纯逻辑，无 UI 依赖，Pydantic 数据模型）
  battle/   战斗调度与结算（围城 / 巷战 / 战后处理）
  systems/  城市 / 资源 / 将领 / 外交 / 地图 / 影响力
  element.py    五行与相克
  personality.py 人设档案（53 名武将）
players/    玩家层：cli_player（启发式）+ llm/（LLMPlayer、prompt、解析、记忆）
renderer/   Pygame 渲染（降级/调试通道）
web/        React + PixiJS Web 前端（一等公民渲染通道）
api/        FastAPI + WebSocket 桥接（并发决策在此）
data/       地图 / 城市 / 将领 / 省界数据
examples/   示例 mod（扩展点用法示范，可直接运行）
tests/      单元 + 集成 + 平衡实验 + LLM runner
docs/       设计文档 / ADR / QA 报告 / 审计报告
```

---

## 📚 文档

- [更新日志](./CHANGELOG.md)
- 设计文档：`docs/design/`
- 写一个 Mod（扩展点指南）：[`docs/design/modding-guide.md`](./docs/design/modding-guide.md)
- 架构决策记录：`docs/adr/`
- 文档与玩法审计：`docs/audit/2026-10-docs-and-gameplay-audit.md`
- 历史审计报告（回合/年份、武将数据、节奏平衡）：`docs/archive/design/v31-*.md`
- 已知陷阱：`docs/pitfalls.md`

---

## 🤝 贡献

欢迎 PR！提交前请保证：

```bash
python -m pytest tests/ -q          # 全绿
cd web && npx tsc --noEmit          # 前端类型检查
```

新功能建议附测试；涉及数值平衡的改动请附对照实验数据（`tests/balance/`）。

---

## 📄 许可

[MIT](./LICENSE)

## 🙏 素材与致谢

- 灵感：腾讯云开发者社区《赛博斗蛐蛐：9大模型决战三国志》
- 五行设计参考：《全面战争：三国》属性体系
- 地图省界：阿里云 DataV GeoJSON
- 图标：game-icons.net（CC BY 3.0，详见 `assets/art/ATTRIBUTION.md`）
- 六角地块：Kenney（CC0）
