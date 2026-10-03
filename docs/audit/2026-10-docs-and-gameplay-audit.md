# 文档与玩法审计报告

> 审计人：文策渊（design-strategist）｜日期：2026-10-03｜分支：`feat/web-frontend`｜HEAD：`eff4c8a`
> 性质：只读研究。除本文件外未改动任何文件。
> 方法：全量实读 62 份文档 + 用 `Grep`（ripgrep 内核）复核代码事实。所有裁定均基于实读，引用给 `文件:行号`。未核实的地方直接写明「未核实」。
> 口径警告：本机 `rg` 未在 PATH，改用内置 Grep（ripgrep 内核）；BSD `grep` 全程未用。
> 🔴 **修订记录（2026-10-03，v2）**：§3-5 原稿误判「忠诚不影响战力」——实为 v4.0 已接线（详见 §3-5 的自我更正）。§1.10 与 C-14 同步更正；§④bis 增补主理人拍板的 4 项决策。此误判本身是本报告 §2 所指「旧报告结论已失效却未标注」的现场案例。

---

## 〇、总体结论（先看这三条）

1. **文档与代码的偏差集中在 4 个数字上：城市数（22 vs 31）、将领数（47 vs 53）、测试数（504/572 vs 604）、默认回合（文档建议 48，代码写死 192）**。前三个是纯文案漂移，改文档即可；第四个已由主理人拍板（48，见 §④bis）。
2. **大量「施工过程文档」已过时**：`docs/handoff/`(4)、`docs/tasks/`(3)、`docs/superpowers/`(3)、`docs/qa/`(3)、`施工指南.md`、`docs/design/v31-*.md`(3) 共 **17 份**是 6 月–10 月的阶段性记录，内容不再代表当前系统，建议整体归档。另有 **2 份**先归档再考虑删除（含一份自称「已过时」）。
3. **玩法层的真问题不是「缺功能」，是「功能算了但没人用 / 没人看见」**：流言、探索、赏赐三条命令在生产 AI（CLI）里 0 次调用；**智力（流言侧）不可达**；12 方在 192 回合内没有任何一方能被灭国（三份独立报告一致）。详见第③节。
   （注：忠诚战力**已**接线，不在缺口之列——见 §3-5 更正。）

裁定统计：**KEEP 25 份 / UPDATE 18 份 / ARCHIVE 17 份 / DELETE 2 份**（共 62 份，含 4 张截图）。

---

## ① 逐文件裁定表

> 裁定含义：`KEEP`=权威事实源；`UPDATE`=内容有用但过时需改写；`ARCHIVE`=历史记录移 `docs/archive/`；`DELETE`=无保留价值（可先备份）。

### 1.1 根目录（6 md + 3 脚本）

| 文件 | 裁定 | 一句话理由 | 实读依据 |
|---|---|---|---|
| `README.md` | **UPDATE** | 功能描述与 v4 一致，但「测试 572」`README.md:166` 与 AGENTS/MAINT 的 504 打架；「建议回合默认 48」`README.md:79` 与代码默认 192 不符 | `README.md:79,166`；`main.py:54` |
| `CHANGELOG.md` | **KEEP** | v4.0.0 记录与代码一致，是版本权威；建议补一条 4.0.1（用户口径） | `CHANGELOG.md:7` |
| `AGENTS.md` | **UPDATE** | 目录结构列了 5 个不存在的文件（见②C-7）；「504 tests」「22 城」「统一 OpenRouter」全过时 | `AGENTS.md:37,342,408` |
| `MAINTENANCE.md` | **UPDATE** | 「504 tests」「22 城 /47 将」`MAINTENANCE.md:17,31` 全过时；技术债表部分项已修 | `MAINTENANCE.md:17,31,67` |
| `施工指南.md` | **ARCHIVE** | 最后更新 2026-06-24 `施工指南.md:446`，通篇 v2.0/v2.3 阶段进度，已被 `concept.md` + 实际代码取代 | `施工指南.md:18,28,446` |
| `LLM三国志施工手册（已过时）.md` | **DELETE** | 标题即自认过时；内容是旧「魏蜀吴 3 方 / 24 回合 / OpenRouter」设计，与现状全面冲突，会误导新人 | 全文；`LLM三国志施工手册（已过时）.md:14,15,337` |
| `verify.sh` | **UPDATE** | 标题写 v2.3 `verify.sh:2`；硬编码解释器路径 `verify.sh:8`；只跑 unit，不跑 balance/perf/stability（这三个目录现已存在） | `verify.sh:2,8`；`tests/` 实有 balance/perf/stability |
| `build_app.sh` | **DELETE** | 与 `build_release.sh` 功能重叠且更旧：Info.plist 写死 `2.2` `build_app.sh:45`，标题写 v2.3 `build_app.sh:2`；产物路径写死 `$SCRIPT_DIR` | `build_app.sh:2,45` |
| `build_release.sh` | **UPDATE** | `VERSION="2.3.0"` `build_release.sh:8` 但 Info.plist 又写 `2.2` `build_release.sh:70`，两者自相矛盾，且都落后于 v4.0.1 | `build_release.sh:8,70` |

