# 平衡性调参方案（Balance Tuning Plan）

> 作者：文策渊（design-strategist）
> 日期：2026-10-01
> 状态：**方案文档（只读根因分析 + 调参建议）**，未改动任何源码/数据。
> 数据来源：`docs/qa/acceptance-2026-10-01.md`（100 局真实实跑）、`data/cities.json`、`data/generals.json`、`game/personality.py`、`game/constants.py`、`game/engine.py`、`players/cli_player.py`，以及本文件附带的只读量化脚本（`/tmp/analysis.py`，仅读 JSON 不写项目）。

---

## 0. 摘要

- 100 局真实平衡模拟：0 崩溃、33 平局、67 可决出；**孙坚 32.0% 胜率（公平份额 8.33% 的 3.8×）显著 OP**；**张角/董卓/刘备/马腾 100 局 0 胜**。
- **孙坚 OP 根因一句话**：孙坚拥有全 12 方**最高平均统帅（82.0）**、**最少敌方邻接（仅 2 个敌势力）**、以及**专属的 3 座中立扩张城（panyu/cangwu/jianye）**，三者在「将领质量 × 低敌压 × 安全扩张」上同时拉满，而非性格最激进（其 aggression 0.6 低于董卓 0.9、张角 0.8）。
- **四方 0 胜根因一句话**：四方全部卡在「无安全扩张通道」——要么 0 中立邻城且被 4–6 个敌势力包围（张角 6 敌/0 中立缓冲、刘备 5 敌 0 中立、董卓 4 敌 0 中立），要么是西北角**孤城 1 座且唯一邻城即敌（马腾 wuwei 仅邻 tianshui）**，导致无法在 192 回合前累积城市数。
- 本方案列 **15 条具体改动**（孙坚减配 4 条 / 四方补强 9 条 / 平局处理 1 条 / 文档基准 1 条），并给出 12 方新平衡基准区间。

---

## 1. 起始局面量化快照（证据基线）

下列各值由 `data/cities.json` + `data/generals.json` 解析得出（`/tmp/analysis.py`）：

| 势力 | 城数 | 等级和 | 总守军 | 总gold | 总人口 | 邻接敌势力数 | 中立邻城数 | 平均统帅 | 将领数 |
|------|----|----|----|----|----|----|----|----|----|
| han 汉室 | 2 | 7 | 5500 | 2300 | 90000 | 7 | 0 | 76.8 | 4 |
| zhangjiao 张角 | 2 | 5 | 3000 | 1200 | 45000 | **6** | 3 | **66.8** | 4 |
| dongzhuo 董卓 | **1** | 2 | **1000** | **400** | **15000** | 4 | **0** | 68.0 | 6 |
| yuanshao 袁绍 | 1 | 3 | 2000 | 800 | 30000 | 4 | 4 | 63.3 | 6 |
| caocao 曹操 | 2 | 5 | 3000 | 1200 | 45000 | 4 | 0 | 76.8 | 8 |
| liubei 刘备 | 2 | 4 | **2000** | **800** | 30000 | 5 | **0** | 71.0 | 4 |
| **sunjian 孙坚** | 2 | 5 | 3000 | 1200 | 45000 | **2** | **3** | **82.0** | 4 |
| liubiao 刘表 | 2 | 6 | 4000 | 1600 | 60000 | 5 | 0 | 63.2 | 4 |
| liuyan 刘焉 | 2 | 7 | 5500 | 2300 | 90000 | 3 | 0 | 73.3 | 3 |
| gongsunzan 公孙瓒 | 1 | 3 | 2000 | 800 | 30000 | 2 | 4 | 82.7 | 3 |
| **mateng 马腾** | **1** | 2 | **1000** | **400** | **15000** | **1** | **0** | 80.7 | 3 |
| yuanshu 袁术 | 2 | 4 | 2000 | 800 | 30000 | 1 | 6 | 64.5 | 4 |

