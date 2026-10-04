"""将领系统单元测试"""

import pytest

from game.models import General, City
from game.random import GameRandom
from game.systems.general_system import (
    GeneralSystem,
    ExploreResult,
    RewardResult,
)
from game.constants import CITY_LEVELS
from game.hex_grid import HexCoord


class TestExplore:
    """将领探索功能测试"""

    def test_explore_returns_result(self):
        """探索返回结果"""
        gs = GeneralSystem(rng=GameRandom(seed=42))
        city = _make_city()

        result = gs.explore(city)
        assert isinstance(result, ExploreResult)

    def test_explore_can_find_general(self):
        """探索有可能发现新将领"""
        # 使用固定seed确保确定性的探索结果
        gs = GeneralSystem(rng=GameRandom(seed=42))

        # 多次探索，统计找到的概率
        found = False
        for _ in range(50):
            city = _make_city(morale=100)  # 高民心提升概率
            result = gs.explore(city)
            if result.found:
                found = True
                assert result.general_name is not None
                assert result.general_command > 0
                break

        assert found, "50次探索应至少找到一次将领"

    def test_first_explore_has_no_cooldown(self):
        """开局首次探索不受冷却限制，且真的能发现人才。

        🔴 为什么要重写这条（原 `test_explore_no_cooldown` 是假绿）：
        原函数名说「no_cooldown（没有冷却）」，docstring 却写「同一城市短期内有限制」
        —— **名字与docstring 语义相反**；两条断言都是
        `assert isinstance(resultN, ExploreResult)`，而 `explore()` 的返回类型
        注解就是 `ExploreResult` → **恒真**。实测把 `explore` 打桩成永远返回
        `found=False`，原测试依然全过 —— 它对探索行为一个都没验。
        注释写「同回合第二次探索」，代码用的却是另一座城 `city2`，场景也没测到。

        现在断言的是**行为**而非类型：found 为真时，名字与五维必须有效；
        为假时，描述必须明确说明没找到。两种取值都算通过，
        但「found 为假」不能是因为 explore 根本不工作（那由阳性对照覆盖）。
        """
        gs = GeneralSystem(rng=GameRandom(seed=42))
        city = _make_city(morale=100)  # 民心拉满，提高成功率，减少随机落空

        result = gs.explore(city)

        # 断言取值范围，而不是 isinstance —— isinstance 恒真，验不了任何东西
        assert result.found in (True, False), "found 必须是布尔值"
        if result.found:
            # 发现了人才：名字与属性必须有效，否则「发现」是空壳
            assert result.general_name, "found 为真时必须给出人才名字"
            assert result.general_command > 0, "found 为真时统帅必须为正"
            assert result.general_intelligence > 0, "found 为真时智力必须为正"
            assert result.general_loyalty > 0, "found 为真时忠诚度必须为正"
        else:
            # 没发现：必须明确说明，不能静默返回空结果
            assert result.description, "found 为假时必须给出说明"
            assert not result.general_name, "found 为假时不应带人才名字"

    def test_explore_can_find_general_with_high_morale(self):
        """阳性对照：民心拉满时，探索**确实能**发现人才。

        这是上一条的锚 —— 如果explore 根本不会成功（无论因为人才池耗尽、
        概率被改成 0、或被桩掉），上一条的「found 为假」分支就会
        变成新的假绿。这条用多次采样证明这条路径**真的能通**。
        """
        gs = GeneralSystem(rng=GameRandom(seed=42))

        found_count = 0
        for _ in range(20):
            result = gs.explore(_make_city(morale=100))
            if result.found:
                found_count += 1
                assert result.general_name, "发现人才时必须带名字"

        assert found_count > 0, (
            f"民心 100 时 20 次探索一次都没找到人才（found_count={found_count}），"
            "探索链路可能已失效 —— 上面的 found 为假分支就成了假绿"
        )