### 1.2 `docs/adr/`（5）— 全部 KEEP

| 文件 | 裁定 | 理由 |
|---|---|---|
| `ADR-0001-three-layer-separation.md` | **KEEP** | Engine 不 import pygame 的铁律仍成立（`game/` 实扫无 pygame） |
| `ADR-0002-determinism.md` | **KEEP** | 确定性 ADR 仍有效；文末「未通读 random.py」是已知缺口，不影响结论 |
| `ADR-0003-llm-output-defense.md` | **KEEP** | 五层防御与代码一致；它自己点出了 VAP 命名不统一的术语缺口 |
| `ADR-0004-graceful-degradation.md` | **KEEP** | 三级降级仍有效（`MAX_TURNS` 写 192 与代码一致） |
| `ADR-0005-web-frontend-stack.md` | **KEEP** | Web 栈描述与 `web/package.json` 一致；「待合入 main」的状态仍成立 |

### 1.3 `docs/design/`（12）

| 文件 | 裁定 | 一句话理由 | 实读依据 |
|---|---|---|---|
| `architecture.md` | **UPDATE** | 引用 `battle_context.py`（不存在，模型在 `models.py`）、`state_manager.py`/`state_validator.py`/`game_logger.py`（均不存在）；`max_turns=192` | `architecture.md:79,246,389`；文件系统实扫 |
| `art-asset-plan.md` | **UPDATE** | 「最大缺口：tab 里没有决策」`art-asset-plan.md:28` 已被 v4 补上（前端有「决策」引用）；TopBar「回合 x/24」`art-asset-plan.md:17` 过时 | `art-asset-plan.md:17,28`；`web/src` 命中「决策」 |
| `balance-tuning-plan.md` | **UPDATE** | 其 C1（终局并列决胜）已实现（`engine.py:1362`）；§7.1「TOTAL_CITIES=22」已修为 31 | `balance-tuning-plan.md:114,191`；`engine.py:1362` |
| `battle-system.md` | **UPDATE** | 写「围城阶段每回合对城墙造成伤害」`battle-system.md:131`，与代码不符（见②C-12）；模块图含不存在的 `battle_context.py` | `battle-system.md:11,131` |
| `command-pattern.md` | **UPDATE** | 内容基本对（12 方 key 已修），但 `BaseCommand/CommandType` 结构与 `models.py` 实际命令类不一致，VAP 命名与 ADR-0003 未对齐 | `command-pattern.md:53,63` |
| `concept.md` | **UPDATE** | 设计锚点，但「22 座历史城池」`concept.md:14,83` 与实际 31 不符 | `concept.md:14,83` |
| `data-models.md` | **UPDATE** | 自标「v1.0 设计稿」；「22 城」`data-models.md:201,337` | `data-models.md:5,201` |
| `llm-integration.md` | **UPDATE** | provider 描述与代码默认（deepseek）不符；其余流程与代码一致 | `llm-integration.md:489` |
| `v31-generals-audit.md` | **ARCHIVE** | 其「最严重发现：俘虏链断裂、忠诚链路从不触发」`v31-generals-audit.md:81` 已被 v4 修复（`battle_resolver.py:165` 现传 `defender_generals`），文档结论已失效 | `v31-generals-audit.md:81`；`battle_resolver.py:158-165` |
| `v31-pacing-balance.md` | **ARCHIVE** | 2026-10-03 的实验报告，「终极瓶颈=围城交换比」部分被 v4 取代 | `v31-pacing-balance.md:286-287` |
| `v31-turn-year-audit.md` | **ARCHIVE** | 2026-10-03 报告；其 B-1（prompt 回合数）与 B-2（启动参数不生效）均已修复 | `v31-turn-year-audit.md:316-317`；`prompt_builder.py:44`、`api/server.py:61` |
| `v4-conquest-pressure.md` | **KEEP** | 最新、最权威的 v4 决策文档（G 杠杆最终结论），引用链清晰 | `v4-conquest-pressure.md:465` |

### 1.4 `docs/handoff/`（4）— 全部 ARCHIVE

| 文件 | 裁定 | 理由 | 依据 |
|---|---|---|---|
| `agent-handoff-log.md` | **ARCHIVE** | 2026-06-24 的 Kimi/DeepSeek 协作日志，v2.x，硬编码 `/Library/Frameworks/...` | `agent-handoff-log.md:283,297` |
| `deepseek-execution-prompt.md` | **ARCHIVE** | 让 DeepSeek 修 B-01~B-09 的提示词，9 项均已修 | `deepseek-execution-prompt.md:33-75` |
| `hex-map-rendering-handoff.md` | **ARCHIVE** | 地图生成 Phase 1 交接，任务已完成 | `hex-map-rendering-handoff.md:67-74` |
| `kimi-rendering-handoff.md` | **ARCHIVE** | 含已废弃的「200×120 六角格」设计（concept D2 已判废弃）；是②C-6 冲突的另一端 | `kimi-rendering-handoff.md:10,130` |

