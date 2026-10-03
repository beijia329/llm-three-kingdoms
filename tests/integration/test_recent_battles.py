"""战斗可见性：get_state()['recent_battles'] 回归测试

契约（v4.1，见 docs/design/v4.1-gameplay-gaps.md §4.3/§4.3.1）：
- `get_state()` 暴露 `recent_battles`（近 MAX_RECENT_BATTLES 场战斗，有上限）；
- 每场含 攻方势力/守方势力/双方兵力/伤亡/结果/城墙前后/攻方出发城（**复数**）；
- 🔴 `attacker_from_cities` 是 `list[str]` 且**去重+排序**（一场战斗可能有多支来自
  不同出发城的攻方部队被合并进同一 BattleContext，约 15% 的战斗如此）。

用 CLI 模式（use_llm=False）：不联网、不花钱、确定。
"""

from __future__ import annotations

from api.game_manager import MAX_RECENT_BATTLES, GameConfig, GameManager

_REQUIRED_FIELDS = {
    "battle_id", "turn", "attacker_faction", "defender_faction",
    "attacker_from_cities", "defender_city",
    "attacker_soldiers", "defender_soldiers",
    "attacker_casualties", "defender_casualties",
    "result", "wall_hp_before", "wall_hp_after",
    "captured_city", "attacker_general_name",
}


def _run(seed: int = 1, turns: int = 40) -> dict:
    m = GameManager(GameConfig(seed=seed, max_turns=turns, use_llm=False))
    for _ in range(turns):
        if m.engine and m.engine.game_over:
            break
        m.process_turn()
    return m.get_state()


def test_recent_battles_populated_with_all_fields():
    rb = _run()["recent_battles"]
    assert rb, "整局打完 recent_battles 仍为空——事件订阅/打包未生效"
    missing = _REQUIRED_FIELDS - set(rb[0].keys())
    assert not missing, f"BattleReport 缺字段: {missing}"


def test_attacker_from_cities_is_sorted_unique_list():
    for b in _run()["recent_battles"]:
        cities = b["attacker_from_cities"]
        assert isinstance(cities, list)
        assert cities == sorted(set(cities)), (
            f"attacker_from_cities 未去重/未排序（集合迭代序确定性坑）: {cities}"
        )


def test_recent_battles_is_capped():
    rb = _run(seed=1, turns=48)["recent_battles"]
    assert 0 < len(rb) <= MAX_RECENT_BATTLES, f"recent_battles 越界: {len(rb)}"


def test_multi_from_city_battle_present():
    """至少有一场战斗是多出发城的（否则本字段的复数设计无从被验证）。"""
    rb = _run(seed=1, turns=40)["recent_battles"]
    multi = [b for b in rb if len(b["attacker_from_cities"]) > 1]
    assert multi, "seed=1/40回合未出现多出发城战斗——契约关键场景未被覆盖"
    sample = multi[0]
    assert sample["defender_city"]  # 目标城是单数且存在