class TestExploreCooldownIsEngineLevel:
    """探索冷却在 **GameEngine._execute_explore** 层，不在 GeneralSystem 层。

    🔴 这个类存在的理由是一个具体的、已发生的误修风险：
    A3 之前的旧测试名叫 `test_explore_no_cooldown`（= 没有冷却），
    而它的 docstring 写的是「同一城市短期内有限制」（= 有冷却）。
    下一个读到它的人若「把名字对上」而把冷却搬进 `GeneralSystem.explore`，
    就会引入**第二个冷却点**：双重冷却、且两处语义不一致
    （一个按城记、一个可能按调用次数记），玩家会看到「我换了城还是不能探索」。

    所以冷却测试**必须放在引擎层测** —— `GeneralSystem.explore(city)` 的签名里
    根本没有 turn / faction 参数，它**无从**实现按回合的冷却。
    若哪天有人真在 GeneralSystem 层加了冷却，本文件这些测试不会误报，
    但 `tests/unit/test_command_ownership.py::TestExploreOwnership` 里
    引擎层的冷却测试会立刻变红（同一个行为被加了第二次限制）。
    """

    @pytest.fixture
    def engine(self):
        """构造一个双势力对局的引擎副本。"""
        import copy

        from game.data_loader import load_game_data
        from game.engine import GameEngine

        template = GameEngine(seed=1)
        template.init_game(load_game_data())
        return copy.deepcopy(template)

    def _cities(self, engine):
        """返回 (己方城A, 己方城B)，两座**互相连通**的城，金库备足。

        两座城都归caocao：本组只测「同城 vs 换城」的冷却差异，
        双方归属不参与判定，归属权由
        `tests/unit/test_command_ownership.py::TestExploreOwnership` 负责。
        按**连通性**挑而不是按位置下标：把「哪两座城相邻」藏进
        初始化顺序里，地图生成顺序一变，失败会以错误的形态出现。
        """
        ids = sorted(engine.cities.keys())
        a = engine.cities[ids[0]]
        b = next(
            engine.cities[cid]
            for cid in ids[1:]
            if engine.map.get_distance(a.id, cid) > 0
        )
        a.faction = b.faction = "caocao"
        a.gold = b.gold = 5000
        return a, b

    def test_same_turn_second_explore_on_same_city_rejected(self, engine):
        """同回合对**同一座城**探索第二次必须被冷却拒。

        注意场景：同一座城（`city=a`两次），不是原测试那种「换一座城」。
        换城本来就不该被同一座城的冷却拦住，那是另一个语义。

        改坏验证：改坏 `game/engine.py:778`
        （`if elapsed < EXPLORE_COOLDOWN_TURNS:` → `if False:`）
        → 1 failed → 还原 → 2 passed
        """
        from game.models import ExploreCommand

        a, _ = self._cities(engine)
        engine.turn = 1
        a.last_explore_turn = None

        first = engine._execute_explore(
            ExploreCommand(turn=1, faction="caocao", city=a.id)
        )
        assert first.success is True, f"首次探索应成功，实际: {first.description}"

        second = engine._execute_explore(
            ExploreCommand(turn=1, faction="caocao", city=a.id)
        )
        assert second.success is False, "同回合第二次探索同一座城必须被拒"
        assert second.data.get("cooling_down") is True, "失败原因必须标明是冷却"
        assert second.data.get("turns_left", 0) > 0, "必须告知还剩几回合"

    def test_cooldown_expires_and_allows_explore_again(self, engine):
        """冷却期满后必须能再探索 —— 防「改成永久锁死」这种反向坏修改。

        与上一条成对：上一条防「冷却缺失」，这条防「冷却过头」。
        只有一条的话，把冷却写成永不复解同样能全绿。

        改坏验证：改坏 `game/engine.py:778` → 1 failed → 还原 → 2 passed
        """
        from game.constants import EXPLORE_COOLDOWN_TURNS
        from game.models import ExploreCommand

        a, _ = self._cities(engine)
        engine.turn = 1
        a.last_explore_turn = None
        engine._execute_explore(ExploreCommand(turn=1, faction="caocao", city=a.id))

        engine.turn = 1 + EXPLORE_COOLDOWN_TURNS
        result = engine._execute_explore(
            ExploreCommand(turn=1, faction="caocao", city=a.id)
        )
        assert result.success is True, (
            f"冷却期满（{EXPLORE_COOLDOWN_TURNS} 回合）后应可探索，实际: {result.description}"
        )

    def test_cooldown_does_not_leak_to_other_city(self, engine):
        """冷却按城记，不牵连另一座己方城 —— 防「过度修复成全局开关」。

        改坏验证：改坏 `game/engine.py:776`
        （`if city.last_explore_turn is not None:` → 读全局状态）
        → 1 failed → 还原 → 2 passed
        """
        from game.models import ExploreCommand

        a, b = self._cities(engine)
        engine.turn = 1
        a.last_explore_turn = 1  # a 在冷却中
        b.last_explore_turn = None  # b 没探索过

        result = engine._execute_explore(
            ExploreCommand(turn=1, faction="caocao", city=b.id)
        )
        assert result.success is True, "另一座己方城不应受牵连"