### 1.5 `docs/knowledge-base/`（13）— 全部 KEEP

外部资料摘要（Wesnoth/FreeCiv/boardgame.io/json_repair 等），无项目状态断言，不与代码冲突，作为方法论留存。
一个提醒：`references.md:140,184` 与 `monte-carlo-balance-testing.md:34` 里的「三方胜率 25%-40%」是**出处**——它就是 milestone/testing 里那条过时验收口径的来源，保留时应加一句「本项按 12 方已修订」。

| 文件 | 裁定 |
|---|---|
| `knowledge-base/README.md` / `references.md` | KEEP |
| `ai-development/vibe-coding-sdlc.md` / `agents-md-best-practices.md` | KEEP |
| `game-architecture/boardgame-io-architecture.md` / `deterministic-game-design.md` / `event-driven-architecture.md` | KEEP |
| `hex-map-rendering-reference.md` | KEEP |
| `llm-integration/json-repair-best-practices.md` / `llm-output-parsing-defense.md` | KEEP |
| `multi-agent/multi-agent-architecture.md` | KEEP |
| `testing/game-balance-methodology.md` / `monte-carlo-balance-testing.md` | KEEP |

### 1.6 `docs/qa/`（3 md + 4 png）

| 文件 | 裁定 | 理由 | 依据 |
|---|---|---|---|
| `qa-report-2026-10-01.md` | **ARCHIVE** | 质量门 FAIL 报告，其两大阻塞项（`FONT_CJK_XS` 未定义、numpy 缺失）已不在当前失败清单中（用户口径 604 全过） | `qa-report-2026-10-01.md:16,109` |
| `acceptance-2026-10-01.md` | **ARCHIVE** | Phase 7 验收，孙坚 OP 等发现已被后续平衡实验覆盖 | `acceptance-2026-10-01.md:81` |
| `doc-reconciliation.md` | **ARCHIVE** | 对账清单，其 P0/P1（API key 改名、milestone 真 key）已执行完毕，清单本身完成使命 | `doc-reconciliation.md:29,51,81` |
| `v4-screenshots/*.png`（4） | **KEEP** | v4 界面的视觉证据，时效性好 | — |

### 1.7 `docs/specs/`（5）— 全部 UPDATE

| 文件 | 裁定 | 一句话理由 | 依据 |
|---|---|---|---|
| `testing.md` | **UPDATE** | 「三方胜率 25%-40%」「理想各 33%」「三方对战」`testing.md:290-293` 与 12 方冲突 | `testing.md:290` |
| `deployment-guide.md` | **UPDATE** | 引用 `config/config.yaml` `deployment-guide.md:64`、`tools/benchmark/run_benchmark.py` `deployment-guide.md:196`（均不存在）；命令示例用 `llm:wei,llm:shu,llm:wu` `deployment-guide.md:130` | 文件系统实扫（两文件 MISSING） |
| `milestone-acceptance.md` | **UPDATE** | 已按 v2.3 修到 12 方/192 回合，但 Demo1 仍写「共 22 城」`milestone-acceptance.md:273`；`--mode ai-vs-ai` 默认模型示例过时 | `milestone-acceptance.md:273` |
| `model-evaluation.md` | **UPDATE** | 依赖 `tools/benchmark/`、`tools/analysis/`（均不存在）`model-evaluation.md:302,311`；通篇「三方」框架 | 文件系统实扫 |
| `prompt-tuning-guide.md` | **UPDATE** | 「24 回合」`prompt-tuning-guide.md:51`、输出格式示例为单个 `{"command":...}` `prompt-tuning-guide.md:209`（实际是命令数组 + 先理由） | `prompt-tuning-guide.md:51,209` |

### 1.8 `docs/superpowers/`（3）— 全部 ARCHIVE

| 文件 | 裁定 | 理由 |
|---|---|---|
| `plans/2026-06-23-civ-style-hex-map-plan.md` | **ARCHIVE** | 25 任务施工计划，六角格已落地；含 `position=[x,y]` 旧模型 |
| `prompts/2026-06-23-deepseek-execution-prompt.md` | **ARCHIVE** | 配套执行提示词 |
| `specs/2026-06-23-civ-style-hex-map-design.md` | **ARCHIVE** | 已确认的旧 spec（每回合=1 月等设定已被现行每季度 1 回合取代） |

### 1.9 `docs/tasks/`（3）— 全部 ARCHIVE

| 文件 | 裁定 | 理由 |
|---|---|---|
| `development-tasks.md` | **ARCHIVE** | 阶段一~八共 36 任务清单，引用 `state_manager.py` 等不存在文件 |
| `2026-06-24-massive-game-improvements.md` | **ARCHIVE** | 4 个提交的完成记录（含里程碑 1-6），历史 |
| `2026-06-24-rename-to-luandou-sanguo.md` | **ARCHIVE** | 更名改动清单，历史 |

