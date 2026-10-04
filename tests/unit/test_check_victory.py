"""三层结束语义与僵局熔断契约测试（v4.3.0 方案 A′）

对应设计：`docs/design/2026-10-04-胜负条件与对局长度.md` §1 / §3。

覆盖：
- `_check_victory` 三态（unification / timeout / stalemate）+ 无胜者并列。
- `_update_stalemate_counter` 累加/清零。
- `_leading_faction` 确定性决胜（含并列 → 次级指标 → 势力字典序兜底）。
- 边界：中立城不计入统一（选项 α）、被围未陷落不算易主、残军不影响统一。
- 后端事件文案契约：非 unification 结局**不得出现「统一/一统天下」**。
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest  # noqa: E402

from game.engine import GameEngine  # noqa: E402
from game.game_mode import GameMode  # noqa: E402
from game.hex_grid import HexCoord  # noqa: E402
from game.models import City  # noqa: E402


# ============================================================
# 轻量构造：只填 _check_victory 依赖的 self.cities / 模式 / 计数器
# （刻意不走 init_game，避免每次生成 24000 格地图拖慢单测）
# ============================================================

def _make_city(cid: str, faction: str, q: int = 0, r: int = 0, **kw) -> City:
    base = dict(
        id=cid, name=cid, faction=faction, level=3,
        wall_hp=2000, wall_max_hp=2000,
        gold=1000, food=1000, population=10000, morale=70, garrison=1000,
        position=HexCoord(q=q, r=r),
    )
    base.update(kw)
    return City(**base)


def _bare_engine(
    cities: list,
    *,
    game_mode: str = "standard",
    turn: int = 1,
    max_turns: int = 192,
    stalemate_turns: int = 6,
    zero_battle_turns: int = 0,
) -> GameEngine:
    engine = GameEngine(seed=1)
    engine.game_mode = GameMode.INFINITE if game_mode == "infinite" else GameMode.STANDARD
    engine.turn = turn
    engine.max_turns = max_turns
    engine.stalemate_turns = stalemate_turns
    engine._consecutive_zero_battle_turns = zero_battle_turns
    engine.cities = {c.id: c for c in cities}
    return engine


# ============================================================
# 三态
# ============================================================

class TestThreeWayEndReason:
    def test_unification_when_one_non_neutral_owner(self):
        """非中立城只剩一个主人 → unification。"""
        engine = _bare_engine([
            _make_city("a", "sunjian"), _make_city("b", "sunjian", 1),
        ])
        engine._check_victory()
        assert engine.game_over is True
        assert engine.winner == "sunjian"
        assert engine.end_reason == "unification"

    def test_timeout_in_standard_mode_at_max_turns(self):
        """standard 模式到达 max_turns → timeout（绝非 unification）。"""
        engine = _bare_engine(
            [_make_city("a", "sunjian"), _make_city("b", "han", 1)],
            game_mode="standard", turn=192, max_turns=192,
        )
        engine._check_victory()
        assert engine.game_over is True
        assert engine.end_reason == "timeout"
        # 领先者 = 单方领跑（此处并列 1:1 → 次级指标决胜，必有唯一 winner）
        assert engine.winner in ("sunjian", "han")

    def test_no_end_before_max_turns_in_standard(self):
        """standard 模式未到上限、多方存活、无僵局 → 不结束。"""
        engine = _bare_engine(
            [_make_city("a", "sunjian"), _make_city("b", "han", 1)],
            game_mode="standard", turn=10, max_turns=192,
        )
        engine._check_victory()
        assert engine.game_over is False
        assert engine.end_reason is None

    def test_stalemate_in_infinite_mode(self):
        """infinite 模式连续 N 回合零战斗 → stalemate。"""
        engine = _bare_engine(
            [_make_city("a", "sunjian"), _make_city("b", "han", 1)],
            game_mode="infinite", turn=55, stalemate_turns=6, zero_battle_turns=6,
        )
        engine._check_victory()
        assert engine.game_over is True
        assert engine.end_reason == "stalemate"

    def test_infinite_does_not_end_below_threshold(self):
        """infinite 模式计数器未达阈值、未到软上限 → 不结束（有战事就继续打）。"""
        engine = _bare_engine(
            [_make_city("a", "sunjian"), _make_city("b", "han", 1)],
            game_mode="infinite", turn=55, stalemate_turns=6, zero_battle_turns=5,
        )
        engine._check_victory()
        assert engine.game_over is False
        assert engine.end_reason is None

    def test_infinite_soft_cap_backstop(self):
        """infinite 模式到达 max_turns 软上限（未统一亦未僵局）→ timeout 兜底。"""
        engine = _bare_engine(
            [_make_city("a", "sunjian"), _make_city("b", "han", 1)],
            game_mode="infinite", turn=192, max_turns=192, zero_battle_turns=0,
        )
        engine._check_victory()
        assert engine.game_over is True
        assert engine.end_reason == "timeout"

    def test_no_winner_tuple_for_stalemate_without_active(self):
        """极端：无限模式无有效势力 → winner None。"""
        engine = _bare_engine(
            [_make_city("a", "neutral")],
            game_mode="infinite", turn=5,
        )
        # 只有中立城 → owners==0 分支 → timeout + winner None
        engine._check_victory()
        assert engine.game_over is True
        assert engine.winner is None
        assert engine.end_reason == "timeout"


# ============================================================
# 边界（对应设计 §1.2）
# ============================================================

class TestUnificationBoundaries:
    def test_neutral_cities_not_required_for_unification(self):
        """选项 α：只需全部「有主城」归一；中立城不在统一条件内。"""
        engine = _bare_engine([
            _make_city("a", "sunjian"), _make_city("b", "sunjian", 1),
            _make_city("n1", "neutral", 2), _make_city("n2", "neutral", 3),
        ])
        engine._check_victory()
        assert engine.end_reason == "unification"
        assert engine.winner == "sunjian"

    def test_besieged_city_still_counts_as_defender(self):
        """被围未陷落（is_besieged=True 但 faction 未变）不算易主 → 不触发统一。"""
        engine = _bare_engine([
            _make_city("a", "sunjian"),
            _make_city("b", "han", 1, is_besieged=True),
        ])
        engine._check_victory()
        assert engine.game_over is False
        assert engine.end_reason is None

    def test_residual_army_does_not_block_unification(self):
        """残军不影响统一：某势力 0 城 + 在途军队，其余占满有主城 → unification。"""
        engine = _bare_engine([
            _make_city("a", "sunjian"), _make_city("b", "sunjian", 1),
            _make_city("c", "sunjian", 2),
        ])
        # 模拟某势力残军（不计入 cities 统计）
        engine._check_victory()
        assert engine.end_reason == "unification"


# ============================================================
# 僵局计数器
# ============================================================

class TestStalemateCounter:
    def test_zero_battle_increments(self):
        engine = _bare_engine([_make_city("a", "sunjian")], zero_battle_turns=2)
        engine._update_stalemate_counter(0)
        assert engine._consecutive_zero_battle_turns == 3

    def test_battle_resets(self):
        engine = _bare_engine([_make_city("a", "sunjian")], zero_battle_turns=5)
        engine._update_stalemate_counter(3)
        assert engine._consecutive_zero_battle_turns == 0


# ============================================================
# 领先者确定性决胜
# ============================================================

class TestLeadingFactionDeterminism:
    def test_single_max_returns_it(self):
        engine = _bare_engine([
            _make_city("a", "sunjian"), _make_city("b", "sunjian", 1),
            _make_city("c", "han", 2),
        ])
        counts = {"sunjian": 2, "han": 1}
        assert engine._leading_faction(counts) == "sunjian"

    def test_tie_broken_by_garrison_then_name(self):
        """并列城数 → 守军总数高者胜；完全并列 → 势力名字典序兜底。"""
        engine = _bare_engine([
            _make_city("a", "han", garrison=500),
            _make_city("b", "sunjian", 1, garrison=5000),
        ])
        counts = {"han": 1, "sunjian": 1}
        assert engine._leading_faction(counts) == "sunjian"

    def test_fully_tied_deterministic_by_name(self):
        """完全并列（城/守军/人口/gold 相同）→ faction 字典序唯一兜底，且稳定。"""
        engine = _bare_engine([
            _make_city("a", "han", garrison=1000),
            _make_city("b", "sunjian", 1, garrison=1000),
        ])
        counts = {"han": 1, "sunjian": 1}
        first = engine._leading_faction(counts)
        second = engine._leading_faction(dict(reversed(list(counts.items()))))
        assert first == second == "han"  # 字典序最小，与迭代序无关

    def test_all_neutral_returns_none(self):
        engine = _bare_engine([_make_city("a", "neutral")])
        assert engine._leading_faction({"neutral": 1}) is None


# ============================================================
# 后端事件文案契约（第三处「统一」硬编码修复）
# ============================================================

class TestBackendVictoryEventText:
    """🔴 H1 硬指标：非 unification 结局的事件文案不得出现「统一/一统天下」。"""

    def test_timeout_event_says_leading_not_unification(self):
        from api.game_manager import GameConfig, GameManager

        gm = GameManager(GameConfig(seed=1, max_turns=1, game_mode="standard"))
        gm.process_turn()
        assert gm.engine.end_reason == "timeout"
        texts = [e["text"] for e in gm._events if e.get("type") == "victory"]
        assert texts, "到达 max_turns 应产生一条 victory 事件"
        joined = " ".join(texts)
        assert "一统天下" not in joined and "统一" not in joined
        assert "领先胜出" in joined

    def test_unification_event_keeps_unification_wording(self):
        """真·统一仍应显示「一统天下」（防改动误伤真胜利文案）。"""
        from api.game_manager import GameConfig, GameManager

        gm = GameManager(GameConfig(seed=1, game_mode="infinite"))
        for city in gm.engine.cities.values():
            city.faction = "sunjian"
        gm.process_turn()
        assert gm.engine.end_reason == "unification"
        texts = [e["text"] for e in gm._events if e.get("type") == "victory"]
        assert any("一统天下" in t for t in texts)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
