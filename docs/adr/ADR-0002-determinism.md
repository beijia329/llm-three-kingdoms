# ADR-0002 确定性随机与可复现性

- **状态**：Accepted（已落地，AGENTS.md 5.2 列为规范）
- **日期**：2026-06-24（记录于 Phase 5→6 收口）
- **相关**：architecture.md 八（状态快照与回滚）、AGENTS.md 5.2、game/engine.py、game/random.py

---

## 背景（Context）

游戏要支持**回放、评测可比性、bug 复现**。LLM 决策本身有随机性，但游戏世界的推进（战斗结算、征兵概率、探索发现、断粮判定、将领俘降）必须是**可复现**的：相同 seed + 相同命令序列 = 相同结果。否则：

- 回放系统无法精确重建一局；
- 不同 run 的评测结果不可比；
- 线上 bug 无法用固定 seed 稳定复现。

---

## 决策（Decision）

1. **唯一随机入口**：所有随机性走 `game/random.py` 的 `GameRandom`，Engine 持有唯一实例 `self.rng = GameRandom(seed)`（`game/engine.py` 构造函数）。
2. **禁用非确定来源**：禁止 `random.random()`、`time.time()`、`uuid` 等进入数值随机路径（AGENTS.md 提交清单明确禁止）。
3. **快照携带 RNG 状态**：`GameState` 包含 `rng_state`（随机数生成器内部状态），回放/回滚时精确恢复 RNG 状态；`engine.reset()` 重新 `GameRandom(self.seed)`（`game/engine.py` 末段 `self.rng = GameRandom(self.seed)`）。
4. **线程隔离**：LLM 决策可并发（`ThreadPoolExecutor`），但 Engine 推进是单线程，RNG 不跨线程，避免并发污染确定性。
5. **命令驱动可复现**：所有玩家输入是 `Command` 对象（命令模式），配合 seed 可从头重建整局（见 command-pattern.md）。

---

## 后果（Consequences）

**正面**
- 回放 / 评测可比；bug 可固定 seed 复现。
- 多线程 LLM 决策与单线程 Engine 推进解耦，RNG 状态不跨线程漂移。
- 状态哈希（`state_hash`）可校验回放一致性。

**负面**
- 降级随机 AI（ADR-0004 L3）也必须复用同一 `GameRandom`，否则破坏可复现——需在实现上显式传入 `rng`（`LLMPlayer.__init__(rng=...)` 已做）。
- 任何新增随机点若漏接 `GameRandom`，会留下"确定性漂移"隐患（与已知技术债"常数分散/未收敛到 constants.py"同源，需 code review 把关）。

---

## 备选方案（Alternatives Considered）

| 方案 | 结论 |
|------|------|
| 各模块直接用标准 `random` 模块 | 简单但不可复现，否决 |
| 完全无随机（纯确定性策略） | 牺牲策略多样性与探索机制，否决 |
| 用时间/UUID 做随机数 | 仅可用于不可变 id，不可用于数值随机，限定使用 |

---

## 知识缺口（Knowledge Gap，待补读确认）

- 未通读 `game/random.py` 全文：其底层是 Python `random.Random` 封装还是 `numpy`？建议补读并加单测覆盖 `seed → 取数 → getstate → setstate → 一致性`，确保 `GameState.rng_state` 的序列化/反序列化无损。当前按 architecture.md 约定以 `GameRandom` 为唯一入口，底层实现不影响本 ADR 结论。