### 1.10 `docs/pitfalls.md`（1）— KEEP（一段需就地修）

「未接入的常量（v4.0.1 核实）」`pitfalls.md:418-431` 与代码一致（`MORALE_LOSS_BESIEGED` 除外，见②C-14），是目前最准确的死常量记录。KEEP。

**但末尾 `pitfalls.md:439-441` 一段已过时**：它写 `CAPTURE_SURRENDER_LOYALTY_FACTOR`「仍是死 import，本轮未动，留待确认」——
该 import 已在 `2f0281e`（HEAD 祖先，`git merge-base --is-ancestor` 已证）从 `general_system.py:16` 删除；
不过**常量定义 `constants.py:378` 仍在、仍零引用**（全仓 `*.py` 仅此一处命中）。
→ pitfalls 应删掉那段「死 import」的过期描述，并把 `CAPTURE_SURRENDER_LOYALTY_FACTOR` 作为**死常量**处理（删定义或接线）。

---

## ② 矛盾清单（谁对谁错 + 依据）

| # | 冲突项 | 一方 | 另一方 | 谁对 | 依据 |
|---|---|---|---|---|---|
| **C-1** | 城市数 | 22（`AGENTS.md:342`、`MAINTENANCE.md:31`、`concept.md:14`、`data-models.md:337`、`milestone-acceptance.md:273`、`deployment-guide.md:299`） | **31**（`data/cities.json` 实为 31 条；`constants.py:62` `TOTAL_CITIES=31`） | **31** | `python -c` 实读 `cities.json` 长度=31；`constants.py:62` |
| **C-2** | 将领数 | 47（`MAINTENANCE.md:31`、`kimi-rendering-handoff.md:254`） | **53**（`generals.json` 实为 53；`README.md:31`、`v4-conquest-pressure.md` 同） | **53** | 实读 `generals.json` 长度=53 |
| **C-3** | 测试数 | 504（`AGENTS.md:37`、`MAINTENANCE.md:17,84`） / 572（`README.md:166`） | **604**（用户 v4.0.1 口径，未核实具体数） | 以**实测**为准 | 三个数字互不相等，说明从没人同步过；需跑一次 `pytest` 落定 |
| **C-4** | 默认回合 | 「建议默认 48」（`README.md:79`、`v31-turn-year-audit.md:301`） | **192**（`constants.py:44` `MAX_TURNS=192`；`main.py:54` `default=192`） | 代码=192 | `main.py:54` 实读；README 的「48」是建议非实现 |
| **C-5** | 覆盖年份上限 | 232（`constants.py:23` 注释、多篇文档） | **231**（`(192-1)//4+184=231`） | **231** | `v31-turn-year-audit.md:131` 实算，复核通过 |
| **C-6** | 地图尺寸 | 120×90（README/AGENTS/concept） | 200×120（`kimi-rendering-handoff.md:10`） | **120×90** | `kimi-rendering-handoff.md:10` 自己标注「历史预研草案，已废弃」 |
| **C-7** | 目录结构含不存在文件 | `AGENTS.md:72-95` 列 `state_manager.py`/`state_validator.py`/`game_logger.py`/`battle_context.py`/`gui_player.py` | 文件系统**均无** | 文件系统对 | 实扫：5 个文件全部 MISSING |
| **C-8** | LLM provider | 「统一通过 OpenRouter」（`AGENTS.md:44`、`llm-integration.md:489`、`deployment-guide.md:109`） | **默认 deepseek**（`llm_client` 默认 provider=deepseek） | 代码对 | `doc-reconciliation.md:80` 已指出；API key 已改 `LLM_API_KEY`（部分修） |
| **C-9** | 势力 key | AGENTS/MAINT 明令禁用 `wei/shu/wu` | 但 `deployment-guide.md:130`、`superpowers/plans:1740`、`prompts:1740` 仍在用 | 禁用的对（应为 `caocao/liubei/sunjian`） | `MAINTENANCE.md:87` |
| **C-10** | 版本号 | README/AGENTS/MAINT「v2.3」；`web/package.json`/`api/server.py`「2.2.0」；`build_release.sh`「2.3.0」；Info.plist「2.2」 | 实际发布 **v4.0.1** | 4.0.1 | `git log` 与用户口径；构建脚本落后两个大版本 |
| **C-11** | 平衡验收口径 | 「三方胜率 25%-40%」（`milestone-acceptance.md`旧稿、`testing.md:290`） | 12 方公平份额=8.33%，25-40% 数学不可达 | 12 方基准（`balance-tuning-plan.md:159`） | `QA acceptance-2026-10-01.md:137` 已证 |
| **C-12** | 「围城」语义 | `battle-system.md:131` 「围城阶段每回合对城墙造成伤害」 | 代码无「围城逐回合破墙」；`is_besieged` 仅使该城民心每回合 -3 | 代码对 | `city_system.py:376-377`；见③-1 |
| **C-13** | 默认列表里 `battle_context.py` | `architecture.md:246`、`battle-system.md:11`、`AGENTS.md:86`、`development-tasks.md:183` | `BattleContext` 定义在 `models.py`，无独立文件 | 代码对 | 实扫 MISSING |
| **C-14** | 死常量目录 | `pitfalls.md:423-431` 列了 3 个未接入常量 | 实扫还发现 `MORALE_LOSS_BESIEGED=3`（`constants.py:279`）也零引用——`city_system.py:377` 直接硬编码 `change -= 3`，没读常量 | 应补进 pitfalls | `constants.py:279` vs `city_system.py:377` |
| **C-15** | `CAPTURE_SURRENDER_LOYALTY_FACTOR` 状态 | `pitfalls.md:439-441` 称「仍是死 import，本轮未动」 | `2f0281e` 已删该 import（`general_system.py:16`），但常量定义 `constants.py:378` 仍在、仍零引用 | 文档对一半：import 已清，常量**仍是死常量** | `git show 2f0281e -- game/systems/general_system.py`；`constants.py:378` |