> 关键观察：**胜率与「起始城基地 × 将领质量 × 安全扩张通道（中立邻城/低敌压）」强相关**。
> - 孙坚：将领质量最高 + 敌压最低(2) + 安全中立(3) = 三因子全满 → OP。
> - 张角/刘备/董卓/马腾：均缺失「安全扩张通道」（中立邻城=0 或 被 4–6 敌包围），且董卓/马腾仅 1 城 → 0 胜。
> - 反例验证：袁术(敌压1/中立6)与公孙瓒(敌压2/中立4/统帅82.7)位置同样安全，但袁术统帅仅 64.5、公孙瓒仅 1 城，故分别仅 3%/5% —— 说明「安全位置」必须配上「将领质量+城基地」才能转化为胜率，孙坚恰好三项全有。

---

## 2. 根因结论

### 2.1 孙坚（sunjian）OP 根因
**一句话**：孙坚是全局唯一在「最高将领质量（avgCmd 82.0）+ 最少敌压（仅邻 liubiao、yuanshu 两方）+ 专属安全扩张走廊（3 座可达中立城 panyu/cangwu/jianye）」三项同时拉满的势力，叠加 aggression 0.6 的适中进攻性，使其既能稳吃南部无主城、又不被多线夹击，结构性滚雪球。

**具体证据（来自文件）**：
- `data/generals.json`：孙坚四将 `sun_jian(comm90/brav92)`、`huang_gai(80/85)`、`cheng_pu(82/80)`、`han_dang(76/82)`，avgCmd **82.0（全方最高）**；对比张角 66.8、董卓 68.0、袁术 64.5、刘表 63.2。
- `data/cities.json`：孙坚 `changsha(L2, q126/r81)` 邻 `panyu(neutral)`、`cangwu(neutral)`；`chai_sang(L3, q136/r76)` 邻 `jianye(neutral)`。其 **3 座中立邻城**为全方之最，且这些城仅与孙坚（及彼此）相连，等同「私属后院」。
- 邻接敌势力仅 **2 个**（liubiao、yuanshu），远低于中心的张角(6)/刘备(5)/刘表(5)/汉室(7)。
- `game/personality.py` 第 30 行：`sunjian aggression=0.6`（并非最高；dongzhuo 0.9、zhangjiao 0.8 更高却 0 胜）→ 排除「性格过激」假说，坐实是**布局/将领/邻接**问题。
- `players/cli_player.py`：进攻门槛 `attack_garrison = 1200 - aggression*800` → 孙坚 ≈720 兵即出击、`attack_gold≈220`；配合高统帅将领，攻城胜率高、扩张快。

### 2.2 四方 0 胜根因（分别举证）
| 势力 | 根因 | 证据 |
|------|------|------|
| **张角 zhangjiao** | 处于**最密集的中心十字路口**，被 6 个敌势力包围（han/caocao/yuanshao/liubiao/liubei + 间接），且 nanyang 一城**0 中立邻城**；将领偏文（avgCmd 66.8 最低档），aggression 0.8 在 6 线同时开战导致兵力分散。 | `cities.json`：nanyang 邻 6 敌 0 中立；julu 邻 5 敌；`generals.json` zhang_jiao(70/30/88)、zhang_bao(65)、zhang_liang(60) 统帅偏低；`personality.py` aggression 0.8。 |
| **董卓 dongzhuo** | **仅 1 座起始城（tianshui L2）**，且周边 4 敌（liubei/liuyan×2/han）、**0 中立邻城**；单城基地最低（守军1000/金400/人15000）。即便有 6 将领也无城可铺。 | `cities.json` tianshui faction=dongzhuo，level 2，邻 jian_ge/hanzhong/changan/chengdu/wuwei 全为敌；`analysis` 表：城数1/中立0/基地最低。 |
| **刘备 liubei** | 2 城但**均为 L2（最低档）**，被 5 敌包围、**0 中立邻城**；性格外交型 aggression 仅 0.3，**几乎不主动进攻**，被锁死在西川走廊无法外扩。 | `cities.json` jian_ge(L2)邻 4 敌 0 中立、bai_di(L2)邻 6 敌 0 中立；`personality.py` liubei aggression 0.3（全方最低档）；基地 gold800/人30000 为 2 城方中最低。 |
| **马腾 mateng** | **西北角孤城 1 座（wuwei L2），唯一邻城即敌（tianshui=董卓）**，完全脱离中央战场；无中立扩张、无法在 192 回合前累积城市数。 | `cities.json` wuwei 邻 `["tianshui"]` 仅 1 条；`analysis` 表：城数1/敌压1/中立0/基地最低（与董卓并列）。 |

