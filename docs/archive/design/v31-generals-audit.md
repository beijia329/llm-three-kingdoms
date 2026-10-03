# v3.1 武将数据合理性评估

> **作者**：文策渊（design-strategist）
> **日期**：2026-10-03
> **分支**：`feat/web-frontend`（工作区只读，未改任何 `game/` `web/` 代码）
> **任务**：Task #2 — 武将数据合理性评估
> **方法**：全量读 `data/generals.json`（53 名）+ `game/models.py` 武将模型 + `game/battle/battle_scheduler.py` 全文 + 全仓 grep，并跑属性 A/B 篡改实验（11 变体 × 6 seeds × 192 回合）。

---

## 0. 一句话结论

**任务简报的核心判断需要修正**：`intelligence / politics / loyalty` **不是**死数据。

- `politics` **真实生效**，且是五维中影响最大的（实测最大产出 ×2.925）。
- `intelligence` 与 `loyalty` 虽在代码里有引用点，但**引用点全部不可达或恒定**，实测对胜负**零影响**。
- 真正的问题是另一件事：**忠诚度系统整条链路在生产路径上从未被触发**，导致 `loyalty` 这个字段在 192 回合里必然衰减到 0。
- 数值分布上，**没有发现历史名将的明显错位**；数据质量反而是全项目最好的部分。真正的不平衡来自"政治加成按城池内武将求和"这条规则。

---

## 1. 五维各自用在哪：实读结果

### 1.1 全仓 grep 汇总（排除 `tests/`）

| 属性 | 生产代码引用点 | 是否可达 |
|---|---|---|
| **command** | `battle_scheduler.py:209`（守方平均统帅）、`:280`（攻方加权统帅）、`battle_resolver.py:308`（攻城伤害）、`:389`（巷战伤害） | ✅ 可达 |
| **bravery** | `battle_scheduler.py:210,281`（攻守加权勇武）、`battle_resolver.py:373,399`（暴击概率） | ✅ 可达 |
| **politics** | `resource_system.py:54,66,70`（`_get_politics_bonus`），被 `:107,153,237` 调用（金/粮/人口三处产出） | ✅ 可达 |
| **intelligence** | `diplomacy_system.py:193`（`spy_intelligence * RUMOR_INTELLIGENCE_FACTOR`），唯一调用链 `engine.py:685` | ⚠️ **实际不可达/恒定**，见 §2 |
| **loyalty** | `general_system.py:205`（衰减）、`:178`（赏赐）、`:267`（投降概率）；`diplomacy_system.py:202`（流言降忠） | ⚠️ **整条链不可达**，见 §3 |

### 1.2 数据里存在但**零引用**的常量（实读确认）

| 常量 | 位置 | 状态 |
|---|---|---|
| `INTELLIGENCE_STRATEGY_SUCCESS_RATE` | `constants.py:332` | 🔴 **定义即死**，全仓零引用 |
| `LOYALTY_COMBAT_BONUS_DEVOTED` | `constants.py:310` | 🔴 **定义即死**，零引用 |
| `LOYALTY_COMBAT_PENALTY_UNSTABLE` | `constants.py:313` | 🔴 **定义即死**，零引用 |
| `LOYALTY_COMBAT_PENALTY_DANGEROUS` | `constants.py:316` | 🔴 **定义即死**，零引用 |
| `LOYALTY_DEVOTED_THRESHOLD` / `_LOYAL_` / `_NORMAL_` / `_UNSTABLE_` | `constants.py:297-306` | 🔴 四个阈值常量全部零引用 |
| `MAX_LOYALTY_FROM_REWARD` | `constants.py:278` | 🔴 零引用（`general_system.py:178` 硬编码 `100`） |
| `EXPLORE_COOLDOWN_TURNS` | `constants.py:293` | 🔴 零引用 |

**`INTELLIGENCE_STRATEGY_SUCCESS_RATE`（智力→计谋成功率）是"智力影响计谋"这条设计意图的唯一实现入口，但它从未被接线。** `models.py:266` 的字段描述写着「智力 影响计谋」——描述与实现不符。

---

## 2. 为什么 `intelligence` 实测无效（不是死数据，是不可达）

`intelligence` 唯一的计算点是 `diplomacy_system.py:191-195`：