---

## ③ 玩法缺口清单

> 判据：一个系统「闭环」= 输入→处理→反馈→**行动者（LLM/观众）可感知**。任一环断即缺口。
> 复核基准：`HEAD=eff4c8a`。

### 3-1. 战斗系统 —— 闭环基本完整，但「围城」名不副实

- **闭环**：出征 → 行军(A*) → 触发战斗 → `BattleEndedEvent` → 前端战报。输入/处理/反馈都在。v4 已修：城墙无限膨胀、破墙仍享加成、僵尸军队、撤退蒸发。
- **缺口 1（机制语义）**：`is_besieged` 只产生一项效果——围城期间该城民心每回合 -3（`city_system.py:376-377`）。**没有断粮、没有围城逐回合破墙、也没有围困导致的守军损耗**。攻城是一次性结算的战斗，不是「围城」。文档 `battle-system.md:131` 承诺的「每回合对城墙造成伤害」在代码里不存在。
- **缺口 2（数值）**：实测围城交换比攻方吃亏——攻方平均伤亡 63.2%、守方 77.4%，28 场围城无一攻下（`v31-pacing-balance.md:236-244`）；守军每回合由资源系统补至 `等级×1000`（`v4-conquest-pressure.md:97`）。攻方永远打不穿消耗战。
- **缺口 3（死常量）**：`MORALE_LOSS_BESIEGED=3`（`constants.py:279`）零引用，`city_system.py:377` 硬编码 3。改数值时改常量无效——是个坑。
- **玩家可感知**：围城城市前端有红色脉冲（`CityMarker`）；但「为什么掉民心」「围城会持续多久」不在 prompt/UI 说明里。

### 3-2. 经济系统 —— 闭环缺「出口」，中后期资源堆积无人花

- **闭环**：产出（金/粮/人口，受民心+政治加成）→ 消耗（征兵/发展）→ 前端城池面板可见。v4 把政治加成从「求和」改为「主官全额+副手半额并封顶」，消除了 2.9 倍堆叠差。
- **缺口**：`v31-pacing-balance.md:279` 记「钱粮堆积无人用」；`v31-turn-year-audit.md` 记 65 回合后资源不再影响战局。产出没有足够多的消耗出口（命令只有 9 类，花钱的就征兵/发展/赏赐），且 AI 到中期不再需要钱。**经济系统事实上退出了决策**。
- **暗机制**：政治加成、民心倍率、经济发展的叠加效果都没有在 prompt 里拆解给 LLM 看，模型无法据此做「发展还是征兵」的定量权衡。

### 3-3. 外交系统 —— 契约层完整，情报层不可达

- **闭环**：`message` / `propose_alliance` / `declare_war` + `DiplomacyRelationSystem`（WAR/NEUTRAL/ALLIANCE/TRUCE + 信任度）→ 关系事件 → 前端 `DiplomacyPanel` 可见。这条链是通的。
- **缺口（智力不可达，两层断）**：
  1. `intelligence` 唯一的计算点在流言成功率（`diplomacy_system.py:193`），要生效必须 LLM 主动发 `rumor` 且**显式指定 `spy_general`**；但 `spy_general` 是可选参数（`output_parser` 只要求 `city`），不指定时 `spy_intelligence` 恒为默认 50（`engine.py:730`）。
  2. `engine.py:738` 传 `target_faction=""`，注释写「由 GameEngine 查城市归属」，**后面没有任何代码回填**（`engine.py:736-742` 全文实读）。流言不校验目标城归属，等于可对任意城无成本降忠。
  3. CLI AI 从不发 `rumor`（`cli_player.py` 只 append: propose_alliance/declare_war/message/attack/recruit/develop，实读 91/120/132/204/214/234 行）。→ **智力对结果零影响**。
