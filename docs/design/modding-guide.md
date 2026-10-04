# 写一个 Mod：本项目的三个扩展点

> 面向想「加玩法但不改引擎」的贡献者。
> 本文所有签名与行为均**实读代码 + 实跑验证**，验证脚本见 `examples/run_mod_demo.py`。

---

## 1. 为什么要有扩展点

原实现里，加一条命令需要同步修改**至少 5 处平行清单**：

| # | 位置 | 作用 | 现状 |
|---|---|---|---|
| 1 | `game/engine.py` `execute_command` | 9 分支 `if/elif` 分发 | ✅ 已收口到注册表 |
| 2 | `players/llm/llm_player.py:44` `COMMAND_CLASSES` | 命令名 → 命令类 | ⚠️ 仍需手工维护 |
| 3 | `players/llm/output_parser.py:333` `VALID_COMMAND_TYPES` | LLM 输出白名单 | ⚠️ 仍需手工维护 |
| 4 | `api/game_manager.py:479` `_deserialize_command` | HTTP 请求反序列化 | ⚠️ 仍需手工维护 |
| 5 | `web/src/constants/commands.ts:40,66` | 前端名称 + 图标 | ⚠️ 仍需手工维护（TS，跨语言） |

漏改任何一处的表现都是**静默不一致**：后端认、前端不认，或者 LLM 根本不知道有这条命令。
这正是「像 mod 一样加玩法」成本高的结构性原因。

**当前进度：5 处中的第 1 处已完成收口。** 引擎分发不再枚举命令类型。
其余 4 处是已知待办（见 §5），本文不把它们说成已完成。

---

## 2. 三个扩展点

### 2.1 回合相位钩子 —— 加「每回合自动结算」的被动机制

`game/turn_phase.py`。

```python
class TurnPhase(str, Enum):
    TURN_START        = "turn_start"         # 回合开始（外交到期之前）
    AFTER_PRODUCTION  = "after_production"   # 资源产出后、行军前
    AFTER_MOVEMENT    = "after_movement"     # 行军+收容撤退军后、忠诚衰减前
    AFTER_RESOLUTION  = "after_resolution"   # 战斗结算+清理死军后、胜利判定前
    TURN_END          = "turn_end"           # 回合递增后、广播回合结束前
```

```python
def register_phase_hook(
    phase: TurnPhase,
    fn: Callable[[object, Dict[str, Any]], None],   # (engine, result) -> None
    *,
    priority: int = 100,     # 越小越先执行
    name: str | None = None, # 默认取函数名
) -> None: ...
```

已核实的行为：

- **触发点**：`game/engine.py` 的 `process_turn` 在 `:851 / :895 / :927 / :1018 / :1041`
  依次触发五个相位，顺序即 `PHASE_ORDER`。
- **执行顺序**：按 `(priority, 注册序 seq)` **双键排序**。不依赖 dict/hash 迭代序
  —— 本项目的确定性底线（ADR-0002）。
- **失败策略**：钩子抛异常 → `logger.exception` + 写入 `result["hook_errors"]`
  （含 `phase` / `hook` / `error`）**并继续执行后续钩子**。
  一个 mod 的 bug 不该让整局崩，但**必须可观测**。无错误时 `result` 里不出现
  `hook_errors` 键（零行为变更）。
- **引擎自己在用**：`nature_strain`（人设代价）与 `city_morale`（民心自然变化）
  两个内置机制都以钩子形式在跑（`game/engine.py:2063-2115`）。
  这不是"预留的架子"，是在跑的生产路径。

辅助函数：`list_phase_hooks(phase) -> list[str]`、`clear_phase_hooks()`（仅供测试清理）。

### 2.2 命令注册表 —— 加玩家/LLM 可下发的主动命令

`game/command_registry.py`。

```python
def register_command(
    command_type: str,
    command_cls: Type[Command],                     # 用于 isinstance 校验
    handler: Callable[[object, Command], CommandResult],  # (engine, command)
    *,
    override: bool = False,   # 默认 False：重复注册直接 ValueError，不静默顶替
) -> None: ...
```

分发逻辑（`GameEngine.execute_command`）：查注册表 → `isinstance` 校验 →
`handler(self, command)`。未注册、或 type 命中但类不匹配，都返回
`CommandResult(success=False, description="未知命令类型: ...")`（保持原语义）。

`registered_command_types()` 返回**注册顺序**（dict 插入序，确定），可用于需要稳定顺序的遍历。

### 2.3 事件总线 —— 事后广播

`game/event_bus.py`。分工与相位钩子**不同，不是替代关系**：

- **EventBus** = 通知**已发生**的事（广播 → 订阅者被动响应，发布者不关心谁听）
- **相位钩子** = 在**固定时机执行**逻辑（注册者主动结算，可修改状态）