```python
success_chance = RUMOR_BASE_SUCCESS_RATE + spy_intelligence * RUMOR_INTELLIGENCE_FACTOR
```

`spy_intelligence` 来自 `engine.py:681-685`：

```python
spy_intelligence = 50                    # 默认值
if cmd.spy_general:
    spy = self.generals.get(cmd.spy_general)
    if spy:
        spy_intelligence = spy.intelligence
```

**`intelligence` 要影响结果，前提是 LLM 主动发 `rumor` 命令且显式指定 `spy_general`。** 两个前提都不成立：

1. **`output_parser.py:369`**：`"rumor": ["city"]` —— `spy_general` 是**可选参数**。LLM 只要输出 `{"type":"rumor","params":{"city":"x"}}` 就能通过校验，`spy_intelligence` 恒为 50。
2. **`engine.py:675-699` 的 `_execute_rumor` 有硬伤**：`target_faction=""`（第 689 行，注释「由 GameEngine 查城市归属」），但**没有任何后续代码回填这个值**。流言逻辑不校验目标城归属，等于可以对任意城（含敌方核心城）无成本降忠。

3. **实测（seed 1, 192 回合）**：CLI AI 累计发出的命令类型为
   `{AttackCommand: 1190, RecruitCommand: 2319, DevelopCommand: 3620, DeclareWarCommand: 26, MessageCommand: 448}`
   —— **`RumorCommand` / `RewardCommand` / `ExploreCommand` 均为 0 次**。

**结论**：`intelligence` 不是"没接"，是"接了但玩家（CLI AI）从不用，且 LLM 用法即使发生也走默认值"。这是**设计意图与玩法激励不匹配**，不是单纯的死代码。

---

## 3. 🔴 最严重发现：忠诚度链路在生产路径上从未被触发

这是本次审计最重要的发现，任务简报未提及。

### 3.1 断链点 1：被俘武将永远为空

`engine.py:1011-1017` 消费 `result.captured_generals`：

```python
for gen_id in result.captured_generals:
    if gen_id in self.generals:
        self._general_system.process_capture(gen, ...)
```

但 `result.captured_generals` 的唯一填充点是 `battle_resolver.py:534-540`：

```python
for gen_id in defender_generals:          # ← defender_generals
    if context.defender_total_soldiers <= 0 and context.attacker_total_soldiers > 0:
        result.captured_generals.append(gen_id)
    elif self._rng.random() < 0.3:
        result.captured_generals.append(gen_id)
```

而 `resolve_battle` 调用 `process_aftermath` 时（`battle_resolver.py:156-159`）：

```python
result = self.process_aftermath(
    context,
    defender_city_owner="",  # 由 GameEngine 填充
)                              # ← 没有传 defender_generals
```

`process_aftermath` 签名（`:493,497`）中 `defender_generals: Optional[List[str]] = None`，`:514-515` 兜底为 `[]`。

🔴 **因此 `for gen_id in []` 永不执行 → `captured_generals` 永远为空 → `process_capture` 永不调用 → 忠诚度永不被读取、也永不影响任何事。**

**测试为什么没发现**：`tests/unit/test_battle_resolver.py:399-403` 直接调用 `process_aftermath` 并**显式传入** `defender_generals=["guanyu","zhangfei"]`，绕过了 `resolve_battle` 这条生产链。27 个测试全绿，但生产路径是断的。

### 3.2 断链点 2：忠诚度衰减是整数截断，实际衰减 = 1/回合

`general_system.py:205`：

```python
general.loyalty = max(0, int(general.loyalty - LOYALTY_DECAY_PER_TURN))
```

`LOYALTY_DECAY_PER_TURN = 0.5`（`constants.py:272`）。但 `int()` **向零截断**，`int(89.5) = 89`。实测：

```
loyalty 100 → 99  (衰减 1，不是 0.5)
loyalty  90 → 89  (衰减 1)
loyalty   1 →  0  (衰减 1)
```

**任何忠诚度值每回合都精确掉 1 点。** 从 100 降到 0 需 **100 回合 = 25 年**。

### 3.3 实测：192 回合后全体忠诚度归零

seed 1，`max_turns=192`，逐回合采样：