> 共性：**四方全部缺失「安全扩张通道」**（中立邻城=0，或被 4–6 敌淹没）。这是 0 胜的结构性主因，而非单纯将领弱（马腾 avgCmd 80.7 其实很高，但孤城无用）。

---

## 3. 具体改动清单（文件 + 字段/id + 目标值 + 预期效果）

> 标识符：`cities.json` 用城市 `id`；`generals.json` 用将领 `id`；`personality.py` 用 `FACTION_PERSONALITY` 键。
> 等级字段对照（`game/constants.py` CITY_LEVELS）：L2 = wall_hp1000/gold400/food600/pop15000/garrison1000；L3 = wall_hp2000/gold800/food1000/pop30000/garrison2000。

### A. 孙坚减配（4 条）

| # | 文件 | 字段/id | 当前 → 目标 | 预期效果 |
|---|------|---------|------------|----------|
| A1 | `data/cities.json` | `chai_sang`：level / wall_hp / gold / food / population / garrison | 3→2 / 2000→1000 / 800→400 / 1000→600 / 30000→15000 / 2000→1000 | 孙坚次城产能与守军减半，扩张节奏放慢，削弱滚雪球起点。 |
| A2 | `data/generals.json` | `sun_jian`：command | 90 → 82（bravery 保留 92） | 主将单场战斗加成（COMMAND_COMBAT_BONUS_RATE 0.01/点）下降，平均统帅 82.0→约 78。 |
| A3 | `data/generals.json` | `huang_gai`：command | 80 → 73 | 进一步压低孙坚将领均值，缩小与中游方差距。 |
| A4 | `data/generals.json` | `cheng_pu`：faction + location | sunjian/changsha → **dongzhuo/tianshui** | **一石二鸟**：孙坚再减一员上将（剩 3 将，均值≈77）；同时直接补强董卓（见 B1）。 |

### B. 四方补强（9 条）

**董卓 dongzhuo**
| # | 文件 | 字段/id | 当前 → 目标 | 预期效果 |
|---|------|---------|------------|----------|
| B1 | `data/generals.json` | `cheng_pu`（来自 A4） | 改隶 dongzhuo @ tianshui | 接收孙坚上将，董卓平均统帅 68.0→约 70。 |
| B2 | `data/cities.json` | `tianshui`：level / wall_hp / gold / food / population / garrison | 2→3 / 1000→2000 / 400→800 / 600→1000 / 15000→30000 / 1000→2000 | 唯一城基地翻倍；配合 aggression 0.9 主动出击，能向 liuyan/han 方向占城。 |

**马腾 mateng**
| # | 文件 | 字段/id | 当前 → 目标 | 预期效果 |
|---|------|---------|------------|----------|
| B3 | `data/cities.json` | `wuwei`：level / wall_hp / gold / food / population / garrison | 2→3 / 1000→2000 / 400→800 / 600→1000 / 15000→30000 / 1000→2000 | 孤城基地翻倍，具备攻取邻城 tianshui 的兵力。 |
| B4 | `data/generals.json` | `zhang_ren`（原 liuyan）：faction + location | liuyan/chengdu → **mateng/wuwei** | 补一员上将（comm82/brav78），马腾均值≈81。 |
| B5 | `data/cities.json` | `jinyang`（neutral）→ 改 faction=**mateng** | neutral → mateng | 给马腾**第 2 座城**，脱离「必 0 胜」的孤城结构，并在并州获得北向据点。（⚠ 地理上 wuwei 与 jinyang 不相邻，需 re-sim 验证；备选：若显割裂，改为只做 B3+B4 并接受马腾靠吞并 tianshui 扩张。） |

