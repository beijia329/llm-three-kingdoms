"""势力差异化守卫（相性 / 史实立场 / 结盟门槛）

## 这个文件解决什么问题

玩家实测反馈：

> 「AI 行动同质化，角色扮演后并不符合史实人物的特点，**曹操、刘备、孙坚居然
>  互相都结盟**，破坏了历史沉浸感，而且不能突出各派系、各城市、各州县之间的
>  特点与差异。」

根因有三处（2026-10-03 定位）：

1. **外交白板起手**：`diplomacy_relation.__init__` 把所有两两关系初始化为
   `NEUTRAL, trust=50`。12 方在模型眼里完全对称 → 谁跟谁结盟纯看当回合随机。
2. **`trust` 是装饰数字**：它只被显示、被事件增减，**没有任何决策读它**。
3. **提示词明确鼓励抛弃角色**：`prompt_builder.py` 原文写着
   「不必复刻史实走向，你的判断优先于历史常识」「允许欺诈、背盟等一切合法手段」，
   且**完全没有任何势力立场信息** —— 模型不知道谁跟谁是世仇。

修复：相性表 + 史实硬禁 + 初始信任度 + 信任门槛 + 提示词立场段。

## 判据

本文件里每一条都对应一个"回退即失败"的守卫：
把相性表删掉、把白板起手改回来、把信任门槛去掉、把提示词立场段删掉 ——
都会让这里的测试变红。
"""

from __future__ import annotations

import pytest

from game.constants import DIPLOMACY_TRUST_MIN_FOR_ALLIANCE, FACTIONS
from game.personality import (
    FACTION_XIANGXING,
    FORBIDDEN_ALLIANCE,
    can_ally,
    initial_trust,
    relation_stance,
    xiangxing_distance,
)

_ALL_IDS = set(FACTIONS.keys())


# ============================================================
# 1. 相性表与硬禁表的完整性
# ============================================================


class TestXiangxingTable:
    def test_covers_exactly_the_12_factions(self):
        """相性表必须恰好覆盖 12 个势力（多一个少一个都是漂移）。"""
        assert set(FACTION_XIANGXING.keys()) == _ALL_IDS

    def test_values_in_ring_range(self):
        assert all(0 <= v < 150 for v in FACTION_XIANGXING.values()), (
            f"相性值必须落在 [0,150) 环内，实际: {FACTION_XIANGXING}"
        )

    def test_distance_is_symmetric(self):
        """相性距离必须对称 —— 否则"谁看谁"会不一样。"""
        for a in _ALL_IDS:
            for b in _ALL_IDS:
                assert xiangxing_distance(a, b) == xiangxing_distance(b, a)
        assert xiangxing_distance("caocao", "caocao") == 0

    def test_distance_never_exceeds_half_ring(self):
        for a in _ALL_IDS:
            for b in _ALL_IDS:
                d = xiangxing_distance(a, b)
                assert 0 <= d <= 75, f"{a}×{b} 距离 {d} 越界（环长 150，最大应 75）"


class TestForbiddenAlliance:
    def test_all_ids_are_valid_factions(self):
        """硬禁表里不能有写错的 id（否则那条禁令静默失效）。"""
        for pair in FORBIDDEN_ALLIANCE:
            assert len(pair) == 2, f"硬禁项必须是二元组: {pair}"
            bad = set(pair) - _ALL_IDS
            assert not bad, f"硬禁表里有非法势力 id: {bad}"

    def test_no_self_pair(self):
        assert all(len(p) == 2 for p in FORBIDDEN_ALLIANCE)

    def test_historical_anchors_are_forbidden(self):
        """史实锚点：这几对若能被结盟，就是历史沉浸感崩了。"""
        anchors = [
            ("han", "zhangjiao"),      # 汉室 × 黄巾
            ("yuanshao", "yuanshu"),   # 兄弟死敌
            ("yuanshao", "gongsunzan"),  # 界桥
            ("sunjian", "liubiao"),    # 杀父之仇
            ("dongzhuo", "caocao"),
            ("dongzhuo", "sunjian"),
        ]
        for a, b in anchors:
            assert not can_ally(a, b), f"{a}×{b} 是史实宿敌，不该能结盟"

    def test_zhangjiao_is_everyones_enemy(self):
        """黄巾是天下公敌：184 年其余 11 方都在讨黄巾。"""
        others = _ALL_IDS - {"zhangjiao"}
        assert len(others) == 11
        for f in others:
            assert not can_ally("zhangjiao", f), f"黄巾不该能与 {f} 结盟"

    def test_self_alliance_impossible(self):
        for f in _ALL_IDS:
            assert not can_ally(f, f)


# ============================================================
# 2. 初始信任度：不能是白板
# ============================================================


