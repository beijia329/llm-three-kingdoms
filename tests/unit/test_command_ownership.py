"""命令层归属权对抗性测试（A2）

# 这个文件为什么存在

本项目是「LLM 大乱斗」——12 方势力由不同大语言模型驱动，观众看模型如何决策。
判据一：**AI 必须守规矩**。一旦某方能靠规则漏洞获益，产品价值归零。
判据二：状态和显示必须对得上。「显示成功但实际没生效」等于骗观众。

本文件对 10 类命令**逐一**构造「非所有者身份调用」场景，断言 `success is False`。
这不是防御性冗余，而是本项目历史上真实出现过漏洞的地方：
`explore` / `reward` / `attack`（调将分支）曾各漏一处归属校验，
详见 `game/engine.py:_assert_owns` 的 docstring。

# 准入纪律（本文件的硬约束）

历史上本项目多次出现「写了个永远为真的断言」当成合格章。**假绿比没测试更糟
—— 它给未来的错误修改发许可证。** 因此本文件遵守：

1. **每条新断言都做过「改坏验证」**：临时把被保护的校验改坏，证明该测试变红，
   再还原证明变绿。逐条记录写在各测试的 docstring 里，格式：
   `<测试函数名> → 改坏 <具体改了哪一行> → N failed → 还原 → M passed`
2. **不写死基线值**（不写 `trust == 50`、`garrison == 4000`），断言**增量**或**行为**。
3. **零观测先跑阳性对照**：断言「己方城探索成功」之前，必须先证明同样构造下
   换成己方城确实能成功，否则无法区分「校验生效」和「这个操作从来就不可能成功」。
4. **不依赖随机命中**：涉及 explore/rumor 概率处，或用固定 seed，
   或直接构造前提（如把 `last_explore_turn` 设为确定值），不写会偶发失败的测试。

# 覆盖矩阵

| 命令 | 被保护的不变量 | 状态 |
|---|---|---|
| develop | 只能发展己方城市 | A1 已修，本文件回归保护 |
| recruit | 只能征自己城的兵 | A1 已修，本文件回归保护 |
| attack | 只能带己方且未被俘将领出征 | A1 已修，本文件回归保护 |
| reward | 只能赏己方将领，且由己方金库付款 | A1 已修，本文件回归保护 |
| explore | 只能探索己方城市 | A1 已修，本文件回归保护 |
| rumor | 间谍必须是自己人 | 第二批 B3 已修，本文件回归保护 |
| message | 发信方必须是真实势力 | 第二批 幽灵闸门 已修，本文件回归保护 |
| propose_alliance | 结盟方必须是真实势力 | 第二批 幽灵闸门 已修，本文件回归保护 |
| declare_war | 宣战方必须是真实势力 | 第二批 幽灵闸门 已修，本文件回归保护 |
| truce | 停战方必须是真实势力，且仅交战态可求和 | 第三批 #3 新增，本文件回归保护 |

后 4 项在 A1 时尚属未覆盖缺口，第二批已统一修复：
- `rumor` 的间谍归属在 `_execute_rumor` 内校验（见 B3 注释）；
- `message` / `propose_alliance` / `declare_war` 的发起方存在性，
  由 `execute_command` 分发前单一闸门 + 各 `_execute_*` 方法内的二次校验挡住
  （幽灵势力无法建关系行 / 刷信任 / 结盟）。
原 `xfail(strict=True)` 标记已在修复后摘掉、断言翻正，缺口不再被静默遗忘。

# 改坏验证记录（实测数据，逐条勿删；由 tests/unit/_mutation_check_tmp.py 复现）

⚠️ 下列「N failed」里的 N 是**只跑该条/该类测试**的结果，不是全文件。
全文件基线：31 passed（其中 4 条 xfail）。

## develop（`game/engine.py:534`）
- 改坏 `if city.faction != cmd.faction:` → `if False:` → **2 failed** → 还原 → 3 passed
  （`test_develop_enemy_city_rejected` + `test_develop_enemy_city_no_side_effect` 双双变红；
   阳性对照 `..._succeeds_positive_control` 仍绿，说明它测的是另一侧）

## recruit（`game/engine.py:552`）
- 改坏同上→ **2 failed** → 还原 → 3 passed

## attack（`game/engine.py:599`）
- 改坏 `denied = _assert_owns(...)` → `denied = None` → **1 failed** → 还原 → 5 passed
- ⚠️ **首次写错了**：当时敌将放在敌方城 `b.id`，改坏后测试**依然全绿**——
  因为被 `if general.location != from_city.id` 分支里的「将领不在 from_city」拦住了。
  断言过了，但过的原因不对，**这就是假绿**。改为 `location=a.id`（出发城）
  + `is_captured=False` 后才真正捕获该 guard。
- 改坏 `if general.is_captured:` → `if False:`（`game/engine.py:603`）
  → **1 failed** → 还原 → 1 passed

## reward（`game/engine.py:707` / `729`）
- 改坏第一道（`general.faction`）→ **1 failed** → 还原 → 4 passed
- 改坏第二道（`city.faction`）→ **1 failed** → 还原 → 1 passed
- ⚠️ `test_reward_enemy_general_does_not_drain_enemy_treasury`（敌将驻**敌方城**，
  即原缺陷复现姿势）**只改坏一道时仍然全绿** —— 第二道 guard 会接手拦住。
  **同时改坏两道**（= 还原 A1 修复前状态）→ **1 failed**（敌国金库被扣 500）
  → 还原 → 1 passed。该测试守的是「两道合起来」，单道隔离由另两条承担。

## explore（`game/engine.py:757`）
- 改坏 `denied = _assert_owns(...)` → `denied = None` → **3 failed** → 还原 → 8 passed
  （敌方城 / 无副作用 / 中立城 三条同时变红）

## explore 成功分支（`game/engine.py:812`）
- 改坏 `city.generals.append(gen_id)` → `pass`（建了将领但不登记守将名单）
  → **1 failed** → 还原 → 1 passed
- 这条专门覆盖 `_execute_explore` 的**成功**路径（797-818）。
  上面那批只测被拒的路径，实测这段建将逻辑**完全没被覆盖** ——
  而它恰恰决定了新将领被算进**哪座城**的战力。

## explore 冷却（`game/engine.py:776/777/778`）
- 改坏 `if elapsed < EXPLORE_COOLDOWN_TURNS:` → `if False:` → **2 failed** → 还原 → 3 passed
- 改坏 `elapsed = self.turn - ...` → `elapsed = cmd.turn - ...`
  → **1 failed** → 还原 → 1 passed（抗伪造 cmd.turn）
- 改坏 `if city.last_explore_turn is not None:` → 全局化
  → **1 failed** → 还原 → 1 passed（冷却须按城记）

## `_assert_owns` 自身（`game/engine.py:160/166/172`）
- 删掉 `owner is None` 分支的拒绝 → **1 failed** → 还原 → 1 passed
- `if owner != actor:` → `if False:` → **1 failed** → 还原 → 1 passed
- 通过时 `return None` → `return CommandResult(success=True,...)`
  → **1 failed** → 还原 → 1 passed（防返回值语义被反转后全部校验静默失效）

## 原未修缺口（第二批已修复，xfail 标记已摘、断言翻正）
- `test_rumor_enemy_general_as_spy_rejected`：原可用敌方将领当间谍抬高成功率。
  🔴 这条最初写成「掷一次骰子看 success」，结果 strict xfail 变成 XPASS 而报红——
  掷输了就"通过"了。**已改为把 `spread_rumor` 的 RNG 打成常量 0.0**，
  让 success 只由归属校验决定，与骰子无关。现 `_execute_rumor` 校验间谍归属，
  该测试已无 xfail、直接绿。
- `test_declare_war_ghost_faction_rejected`：幽灵势力能宣战并建出关系行 —— 第二批
  幽灵闸门修复。
- `test_propose_alliance_ghost_faction_rejected`：幽灵势力刷满信任后能结盟 —— 第二批
  幽灵闸门修复。
- `test_message_ghost_sender_rejected`：幽灵势力能发信并刷信任 —— 第二批
  幽灵闸门修复。

## truce（第三批 #3 新增，`game/engine.py:_execute_truce`）
- 改坏幽灵闸门（`if cmd.faction not in FACTIONS:` → `if False:`）→ 1 failed → 还原 → 通过
  （场景特意先把 `ghost↔liubei` 直接置为 WAR，让幽灵闸门成为唯一拦截点；
   否则幽灵势力会被「非交战不得停战」那道闸顺手拦下，看起来绿但原因不对）
- 改坏交战闸门（`if status != DiplomaticStatus.WAR:` → `if False:`）
  → 1 failed → 还原 → 通过
- 改坏自停战闸门（`if cmd.to == cmd.faction:` → `if False:`）
  🔴 首版只断言 `success is False` 时**仍绿** —— 自己与自己没有关系行 →
  get_relation 返回 None → 状态 NEUTRAL → 被 WAR 闸门顺手拦下（假绿）。
  补断言 `"自己" in result.description` 后才变红 → 还原 → 通过
- 改坏成功路径（`set_status(..., TRUCE ...)` → `NEUTRAL`）→ 2 failed → 还原 → 通过
- 改坏 `update_turn` 停战到期分支（`elif ... TRUCE ...:` → `elif False:`）
  → 1 failed → 还原 → 通过（证明命令层写下的到期回合真的被引擎回合消费）
"""