当前保留且**有真实产生点**的事件：`TurnStartedEvent`、`TurnEndedEvent`、
`CityCapturedEvent`、`BattleEndedEvent`、`DiplomacyMessageSentEvent`。
无产生点的 5 个事件类已删除（不预挂空类）。单个 handler 异常被捕获并记日志，不影响其他订阅者。

---

## 3. 快速上手：一个完整可运行的 mod

完整源码：`examples/mods/harvest_festival.py`（**丰年祭**：高民心城每回合 +2 金，
低民心城 -1 金；外加一条 `festival` 命令，花 300 金换民心 +8）。

核心就两段：

```python
from game.turn_phase import TurnPhase, register_phase_hook
from game.command_registry import register_command

# ① 被动机制
def hook_harvest_festival(engine, result):
    for city_id in sorted(engine.cities):        # ← 显式排序，保确定性
        city = engine.cities[city_id]
        if city.morale >= 80:
            city.gold += 2
        elif city.morale <= 20:
            city.gold = max(0, city.gold - 1)

register_phase_hook(TurnPhase.AFTER_PRODUCTION, hook_harvest_festival,
                    priority=150, name="harvest_festival")

# ② 主动命令
register_command("festival", FestivalCommand, _execute_festival)
```

**导入即注册**。之后正常跑引擎即可，`process_turn` 一行没改。

### 实测输出（`examples/run_mod_demo.py`，24 回合，`PYTHONHASHSEED=0`）

```
[0] 注册是否生效
  命令 'festival' 已注册: True
  当前已注册命令: ['develop', ..., 'declare_war', 'festival']

[1] 相位钩子是否在生产 process_turn 中被调用
  丰年加成命中次数: 148
  民不聊生扣款次数: 43
  → 钩子被执行: True

[2] 新命令是否被生产 execute_command 分发
  提交 festival 命令 → success=True  desc=洛阳 举办丰年祭，民心 +8
  民心 70 → 78
  金=0 时同命令 → success=False  desc=金不足（需 300，现有 0）

[3] 装 mod 后确定性是否保持（同 seed 跑两次）
  run A 指纹: 7e37116f160471ed
  run B 指纹: 7e37116f160471ed
  → 一致: True
```

三项全绿：钩子在**生产** `process_turn` 里被执行（不是只在测试里能跑）、
命令被**生产** `execute_command` 分发（含失败路径）、**确定性未破**。

---

## 4. 写 mod 的纪律

1. **确定性**：遍历 `set` 必须显式排序；遍历 `dict` 用插入序。浮点求和不满足结合律，
   顺序不同可能产生 1-ULP 差异，`int()` 截断后差 1，进而使整局分叉（ADR-0002）。
   本项目因集合迭代序非确定性栽过 4 次。
2. **不要吞异常**：钩子抛异常会被记录进 `result["hook_errors"]`。
   自己再包一层 `except: pass` 会让失败彻底不可观测——本项目反复栽在「静默兜底」上。
3. **不要改 `process_turn`**：如果发现必须改，说明选错了扩展点，先提 issue。
4. **注册是进程级全局**：测试里务必用 `clear_phase_hooks()` / `unregister_command()`
   清理，避免污染（见 `tests/unit/test_turn_phase.py` 的 autouse fixture）。
5. **别把「测试能过」当成「生产能跑」**：本项目最贵的教训是单测全绿而生产链路从未执行
   （`update_city` 与 `defender_generals` 两例）。验收要在**真实调用链**上证明。

---

## 5. 已知待办（诚实清单）

| 项 | 状态 | 说明 |
|---|---|---|
| 引擎命令分发收口 | ✅ 完成 | `execute_command` 不再枚举命令 |
| 相位钩子 + 引擎自用 | ✅ 完成 | 2 个内置机制在跑 |
| EventBus 去死代码 | ✅ 完成 | 删掉 5 个无产生点事件类 |
| `llm_player.COMMAND_CLASSES` 由注册表派生 | ⚠️ 待办 | 现需手工同步 |
| `output_parser.VALID_COMMAND_TYPES` 由注册表派生 | ⚠️ 待办 | 现需手工同步 |
| `api/game_manager._deserialize_command` 由注册表派生 | ⚠️ 待办 | 现需手工同步 |
| 前端 `commands.ts` 与后端注册表一致性校验 | ⚠️ 待办 | 跨语言，建议加一条测试断言「后端已注册 ⊆ 前端已声明」 |

> 简言之：**引擎侧已经是单一扩展点，全链路还不是。**
> 在 §5 全部收口之前，「加一条命令 = 改一处」这个说法不成立，本文不这么写。