**张角 zhangjiao**
| # | 文件 | 字段/id | 当前 → 目标 | 预期效果 |
|---|------|---------|------------|----------|
| B6 | `game/personality.py`（第 25 行） | `zhangjiao.aggression` | 0.8 → 0.6 | 减少在 6 线同时开战导致的兵力分散，集中兵力打相邻弱敌/中立。 |
| B7 | `data/generals.json` | `zhang_jiao` command 70→80；`zhang_bao` 65→72；`zhang_liang` 60→70 | 提升军事属性 | 平均统帅 66.8→约 73.5，能在中心混战中立足、提升攻城/防守胜率。 |
| B8 | `data/cities.json` | `julu`：level / wall_hp / gold / food / population / garrison | 2→3 / 1000→2000 / 400→800 / 600→1000 / 15000→30000 / 1000→2000 | 北疆基地加强，支撑多线防御。 |

**刘备 liubei**
| # | 文件 | 字段/id | 当前 → 目标 | 预期效果 |
|---|------|---------|------------|----------|
| B9 | `game/personality.py`（第 29 行） | `liubei.aggression` | 0.3 → 0.5 | 外交型过于保守（几乎不进攻）是 0 胜主因；提至 0.5 使其更主动占城/打中立。 |
| B10 | `data/cities.json` | `bai_di`：level / wall_hp / gold / food / population / garrison | 2→3 / 1000→2000 / 400→800 / 600→1000 / 15000→30000 / 1000→2000 | 双城基地提升（与 jian_ge 合计 L5→L6），增强西川走廊生存力。 |

### C. 平局处理（1 条）
| # | 文件 | 位置 | 当前 → 目标 | 预期效果 |
|---|------|------|------------|----------|
| C1 | `game/engine.py` | `_check_victory`（约第 1023–1024 行）：`self.winner = winners[0] if len(winners)==1 else None` | 当 `len(winners)>1`（并列最多城）时，按**次级指标决胜**取唯一胜者：① 总守军(garrison)降序 → ② 总人口降序 → ③ 总 gold 降序 → ④ faction 字典序。 | 几乎消除平局（除非所有次级指标也完全相同，概率极低）；平局率从 ~33% 压到 <5%，保证「每局有胜者」。 |

### D. 验收文档基准修订（1 条）
| # | 文件 | 位置 | 当前 → 目标 | 预期效果 |
|---|------|------|------------|----------|
| D1 | `docs/specs/milestone-acceptance.md` | 阶段七「平衡性三方胜率在 25%-40% 之间」 | 改为 12 方基准（见第 5 节）：健康区间 [3%,16%]、OP 阈值 >16.67%、无方 0 胜、平局率 <10% | 修正「按 3 方设计、12 方不可达」的文档缺陷，使验收判据与 NUM_FACTIONS=12 一致。 |

**合计：15 条改动**（A 组 4 + B 组 9 + C 组 1 + D 组 1）。

---

## 4. 平局处理方案详述（C1）

**问题**：`game/engine.py` 第 1023–1024 行，到达 `MAX_TURNS=192` 时若多个势力并列最多城市，`winner=None` → 平局。100 局中 33 局如此（33%），严重削弱「每局有胜者」。

**方案（首选：确定性次级指标决胜）**：
```python
# 现状（engine.py ~1023-1025）
max_count = max(active_counts.values())
winners = [f for f, c in active_counts.items() if c == max_count]
self.winner = winners[0] if len(winners) == 1 else None  # 平局

# 建议改为
max_count = max(active_counts.values())
winners = [f for f, c in active_counts.items() if c == max_count]
if len(winners) == 1:
    self.winner = winners[0]
else:
    # 并列最多城 → 次级指标决胜，保证唯一胜者
    def tiebreak(f):
        fac_cities = [c for c in self.cities.values() if c.faction == f]
        garri = sum(c.garrison for c in fac_cities)
        pop   = sum(c.population for c in fac_cities)
        gold  = sum(c.gold for c in fac_cities)
        return (garri, pop, gold)  # 降序；最后用 faction 名做稳定兜底
    self.winner = sorted(winners, key=lambda f: tiebreak(f), reverse=True)[0]
```
**预期效果**：平局率从 ~33% 降至 <5%（仅当两方在所有次级指标上完全相等才仍并列，概率极低）。零额外耗时、确定性强。

