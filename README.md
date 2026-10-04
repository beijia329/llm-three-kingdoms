# 乱斗三国 · LLM 大乱斗

[![CI](https://github.com/beijia329/llm-three-kingdoms/actions/workflows/ci.yml/badge.svg)](https://github.com/beijia329/llm-three-kingdoms/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)

> 184 年，黄巾之乱。十二路诸侯逐鹿中原——这一次，坐在帅位上的是大语言模型。

一个 LLM 驱动的多智能体策略对战平台。大多数评测给大模型打一个分数，这个项目让它们下完一整盘棋：不同模型各领一方，同一套规则、同一份地图，看谁更会推理、规划、合纵连横。

灵感来自腾讯云开发者社区《赛博斗蛐蛐：9大模型决战三国志，天命在谁？》。

---

## 🎯 这个项目在做什么

大多数评测给大模型一个分数，这个项目给的是完整的一局棋。

每个势力背后都是一个模型。每回合它得先写决策理由，再下命令；理由、外交密信、结盟与背盟的瞬间，全部在围观台上实时可见。你能看到曹操在「先取弱城滚雪球」和「先稳后方」之间权衡，看到刘备顶着汉室宗亲的名号四处结好，看到黄巾靠宗教号召力爆兵。

所以项目有两个同等要紧的目标：

1. **公平** —— 同一套规则、同一份地图、同一个随机种子，输赢可复现
2. **好看** —— 观众能看懂每步决策背后的判断，而不是只看到结果

---

## ✨ 核心特性

| | |
|---|---|
| 🧠 **LLM 即玩家** | 每方一个模型，先给决策理由再下命令，它的判断过程全程可见 |
| 🎭 **角色不是枷锁** | 人设给倾向和代价，不给行动脚本；违背本性也不会判负（[见下文](#-设计立场llm-与角色的关系)） |
| ☯️ **五行相克** | 火勇武 / 土统帅 / 金智力 / 水政治 / 木忠诚；相克环 火→金→木→土→水→火，克制 +15% |
| 👤 **53 名武将** | 每人有称号、性格、特质和五维；忠诚随国势浮动，被俘可能倒戈 |
| ⚔️ **机制闭环** | 攻城→俘将→降将→转投；失城→人心浮动→更容易被策反 |
| 🤝 **外交博弈** | 信使往来、正式盟约、流言策反、背盟欺诈 |
| 🗺️ **真实中国地图** | 六角格 + 省界，古地图画风（羊皮纸 + 墨线 + 半透明势力色），含黄河、长江、珠江 |
| 🏯 **领地系统** | 以城为源多源扩张，占城即夺地，边界随占领实时重划 |
| 👑 **建国机制** | 控 3 城称王，5 城称帝 |
| 🎥 **Web 围观台** | React + PixiJS，实时看模型勾心斗角（决策理由 / 外交 / 事件流） |
| 🔁 **确定性** | 同 seed 可复现；并发决策也不破坏一致性（有逐回合测试证明） |
| 🧩 **可插拔子系统** | 三个扩展点（回合相位钩子 / 命令注册表 / 事件总线），加玩法不改引擎——[写一个 Mod](./docs/design/modding-guide.md) |

---

## 🚀 快速开始

### 环境

- Python 3.12+
- Node.js 18+（只有 Web 前端需要）
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

> ⚠️ 别把占位符（如 `sk-你的key`）留在 `.env` 里——程序识别到占位符会直接报错。
> 这是有意的：静默退回启发式 AI 的话，「决策理由」面板会一直空着，排查起来很费劲。

### 跑一局

```bash
# CLI 纯 AI 对战（启发式 AI，零成本，秒级完成）
python main.py --mode ai-vs-ai --max-turns 48

# 3 方 LLM 对战（DeepSeek 实跑，48 回合约 $0.30）
python tests/llm_3p_run.py --turns 48 --factions caocao,liubei,sunjian
```

默认 48 回合（= 184–195 年，每回合 1 季度，4 回合 1 年）。实测跑满 192 回合的话，第 49 回合起就不再发生战斗，后 144 回合纯空转，成本还翻 4 倍。

### 启动 Web 围观台

```bash
cd web && npm install && npm run build && cd ..

python -m uvicorn api.server:app --host 127.0.0.1 --port 8000
# 打开 http://127.0.0.1:8000
```

在顶部工具栏选 **LLM 围观** 模式 + 参战势力（建议 3 方），点「重开一局」。切到「决策」tab 就能看每回合的策略理由。

启动参数也可以走 `run_web.py`：

```bash
python run_web.py --seed 42 --max-turns 48    # v4.0 起真正生效
```

### LLM 模型说明

- 默认 `deepseek-flash`（推理模型，隐藏思维链计入 `max_tokens`，客户端已按需提升上限）
- 可用 id：`deepseek-flash`、`deepseek-v4-pro`
- 换其它 OpenAI 兼容端点：`LLMClient(provider=..., base_url=...)`

---

## 🎭 设计立场：LLM 与角色的关系

这是项目最核心的设计选择（v4.0 定下）：

> 让 LLM 读角色设定再执行，会不会限制它的智能？

会。把人设当成必须遵守的脚本，模型就会为了「像曹操」而放弃好棋，甚至为了圆人设编造史实——对一个比拼博弈的平台来说，这是致命的。

但完全不给角色设定也不行：观众看到的会是一个通用优化器，每局决策理由千篇一律。

所以走第三条路：

| | 做法 |
|---|---|
| 人设定位 | 给视角和偏好（你是谁、你倾向什么），不给行动脚本 |
| 自由边界 | 提示词里明说：可以为了取胜违背本性，不会判负 |
| 代价来源 | 代价不来自提示词的警告，而来自世界机制：违背本性能掉一点人心 |
| 代价强度 | 刻意做得很轻（一次 1 点民心），不至于让好棋变坏棋 |

于是「像不像自己」成了一个真实的决策维度，而不是枷锁。模型可以演，也可以务实，观众都看得见。

配套机制：

- 君主性格影响势力的进攻、外交权重
- 谨慎型君主主动开战、激进型整回合避战 → 本势力民心 -1
- 将领表带「称号 + 将道（五行）」，模型能据此判断「派谁去打谁」

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

相克环 火 → 金 → 木 → 土 → 水 → 火：克制方伤害 +15%，被克方 -15%。

将领五行取加权最高的一项。忠诚的权重压到 0.8——不然忠诚普遍偏高，人人都判成「木」。

### 攻城与忠诚

- 城墙完好时守方有防御加成；城墙一破加成即消失，转入势均力敌的巷战
- 兵力到守军 1.25 倍以上，攻城胜率极高；低于 0.75 倍基本必败
- 忠诚 ≥90 的将领所部 +10% 战力；跌破 30 则 -20%（随时哗变）
- 将领被俘后按忠诚分档决定是否投降（0% / 5% / 25% / 50% / 75%）
- 丢城会让原主其余将领忠诚度下降——国势受挫，人心浮动

---

## 🧩 可插拔：加玩法不改引擎

加一个新玩法，不该意味着去改 `process_turn`。为此留了三个扩展点：

| 扩展点 | 用途 | 关键文件 |
|---|---|---|
| **回合相位钩子** | 挂「每回合自动结算」的被动机制 | `game/turn_phase.py` |
| **命令注册表** | 加一条玩家/LLM 可下发的主动命令 | `game/command_registry.py` |
| **事件总线** | 事后广播已发生的事，供 UI/日志订阅 | `game/event_bus.py` |

五个相位（`TURN_START` / `AFTER_PRODUCTION` / `AFTER_MOVEMENT` / `AFTER_RESOLUTION` / `TURN_END`）覆盖了回合内所有「新机制可能想挂的位置」。钩子按 `(priority, 注册序)` 双键排序执行，不依赖容器迭代序；钩子抛异常会被记进 `result["hook_errors"]` 并继续执行——一个 mod 的 bug 不该让整局崩，但必须能被看到。

这不是预留的架子，引擎自己在用：人设代价（`nature_strain`）从内联逻辑迁成了钩子，民心自然变化（`city_morale`）也挂在 `AFTER_MOVEMENT` 上。

完整签名、纪律和一个可运行的示例 mod 见 **[写一个 Mod](./docs/design/modding-guide.md)**；示例源码在 `examples/mods/harvest_festival.py`，验收脚本 `examples/run_mod_demo.py`。

> 一点实情：引擎侧的命令分发已经是单一扩展点，但加一条新命令仍需同步
> `llm_player.COMMAND_CLASSES`、`output_parser.VALID_COMMAND_TYPES`、
> `game_manager._deserialize_command`、前端 `commands.ts` 四处清单。
> 收口进度见 modding-guide 的「已知待办」一节。

---

## 🧪 测试与实验

```bash
python -m pytest tests/ -q          # 单元 + 集成 + 平衡实验
```

全量用例由 CI 在每次推送和 PR 时跑（见顶部徽章）。这里不写用例数量——写死的数字一定会随迭代失真，本项目吃过「旧结论被当现状」的亏（见 `docs/pitfalls.md`）。想要当前真实数字：

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

实验守三条规矩：**一变量一改**、**每次至少 5 局**、**必须设对照组**。`PYTHONHASHSEED=0` 是必须的——引擎内部有依赖集合迭代顺序的逻辑。

「某机制从未发生」这类零观测结论，必须先跑阳性对照再下结论，否则分不清「真的没发生」和「探针没跑起来」。`exp18`/`exp19` 都内置了阳性对照与探针有效性判定。历史教训见 `docs/pitfalls.md`。

---

## 📁 项目结构

```
game/       游戏引擎（纯逻辑，无 UI 依赖，Pydantic 数据模型）
  battle/   战斗调度与结算（围城 / 巷战 / 战后处理）
  systems/  城市 / 资源 / 将领 / 外交 / 地图
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

欢迎 PR。提交前保证两件事：

```bash
python -m pytest tests/ -q          # 全绿
cd web && npx tsc --noEmit          # 前端类型检查
```

新功能建议附测试；涉及数值平衡的改动，请附对照实验数据（`tests/balance/`）。

---

## 📄 许可

[MIT](./LICENSE)

## 🙏 素材与致谢

- 灵感：腾讯云开发者社区《赛博斗蛐蛐：9大模型决战三国志》
- 五行设计参考：《全面战争：三国》属性体系
- 地图省界：阿里云 DataV GeoJSON
- 图标：game-icons.net（CC BY 3.0，详见 `assets/art/ATTRIBUTION.md`）
- 六角地块：Kenney（CC0）