from __future__ import annotations

import copy

import pytest

from game.constants import EXPLORE_COOLDOWN_TURNS, FACTIONS
from game.data_loader import load_game_data
from game.engine import GameEngine
from game.models import (
    AttackCommand,
    DeclareWarCommand,
    DevelopCommand,
    DiplomaticStatus,
    ExploreCommand,
    MessageCommand,
    ProposeAllianceCommand,
    RecruitCommand,
    RewardCommand,
    RumorCommand,
    TruceCommand,
)

# 本文件所有测试的基准构造里，攻击方 = caocao，守方 = liubei，
# 第三座城归 mateng（一个与双方都无外交关系的第三方）。
# 选这几个是刻意的：`can_attack` 只看外交关系，第三方保证「能到达且外交允许」，
# 这样阴性用例失败就一定是被测的归属校验，而不是被可达性或外交挡住。
ATTACKER = "caocao"
DEFENDER = "liubei"
THIRD_PARTY = "mateng"


@pytest.fixture(scope="module")
def _engine_template():
    """构建一次开局引擎作为模板，供各测试 deepcopy。

    `init_game` 单次要4.2 秒（本文件 31 个测试各建一次 = 2 分钟，
    而全量套件本身才 9 分钟 —— 相当于给每次 CI 白加 20% 时长）。
    deepcopy 只需 0.32 秒且已验证：城市/将领/军队字典与对象均深拷贝独立，
    模板本身不被污染，副本之间互不干扰。

    用 module 作用域而非 session：模板只在内存里，不跨测试文件共享状态，
    避免某个文件的测试意外改到别人的基准。
    """
    engine = GameEngine(seed=1)
    engine.init_game(load_game_data())
    return engine


def _build(template):
    """从模板深拷贝出一局干净对局，返回 (engine, 攻方城, 守方城, 第三方城)。

    金库/守军给足额度，是为了让「己方操作被误拒」与「越权操作生效」在数值上可区分：
    钱不够时命令会因资源失败而返回 success=False，那样的假绿毫无意义。

    🔴 选城不按 `ids[0]/[1]/[2]` 的位置，而是按**地图连通性**挑：
    攻方城与守方城必须**互相可达**（attack 的阳性对照要真能出征），
    且守方城必须与攻方城**不同**。用位置下标取城看着简洁，
    但它把「哪两座城相邻」这件事藏进了对局初始化顺序里 ——
    一旦地图生成顺序变化（这正是 A3 前后改过的地方），
    失败会以「归属权校验没生效」的形式出现，**误诊方向完全相反**。
    所以这里显式按距离挑，并断言挑到了（挑不到就直接 fail，不静默退化）。
    """
    engine = copy.deepcopy(template)
    ids = sorted(engine.cities.keys())
    a = engine.cities[ids[0]]
    # 找一座与 a 相通、且不是 a 自己的城当守方城
    b = None
    for cid in ids[1:]:
        if engine.map.get_distance(a.id, cid) > 0:
            b = engine.cities[cid]
            break
    assert b is not None, "找不到与攻方城相连的城市，无法构造对局"
    # 第三方城：与 a 相连、且不是 a/b 的任意一座（用于中立城等场景）
    c = next(
        engine.cities[cid]
        for cid in ids
        if cid not in (a.id, b.id) and engine.map.get_distance(a.id, cid) > 0
    )

    a.faction, b.faction, c.faction = ATTACKER, DEFENDER, THIRD_PARTY
    a.gold = b.gold = c.gold = 5000
    a.garrison = b.garrison = c.garrison = 2000
    return engine, a, b, c


def _general_of(engine, faction, captured=False, location=None):
    """取一个指定势力的将领，改造归属与被俘状态后返回。

    直接改字段而不重新 new General()：避免 pydantic 校验与 id 唯一性检查
    掩盖我们要测的东西。
    """
    general = next(g for g in engine.generals.values() if g.faction == faction)
    general.is_captured = captured
    if location is not None:
        general.location = location
        city = engine.cities.get(location)
        if city is not None and general.id not in city.generals:
            city.generals.append(general.id)
    return general


def _snapshot(city, fields=("gold", "food", "garrison", "morale", "population", "level")):
    """取城市关键数值的快照，用于断言「被拒的命令没有留下任何副作用」。

    只断言 success=False 是不够的：一个实现可能先扣了钱再返回失败。
    判据二要求状态和显示对得上，所以这里比对数值是否原封不动。
    """
    return {f: getattr(city, f) for f in fields}


def _force_rumor_always_succeeds(engine):
    """把流言的骰子换成常量 0.0，让「掷骰成功」恒成立。

    `DiplomacySystem.spread_rumor` 的判定是 `if self._rng.random() < success_chance`，
    而 success_chance 最低也有 0.5。把 random() 固定成 0.0，
    这个分支恒为真 —— 于是命令的 success 只取决于**归属校验**，
    不再取决于骰子。用固定 seed 做不到这一点：那是「这次恰好中」，
    换个 seed 或并行执行就翻脸（本文件首次运行时就是这么翻的：
    单次投掷恰好失败，导致 strict xfail 变成 XPASS 而报红）。

    这不是为了「让测试变绿」而放宽断言 —— 恰恰相反，它把一个
    概率性断言换成了确定性断言，让测试在任何 seed 下结果一致。
    """
    engine._diplomacy_system._rng.random = lambda: 0.0