| 回合 | 年份 | 忠诚度 min/median/max | 被俘武将 | 易主武将 |
|---|---|---|---|---|
| 1 | 184 | 64 / 89 / 99 | 0 | 0 |
| 12 | 186 | 53 / 78 / 88 | 0 | 0 |
| 24 | 189 | 41 / 66 / 76 | 0 | 0 |
| 48 | 195 | 17 / 42 / 52 | 0 | 0 |
| 96 | 207 | **0 / 0 / 4** | 0 | 0 |
| 144 | 219 | **0 / 0 / 0** | 0 | 0 |
| 192 | 231 | **0 / 0 / 0** | 0 | 0 |

**没有任何一个 `reward` 命令被发出（见 §2.3 的命令计数），所以忠诚度单调衰减到 0，无人补血。**

### 3.4 这解释了 A/B 实验的结果

| 变体 | 胜者序列 | 城市分布不同 | 判定 |
|---|---|---|---|
| `intelligence=1` | 与 baseline **完全相同** | **0/6** | 零影响 |
| `intelligence=100` | 与 baseline **完全相同** | **0/6** | 零影响 |
| `loyalty=1` | 与 baseline **完全相同** | **0/6** | 零影响 |
| `loyalty=100` | 与 baseline **完全相同** | **0/6** | 零影响 |
| `politics=1` | 不同 | **6/6** | 有影响 |
| `politics=100` | 不同 | **6/6** | 有影响 |
| `bravery=1` | 不同 | 5/6 | 有影响 |
| `bravery=100` | 不同 | 5/6 | 有影响 |
| `command=1` | 不同 | **6/6** | 有影响 |
| `command=100` | 不同 | 5/6 | 有影响 |

实验脚本：`/tmp/exp_ab_par.py`（每变体 6 seeds × 192 回合，全势力 CLI AI 驱动）。

⚠️ **实验的一处已知局限**：`GameRandom` 是全局单流，属性篡改改变了消耗随机数的路径，因此这些"有影响"的部分是**随机流发散**，而非纯属性因果。为排除这一干扰，`command` 与 `politics` 的影响另有**独立解析验证**（§4、§5）——两者都能从公式直接算出影响幅度，与随机流无关。

---

## 4. `politics`：真实生效，且是五维中影响最大的

### 4.1 公式

`resource_system.py:70`：

```python
politics_bonus = 1.0 + total_politics * POLITICS_PRODUCTION_BONUS_RATE   # 0.005
```

`total_politics` 是**该城池内所有武将的 politics 之和**（`:65-69`，遍历 `city.generals`）。该倍率同时作用于 **金币、粮草、人口** 三项产出（`:108,154,237`）。

### 4.2 实测：堆叠导致 2.9 倍产出差

53 名武将按 `location` 堆叠到 19 座有武将的城市（`engine.py:205-210` 完成分配）：

| 城市 | 势力 | 武将数 | Σpolitics | 产出倍率 |
|---|---|---|---|---|
| 邺城 | yuanshao | 6 | 385 | **×2.925** |
| 许昌 | caocao | 5 | 329 | ×2.645 |
| 天水 | dongzhuo | 7 | 300 | ×2.500 |
| 武威 | mateng | 4 | 180 | ×1.900 |
| 蓟 | gongsunzan | 3 | 177 | ×1.885 |
| 襄阳 | liubiao | 2 | 160 | ×1.800 |
| 洛阳 | han | 3 | 155 | ×1.775 |
| 寿春 | yuanshu | 4 | 155 | ×1.775 |
| … | | | | |
| 成都 | liuyan | 1 | 80 | ×1.400 |
| 长沙 | sunjian | 1 | 60 | ×1.300 |
| 汉中 | liuyan | 1 | 40 | **×1.200** |

**袁绍（1 城 ×2.925）vs 刘焉（2 城 ×1.30）—— 单城产出差 2.25 倍。** 这是明确的**主导策略**（§8 红线第 1 条）：武将多的势力滚雪球，且没有任何机制抵消。

---

## 5. `command` / `bravery`：影响幅度量化

### 5.1 战斗伤害公式

`battle_resolver.py:386-403`：

```
damage = soldiers × 0.1 × command_bonus × morale_bonus × terrain_bonus × (暴击 ? 1.5 : 1)
command_bonus = max(0.5, 1 + (avg_command - 50) × 0.01)
crit_chance  = min(0.5, avg_bravery × 0.005)
```