- **设计立场正确**：盟约无系统强制、可背刺，是 `concept.md` 支柱 2.3 的**刻意选择**，不是缺陷。

### 3-4. 招募 / 探索系统 —— 命令存在，生产 AI 从不调用

- `explore` 命令与真实人物池（v4 改了「史实人才池」）都在，但 CLI 从不发 `ExploreCommand`（同上实读）。`EXPLORE_COOLDOWN_TURNS=3`（`constants.py:388`）零引用——冷却从未实现。
- 闭环断在「输入」：没有任何玩家（AI）会去探索，机制等于沉睡。

### 3-5. 忠诚系统 —— v4 已重写，忠诚**已**参与战力（🔴 2026-10-03 自我更正）

- v4 修复：向忠诚基准回归、失城打击、投降分档（0/5/25/50/75%）、俘虏链接线（`battle_resolver.py:165` 现传 `defender_generals`）。
- **【更正】原稿此处写「`LOYALTY_COMBAT_*` 三处均零引用——忠诚当前不影响战力」——错了。** v4.0 已把这三个常量接线：
  `general_system.py:360` 新增 `loyalty_combat_factor(loyalty)`，`:378/382/383` 三处直接读常量；
  `battle_scheduler.py:33` 导入、`:279-283` 在战斗中真实调用（攻守双方主将各算一次），
  经 `BattleContext.attacker/defender_loyalty_factor` 进入 `battle_resolver._calculate_damage`。
  **忠诚（≥90 +10% / <30 -20%）是生效的**；`tests/unit/test_loyalty_system.py:170-192` 有 6 条分档测试。
- **我错在哪**：我把 `docs/design/v31-generals-audit.md:39-41` 的「零引用」结论（**v31 时代**）当成了当前事实，
  而该结论 **v4.0 已推翻**；反倒是我在 §1.10 判为 KEEP 的 `pitfalls.md:418-431` 本来就没把它列进死常量表（它是对的）。
  → 这正是本报告 §2 所指「`docs/design/` 里旧报告结论已失效却未标注」的**现场踩坑**，
  也是「必须归档 `v31-generals-audit.md`（结论被 v4 修复推翻的那份）」的**实证案例**。
- **剩余真缺口（无主动管理）**：`reward`（赏赐）命令 CLI 从不发，忠诚只能靠系统回归，玩家没有「花钱保忠」的手段。

### 3-6. 内政 / 城市 —— 基本闭环

- `develop`(economy/military/culture)、`recruit`、民心系统都在；v4 把「军事发展永久抬高城墙上限」改成上限由数据决定、满墙转训守军（消除「越修越硬」）。
- 未核实：`culture` 发展的实际数值效果（本次未逐行追 `city_system` 的 culture 分支，标「未核实」）。

### 3-7. 情报系统 —— 只有「看」，没有「谋」

- 信息迷雾 5 层可见性规则在（`visible_armies`）。但**主动情报行为（流言/侦察/计谋）全部不可用**：流言见 3-3；`INTELLIGENCE_STRATEGY_SUCCESS_RATE`（`constants.py:443`）零引用，因为根本没有「计谋」命令类型。智力作为五维之一，在生产路径上是空转的。

### 3-8. 胜利条件 —— 平局已解，但「统一」永不发生

- **已修**：v4 加了确定性 tiebreak（守军→人口→金→字典序，`engine.py:1362-1372`），消除了此前约 33% 的终局平局（`acceptance-2026-10-01.md:141`）。
- **核心缺口**：`_check_victory` 只有在「只剩 1 方」或「到回合上限」时才结束（`engine.py:1339-1352`）。而三份独立报告一致：**12 方在 192 回合内无一被灭**（`v31-turn-year-audit.md:53-55`、`v31-pacing-balance.md:99`、`v4-conquest-pressure.md:47`）。所以「统一」这条胜利路径事实上从未触发，胜负永远靠回合上限按城数判定。v4 的 G 杠杆（跨城派将）把存活 12→9（3 方被灭），是迄今最大改善，但仍无 `surv=1`。
- 缺「终局加速」机制：无劝降 / 无霸权威慑 / 无加时（`OVERTIME_EXTRA_SOLDIERS=500`，`constants.py:71`，零引用）。

### 3-9. 灭国机制 —— 无从触发

- v4 实验的 D 杠杆（无城势力清场）**零效果**，因为没有任何势力会到 0 城（`v4-conquest-pressure.md:255`）。机制写了也没机会跑。

### 3-10. 五行相克 —— v4 新增，感知度待确认

- 火/土/金/水/木相克环（+15%/-15%）在 `element.py`；将领表带「将道」列（v4）。未核实：相克数值是否写进 prompt 说明、LLM 是否知道该怎么用。任务书提到「全战三国还有更多维度」——当前只有五行一维。

### 3-11. 「暗机制」总表（算了但没告诉行动者）

