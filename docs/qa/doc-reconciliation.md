# 文档对账清单（Doc Reconciliation）

> **目的**：在项目「乱斗三国」Phase 5→6 收口质量门前，核对核心文档与代码实际状态的一致性，列出需要修正的过时内容。
> **范围**：仅**新增**本清单文件，**不修改**任何现有文档/源码（README / AGENTS / MAINTENANCE / milestone / design 等）。所有修正待主理人请用户批准后再执行。
> **方法**：读 `docs/design/*` 与代表性代码（`game/engine.py`、`api/server.py`、`web/package.json`、`players/llm/*`、`main.py`），逐项比对文档声明与代码事实；事实性结论均有 `文件:行号` 锚点。
> **日期**：2026-06-24（收口核对）

---

## 0. 总览

| 类别 | 主题 | 发现数 | 优先级 |
|------|------|-------|-------|
| 1 | 版本号与日期 | 3 | P1 |
| 2 | 技术栈描述（Pygame 为主 / Web 只在 changelog） | 3 | P1 |
| 3 | milestone 的 `wei/shu/wu` + 三方 / 15城 / 24回合 | 7 | **P0** |
| 4 | 双命名 乱斗三国 vs LLM三国志 | 4 | P2 |
| 5 | API key 命名错位 | 2 | **P0** |
| — | 关联发现（超出指定核心文档的同源问题） | 3 | P2 |

> 判定依据：P0 = 会导致运行失败或严重误导新成员/测试；P1 = 收口质量门相关（文档须与代码一致）；P2 = 仓库清洁度。

---

## 1. 版本号与日期

| # | 位置 | 过期内容 | 实际现状 | 建议改法 |
|---|------|---------|---------|---------|
| 1.1 | `build_app.sh:2`、`build_release.sh:2` | 注释写"**v2.3** 构建/发布脚本" | `verify.sh`、`release/llm-sanguo-v2.2.0/` 产物均为 **v2.2.0**；README/AGENTS/MAINTENANCE 标 v2.2 | 确认本次收口是否发 2.3：若否，构建脚本注释改回 2.2；若是，README/AGENTS/MAINTENANCE/`web/package.json`/`api/server.py` 同步升 2.3 |
| 1.2 | README/AGENTS/MAINTENANCE 顶部 | "最后更新：2026-06-24" 为笼统 stamp | 代码在该日期后（`feat/web-frontend`，最近提交 2026-06-24）仍有大量迭代；`architecture.md` 等设计文档混用 2026-06-23/24 | 文档顶部加"同步于 commit `<sha>` / 日期"，而非笼统日期；或至少把日期更新到内容真正定稿时 |
| 1.3 | MAINTENANCE.md:5 "v2.2 更新"清单 | 未提及 Web 栈 | README changelog v2.1 才提 Web（FastAPI+React+PixiJS），但正文技术栈/结构未体现 | MAINTENANCE 架构速览补 Web 行（见类别 2） |

---

## 2. 技术栈描述（Pygame 为主 / Web 只在 changelog）

| # | 位置 | 过期内容 | 实际现状 | 建议改法 |
|---|------|---------|---------|---------|
| 2.1 | README.md:22-28 技术栈 / :56-109 项目结构 | `GUI: Pygame 2.6+`；`LLM: OpenRouter（多模型接入）`；`renderer/` 仅列 Pygame；Web 仅 changelog v2.1 一行 | `web/package.json`(v2.2.0)=React18.2+PixiJS8+TS5.4+Vite5.1+Playwright1.61；`api/server.py`(v2.2.0)=FastAPI+WebSocket | 技术栈表新增"Web 前端：React 18 + PixiJS 8 + TS + Vite 5；后端桥接：FastAPI + WebSocket；E2E：Playwright"；Web 与 Pygame 并列渲染通道 |
| 2.2 | AGENTS.md:2.1 / 2.2 / 1.3 | `Pygame 2.5+（GUI渲染）`；`统一通过 OpenRouter API 接入多模型`；`非目标：不做联网对战（本地单机即可）` | 代码默认 `LLMClient(provider="deepseek")`；Web 是本地单机单 `GameManager` 单局 | 2.1 补 Web/前端栈与 FastAPI；2.2 改"默认 DeepSeek，兼容 OpenRouter/OpenAI（见 ADR-0005 / 类别5）"；1.3 补"Web 为本地单机浏览器展示，非多人在线对战" |
| 2.3 | MAINTENANCE.md:29 架构速览 / :96 部署注意 | Renderer 行=`Pygame GUI`；部署仅提 pygame/SDL | Web 栈已成第一梯队渲染通道 | Renderer 行改"Pygame GUI + Web(React+PixiJS)"；部署注意补 Web（Node/Vite 构建、FastAPI 运行） |