### 5.2 幅度对比

| 属性 | 最低值效果 | 最高值效果 | 极差 |
|---|---|---|---|
| **command** | 30 → ×0.800 | 96 → ×1.460 | **1.825 倍** |
| **bravery** | 20 → 暴击 10%，期望 ×1.050 | 98 → 暴击 49%，期望 ×1.245 | **1.186 倍** |
| politics（单城） | 40 → ×1.200 | 385 → ×2.925 | **2.438 倍** |

**结论：影响力排序 `politics` > `command` > `bravery` > `intelligence` = `loyalty`（零）。**

设计意图上"勇武影响单挑"（`models.py:265`）与实现不符——勇武只驱动暴击概率，不是单挑。

---

## 6. 数值分布评估（任务第 3 问）

### 6.1 五维分布（53 名，实跑统计）

| 属性 | min | max | mean | median | sd | 不同取值数 |
|---|---|---|---|---|---|---|
| bravery | 20 | 98 | 65.85 | 70.0 | 23.43 | 22 |
| command | 30 | 96 | 72.09 | 76.0 | 13.98 | 23 |
| intelligence | 25 | 96 | 62.60 | 65.0 | 18.59 | 28 |
| politics | 20 | 95 | 53.83 | 55.0 | 20.80 | 22 |
| loyalty | 65 | 100 | 88.77 | 90.0 | 10.33 | 10 |

### 6.2 忠诚度：分布偏窄，但**问题不是初始值**

直方图：

```
loyalty=65: 3人   70: 3人   75: 2人   80: 5人   85: 6人
       88: 1人   90: 9人   92: 1人   95: 10人  100: 13人
```

- **有区分度**（10 个不同取值，65–100 跨度 35），不是简报担心的"全满"。
- 🔴 **真正的问题是 `loyalty` 在模型里被映射成了错误的含义**：`models.py:269` 默认 70，而投降公式 `general_system.py:266-267` 是 `0.30 - loyalty × 0.01`，clamp 到 [0,1]。因为**所有初始 loyalty ≥ 65 > 30，投降概率恒为 0**：

```
loyalty=100 → 0.00    loyalty=50 → 0.00    loyalty=30 → 0.00    loyalty=0 → 0.30
```

即：**只要被俘就必然不降**。`CAPTURE_SURRENDER_BASE_CHANCE=0.30` 与 loyalty 的线性修正共同导致——忠诚度低于 30 才会投降，而初始数据里没有一个人低于 65，且 decay 会把所有人推到 0。

**这是数据与公式的量纲错配**，不是数值分布问题。

### 6.3 势力间武将数差异：严重不平衡

| 势力 | 初始城数 | 武将数 | 单城武将密度 |
|---|---|---|---|
| caocao | 2 | **8** | 4.0 |
| dongzhuo | 1 | **7** | 7.0 |
| yuanshao | 1 | **6** | 6.0 |
| mateng | 2 | 4 | 2.0 |
| zhangjiao | 2 | 4 | 2.0 |
| yuanshu | 2 | 4 | 2.0 |
| han | 2 | 4 | 2.0 |
| liubei | 2 | 4 | 2.0 |
| liubiao | 2 | 4 | 2.0 |
| sunjian | 2 | 3 | 1.5 |
| gongsunzan | 1 | 3 | 3.0 |
| **liuyan** | 2 | **2** | **1.0** |

**曹操 8 人 / 1 城密度 vs 刘焉 2 人 / 2 城 —— 产出倍率 2.645 vs 1.300。** 直接映射为 §4 的 2 倍产出差 → 影响征兵能力 → 影响战斗。**这是当前最大的平衡缺陷。**

（附注：`data/cities.json` 实为 **31 城**（含 10 座 neutral），而 `constants.py:31` 写 `TOTAL_CITIES = 22`、`concept.md` 与多篇文档也写 22。文档与数据不一致，需核对。）

### 6.4 历史名将数值错位：**未发现明显错位**

全量 53 名按勇武排序后核对，数值与历史评价高度吻合：