# ============================================================
# 1. develop —— 只能发展己方城市
# ============================================================


class TestDevelopOwnership:
    """发展命令的归属权（A1 修复的回归保护）"""

    def test_develop_enemy_city_rejected(self, _engine_template):
        """攻方发展守方城市必须被拒。

        改坏验证：改坏 game/engine.py:534（`if city.faction != cmd.faction:`
        改为 `if False:`）→ 1 failed → 还原 → 通过
        """
        engine, a, b, _ = _build(_engine_template)
        result = engine._execute_develop(
            DevelopCommand(turn=1, faction=ATTACKER, city=b.id, develop_type="economy")
        )
        assert result.success is False

    def test_develop_own_city_succeeds_positive_control(self, _engine_template):
        """阳性对照：同样构造换成**己方**城市就必须成功。

        没有这条，无法区分「归属校验生效」和「develop 无论如何都失败」——
        后者会让上面那条阴性断言变成假绿。
        改坏验证：改坏 game/engine.py:534 → 1 failed → 还原 → 通过
        """
        engine, a, b, _ = _build(_engine_template)
        gold_before = a.gold
        result = engine._execute_develop(
            DevelopCommand(turn=1, faction=ATTACKER, city=a.id, develop_type="economy")
        )
        assert result.success is True, f"己方城市发展应成功，实际: {result.description}"
        # 断言增量而非基线：钱必须真的少了，且少了多少由 develop 规则决定
        assert a.gold < gold_before, "发展经济后己方金库应减少"

    def test_develop_enemy_city_no_side_effect(self, _engine_template):
        """被拒的发展不得改动守方城市任何数值。

        改坏验证：改坏 game/engine.py:534 → 1 failed（守方 gold/food 被扣）→ 还原 → 通过
        """
        engine, a, b, _ = _build(_engine_template)
        before = _snapshot(b)
        result = engine._execute_develop(
            DevelopCommand(turn=1, faction=ATTACKER, city=b.id, develop_type="economy")
        )
        assert result.success is False
        assert _snapshot(b) == before, "被拒的发展命令不得留下任何痕迹"


# ============================================================
# 2. recruit —— 只能征自己城的兵
# ============================================================


class TestRecruitOwnership:
    """征兵命令的归属权（A1 修复的回归保护）"""

    def test_recruit_enemy_city_rejected(self, _engine_template):
        """攻方在守方城市征兵必须被拒。

        改坏验证：改坏 game/engine.py:552（`if city.faction != cmd.faction:`
        改为 `if False:`）→ 1 failed → 还原 → 通过
        """
        engine, a, b, _ = _build(_engine_template)
        result = engine._execute_recruit(
            RecruitCommand(turn=1, faction=ATTACKER, city=b.id, troops=500)
        )
        assert result.success is False

    def test_recruit_enemy_city_no_side_effect(self, _engine_template):
        """被拒的征兵不得扣除守方城市的兵源或金库。

        这是本组最关键的一条：修复前若校验缺失，攻方会**白嫖守方500 兵力**
        （守方 food/gold 被扣、garrison 反而增加）。
        改坏验证：改坏 game/engine.py:552 → 1 failed → 还原 → 通过
        """
        engine, a, b, _ = _build(_engine_template)
        before = _snapshot(b)
        result = engine._execute_recruit(
            RecruitCommand(turn=1, faction=ATTACKER, city=b.id, troops=500)
        )
        assert result.success is False
        assert _snapshot(b) == before, "被拒的征兵不得改动守方城市"

    def test_recruit_own_city_succeeds_positive_control(self, _engine_template):
        """阳性对照：征自己城的兵必须成功且真的增加了守军。

        改坏验证：改坏 game/engine.py:552 → 1 failed → 还原 → 通过
        """
        engine, a, b, _ = _build(_engine_template)
        garrison_before = a.garrison
        food_before = a.food
        result = engine._execute_recruit(
            RecruitCommand(turn=1, faction=ATTACKER, city=a.id, troops=100)
        )
        assert result.success is True, f"己方征兵应成功，实际: {result.description}"
        assert a.garrison > garrison_before, "征兵后守军应增加"
        assert a.food < food_before, "征兵消耗口粮"


# ============================================================
# 3. attack —— 只能带己方且未被俘的将领出征
# ============================================================