| 机制 | 代码位置 | 是否暴露给 LLM/观众 |
|---|---|---|
| 围城 -3 民心 | `city_system.py:376` | 前端有围城脉冲；**掉民心的原因未说明** |
| 政治加成 / 去堆叠 | `resource_system.py` | **未在 prompt 拆解加成来源** |
| 忠诚回归 / 失城打击 | `general_system.py` | **未展示忠诚变化的归因** |
| 五行相克 ±15% | `element.py` | 将领表有将道，**相克数值说明未核实** |
| 人设代价（违本性民心 -1） | `engine.py`（v4 新增） | **是否进事件流未核实** |
| 关系信任度变化 | `diplomacy_relation.py` | 前端关系面板可见；prompt 侧未核实 |

### 3-12. 设计目标 vs 实现：哪些机制在「抑制 LLM 主观智能」

项目定位是「让 LLM 的主观智能可见」（`concept.md:22`、`art-asset-plan.md:4`）。当前**抑制**它的东西：

1. **三条「智力型」命令（流言/探索/赏赐）无正反馈** → 最优策略收敛成「发展 + 征兵 + 攻城」，模型之间的策略差异被压扁。这直接违背支柱 2.3（外交即博弈）与 Bartle 的 Socializers 卖点（`concept.md:157`）。
2. **围城僵局**使「会打仗的模型」与「不会打的模型」在终局城数上拉不开差距（12 方都活着），LLM 的战术智能无法转化为战果。
3. **经济溢出**使「会经营的模型」在中期之后无事可做。
4. 正面的：v4 已解除人设枷锁（可违背本性）、加了解释性 segment、加了「决策」tab——这些是**支持**可见性的，保留。

---

## ④ 清理与更新方案（按优先级，不执行）

> 标注 **[无代码依赖]** = 现在就能改文档；**[需先测/先决]** = 跑一次或主理人拍板后可改；**[需先改代码]** = 代码不动文档就不能对齐。

### P0 — 立即做（纯文档，零依赖）

1. **[无代码依赖] 统一城市数 22→31**：改 `AGENTS.md:342`、`MAINTENANCE.md:31`、`concept.md:14,83`、`data-models.md:337`、`milestone-acceptance.md:273`、`deployment-guide.md:299`。**依据**：`cities.json`=31、`constants.py:62`。
2. **[无代码依赖] 统一将领数 47→53**：改 `MAINTENANCE.md:31`。**依据**：`generals.json`=53。
3. **[无代码依赖] 修年份 232→231**：改 `constants.py:23` 注释 + 各文档。**依据**：`(192-1)//4+184=231`。
4. **[无代码依赖] 修 provider 描述**：`AGENTS.md:44`、`llm-integration.md:489`、`deployment-guide.md:109` 改为「默认 DeepSeek，可 `--provider` 切换；密钥 `LLM_API_KEY`」。**依据**：`doc-reconciliation.md:80` + 代码默认。
5. **[无代码依赖] 清 `wei/shu/wu` 残留**：`deployment-guide.md:130`（改 `caocao/liubei/sunjian`）。归档文档里的一并随归档处理。
6. **[无代码依赖] 修 AGENTS.md 目录结构**：删掉或标注「未实现」这 5 个文件——`state_manager.py`/`state_validator.py`/`game_logger.py`/`battle_context.py`（在 models.py）/`gui_player.py`。
7. **[无代码依赖] 平衡口径改 12 方基准**：`testing.md:290`、`milestone-acceptance.md` 相关行统一为「健康区间 [3%,16%]、OP 阈值 >16.67%、无方 0 胜」。**依据**：`balance-tuning-plan.md:159`。
8. **[无代码依赖] battle-system.md 对齐现状**：把「围城每回合破墙」改成「一次性攻城战 + 围城期民心 -3」，并删 `battle_context.py`。
9. **归档 17 份**（移到 `docs/archive/`，保留目录结构）：`docs/handoff/`(4)、`docs/tasks/`(3)、`docs/superpowers/`(3)、`docs/design/v31-*.md`(3)、`施工指南.md`(1)。
   ⏸️ **暂缓**：`docs/qa/` 三份 md（`qa-report` / `acceptance` / `doc-reconciliation`）——quality-lead 正在审计 `docs/qa/`，待其报告回来再归档（本轮已执行 14 份，qa 3 份挂起）。
10. **删除/备份 2 份**：`LLM三国志施工手册（已过时）.md`、`build_app.sh`（被 `build_release.sh` 取代）。**先归档到 `docs/archive/`，不直接删**（留可回滚）。

### ④bis 主理人已拍板（2026-10-03）