- **勇武顶级**：张飞 98、关羽 96、赵云 96、许褚 96、典韦 94、颜良 92、孙坚 92、文丑 90、夏侯惇 90 —— 均为史书猛将。
- **统帅顶级**：曹操 96、关羽 94、皇甫嵩 90、夏侯渊 86、曹仁 85、公孙瓒 85。
- **智力/政治顶级**：郭嘉 96、荀彧 95、田丰 92、沮授 90、张角 88、李儒 88、审配 82。
- **"低勇武高智谋"的反差建模正确且一致**：郭嘉（武20/智96）、田丰（25/92）、李儒（20/88）、荀彧（30/95）、沮授（30/90）、张角（30/88）—— **6 名顶级军师全部落在勇武 20–30 区间**。

**结论：`data/generals.json` 的数值质量是全项目最好的部分，没有需要修正的错位。** 唯一可讨论的是何进（智 25）作为汉室统帅略低，但 184 年剧本里他本就是庸人，属刻意设计。

---

## 7. 让 intelligence / politics 真正生效：改动范围评估

### 7.1 politics —— 🔴 不建议改，它已经生效且过强

politics **不是死数据**。问题是它**过强且可堆叠**（§4）。这不是"接线"问题，是"配平"问题。

### 7.2 intelligence —— 中等改动，三处即可

| # | 改动 | 位置 | 规模 |
|---|---|---|---|
| I-1 | `rumor` 的 `spy_general` 改为**必填** | `output_parser.py:369` `"rumor": ["city"]` → `["city", "spy_general"]` | 1 行 |
| I-2 | 校验间谍必须是己方在世武将 | `llm_player.py` 或 `engine.py:675` 前置校验 | ~10 行 |
| I-3 | 接入 `INTELLIGENCE_STRATEGY_SUCCESS_RATE`，让高智武将带计谋（现有 9 类命令无计谋，需新增 `scheme` 命令） | `constants.py:332` 已在；需新增命令类型 + 战斗/外交效果 | **~150-250 行，跨 6+ 文件** |

**I-1 + I-2 是"最小改动"**（约 11 行），能让智力对 LLM 的流言决策立即产生区分度。**I-3 是"理想改动"**，需要新命令类型，工程量大。

### 7.3 loyalty —— 修复成本低，但需要先修断链

| # | 改动 | 位置 | 规模 |
|---|---|---|---|
| L-1 | **接线 `defender_generals`**：`resolve_battle` 传 `defender_generals=city.generals` | `battle_resolver.py:156-159` | ~3 行 |
| L-2 | 修 `int()` 截断：`round()` 或改用 float 存储 | `general_system.py:205` | 1 行 |
| L-3 | 让 CLI AI 会发 `reward`（否则 decay 必然归零） | `players/cli_player.py` | ~15 行 |
| L-4 | 投降公式量纲重设（如 `0.9 - loyalty × 0.008`，使 loyalty 65 → 0.38、100 → 0.10） | `general_system.py:266-267` 或 `constants.py:281-285` | 2 行 |
| L-5 | 接入 `LOYALTY_COMBAT_*`（死常量已在，等着被用） | `battle_resolver.py:_calculate_damage` | ~8 行 |

**L-1 是最高杠杆的单点改动**：3 行代码让整个俘虏→忠诚→投降→战斗力链路复活。

⚠️ **L-1 的平衡风险**：`engine.py:971-972` 显示攻方将领在占城后会被移入该城。若开启俘虏，L-5 的战斗力加成会让忠诚度变成**战斗核心属性**，当前战斗已偏"攻方难破城"（`constants.py:210-212` 注释记录守方胜率曾高达 72%）。**建议先只做 L-1~L-4，L-5 单独评审。**

---

## 8. 两档改动建议

### 8.1 最小改动档（约 40 行，1-2 天）

| # | 改动 | 位置 | 目的 |
|---|---|---|---|
| **M-1** | 接线 `defender_generals` | `battle_resolver.py:156-159` | 让俘虏/投降/忠诚链路复活 |
| **M-2** | 修衰减截断 `int()` → `round()`，或把 `LOYALTY_DECAY_PER_TURN` 提到 1.0 与实际行为对齐 | `general_system.py:205` | 消除"配置 0.5 实际 1.0"的误导 |
| **M-3** | 投降概率量纲重设，使 loyalty 在 65–100 区间有真实区分 | `general_system.py:266-267` | 让 loyalty 不恒为 0 |
| **M-4** | `spy_general` 改必填 + 校验间谍归属 | `output_parser.py:369`、`engine.py:675` | 让 intelligence 真正影响流言 |
| **M-5** | `politics_bonus` 改为**城池内取最高值的 1+N×小系数**，或加人数上限（如 `Σpolitics` 只取前 3 名） | `resource_system.py:65-70` | 消除 2.9 倍堆叠差 |
| **M-6** | 平衡武将密度：曹操/董卓/袁绍 减员，或给 1 城势力补将 | `data/generals.json` | 缩小 §6.3 的 4 倍密度差 |
| **M-7** | `city_by_id` 在 `_execute_rumor` 里回填 `target_faction` | `engine.py:689` | 修流言不校验归属 |