class TestAttackOwnership:
    """进攻命令的将领归属权（A1-c 修复的回归保护）"""

    def test_attack_enemy_general_at_departure_city_rejected(self, _engine_template):
        """攻方指定**敌方将领**出征必须被拒。

        🔴 场景是精确设计过的，**不是随手写的**：
        目标将领必须 `location == from_city.id` 且 `is_captured == False`。
        只有这样，`_execute_attack` 里除归属权外的所有拦截点都不成立：
          - `is_captured` 为 False → 被俘校验不触发
          - `location == from_city.id` → 整个「调将合法性」分支被跳过
        于是**归属权是唯一的拦截点**，测试失败必然归因于它。

        改坏验证（第一版曾写成 `location=b.id` 的敌将，结果是**假绿**）：
        改坏 game/engine.py:599 → 仍 5 passed，因为敌将站在敌方城时被
        分支内的「将领不在 from_city」拦住了 —— 断言过了，但过的原因不对。
        改成 `location=a.id` + `is_captured=False` 后，
        改坏 game/engine.py:599 → 1 failed → 还原 → 1 passed。
        """
        engine, a, b, _ = _build(_engine_template)
        enemy = _general_of(engine, DEFENDER, captured=False, location=a.id)

        # 前置断言：确保除归属权外没有任何其他拦截点会生效
        assert enemy.faction != ATTACKER
        assert enemy.is_captured is False, "前置：目标将领不能是战俘，否则被俘校验会先拦住"
        assert enemy.location == a.id, "前置：目标将领必须驻在出发城，否则会落进调将分支"

        result = engine._execute_attack(
            AttackCommand(turn=1, faction=ATTACKER, from_city=a.id,
                          to_city=b.id, troops=100, general=enemy.id)
        )
        assert result.success is False, "敌方将领不得带兵出征"

    def test_attack_enemy_captive_at_departure_city_rejected(self, _engine_template):
        """原缺陷的**精确触发条件**：敌方战俘恰好驻在出发城。

        修复前 `general.faction == cmd.faction` 与 `not general.is_captured`
        写在 `if general.location != from_city.id:` 分支内部 ——
        目标将领恰好驻在出发城时整段被跳过，于是任何一方都能带着**敌方战俘**
        出征，且该战俘会被算进进攻方战力。
        这条测试的价值全在 `location=a.id` 这个前提上，去掉它就退化成上一条。

        改坏验证：改坏 game/engine.py:599 → 1 failed → 还原 → 通过
        """
        engine, a, b, _ = _build(_engine_template)
        captive = _general_of(engine, DEFENDER, captured=True, location=a.id)
        # 前置断言：确保真的构出了「战俘驻在出发城」这个特殊状态
        assert captive.location == a.id
        assert captive.is_captured is True
        assert captive.faction != ATTACKER

        result = engine._execute_attack(
            AttackCommand(turn=1, faction=ATTACKER, from_city=a.id,
                          to_city=b.id, troops=100, general=captive.id)
        )
        assert result.success is False, "带敌方战俘出征必须被拒"

    def test_attack_enemy_captive_no_side_effect(self, _engine_template):
        """带敌方战俘出征被拒时，不得凭空产生军队、不得扣守军。

        判据二：光看返回 False 不够 —— 一个「先扣兵再报错」的实现
        同样会返回 False，但战场已经被污染了。
        改坏验证：改坏 game/engine.py:599 → 1 failed（凭空多出一支军队 + 守军被扣）
        → 还原 → 通过
        """
        engine, a, b, _ = _build(_engine_template)
        captive = _general_of(engine, DEFENDER, captured=True, location=a.id)
        armies_before = len(engine.armies)
        garrison_before = a.garrison

        result = engine._execute_attack(
            AttackCommand(turn=1, faction=ATTACKER, from_city=a.id,
                          to_city=b.id, troops=100, general=captive.id)
        )
        assert result.success is False
        assert len(engine.armies) == armies_before, "被拒的进攻不得创建军队"
        assert a.garrison == garrison_before, "被拒的进攻不得扣减出发城守军"
        assert captive.location == a.id, "被拒的进攻不得改动目标将领位置"

    def test_attack_own_captured_general_rejected(self, _engine_template):
        """己方战俘也不得出征（归属权对，但被俘状态独立生效）。

        这条与前三条是不同的失效模式：前三条错在「归属不对」，
        这条错在「战俘身份」。两者都在 A1-c 里被前置到统一位置，
        但必须各自独立断言 —— 只测归属权会漏掉 `is_captured` 被摘掉的情况。

        改坏验证：改坏 game/engine.py:603（`if general.is_captured:`
        改为 `if False:`）→ 1 failed → 还原 → 通过
        """
        engine, a, b, _ = _build(_engine_template)
        own_captive = _general_of(engine, ATTACKER, captured=True, location=a.id)
        assert own_captive.faction == ATTACKER, "前置：这条测的是己方战俘"

        result = engine._execute_attack(
            AttackCommand(turn=1, faction=ATTACKER, from_city=a.id,
                          to_city=b.id, troops=100, general=own_captive.id)
        )
        assert result.success is False, "战俘不得出征"
        assert len(engine.armies) == 0, "被拒的进攻不得创建军队"

    def test_attack_own_general_succeeds_positive_control(self, _engine_template):
        """阳性对照：带己方自由将领出征必须成功。

        没有这条，`test_attack_*_rejected` 全绿也可能只是因为
        attack 在这个构造下根本走不通（外交/距离/兵力任一挡住），
        阴性断言就成了假绿。
        改坏验证：改坏 game/engine.py:599 → 1 failed → 还原 → 通过
        """
        engine, a, b, _ = _build(_engine_template)
        own = _general_of(engine, ATTACKER, captured=False, location=a.id)
        result = engine._execute_attack(
            AttackCommand(turn=1, faction=ATTACKER, from_city=a.id,
                          to_city=b.id, troops=100, general=own.id)
        )
        assert result.success is True, f"己方将领出征应成功，实际: {result.description}"
        assert len(engine.armies) == 1, "成功出征应创建一支军队"
        assert a.garrison < 2000, "出征应扣减出发城守军"


# ============================================================
# 4. reward —— 只能赏己方将领，且由己方金库付款
# ============================================================


class TestRewardOwnership:
    """赏赐命令的归属权（A1-a 修复的回归保护，两道校验各自独立断言）"""

    def test_reward_enemy_general_rejected(self, _engine_template):
        """赏赐敌方将领必须被拒（第一道校验：被赏赐者归属）。

        🔴 场景是精确设计过的：敌方将领必须驻在**攻方自己的城市**里。
        只有这样，第二道校验（支付城市归属）会放行 ——
        付款城就是攻方自己的城，`city.faction == ATTACKER` 成立。
        于是**第一道校验成为唯一拦截点**，失败必然归因于它。

        改坏验证（第一版曾把敌将放在敌方城 `b.id`，结果是**假绿**）：
        改坏 game/engine.py:707 → 仍 4 passed，因为敌将站在敌城时
        被第二道「支付城市不属于 caocao」拦住了 —— 断言过了，但原因不对。
        改成敌将驻 `a.id` 后，改坏 game/engine.py:707
        → 1 failed → 还原 → 1 passed。
        """
        engine, a, b, _ = _build(_engine_template)
        enemy = _general_of(engine, DEFENDER, captured=False, location=a.id)
        enemy.loyalty = 70

        # 前置断言：确认第二道校验不会先拦（付款城必须是攻方自己的城）
        assert a.faction == ATTACKER, "前置：付款城必须属于攻方，否则第二道校验会先拦"
        assert enemy.location == a.id, "前置：敌将必须驻在攻方城内"

        result = engine._execute_reward(
            RewardCommand(turn=1, faction=ATTACKER, general=enemy.id, gold=500)
        )
        assert result.success is False, "敌方将领不得被我方赏赐"

    def test_reward_enemy_general_does_not_drain_enemy_treasury(self, _engine_template):
        """核心危害：修复前「赏赐敌将」花的是**敌国金库**。

        支付城市由 `general.location` 反推，而修复前全程不判 `general.faction`，
        于是 caocao 赏赐驻在 liubei 城的刘备，钱从 liubei 国库出。
        这是一条「白嫖敌国资源」的直接漏洞，也是本组最有价值的断言：
        它断言的是**两个金库都没被动**，而不只是返回 False。

        🔴 改坏验证必须**同时改坏两道 guard** 才变红 —— 这是本文件最重要的一条留痕：
        本测试把敌将放在**敌方城**（这正是原缺陷的复现姿势），
        于是当只改坏第一道 guard 时，第二道「支付城市归属」会接手拦住，
        测试**依然全绿**。实测：
          - 只改坏 game/engine.py:707（第一道）→ 仍 1 passed ← 单改是假绿
          - 同时改坏 game/engine.py:707 + 729（还原 A1 修复前状态）
            → 1 failed（敌国金库被扣 500）→ 还原 → 1 passed
        结论：这条测的是「两道 guard 合起来守住了金库」，
        单道的隔离验证由上面两条（`..._rejected` / `..._in_enemy_city_rejected`）承担。
        """
        engine, a, b, _ = _build(_engine_template)
        enemy = _general_of(engine, DEFENDER, captured=False, location=b.id)
        enemy.loyalty = 70
        own_gold_before, enemy_gold_before = a.gold, b.gold
        loyalty_before = enemy.loyalty

        result = engine._execute_reward(
            RewardCommand(turn=1, faction=ATTACKER, general=enemy.id, gold=500)
        )
        assert result.success is False
        assert b.gold == enemy_gold_before, "敌国金库不得被扣"
        assert a.gold == own_gold_before, "己方金库不得为一次失败的赏赐买单"
        assert enemy.loyalty == loyalty_before, "敌方将领忠诚度不得被改变"

    def test_reward_own_general_in_enemy_city_rejected(self, _engine_template):
        """第二道校验：支付城市也必须属于本势力。

        第一道只挡「赏赐敌将」。这一条挡的是另一个组合：
        **己方将领**站在敌方城市里 —— 第一道会放行（他确实是 caocao 的），
        但付款城市由 `general.location` 反推出来是敌城，钱照样从敌国出。
        只测第一道会漏掉这一种。

        改坏验证：改坏 game/engine.py:729（支付城市那道 `_assert_owns`
        改为 `denied = None`）→ 1 failed → 还原 → 通过
        """
        engine, a, b, _ = _build(_engine_template)
        own = _general_of(engine, ATTACKER, captured=False, location=b.id)
        own.loyalty = 70
        own_gold_before, enemy_gold_before = a.gold, b.gold

        result = engine._execute_reward(
            RewardCommand(turn=1, faction=ATTACKER, general=own.id, gold=500)
        )
        assert result.success is False, "己方将领站在敌城时赏赐必须被拒"
        assert b.gold == enemy_gold_before, "敌国金库不得被扣"
        assert a.gold == own_gold_before, "己方金库不得被扣"
        assert own.loyalty == 70, "忠诚度不得被改变"

    def test_reward_own_general_succeeds_positive_control(self, _engine_template):
        """阳性对照：赏赐驻在己方城的己方将领必须成功并真的扣己方钱。

        改坏验证：改坏 game/engine.py:707 → 1 failed → 还原 → 通过
        """
        engine, a, b, _ = _build(_engine_template)
        own = _general_of(engine, ATTACKER, captured=False, location=a.id)
        own.loyalty = 50
        gold_before, loyalty_before = a.gold, own.loyalty

        result = engine._execute_reward(
            RewardCommand(turn=1, faction=ATTACKER, general=own.id, gold=500)
        )
        assert result.success is True, f"赏赐己方将领应成功，实际: {result.description}"
        assert a.gold < gold_before, "赏赐应从己方金库扣款"
        assert own.loyalty > loyalty_before, "赏赐应提升忠诚度"
        assert b.gold == 5000, "守方金库不得因守方将领的赏赐而变动"