---

## 3. milestone-acceptance.md 的 `wei/shu/wu` + 三方 / 15城 / 24回合

> 这是**危害最大**的一类：milestone 是验收演示脚本，新成员/测试会直接照抄。AGENTS.md 与 MAINTENANCE.md 已明令禁用 `wei/shu/wu`，但 milestone 全文仍大量使用。实际势力为 12 方（`han/zhangjiao/dongzhuo/yuanshao/caocao/liubei/sunjian/liubiao/liuyan/gongsunzan/mateng/yuanshu`），初始 **22 城**，`MAX_TURNS=192`。

| # | 位置 | 过期内容 | 实际现状 | 建议改法 |
|---|------|---------|---------|---------|
| 3.1 | milestone:271-273（阶段四 Demo1） | `c.faction == 'wei'/'shu'/'wu'`；"每方5座城市"；"魏国/蜀国/吴国城市" | 12 方真实 key；每方 1~2 城，共 22 城 | 改真实 key（如 `caocao/liubei/sunjian`）；"每方1~2城，共22城" |
| 3.2 | milestone:314-322（阶段四 Demo4） | "完整跑**24回合**"、"**24回合**能分出胜负" | `MAX_TURNS=192`（184→232年） | "192回合（184→232年）" |
| 3.3 | milestone:399-407（阶段五 Demo4） | "**三个**LLM对战"、"--models claude-sonnet gpt-4o gemini-pro" | 12 方对战 | "12方对战"；示例模型列表保留但注明"示例，不限三方" |
| 3.4 | milestone:444-446（阶段六 Demo1） | "**15座城市**按位置分布" | 22 城 | "22座城市" |
| 3.5 | milestone:287 / :390（命令示例） | `faction="shu"` | 真实 key | 改真实 key（如 `"caocao"`） |
| 3.6 | milestone:35（Demo 导入） | `from game.models import City, Army, General, AttackCommand` | 命令类名/模型字段需核对（design 用 `AttackCommand`，`llm_player` 也用；但 Pydantic 模型含 `faction/neighbors/position` 等必填） | 核对后修正导入与构造示例，使其可运行（建议用工厂函数而非手写全字段） |
| 3.7 | milestone:90（阶段二 Demo2） | `City(level=3, population=50000, morale=70, ...)` | 当前 `City` 模型有 `faction/wall_*/gold/food/neighbors/position` 等必填，缺字段会构造即失败 | 补齐必填字段或改用 `tests` 里的既有工厂 |

---

## 4. 双命名 乱斗三国 vs LLM三国志

> 事实：2026-06-24 提交 `89271ea` 已全局更名 `LLM三国志 → 乱斗三国`（见 `docs/tasks/2026-06-24-rename-to-luandou-sanguo.md`、`docs/tasks/2026-06-24-massive-game-improvements.md`）。代码、FastAPI title、build 脚本、`web/index.html` 均已 乱斗三国。残留集中在历史文档与旧发布物。

| # | 位置 | 过期内容 | 实际现状 | 建议改法 |
|---|------|---------|---------|---------|
| 4.1 | `LLM三国志施工手册（已过时）.md`（根目录） | 旧名手册，已自标"已过时" | 应删除或移入 `docs/archive/` | 删除 / 归档 |
| 4.2 | `release/llm-sanguo-v2.2.0/LLM三国志.app` + 同目录 `.zip` | 改名前旧发布物 | 新发布物为 `release/乱斗三国.app` | 清理旧 `llm-sanguo-v2.2.0/` 或明确标注"历史版本 v2.2.0（旧名）" |
| 4.3 | `docs/superpowers/prompts/2026-06-23-deepseek-execution-prompt.md`、`docs/superpowers/specs/2026-06-23-civ-style-hex-map-design.md`、`docs/superpowers/plans/2026-06-23-civ-style-hex-map-plan.md`（含示例 `GameRenderer(title="LLM三国志 - 无限模式")`） | 旧设计文档（rename 前） | 历史文档 | 标注"历史/已归档"，或随 rename 扫一遍替换 |
| 4.4 | `docs/knowledge-base/README.md` 等历史引用 | 可能含旧名 | 标题已新（乱斗三国） | 全仓对 `LLM三国志` 做一次 grep 替换/标注（已确认代码/FastAPI/build/`web/index.html` 均为 乱斗三国；`web/dist/index.html` 标题已正确"乱斗三国 - Web"，dist 为构建产物只需保证来源同步） |