**兜底（可选增强，非必须）**：若团队希望「并列时继续打而非按指标判」，可启用 `game/constants.py` 已存在的 `OVERTIME_EXTRA_SOLDIERS=500`，进入突死加时延长 `N=12` 回合（各方每回合 +500 兵强制冲突）。**建议先上线确定性别胜；加时作为后续可选**。

---

## 5. 12 方新平衡基准区间

原文档「三方胜率 25%-40%」按 3 方设计，对 `NUM_FACTIONS=12` 数学不可达（仅约 2.5–4 方能赢）。改为如下 12 方基准：

- **公平份额**：`1/12 ≈ 8.33%`。
- **OP 嫌疑阈值**：胜率 **> 16.67%（= 2× 公平份额）**。沿用 `tests/balance/run_simulation.py` 现行判据（FAIR_SHARE / OP_THRESHOLD）。
- **健康区间**：每方胜率应落在 **[3%, 16%]**（≈ 0.36×–1.92× 公平份额）。
- **偏弱 / 不可行阈值**：胜率 **< 2%（≈0.24× 公平份额）** 或 **100 局 0 胜** → 须补强。
- **统计判据（100 局二项 95% CI）**：单点 ±约 5.4pp；若某方置信区间整体高于 16.67% 或整体低于 3%，即告警。
- **复测达标线（Gate）**：
  1. 最高方胜率 ≤ 16.67%（无 OP 嫌疑）；
  2. **无方 0 胜**（每方 ≥1 胜 / 100 局）；
  3. 平局率 < 10%（C1 生效后预期 <5%）；
  4. 各势力胜率落入 [3%, 16%] 的 12 方合理分布。

> 理由：12 方棋局天然存在方差，要求「每方都≈8.33%」不现实；以公平份额为中心、允许 ±~2× 的容差区间既能识别真 OP（>2×）又能识别真废柴（<0.4×），且 CI 口径避免把随机波动误判为失衡。

---

## 6. 复测与分阶段建议

为便于**归因每条改动的效果**，建议分阶段 re-sim（`python tests/balance/run_simulation.py --games 100 --seed-base 20261001`）：

1. **阶段一（先压 OP）**：仅落地 A1–A4（孙坚减配）。预期孙坚 32%→~15–18%，观察其他方是否自然回升。
2. **阶段二（补弱方）**：落地 B1–B10。重点看张角/董卓/刘备/马腾是否脱离 0 胜、且未把某方推成新 OP。
3. **阶段三（平局 + 文档）**：落地 C1、D1。确认平局率 <10%、验收文档口径更新。
4. 每阶段后对比 `balance_out.json`，用 §5 基准判断是否达标；若仍失衡，微调 A/B 数值（建议每次只动 1–2 个参数再 re-sim）。

> **西部结构性提示（深层建议，非本次必改）**：dongzhuo/mateng/liubei/zhangjiao 均集中在西部/中心且无中立缓冲，本质是「互相吞噬」的零和区。若阶段二后仍偏弱，建议在西部（凉州/并州）**新增 1–2 座中立城**作为安全扩张空间（属地图层改动，需另立任务）。

---

## 7. 数据卫生附注（非阻塞，建议一并修）

- `game/constants.py` 第 31 行 `TOTAL_CITIES: int = 22` 与 `data/cities.json` 实际 **31 座城**不符（数据增长后常量未同步），建议改为 31 或改为运行时统计，避免后续逻辑误用。
- `data/cities.json` 中 `jianye` 与 `pengcheng` 坐标均为 `(144, 69)` 重复，建议修正 `pengcheng` 坐标（如 `145, 68`）以免寻路/渲染重叠。

---

*本文件为只读分析产物，未修改任何源码或数据。所有改动需经主理人（游承峰）拍板后，由对应职能（程基岩落 C1、数据维护落 A/B/D、文策渊落 D1）实施并 re-sim 验证。*