# ============================================================
# 5. explore —— 只能探索己方城市（含 A3 冷却）
# ============================================================


class TestExploreOwnership:
    """探索命令的归属权（A1-b 修复的回归保护）"""

    def test_explore_enemy_city_rejected(self, _engine_template):
        """探索敌方城市必须被拒。

        改坏验证：改坏 game/engine.py:757（`denied = _assert_owns(...)`
        改为 `denied = None`）→ 1 failed → 还原 → 通过
        """
        engine, a, b, _ = _build(_engine_template)
        result = engine._execute_explore(
            ExploreCommand(turn=1, faction=ATTACKER, city=b.id)
        )
        assert result.success is False

    def test_explore_enemy_city_no_injected_general(self, _engine_template):
        """核心危害：修复前会把 `explored_xx` 塞进敌方 `city.generals`。

        危害不止「白嫖人才」：新将领 `faction` 记的是**攻击方**，
        location 记的是敌方城市 id，并被 append 进敌方守将名单——
        `battle_scheduler.stationed_generals` 直接读这个列表算守方平均统帅/勇武，
        于是凭空给守方加成。所以这里断言敌方守将名单**逐项不变**，
        而不只是 success 为 False。

        改坏验证：改坏 game/engine.py:757 → 1 failed（敌方守将名单被塞进 explored_*）
        → 还原 → 通过
        """
        engine, a, b, _ = _build(_engine_template)
        defenders_before = list(b.generals)
        n_generals_before = len(engine.generals)

        result = engine._execute_explore(
            ExploreCommand(turn=1, faction=ATTACKER, city=b.id)
        )
        assert result.success is False
        assert list(b.generals) == defenders_before, "敌方守将名单不得被改动"
        assert len(engine.generals) == n_generals_before, "不得凭空创建将领"
        assert not any(g.startswith("explored") for g in engine.generals), \
            "不得出现任何探索产物"

    def test_explore_neutral_city_rejected(self, _engine_template):
        """中立城（无主之地）同样必须被拒 —— 谁都不能白嫖。

        `faction == "neutral"` 的城不属于任何势力。若可被任意方探索，
        就是与「探索敌方城」同类的白嫖漏洞，只是换个外壳。

        改坏验证：改坏 game/engine.py:757 → 1 failed → 还原 → 通过
        """
        engine, a, b, c = _build(_engine_template)
        c.faction = "neutral"
        generals_before = list(c.generals)

        result = engine._execute_explore(
            ExploreCommand(turn=1, faction=ATTACKER, city=c.id)
        )
        assert result.success is False, "中立城探索必须被拒"
        assert list(c.generals) == generals_before, "中立城守将名单不得被改动"

    def test_explore_own_city_registers_new_general_in_that_city(self, _engine_template):
        """探索**成功**时，新将领必须登记在**被探索的那座城**的守将名单里。

        为什么要单独测成功分支：A1 的危害正是「新将领 location 记的是敌方城市 id、
        faction 记的是攻击方，却被 append 进敌方 `city.generals`」。只测被拒的路径
        覆盖不到 `game/engine.py:797-818` 这段建将逻辑（实测未覆盖），
        而恰恰是这段代码决定新将领**被算进哪座城的战力**——
        `battle_scheduler.stationed_generals` 直接读这个列表。

        做法：把 `GeneralSystem.explore` 的**成功概率**固定住
        （morale 拉满不够，仍是概率事件），改为直接控制
        `POTENTIAL_GENERALS` 之外的手段太重；这里选择
        **多次尝试直到命中**，但每次都换新城市副本以绕开冷却 ——
        命中后立刻断言，**不依赖任何具体 seed 的具体结果**，
        且用 morale=100 把单次成功率提到 0.4，命中只是时间问题。
        若 200 次仍未命中，测试会 fail（而不是静默跳过），
        所以它不会退化成「永远绿」。

        改坏验证：改坏 `game/engine.py:812`（`city.generals.append(gen_id)`
        改为 `pass`，即不登记守将名单）
        → 1 failed → 还原 → 通过
        """
        engine, a, b, _ = _build(_engine_template)
        a.morale = 100  # 成功率提到 0.4
        engine.turn = 1

        found_data = None
        for step in range(200):
            engine.turn = step + 1  # 每次推进回合，绕开 A3 冷却
            a.last_explore_turn = None
            result = engine._execute_explore(
                ExploreCommand(turn=engine.turn, faction=ATTACKER, city=a.id)
            )
            if result.data and result.data.get("general_id"):
                found_data = result.data
                break

        assert found_data is not None, (
            "200 次高民心探索一次都没发现人才 —— 探索链路可能已失效，"
            "本测试会失去意义（不能用「反正不覆盖」蒙过去）"
        )

        gen_id = found_data["general_id"]
        # 新将领必须真实存在于 generals 表中
        assert gen_id in engine.generals, "新将领必须登记进 generals"
        new_general = engine.generals[gen_id]
        # 归属与位置必须都属于攻方与被探索的城 —— 这是判据二「状态和显示对得上」
        assert new_general.faction == ATTACKER, "新将领必须属于发起探索的势力"
        assert new_general.location == a.id, "新将领的位置必须是被探索的城市"
        # 关键：必须出现在**被探索城市**的守将名单里
        assert gen_id in a.generals, "新将领必须登记进被探索城市的守将名单"
        # 守方城市名单不得被牵连
        assert gen_id not in b.generals, "新将领不得出现在其他城市的守将名单里"

    def test_explore_own_city_succeeds_positive_control(self, _engine_template):
        """阳性对照：探索己方城市必须成功。

        这条是整个 explore 分组的锚 —— 上面三条阴性断言只有在
        「换成己方城确实能成功」的前提下才有意义。
        改坏验证：改坏 game/engine.py:757 → 1 failed → 还原 → 通过
        """
        engine, a, b, _ = _build(_engine_template)
        a.morale = 100  # 提高命中率，让两种分支都更容易走到
        a.last_explore_turn = None
        engine.turn = 1

        result = engine._execute_explore(
            ExploreCommand(turn=1, faction=ATTACKER, city=a.id)
        )
        # 关键锚点：无论本次有没有挖到人才，**归属权合法就必须成功**
        assert result.success is True, f"己方城市探索应成功，实际: {result.description}"
        # 然后按 data 里有没有 general_id 分流断言。
        # 判定依据是 CommandResult 的 data（探索成功时才带 general_id），
        # 不用 hasattr 去探测一个根本不存在的属性 —— 那种写法在
        # 「属性被改名」时会静默走错分支，属于自欺欺人的断言。
        gen_id = result.data.get("general_id") if result.data else None
        if gen_id:
            assert gen_id.startswith("explored"), f"新将领 id 命名异常: {gen_id}"
            assert gen_id in a.generals, "新将领必须登记在己方城市守将名单里"
            assert gen_id not in b.generals, "新将领不得出现在敌方城市守将名单里"
        else:
            # 没挖到也算合法结果，但必须**明确说出来**，
            # 不能是一个空 data + 空描述（那是判据二说的「骗观众」）
            assert result.description, "未发现人才时必须给出说明"
            assert "人才" in result.description

    def test_explore_cooldown_blocks_second_same_turn(self, _engine_template):
        """同回合对**同一座城**探索第二次必须被冷却拒（A3）。

        冷却记在 `City.last_explore_turn`，与A1 的归属校验是两回事：
        归属校验答「能不能」，冷却答「这次能不能」。混在一起测就说不清在测哪个。
        改坏验证：改坏 game/engine.py:778（`if elapsed < EXPLORE_COOLDOWN_TURNS:`
        改为 `if False:`）→ 1 failed → 还原 → 通过
        """
        engine, a, b, _ = _build(_engine_template)
        engine.turn = 1
        a.last_explore_turn = None

        first = engine._execute_explore(ExploreCommand(turn=1, faction=ATTACKER, city=a.id))
        assert first.success is True, "首次探索应成功（对照组）"

        second = engine._execute_explore(ExploreCommand(turn=1, faction=ATTACKER, city=a.id))
        assert second.success is False, "同回合第二次探索同一座城必须被冷却拒"
        assert second.data.get("cooling_down") is True, "失败原因必须标明是冷却"
        assert second.data.get("turns_left", 0) > 0

    def test_explore_cooldown_expires_after_turns(self, _engine_template):
        """冷却期满后必须能再探索 —— 防止「改成永久锁死」这种反向坏修改。

        与上一条成对：上一条防「冷却缺失」，这条防「冷却过头」。
        只有一条的话，把冷却写成永不复解同样能全绿。
        改坏验证：改坏 game/engine.py:778 → 1 failed → 还原 → 通过
        """
        engine, a, b, _ = _build(_engine_template)
        engine.turn = 1
        a.last_explore_turn = None
        engine._execute_explore(ExploreCommand(turn=1, faction=ATTACKER, city=a.id))

        engine.turn = 1 + EXPLORE_COOLDOWN_TURNS
        result = engine._execute_explore(
            ExploreCommand(turn=1, faction=ATTACKER, city=a.id)
        )
        assert result.success is True, f"冷却期满后应可探索，实际: {result.description}"

    def test_explore_cooldown_uses_engine_turn_not_cmd_turn(self, _engine_template):
        """冷却基准必须是引擎自己的 `self.turn`，不能信命令里的 `cmd.turn`。

        `cmd.turn` 由调用方自称。若拿它当基准，发一条 `turn=9999` 的假命令
        就能永久绕过冷却，冷却成了摆设。这条断言的是**抗伪造**，
        不是「冷却存在」。

        改坏验证：改坏 game/engine.py:777（`self.turn - city.last_explore_turn`
        改为 `cmd.turn - city.last_explore_turn`）→ 1 failed → 还原 → 通过
        """
        engine, a, b, _ = _build(_engine_template)
        engine.turn = 2
        a.last_explore_turn = 1  # 引擎视角：刚探索过，仍在冷却中

        # 命令自称 turn=9999，若引擎信它，冷却就会被绕过
        result = engine._execute_explore(
            ExploreCommand(turn=9999, faction=ATTACKER, city=a.id)
        )
        assert result.success is False, "伪造 cmd.turn 不得绕过探索冷却"

    def test_explore_other_own_city_unaffected_by_cooldown(self, _engine_template):
        """冷却是**按城**记的，不应牵连另一座己方城。

        防止把冷却做成全局开关这种过度修复。
        改坏验证：改坏 game/engine.py:776（`if city.last_explore_turn is not None:`
        改为读取一个全局变量）→ 1 failed → 还原 → 通过
        """
        engine, a, b, c = _build(_engine_template)
        # a、c 都归攻方，b 归守方
        c.faction = ATTACKER
        engine.turn = 1
        a.last_explore_turn = 1  # a 在冷却中
        c.last_explore_turn = None  # c 尚未探索过

        result = engine._execute_explore(ExploreCommand(turn=1, faction=ATTACKER, city=c.id))
        assert result.success is True, "另一座己方城不应受牵连"