**M-1~M-4 合计约 15 行，直接让 5 维中原本零影响的 2 维（intelligence、loyalty）进入有效状态。M-5~M-6 是配平。**

> **与 quality-lead 配平实验的关系**：其 `docs/design/v31-pacing-balance.md` §4 堵点 2 实测「CLIPlayer 每局下达 ~290 次 `AttackCommand`，成功率仅 13%」，主因是 `cli_player.py:156` 兜底取到**别的城**的将领，被 `engine.py:508` 拒掉。该缺陷已由 commit `150fa87` 修复。
> ⚠️ **但这暴露了一个本报告 M-6 之外的问题**：12 名将领分散在每方 2 座城（如 caocao：`xuchang` 5 / `chenliu` 3），从 A 城出兵时**本城可能无将领可用**。M-6 的「武将密度平衡」若继续减少曹操/董卓/袁绍的人数，会**加剧**这一出本地将领的问题。
> **建议 M-6 调整为「先补将领、把武将摊到每座城」，而不是单纯给 1 城势力补将**——优先保证每座城至少 1 名本地将领（供 `cli_player` 出征与 `battle_scheduler:209-210` 的守方统帅/勇武计算使用）。

### 8.2 理想改动档（约 250-400 行，1-2 周）

在最小档之上追加：

| # | 改动 | 说明 |
|---|---|---|
| **A-1** | 新增 `scheme`（计谋）命令 | 智力终于有"计谋"载体。效果设计建议：守城方智力 > 攻方智力时降低守城伤害（类似"情报差"），或智力高的武将守城时 `DEFENDER_WALL_BONUS` 衰减 |
| **A-2** | 接入 `LOYALTY_COMBAT_BONUS_DEVOTED / PENALTY_UNSTABLE / PENALTY_DANGEROUS` | 常量已备好，只缺接线 |
| **A-3** | 引入 `TURNS_PER_YEAR` 常量，让"每回合多久"可配（配合 Task #1 的回合档位） | 见 `v31-turn-year-audit.md` §7 T-1 |
| **A-4** | 将领调动/挖角机制（低忠诚武将可被策反，智力高者成功率更高） | 让 loyalty 与 intelligence 形成**交叉机制**，而非两条独立死路 |
| **A-5** | 删除 7 个零引用常量，或全部接线 | 见 §1.2 |

⚠️ **A-4 是设计上价值最高的一项**：当前 `intelligence`（流言）和 `loyalty`（投降）是两条互不相交的链，A-4 让"高智挖低忠"成为一条链，两个属性立刻互相成就。这是把"外交即博弈"支柱（`concept.md:54-58`）真正落地的路径。

### 8.3 会不会破坏现有平衡？

**最小档的风险评估：**

| 改动 | 破坏风险 | 说明 |
|---|---|---|
| M-1 接线俘虏 | ⚠️ 中 | 一旦开启，忠诚度进入战斗/外交链。当前战斗已偏守方强（`constants.py:210-212`），但**俘虏本身不直接加战力**，只是让忠诚度有波动源 → 风险可控 |
| M-3 投降量纲重设 | 🔴 高 | 一旦忠诚度能降，武将可能被 AI 反复挖角，12 方格局可能加速收敛，与 Task #1 发现的"48 回合后僵局"叠加后会更早结束。**必须与 Task #1 的回合档位一起决策** |
| M-5 politics 去堆叠 | ⚠️ 中 | 会削弱袁绍/曹操/董卓。缓解了主导策略，但也降低了"名将堆叠"的爽感。需配合 M-6 一起做 |
| M-6 武将密度平衡 | ⚠️ 中 | 纯数据改动，可预期。需重跑平衡测试 |