| # | 项 | 决策 | 落地动作 |
|---|---|---|---|
| D-1 | 默认回合数 | **48**（依据 v3.1：192 回合第 49 起零战斗，96 与 48 终局同性质） | **[需先改代码]** `constants.py:44`（硬上限是否保留由工程岗定）、`main.py:54`；README 保持「建议 48」与代码对齐 |
| D-2 | 发布版本号 | **v4.1.0**（多模型对战是新功能，按语义化版本升 minor；对外发布号待「大更新」再定） | 补 CHANGELOG `[4.1.0]`；同步 `build_release.sh:8,70`、`web/package.json`、`api/server.py`、README/AGENTS/MAINTENANCE |
| D-3 | 测试数 | **604（系统 Python 3.12）** | README/AGENTS/MAINTENANCE 三处统一为「604 passed（系统 Python 3.12）」，并注明 venv 口径因缺 fastapi 少收 23 项 |
| D-4 | 死常量 | `MORALE_LOSS_BESIEGED`→**接线**；`INTELLIGENCE_STRATEGY_SUCCESS_RATE` / `OVERTIME_EXTRA_SOLDIERS` / `EXPLORE_COOLDOWN_TURNS`→**保留待实现** | 见 P2-15 |

---

### P1 — 需先测或先拍板

11. **[已拍板 D-3] 测试数落定**：统一写 `604 passed（系统 Python 3.12）`，并注明 venv 少收 23 项（缺 fastapi）。替换 README 的 572、AGENTS/MAINT 的 504。
12. **[已拍板 D-1] 默认回合数 = 48**：**[需先改代码]** `constants.py:44`、`main.py:54`（及 `api/game_manager` 若涉及），再把 README 的「建议 48」变为与代码一致。
13. **[已拍板 D-2] 版本号 = v4.1.0**：补 CHANGELOG 条目；同步 `build_release.sh:8,70`（VERSION + Info.plist 现为 2.3.0/2.2 自相矛盾）、`web/package.json`、`api/server.py`、三份根文档的版本戳。
14. **[无代码依赖] 修 `verify.sh`**：标题 v2.3→当前版本；去掉硬编码解释器路径（用 `$PYTHON` 或 `python3`）；可选加 balance/perf 冒烟。

### P2 — 需先改代码，文档随后

15. **[已拍板 D-4] 死常量裁决**：
    - **接线**：`MORALE_LOSS_BESIEGED`（删掉 `city_system.py:377` 的硬编码 3，改读常量）。
    - **保留待实现**：`INTELLIGENCE_STRATEGY_SUCCESS_RATE`（需先有「计谋」命令）、`OVERTIME_EXTRA_SOLDIERS`（加时机制）、`EXPLORE_COOLDOWN_TURNS`（探索冷却）。
    - **新增待裁决**：`CAPTURE_SURRENDER_LOYALTY_FACTOR`（`constants.py:378`）——import 已删、定义仍在，属死常量，删定义或接线二选一（见 C-15）。
    - **订正**：原稿把 `LOYALTY_COMBAT_*` 列为「接线候选」是错的——它 v4.0 已接线（见 §3-5 更正），不在本项。
16. **[需先改代码] 玩法缺口立项**（详见③，按性价比排序）：
    - 3-3 流言可达性：`target_faction` 回填 + `spy_general` 改必填 + 校验归属（约 11 行，`v31-generals-audit.md:312-314`）。
    - 3-1 真围城：给 `is_besieged` 加断粮/逐回合损耗（设计+数值，高风险，需专项实验）。
    - 3-5 忠诚→战力接线：让忠诚维度真正参与战斗。
    - 3-8 终局加速：劝降/霸权威慑/加时（`v4-conquest-pressure.md:541` 已列方向）。
    - 3-2 经济出口：给金钱/粮草增加有效消耗出口。

### 依赖关系一览（谁挡谁）

```
P0 全部（文档）         → 可立即执行，无阻塞；qa 三份 md 挂起（等 quality-lead）
D-1 默认回合=48         → 需先改代码 constants.py:44 + main.py:54，再同步 README/docs
D-2 版本号=v4.1.0       → 需先定；阻塞 CHANGELOG + build 脚本 + README
D-3 测试数=604          → 无代码依赖，可直接落三份文档
D-4 死常量              → MORALE_LOSS_BESIEGED 需先改代码；其余三项保留
P2 玩法补洞             → 全部被「代码改动」阻塞（先改代码，文档随后）
```

---

## 附：本次审计的核实动作清单

- 实读：62 份文档全文（4 张 PNG 未逐张阅图，仅记录为 v4 视觉证据）。
- `Grep`（ripgrep 内核）复核：`TOTAL_CITIES`、`target_faction`、`spy_intelligence`、`defender_generals`、`captured_generals`、`ATTACK_FORCE_RATIO`、`MORALE_LOSS_BESIEGED`、`GAME_MAX_TURNS`/`GAME_MODE`、`max_turns`、CLI 命令类型、前端「决策」。
- 文件系统实扫：`game/`、`players/`、`api/`、`data/`、`renderer/`、`tests/`、`web/src/`，确认 5 个被引用的文件缺失。
- 数据实读：`cities.json`=31 条、`generals.json`=53 条。
- 未核实项（已在正文标出）：`culture` 发展数值效果、五行相克是否写入 prompt、人设代价是否进事件流、真实测试用例数。