class TestInitialTrust:
    def test_not_a_blank_slate(self):
        """🔴 核心守卫：初始信任度不能所有组合都一样。

        白板起手是玩家反馈「谁跟谁都能结盟」的根因之一。
        若有人把它改回统一值，本测试变红。
        """
        values = {
            initial_trust(a, b)
            for i, a in enumerate(sorted(_ALL_IDS))
            for b in sorted(_ALL_IDS)[i + 1:]
        }
        assert len(values) >= 3, f"初始信任度只有 {len(values)} 种取值，退化成白板了"

    def test_trust_symmetric(self):
        for i, a in enumerate(sorted(_ALL_IDS)):
            for b in sorted(_ALL_IDS)[i + 1:]:
                assert initial_trust(a, b) == initial_trust(b, a)

    def test_within_bounds(self):
        for i, a in enumerate(sorted(_ALL_IDS)):
            for b in sorted(_ALL_IDS)[i + 1:]:
                t = initial_trust(a, b)
                assert 0 <= t <= 100, f"{a}×{b} 信任度 {t} 越界"

    def test_forbidden_pairs_have_minimal_trust(self):
        for a, b in [tuple(p) for p in FORBIDDEN_ALLIANCE]:
            assert initial_trust(a, b) <= 10, (
                f"史实宿敌 {a}×{b} 的初始信任度应接近 0，实际 {initial_trust(a, b)}"
            )

    def test_natural_allies_have_high_trust(self):
        """史实天然亲近的组合应有高信任度（否则差异化只体现"防"，没体现"亲"）。"""
        for a, b in [("liubei", "gongsunzan"), ("sunjian", "yuanshu")]:
            assert initial_trust(a, b) >= 75, f"{a}×{b} 史实亲近，信任度应高"

    def test_184_context_overrides_long_term_xiangxing(self):
        """184 年实际关系 ≠ 长期相性时，覆盖表必须生效。

        曹操(相性25)×袁绍(相性101) 距离 74，按相性会被判成"天然敌对"；
        但 184 年二人同为何进心腹。这是**故意**的覆盖，防止照搬 208 年立场。
        """
        assert xiangxing_distance("caocao", "yuanshao") > 70, "前置：相性距离应该很远"
        assert initial_trust("caocao", "yuanshao") >= 55, (
            "曹操×袁绍在 184 年同为何进心腹，初始信任度应被覆盖上调"
        )
        assert can_ally("caocao", "yuanshao"), "二人 184 年应可结盟（199 才翻脸）"


# ============================================================
# 3. 信任门槛：让 trust 真正参与决策
# ============================================================


class TestTrustGate:
    def test_threshold_is_defined_and_sane(self):
        assert 0 < DIPLOMACY_TRUST_MIN_FOR_ALLIANCE <= 100

    def test_competing_pairs_are_below_threshold(self):
        """「竞争」档（35）必须低于门槛 —— 这正是玩家抱怨的曹刘孙组合。

        曹操×刘备 = 35 < 45 → 结构性挡住，不靠提示词自觉。
        """
        for a, b in [("caocao", "liubei"), ("liubei", "sunjian")]:
            assert initial_trust(a, b) < DIPLOMACY_TRUST_MIN_FOR_ALLIANCE, (
                f"{a}×{b} 初始信任度应低于结盟门槛，否则玩家反馈的问题会复现"
            )

    def test_natural_allies_are_above_threshold(self):
        for a, b in [("liubei", "gongsunzan"), ("caocao", "yuanshao"),
                     ("sunjian", "yuanshu")]:
            assert initial_trust(a, b) >= DIPLOMACY_TRUST_MIN_FOR_ALLIANCE


# ============================================================
# 4. 提示词里的立场段
# ============================================================


@pytest.fixture
def prompt_builder():
    from players.llm.prompt_builder import PromptBuilder
    return PromptBuilder()


class TestPromptStance:
    def test_stance_section_present(self, prompt_builder):
        sp = prompt_builder.build_system_prompt("caocao", "曹操")
        assert "你的立场" in sp, "提示词必须包含势力立场段"

    def test_stance_lists_nemeses_by_name(self, prompt_builder):
        """宿敌必须**按中文名**列出来（模型要能直接读懂，不能只给 id）。"""
        sp = prompt_builder.build_system_prompt("caocao", "曹操")
        assert "宿敌" in sp
        assert "董卓" in sp, f"曹操的宿敌里应有董卓：{sp[sp.find('你的立场'):][:400]}"

    def test_stance_differs_per_faction(self, prompt_builder):
        """不同势力的立场段必须不同 —— 否则差异化只是装饰。"""
        cao = prompt_builder.build_system_prompt("caocao", "曹操")
        jiao = prompt_builder.build_system_prompt("zhangjiao", "黄巾")

        def stance_of(sp: str) -> str:
            i = sp.find("## 你的立场")
            j = sp.find("##", i + 5)
            return sp[i: j if j > 0 else len(sp)]

        assert stance_of(cao) != stance_of(jiao), "两个势力的立场段完全相同"
        # 黄巾是天下公敌：立场段里应出现大量宿敌
        assert "宿敌" in stance_of(jiao)

    def test_old_wording_that_encouraged_dropping_history_is_gone(self, prompt_builder):
        """🔴 回退守卫：原文「不必复刻史实走向，你的判断优先于历史常识」
        是玩家反馈问题的直接成因之一，不得复活。

        注意区分：允许**结果**自由（「不必复刻史实结局」是要保留的），
        但**关系**必须遵守史实。
        """
        sp = prompt_builder.build_system_prompt("caocao", "曹操")
        assert "你的判断优先于历史常识" not in sp, "那句鼓励无视史实的原文又回来了"
        assert "史实关系必须遵守" in sp or "史实立场不是偏好" in sp, (
            "应明确区分「史实关系必须遵守」与「史实结局无需复刻」"
        )
        # 保留的那半边：结局自由
        assert "不必复刻史实结局" in sp

    def test_style_hints_are_executable_rules_not_adjectives(self, prompt_builder):
        """人设提示应是可执行的判断规则，不是形容词。

        依据（业界实践）：扁平形容词无法给出决策框架，模型遇到未覆盖场景就回退到
        默认行为 → 人设漂移。故要求写成"你的第一反应是…"。
        """
        sp = prompt_builder.build_system_prompt("caocao", "曹操")
        assert "第一反应" in sp, "性情倾向应写成可执行的判断规则（'你的第一反应是…'）"