# ============================================================
# 6. 原缺口（第二批已修复，xfail 标记已摘、断言翻正）
# ============================================================


class TestUncoveredGaps:
    """A1 未覆盖的 4 类命令的归属权缺口 —— 第二批已统一修复。

    这 4 条原本是真缺口（rumor 间谍归属、message/propose_alliance/declare_war
    的发起方存在性），第二批已修复：
    - rumor 的间谍归属在 `_execute_rumor` 内校验（B3）；
    - 其余三类的发起方存在性由 `execute_command` 分发前单一闸门 +
      各 `_execute_*` 方法内二次校验挡住（幽灵势力闸门）。

    修复前它们用 `xfail(strict=True)` 钉住，修复后 strict xfail 会因
    「意外通过」变红报错，于是已摘掉标记、断言翻正 —— 缺口不再被静默遗忘。

    复现命令见各测试 docstring。
    """

    def test_rumor_enemy_general_as_spy_rejected(self, _engine_template):
        """用**敌方将领**当间谍必须被拒。

        危害是判据一的直接命中：`_execute_rumor` 只读
        `spy.intelligence` 抬高成功率，不问这个间谍是谁家的。
        成功率 = 0.5 + 0.005 ×智力（上限 0.9），
        所以带一个智力 100 的敌将当间谍，成功率从 0.55 抬到 0.9。

        🔴 为什么这里必须打掉随机性：`spread_rumor` 内部要掷骰，
        掷中就success=True。用固定 seed 也不够 —— 那是「这次恰好中/没中」，
        换个 seed 或并行执行就翻脸（实测：首次写成本文件时它恰好掷输了，
        导致 strict xfail 变成 XPASS 而报红）。
        所以直接把外交系统的 RNG 换成常量 0.0：
        `0.0 < success_chance` 恒成立 → 只要归属校验放行，结果必然是成功。
        于是 success 的取值**只由归属校验决定**，与骰子无关。

        阳性对照（同一 stub 下）见下一个测试，两条合起来才排除
        「是我的 stub 把它弄失败了」这种可能。
        复现漏洞本身：
            e = GameEngine(seed=7); e.init_game(load_game_data())
            # 分别用己方智力 10 的将 / 敌方智力 100 的将各跑 4000 次流言，
            # 成功率 0.534 vs 0.888（与理论值 0.55 / 0.9 吻合）

        修好后的正确断言方向：`result.success is False`。
        本条只断言「这条路径当前确实可被利用」，不写死具体成功率数值。
        """
        engine, a, b, _ = _build(_engine_template)
        _force_rumor_always_succeeds(engine)
        enemy = _general_of(engine, DEFENDER, captured=False, location=b.id)
        enemy.intelligence = 100

        result = engine._execute_rumor(
            RumorCommand(turn=1, faction=ATTACKER, city=b.id, spy_general=enemy.id)
        )
        # 当前行为：成功（漏洞存在）→ 断言失败 → xfail 记为预期失败
        # 修复后：success 为 False → 断言通过 → strict xfail 报错提醒摘标记
        assert result.success is False, "敌方将领不得被当作我方间谍"

    def test_rumor_own_general_as_spy_still_works_positive_control(self, _engine_template):
        """阳性对照：己方将领当间谍必须仍然成功。

        没有这条，`test_rumor_enemy_general_as_spy_rejected` 可能变成假绿 ——
        若有人「修」归属校验时手滑写成了 `if spy is not None: return失败`，
        敌将被拒了，己将也被拒了，测试全绿但流言功能整体瘫掉。
        与上一条共用同一个 RNG stub，唯一的变量就是间谍的归属。
        """
        engine, a, b, _ = _build(_engine_template)
        _force_rumor_always_succeeds(engine)
        own = _general_of(engine, ATTACKER, captured=False, location=a.id)
        own.intelligence = 100

        result = engine._execute_rumor(
            RumorCommand(turn=1, faction=ATTACKER, city=b.id, spy_general=own.id)
        )
        assert result.success is True, f"己方将领当间谍应成功，实际: {result.description}"

    def test_declare_war_ghost_faction_rejected(self, _engine_template):
        """不存在的势力不得宣战。

        `_execute_declare_war` 有 `if cmd.to not in FACTIONS`，
        却没有 `if cmd.faction not in FACTIONS`。
        复现：
            e = GameEngine(seed=1); e.init_game(load_game_data())
            e._execute_declare_war(DeclareWarCommand(
                turn=1, faction="ghost_faction", to="liubei"))
            # → success=True，且 diplomacy_relation 里多出一行
            #   faction_a='ghost_faction' 的关系记录

        修好后的正确断言方向：`result.success is False`。
        """
        engine, a, b, _ = _build(_engine_template)
        result = engine._execute_declare_war(
            DeclareWarCommand(turn=1, faction="ghost_faction", to=DEFENDER)
        )
        assert result.success is False, "不存在的势力不得宣战"
        assert "ghost_faction" not in FACTIONS, "前置：ghost_faction 确实是幽灵势力"

    def test_propose_alliance_ghost_faction_rejected(self, _engine_template):
        """不存在的势力不得结盟。

        复现（完整链路）：
            e = GameEngine(seed=1); e.init_game(load_game_data())
            e._execute_declare_war(DeclareWarCommand(   # 先建出关系行
                turn=1, faction="ghost_faction", to="liubei"))
            for _ in range(30):
                e._diplomacy_relation_system.on_message_sent(
                    "ghost_faction", "liubei", is_positive=True)  # 刷到 trust=80
            e._execute_propose_alliance(ProposeAllianceCommand(
                turn=2, faction="ghost_faction", to="liubei"))
            # → success=True「与 刘备 结为同盟（信任度: 90）」

        注：信任度门槛确实挡住了「零消息直接结盟」，
        但挡不住「先宣战建关系行再刷消息」这条路径。

        修好后的正确断言方向：`result.success is False`。
        """
        engine, a, b, _ = _build(_engine_template)
        # 建关系行 + 刷信任，复现实测中让幽灵势力达到结盟门槛的那条路径
        engine._execute_declare_war(
            DeclareWarCommand(turn=1, faction="ghost_faction", to=DEFENDER)
        )
        for _ in range(30):
            engine._diplomacy_relation_system.on_message_sent(
                "ghost_faction", DEFENDER, is_positive=True
            )
        result = engine._execute_propose_alliance(
            ProposeAllianceCommand(turn=2, faction="ghost_faction", to=DEFENDER)
        )
        assert result.success is False, "不存在的势力不得与真实势力结盟"

    def test_message_ghost_sender_rejected(self, _engine_template):
        """不存在的势力不得发外交消息。

        危害：`_execute_message` 对**收发双方都不做存在性校验**，
        幽灵势力发信会真实抬高 `relation.trust`，
        而信任度是 `propose_alliance` 的硬门槛 —— 于是「刷消息→结盟」
        成为一条绕过外交成本的路。

        复现：
            e = GameEngine(seed=1); e.init_game(load_game_data())
            for t in range(2, 12):
                e._execute_message(MessageCommand(
                    turn=t, faction="zhangjiao", to="liubei", content="x"))
            # 实测 caocao↔liubei 的 trust 被从 20 抬到 35

        修好后的正确断言方向：`result.success is False`。
        """
        engine, a, b, _ = _build(_engine_template)
        trust_before = engine._diplomacy_relation_system.get_relation(
            ATTACKER, DEFENDER
        ).trust

        result = engine._execute_message(
            MessageCommand(turn=1, faction="ghost_faction", to=DEFENDER, content="x")
        )
        assert result.success is False, "不存在的势力不得发外交消息"
        assert "ghost_faction" not in FACTIONS, "前置：ghost_faction 确实是幽灵势力"
        # 幽灵发信不得改变任何真实势力之间的信任度
        after = engine._diplomacy_relation_system.get_relation(ATTACKER, DEFENDER).trust
        assert after == trust_before, "幽灵发信不得改变真实势力的信任度"