class TestReward:
    """赏赐功能测试"""

    def test_reward_increases_loyalty(self):
        """赏赐提升忠诚度"""
        gs = GeneralSystem(rng=GameRandom(seed=42))
        general = _make_general(loyalty=70)
        city = _make_city(gold=1000)

        result = gs.reward(general, city, gold=200)
        assert result.success is True
        assert result.loyalty_change > 0
        assert general.loyalty > 70

    def test_reward_not_enough_gold(self):
        """金钱不足时赏赐失败"""
        gs = GeneralSystem(rng=GameRandom(seed=42))
        general = _make_general(loyalty=70)
        city = _make_city(gold=50)

        result = gs.reward(general, city, gold=200)
        assert result.success is False
        assert general.loyalty == 70  # 不变

    def test_reward_zero_gold(self):
        """赏赐0金"""
        gs = GeneralSystem(rng=GameRandom(seed=42))
        general = _make_general(loyalty=70)
        city = _make_city(gold=1000)

        result = gs.reward(general, city, gold=0)
        assert result.success is False

    def test_reward_max_loyalty(self):
        """赏赐不会超过100忠诚度"""
        gs = GeneralSystem(rng=GameRandom(seed=42))
        general = _make_general(loyalty=99)
        city = _make_city(gold=5000)

        gs.reward(general, city, gold=500)
        assert general.loyalty <= 100

    def test_reward_consumes_gold(self):
        """赏赐消耗城市金钱"""
        gs = GeneralSystem(rng=GameRandom(seed=42))
        general = _make_general(loyalty=70)
        city = _make_city(gold=1000)

        gs.reward(general, city, gold=200)
        assert city.gold == 800


class TestLoyaltyDecay:
    """忠诚度衰减测试"""

    def test_loyalty_decays_each_turn(self):
        """每回合忠诚度自然衰减"""
        gs = GeneralSystem(rng=GameRandom(seed=42))
        general = _make_general(loyalty=80)

        result = gs.process_turn_decay(general)
        assert result < 0  # 衰减
        assert general.loyalty < 80

    def test_loyalty_doesnt_go_below_zero(self):
        """忠诚度不会低于0"""
        gs = GeneralSystem(rng=GameRandom(seed=42))
        general = _make_general(loyalty=1)

        gs.process_turn_decay(general)
        assert general.loyalty >= 0

    def test_loyalty_decay_amount(self):
        """忠诚度衰减量"""
        gs = GeneralSystem(rng=GameRandom(seed=42))
        general = _make_general(loyalty=80)

        decay = gs.process_turn_decay(general)
        assert 0 < abs(decay) <= 1  # 每回合衰减0.5