---

## 5. API key 命名错位

> 这是**会导致运行失败**的一类：按文档配置后 LLM 全部调用失败并静默降级为随机 AI。

| # | 位置 | 过期内容 | 实际现状 | 建议改法 |
|---|------|---------|---------|---------|
| 5.1 | `main.py:268` | `api_key = args.api_key or os.environ.get("OPENROUTER_API_KEY") or ""` | 实际调用 `LLMClient(provider="deepseek", ...)`（`main.py:94/202/251`），端点 `api.deepseek.com/v1`（`players/llm/llm_client.py:27-31`） | 环境变量名与默认 provider 不匹配：用户设 `OPENROUTER_API_KEY`（OpenRouter key）会被发往 DeepSeek → 鉴权失败 → 全部 LLM 调用失败 → 触发 ADR-0004 降级为随机 AI（对局"看起来在跑但 AI 全随机"） |
| 5.2 | AGENTS.md:2.2；llm-integration.md:5.1；deployment-guide.md:102/105 | "统一通过 OpenRouter API 接入多模型"；示例 OpenRouter provider；指导 `set OPENROUTER_API_KEY=...` | 代码默认 provider = deepseek | 三选一（**需主理人拍板**）：<br>• **方案 A（推荐，最小改动）**：环境变量改名 provider 无关 `LLM_API_KEY`，`--provider` 决定端点；文档改"默认 DeepSeek，可用 `--provider openrouter` 并设 `LLM_API_KEY`"<br>• **方案 B**：保持 DeepSeek 默认，环境变量改 `DEEPSEEK_API_KEY`，deployment-guide 同步<br>• **方案 C**：恢复文档所说"统一 OpenRouter"，`main.py` 默认 provider 改回 openrouter（需 OpenRouter key）<br>同步修正 AGENTS.md 2.2 与 llm-integration.md 5.1 的 provider 描述，使其与代码默认一致 |

---

## 6. 关联发现（超出本次指定核心文档，但同源问题，建议并入后续 tech-debt 清理）

| # | 位置 | 说明 | 建议 |
|---|------|------|------|
| 6.1 | `docs/design/architecture.md:11.3`、`docs/design/command-pattern.md` 各示例、`docs/design/llm-integration.md:2.3` | 设计文档自身也含 `wei/shu/wu` 残留（回放文件示例、命令示例 `faction="wei"/"shu"/"wu"`、状态序列化"长安\|魏"）。与 milestone 同源，但不在主理人指定的"核心文档"清单 | 一并清理，使设计文档与 AGENTS/data-models 的"禁用 wei/shu/wu"自洽 |
| 6.2 | `command-pattern.md` vs `llm-integration.md` | VAP"三层校验（语法/业务静态/业务动态）"与"五层防御"术语不一致 | 在某文档/ADR 明确映射：五层防御(L2–L4)=VAP 语法+Schema 层，业务动态层=Engine 执行期校验（已记入 ADR-0003） |
| 6.3 | `build_app.sh`/`build_release.sh` vs `verify.sh`/`release/` | 构建链路内部版本号 2.2 vs 2.3 不一致（见 1.1） | 收口时统一 |

---

## 7. 执行建议（待主理人请用户批准）

1. **P0（必改）**：类别 3（milestone `wei/shu/wu` + 回合数 + 城数）、类别 5（API key 命名）。不改会导致新成员照抄出错、或 LLM 静默降级。
2. **P1（收口质量门）**：类别 2（技术栈）、类别 1（版本/日期一致性）。
3. **P2（清洁度）**：类别 4（双命名残留清理）。
4. **关联发现**（6.1–6.3）排入后续 tech-debt 清理，不阻塞本次收口硬性门槛。
5. **本清单不触碰任何现有文件**；所有修正应在用户批准后分批执行，并同步更新 `docs/adr/` 中相关 ADR 的"状态/后果"。

---

> **核对依据文件**：`docs/design/{architecture,command-pattern,battle-system,data-models,llm-integration}.md`、`game/engine.py`、`api/server.py`、`web/package.json`、`players/llm/{llm_player,output_parser,llm_client}.py`、`main.py`、`README.md`、`AGENTS.md`、`MAINTENANCE.md`、`docs/specs/milestone-acceptance.md`。
