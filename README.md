# 乱斗三国 · LLM 大乱斗

> 184 年黄巾之乱，十二路诸侯逐鹿中原——让大语言模型各领一方，谁才是真正的「天命之子」？

一个 **LLM 驱动的多智能体策略对战平台**。把大模型评测从传统的「PVE 刷分」搬进「PVP 竞技」：让不同的大模型扮演三国诸侯，在同一套规则下真刀真枪地打一局，看谁更会**推理、规划、合纵连横**。

> 灵感来自腾讯云开发者社区《赛博斗蛐蛐：9大模型决战三国志，天命在谁？》

---

## ✨ 核心亮点

- 🧠 **LLM 即玩家**：每个势力由一个 LLM 驱动，每回合先给「决策理由」再下命令，主观智能全程可见
- 🗺️ **真实中国地图**：六角格 + 省界，古地图美学（羊皮纸 + 墨线 + 半透明势力色域），含黄河/长江/珠江
- ⚔️ **十二方势力**：184 年黄巾剧本，每方有独特性格（aggression/diplomacy/expand）
- 🤝 **外交博弈**：信使系统、口头盟约、流言策反、背盟欺诈
- 🏯 **领地系统**：以城为源多源扩张，占城即夺地，边界随占领实时重划
- 👑 **建国机制**：控 3 城称王、5 城称帝
- 🎥 **Web 围观台**：React + PixiJS，实时看 LLM 勾心斗角（决策理由 / 外交 / 事件流 / 回放）
- 🔁 **确定性**：同 seed 可复现，公平比试

## 📸 效果

（地图 / 决策 tab 截图待补充）

## 🚀 快速开始

### 环境

- Python 3.12+
- Node.js 18+（仅 Web 前端）
- 一个 LLM API key（默认 DeepSeek，兼容任意 OpenAI 格式端点）

### 安装 & 运行

```bash
# 1. 安装 Python 依赖
pip install -r requirements.txt

# 2. 配置 LLM key（二选一）
export LLM_API_KEY="sk-..."        # 推荐
export DEEPSEEK_API_KEY="sk-..."   # 兼容旧名

# 3. CLI 纯 AI 对战（启发式 AI，无 LLM，零成本）
python main.py --mode ai-vs-ai --max-turns 24

# 4. 3 方 LLM 对战（DeepSeek 实跑，24 回合约 $0.04）
python tests/llm_3p_run.py --turns 24 --factions caocao,liubei,sunjian
```

### 启动 Web 围观台

```bash
# 构建前端
cd web && npm install && npm run build && cd ..

# 起后端（FastAPI 同时托管前端产物 + WebSocket）
python -m uvicorn api.server:app --host 127.0.0.1 --port 8000

# 打开 http://127.0.0.1:8000
# 右键 tab 栏「决策」看 LLM 每回合的策略
```

### LLM 模型说明

- 默认 `deepseek-flash`（DeepSeek-V4.1-Flash）
- ⚠️ `deepseek-flash` 是**推理模型**，隐藏思维链计入 `max_tokens`，客户端已按需提升上限
- 可用模型 id：`deepseek-flash`、`deepseek-v4-pro`
- 换其它 OpenAI 兼容端点：`LLMClient(provider=..., base_url=...)`

## 🧪 测试

```bash
python -m pytest tests/ -q        # 516 tests
```

## 📁 项目结构

```
game/       游戏引擎（纯逻辑，无 UI 依赖，Pydantic 数据模型）
players/    玩家层：cli_player（启发式）+ llm/（LLMPlayer、prompt、解析、记忆）
renderer/   Pygame 渲染（降级/调试通道）
web/        React + PixiJS Web 前端（一等公民渲染通道）
api/        FastAPI + WebSocket 桥接
data/       地图/城市/将领/省界数据
tests/      单元 + 集成 + 平衡 + LLM runner
docs/       设计文档 / ADR / QA 报告
```

## 🤝 贡献

欢迎 PR！提交前请 `python -m pytest tests/ -q` 保证全绿。新功能建议附测试。

## 📄 许可

[MIT](./LICENSE)

## 🙏 素材与致谢

- 地图省界：阿里云 DataV GeoJSON
- 图标：game-icons.net（CC BY 3.0，详见 `assets/art/ATTRIBUTION.md`）
- 六角地块：Kenney（CC0）