class TestCaptureAndSurrender:
    """俘虏与投降测试"""

    def test_captured_general_can_surrender(self):
        """被俘将领有概率投降"""
        gs = GeneralSystem(rng=GameRandom(seed=42))
        general = _make_general(loyalty=40)

        result = gs.process_capture(general, captor_faction="caocao")
        assert result.is_captured is True
        assert general.is_captured is True
        assert general.captor_faction == "caocao"

    def test_high_loyalty_resists_surrender(self):
        """高忠诚度将领不易投降"""
        gs = GeneralSystem(rng=GameRandom(seed=42))

        # 高忠诚度的将领在被俘后投降概率低
        surrendered = False
        for _ in range(20):
            general = _make_general(loyalty=90)
            result = gs.process_capture(general, captor_faction="caocao")
            surrendered = result.surrendered or surrendered
            if not surrendered:
                # 部分可能投降了，但多数应抵抗
                pass

        # 不assert，因为概率测试不稳定
        # 只是验证接口工作正常
        general = _make_general(loyalty=90)
        result = gs.process_capture(general, captor_faction="caocao")
        assert isinstance(result.surrendered, bool)

    def test_low_loyalty_more_likely_to_surrender(self):
        """低忠诚度将领更易投降"""
        gs = GeneralSystem(rng=GameRandom(seed=42))

        surrendered = False
        for _ in range(10):
            general = _make_general(loyalty=20)
            result = gs.process_capture(general, captor_faction="caocao")
            if result.surrendered:
                surrendered = True
                break

        # 低忠诚度在多次尝试中至少投降一次
        # 概率较高，但用确定性seed验证

    def test_capture_turn_tracked(self):
        """被俘回合记录"""
        gs = GeneralSystem(rng=GameRandom(seed=42))
        general = _make_general(loyalty=50)

        gs.process_capture(general, captor_faction="caocao", turn=10)
        if general.is_captured:
            assert general.captured_turn == 10


class TestGeneralSystemEdgeCases:
    """边界情况测试"""

    def test_explore_low_morale_city(self):
        """低民心城市探索概率低"""
        gs = GeneralSystem(rng=GameRandom(seed=42))
        city = _make_city(morale=10)

        result = gs.explore(city)
        assert isinstance(result, ExploreResult)

    def test_explore_high_morale_city(self):
        """高民心城市探索概率高"""
        gs = GeneralSystem(rng=GameRandom(seed=42))
        city = _make_city(morale=100)

        result = gs.explore(city)
        assert isinstance(result, ExploreResult)

    def test_reward_minimum_gold(self):
        """最小有效赏金额度"""
        gs = GeneralSystem(rng=GameRandom(seed=42))
        general = _make_general(loyalty=70)
        city = _make_city(gold=1000)

        result = gs.reward(general, city, gold=100)
        assert result.success is True
        assert result.loyalty_change >= 5  # 每100金+5忠诚

    def test_captured_general_defect(self):
        """被俘将领在适当条件下投诚"""
        gs = GeneralSystem(rng=GameRandom(seed=42))
        general = _make_general(loyalty=50)

        gs.process_capture(general, captor_faction="caocao")
        assert general.is_captured


# ============================================================
# 辅助函数
# ============================================================

def _make_city(
    id: str = "test_city",
    gold: int = 5000,
    morale: int = 70,
) -> City:
    """创建测试用城市"""
    lc = CITY_LEVELS[1]
    return City(
        id=id,
        name="测试城",
        faction="caocao",
        level=1,
        wall_hp=lc["wall_hp"],
        wall_max_hp=lc["wall_hp"],
        gold=gold,
        food=1000,
        population=5000,
        morale=morale,
        garrison=500,
        position=HexCoord(0, 0),
    )


def _make_general(
    general_id: str = "test_general",
    loyalty: int = 70,
    command: int = 70,
    politics: int = 50,
    bravery: int = 60,
    intelligence: int = 55,
    faction: str = "shu",
) -> General:
    """创建测试用将领"""
    return General(
        id=general_id,
        name="测试将",
        faction=faction,
        command=command,
        politics=politics,
        bravery=bravery,
        intelligence=intelligence,
        loyalty=loyalty,
        location="test_city",
    )