**结论**：M-3 是唯一有"破坏现有平衡"实质风险的改动，建议**单独 PR + 单独回归测试**。其余最小档改动风险可控。

---

## 9. 设计理论红线检查

| 红线 | 检查结果 |
|---|---|
| **主导策略** | 🔴 **已触发**。§4 的政治堆叠（×1.20 vs ×2.925）叠加 §6.3 的武将密度差（曹操 8 人 vs 刘焉 2 人）形成单一最优解："武将多的势力无脑发展"。M-5 + M-6 针对性修复 |
| **经济失衡** | 🔴 **已触发**。52 倍产出差（×1.2→×2.925）叠加 65 回合后资源不再影响战局（见 `v31-turn-year-audit.md`），经济系统事实上已退出决策 |
| **认知过载** | ⚠️ 轻微。LLM prompt（`prompt_builder.py:208-214`）同时展示 5 维，但其中 2 维（智/忠）当前无实际作用 → 观众/LLM 会据此做**基于无效信息的推理** |
| **支柱漂移** | ⚠️ **已触发**。`concept.md:181` 把"将领单挑、计谋系统细化"列为 Could（不做），但 `models.py:263-266` 的字段描述明确承诺「统帅影响战斗 / 勇武影响单挑 / 智力影响计谋」。**实际做了一半**：统帅 ✅、勇武是暴击不是单挑 ❌、智力不可达 ❌。建议要么补齐，要么改字段描述 |
| **空转/僵局** | 🔴 **已触发，且比预想更严重**。见 `v31-turn-year-audit.md` §1：城市归属在 turn 48 后完全冻结，turn 48/96/144/192 城分布逐项相同。quality-lead 的 167 局实验独立确认「所有配置下 12/12 势力存活到 192 回合」。这直接放大"经济/忠诚系统失效"的后果——资源再充裕也无法转化为攻城 |

---

## 10. 任务简报判断的逐条核实

| 简报断言 | 核实结果 | 依据 |
|---|---|---|
| "战斗系统只读 bravery" | ❌ **不成立** | 战斗读 `command`（`battle_scheduler.py:209,280`、`battle_resolver.py:308,389`）**和** `bravery`（`:210,281,373,399`）。`command` 影响幅度（1.825×）**大于** `bravery`（1.186×） |
| "intelligence/politics/loyalty 疑似死数据" | ⚠️ **部分成立** | `politics` 生效且影响最大；`intelligence`/`loyalty` 实测零影响，但原因是**引用点不可达**（§2、§3），而非无引用 |
| "loyalty 65–100 疑似全满/无区分度" | ❌ **不成立** | 10 个不同取值、35 点跨度，有区分度。真问题是**公式量纲错配**（§6.2） |
| "曹操 8 人 vs 刘焉 2 人是否影响平衡" | ✅ **确认严重影响** | §6.3 + §4，单城产出差 2.25 倍 |
| "有没有明显数值错位的名将" | ❌ **未发现** | §6.4。6 名顶级军师全部正确落在勇武 20–30 区间，数据质量优秀 |

---

## 附录：确定性声明

- §1–§3：代码引用点、行号、公式 —— **实读确认**，含全仓 grep（排除 `tests/`）交叉验证。
- §2.3、§3.3、§4.2、§6.1–6.4：**脚本实跑统计**，数据源 `data/generals.json` / `data/cities.json`，未手工编造。
- §3 断链分析：从 `engine.py:1012` 反向追溯到 `battle_resolver.py:156-159`，确认 `defender_generals` 从未传入；并解释了测试为何漏过（`test_battle_resolver.py:399-403` 直接调用被测函数）。
- §3.3 忠诚度衰减：**实跑 192 回合逐回合采样**。
- §3.4 A/B 结果：11 变体 × 6 seeds × 192 回合实跑（脚本 `/tmp/exp_ab_par.py`）。**已知局限**：`GameRandom` 单流导致随机路径分叉，"有影响"判定含随机成分；已对 `command`/`politics` 补做公式解析验证（§4、§5）以排除该干扰。
- §7 改动规模：**行数是估算**，基于各改动点的代码结构判断，未实做。
- §8.3 平衡风险：**定性判断**，未实跑对照实验。建议 M-3 单独回归。