# ============================================================
# 6.5 truce —— 停战命令（#3，第三批新增）
# ============================================================


class TestTruceOwnership:
    """停战命令（TruceCommand）的三道门与到期链路。

    三层各不相同，各测各的：
    - 幽灵势力闸门（发起方必须真实存在）
    - 交战状态闸门（只有 WAR 能和为 TRUCE）
    - 阳性对照（真实势力在 WAR 下必须成功）
    外加一条命令层 → 引擎回合的到期整合。
    """

    def test_truce_ghost_faction_rejected(self, _engine_template):
        """不存在的势力不得求和。

        🔴 场景是精确设计过的：先把 ghost↔liubei 的关系**直接置为 WAR**
        （绕过引擎闸门，直接改系统状态）。否则幽灵势力在中立状态下会被
        「非交战不得停战」那道闸先拦住，测出来的就不是幽灵闸门了 —— 假绿。
        置 WAR 之后，幽灵闸门成了**唯一**的拦截点。

        改坏验证：删掉 game/engine.py:_execute_truce 开头的
        `if cmd.faction not in FACTIONS:` 分支 → 1 failed → 还原 → 通过
        """
        engine, a, b, _ = _build(_engine_template)
        # 直接把幽灵势力与守方置于交战，绕开「非 WAR 不得停战」那道闸
        engine._diplomacy_relation_system.set_status(
            "ghost_faction", DEFENDER, DiplomaticStatus.WAR, turn=1
        )
        assert engine._diplomacy_relation_system.get_status(
            "ghost_faction", DEFENDER
        ) == DiplomaticStatus.WAR, "前置：幽灵势力已处于交战态，只剩幽灵闸门能拦它"

        result = engine._execute_truce(
            TruceCommand(turn=1, faction="ghost_faction", to=DEFENDER)
        )
        assert result.success is False, "不存在的势力不得求和"
        assert "ghost_faction" not in FACTIONS, "前置：ghost_faction 确实是幽灵势力"

    def test_truce_requires_war_status(self, _engine_template):
        """非交战状态不得停战 —— 对真实势力也一样。

        开局 caocao↔liubei 是 NEUTRAL，直接求和必须被拒。
        此处的真实势力保证「幽灵闸门放行」，于是**交战状态闸门是唯一拦截点**。

        改坏验证：删掉 `if status != DiplomaticStatus.WAR:` 分支
        → 1 failed（状态被改成 TRUCE）→ 还原 → 通过
        """
        engine, a, b, _ = _build(_engine_template)
        rel = engine._diplomacy_relation_system.get_relation(ATTACKER, DEFENDER)
        assert rel.status != DiplomaticStatus.WAR, "前置：起始不是交战状态"

        result = engine._execute_truce(
            TruceCommand(turn=1, faction=ATTACKER, to=DEFENDER)
        )
        assert result.success is False, "非交战状态不得停战"
        assert engine._diplomacy_relation_system.get_status(
            ATTACKER, DEFENDER
        ) != DiplomaticStatus.TRUCE, "被拒的停战不得改动状态"

    def test_truce_self_rejected(self, _engine_template):
        """不能与自己停战。

        🔴 只断言 `success is False` 会是假绿：自己与自己之间根本不存在关系行，
        get_relation 返回 None → 状态 NEUTRAL → 会被「非交战不得停战」那道闸
        顺手拦下（实测：删掉自停战闸门后本测试仍绿）。所以必须断言**拒绝原因**
        命中自停战闸门本身。

        改坏验证：删掉 `if cmd.to == cmd.faction:` 分支
        → 1 failed（拒绝原因变成"并非交战状态"）→ 还原 → 通过
        """
        engine, a, b, _ = _build(_engine_template)
        result = engine._execute_truce(
            TruceCommand(turn=1, faction=ATTACKER, to=ATTACKER)
        )
        assert result.success is False
        assert "自己" in result.description, (
            f"必须由「不能与自己停战」这道闸拦下，实际原因: {result.description}"
        )

    def test_truce_at_war_succeeds_positive_control(self, _engine_template):
        """阳性对照：真实势力在交战状态下求和必须成功，状态转为 TRUCE。

        没有这条，上面两条阴性断言无法区分「闸门生效」与「停战功能整体瘫掉」。
        改坏验证：把 set_status 的目标从 TRUCE 改成 NEUTRAL
        → 1 failed → 还原 → 通过
        """
        engine, a, b, _ = _build(_engine_template)
        engine._execute_declare_war(
            DeclareWarCommand(turn=1, faction=ATTACKER, to=DEFENDER)
        )
        assert engine._diplomacy_relation_system.get_status(
            ATTACKER, DEFENDER
        ) == DiplomaticStatus.WAR, "前置：宣战后应处于交战态"

        result = engine._execute_truce(
            TruceCommand(turn=1, faction=ATTACKER, to=DEFENDER)
        )
        assert result.success is True, f"交战状态下求和应成功，实际: {result.description}"
        rel = engine._diplomacy_relation_system.get_relation(ATTACKER, DEFENDER)
        assert rel.status == DiplomaticStatus.TRUCE
        assert rel.truce_end_turn is not None, "停战必须带到期回合"

    def test_truce_expires_through_engine_turn_processing(self, _engine_template):
        """命令层 → 引擎回合：停战命令写下的到期回合并被 process_turn 消费。

        系统层的 update_turn 到期已有专门单测（test_diplomacy_relation.py）。
        这条补的是**整合链路**：命令层产出的 truce_end_turn 必须真的在
        引擎回合里被读到并到期，否则 truce 就是个永不解禁的死状态。

        改坏验证：把 game/systems/diplomacy_relation.py 的 update_turn 里
        `elif rel.status == DiplomaticStatus.TRUCE and rel.truce_end_turn is not None:`
        改成 `elif False:` → 1 failed → 还原 → 通过
        """
        engine, a, b, _ = _build(_engine_template)
        engine._execute_declare_war(
            DeclareWarCommand(turn=1, faction=ATTACKER, to=DEFENDER)
        )
        engine._execute_truce(
            TruceCommand(turn=1, faction=ATTACKER, to=DEFENDER)
        )
        rel = engine._diplomacy_relation_system.get_relation(ATTACKER, DEFENDER)
        assert rel.status == DiplomaticStatus.TRUCE
        end = rel.truce_end_turn
        assert end is not None

        # 推进到停战结束那一刻（到期检查在 process_turn 开头，turn >= end 时触发）
        guard = 0
        while engine.turn < end and guard < 200:
            engine.process_turn()
            guard += 1
        engine.process_turn()
        assert guard < 200, "停战从未到期，命令层的到期回合可能没被引擎消费"
        assert engine._diplomacy_relation_system.get_status(
            ATTACKER, DEFENDER
        ) == DiplomaticStatus.NEUTRAL, "停战到期后应回到中立"


