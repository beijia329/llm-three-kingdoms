"""`load_state_snapshot` 的行为守卫（显式不可用，不静默降级）

## 为什么会有这条测试

`GameEngine.load_state_snapshot` 曾是「只写不读」的半个功能：全仓零调用者，
而实现只重建了 `rng` 与 `map`。2026-10-03 实测（`tests/balance/exp20_snapshot_restore.py`）：

    原引擎：turn=13  hex_map=已建  season=WINTER  外交关系=69 条
    恢复后：turn=13  hex_map=None  season=SPRING  外交关系=None
    继续推进 12 回合 → 表面"成功"
    但后台抛 AttributeError: 'NoneType' object has no attribute 'set_status'
    （被引擎的命令级 try/except 吞掉）

**最危险的不是它坏，是它不报错**：会造出一个看起来还行、实际静默降级的引擎。
按本项目「拒绝静默兜底」的原则，它已改为显式抛 `NotImplementedError`。

根因不是"接线漏了"，而是**存档格式缺字段**（2026-10-03 实测）：

1. `GameState` **不含任何 hex 地块/领地字段** —— 而 `hex_map` 依赖原始地图数据
   构建，光凭一份 `GameState` 无法重建；
2. 外交关系也**不在快照里** —— `GameState` 模型**有** `faction_relations` 字段，
   但 `get_state_snapshot()` **没传它**，恒取默认 `[]`。
   （教训：字段存在 ≠ 生产端填充它。）

要做存档/读档必须先扩快照格式，属功能开发。

## 判据

若有人把 `load_state_snapshot` 改回"尽力而为"的实现，本文件必须变红。
"""

from __future__ import annotations

import pytest

from game.data_loader import load_game_data
from game.engine import GameEngine


@pytest.fixture
def engine() -> GameEngine:
    e = GameEngine(seed=42)
    e.init_game(load_game_data())
    return e


def test_load_state_snapshot_raises_explicitly(engine: GameEngine):
    """公开入口必须显式拒绝，而不是静默产生降级引擎。"""
    snapshot = engine.get_state_snapshot()
    fresh = GameEngine(seed=42)

    with pytest.raises(NotImplementedError) as ei:
        fresh.load_state_snapshot(snapshot)

    msg = str(ei.value)
    # 错误信息必须说清"为什么"和"去哪里看依据"，否则后人仍会误接线
    assert "GameState" in msg
    assert "hex_map" in msg or "地图" in msg
    assert "exp20" in msg


def test_legacy_implementation_is_marked_unusable(engine: GameEngine):
    """留档的旧实现必须带明确标注，且名字上能看出"别用"。"""
    assert hasattr(engine, "_load_state_snapshot_legacy")
    doc = engine._load_state_snapshot_legacy.__doc__ or ""  # noqa: SLF001
    assert "已停用" in doc or "不要直接调用" in doc


def test_snapshot_format_lacks_both_map_and_diplomacy(engine: GameEngine):
    """文档化当前快照格式的缺口。

    这条不是"测 bug"，而是把「格式缺字段」这件事钉在测试里 ——
    将来谁扩了 `GameState`，这条会红，提醒他同步重新评估
    `load_state_snapshot` 是否可以做完整恢复了。

    实测（2026-10-03）快照**只有 11 个字段**；v4.3.0 增至 **12 个**
    （新增 `end_reason`，D1 三层结束语义，用于回放复现终局文案）：

        turn / max_turns / year / seed / game_over / winner / end_reason /
        cities / armies / generals / messages / turn_logs

    🔴 新增的 `end_reason` **不是**地图字段、也**不是**外交字段 —— 因此它
    **不改变** `load_state_snapshot` 的可行性判断（仍缺 hex_map 与外交）。

    两样关键东西**都没有**：

    1. **无地图/地块/领地字段** → `hex_map` 无法重建（它从原始地图数据构建）；
    2. **无外交关系字段** → 恢复后外交全丢。
       注意：`faction_relations` 属于 **`GameObservation`**（喂给 AI 的观察），
       **不是** `GameState`（存档快照）—— 两者容易看混，这里用断言钉住。
    """
    snapshot = engine.get_state_snapshot()
    data = snapshot.model_dump()

    # 缺口 1：无地图数据
    hex_like = [
        k for k in data
        if "hex" in k.lower() or "tile" in k.lower() or "territor" in k.lower()
    ]
    assert hex_like == [], (
        f"GameState 里出现了疑似地图字段 {hex_like} —— "
        "若格式已扩充，请重新评估 load_state_snapshot 是否可以做完整恢复了"
    )

    # 缺口 2：无外交关系字段
    assert "faction_relations" not in data, (
        "GameState 多出了 faction_relations —— 快照格式可能已被补齐，"
        "请重新评估 load_state_snapshot 的可行性判断"
    )
    # 对照：引擎内部此刻**确实**有外交关系，说明丢的是"没进快照"而非"没有数据"
    rels = engine._diplomacy_relation_system.get_all_relations()  # noqa: SLF001
    assert len(rels) > 0, "前置失败：引擎内部本身就没有外交关系"

    # v4.3.0 新增字段：end_reason（D1）—— 记录在案，且它不解除上面的两个缺口
    assert "end_reason" in data, (
        "GameState 缺少 end_reason —— D1 三层结束语义要求它进快照以复现终局文案"
    )

    # 明确记录字段是 12 个（v4.3.0）：将来扩展格式时这条会红，提醒改这里的判断
    assert len(data) == 12, (
        f"GameState 字段数从 12 变成了 {len(data)}：{sorted(data)} —— "
        "快照格式有变动，请重新评估 load_state_snapshot 的可行性"
    )


def test_faction_relations_lives_on_observation_not_snapshot():
    """防混淆：`faction_relations` 属于 `GameObservation`，不属于 `GameState`。

    这两者极易看混（一个是喂给 AI 的观察，一个是存档快照），
    而看混会导致「以为快照里有外交数据、其实没有」的错误判断。
    """
    from game.models import GameObservation, GameState

    assert "faction_relations" in GameObservation.model_fields
    assert "faction_relations" not in GameState.model_fields