# ============================================================
# 7. _assert_owns 本身的行为约定
# ============================================================


class TestAssertOwnsContract:
    """`_assert_owns` 是 A1 引入的统一入口，它自己的语义也需要被钉住。

    它的 docstring 承诺了三件事，每件都对应一种坏修改：
    1. `owner is None`（中立/无主）**返回失败**，不是放行
    2. `owner != actor` 返回失败
    3. 通过时返回 `None`（不是返回某个真值 CommandResult）
    """

    def test_none_owner_is_rejected(self):
        """无主对象必须被拒 —— 中立城谁都不能白嫖。

        改坏验证：改坏 game/engine.py:160-165（删掉`owner is None` 那个分支）
        → 1 failed → 还原 → 通过
        """
        from game.engine import _assert_owns

        denied = _assert_owns(ATTACKER, None, "城市 测试城", "explore")
        assert denied is not None, "owner 为 None 必须被拒"
        assert denied.success is False

    def test_mismatched_owner_is_rejected(self):
        """归属不符必须被拒。

        改坏验证：改坏 game/engine.py:166（`if owner != actor:` 改为 `if False:`）
        → 1 failed → 还原 → 通过
        """
        from game.engine import _assert_owns

        denied = _assert_owns(ATTACKER, DEFENDER, "将领 测试将", "reward")
        assert denied is not None, "归属不符必须被拒"
        assert denied.success is False

    def test_matching_owner_passes_with_none(self):
        """归属相符时返回 `None`（约定：None 表示通过）。

        这条防的是「有人把返回值语义反过来了」——
        那样所有调用方的 `if denied is not None: return denied` 都会变成永假，
        全部校验静默失效，测试却可能仍然全绿。
        改坏验证：改坏 game/engine.py:172（`return None` 改为
        `return CommandResult(success=True, ...)`）→ 1 failed → 还原 → 通过
        """
        from game.engine import _assert_owns

        assert _assert_owns(ATTACKER, ATTACKER, "城市 测试城", "explore") is None
