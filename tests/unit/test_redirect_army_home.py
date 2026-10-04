"""`_redirect_army_home` 四分支单元测试（v4.2.0 任务C）

`GameEngine._redirect_army_home`（`game/engine.py`）是 v4.0 新增的撤退回落逻辑，
此前**无单元测试**。本文件覆盖它的四个分支：

1. 正常战败撤退 → 回程路径重算（`path_hexes` 指向 home、`status=RETREATING`）；
2. 出发城丢失、目标城仍是己方 → home 改为目标城；
3. 出发城与目标城都不是己方 → 保持 RETREATING（不动路径）；
4. 无可行回程路径 → 残部归建（`_disband_army_into_city` 被调用）。

## 改坏验证（每条断言的"破坏方式"）
- 分支1：把重算路径段改成"只对调 from/to"（删掉 `find_path`/回写 `path_hexes`）
  → `test_branch1_*` 的 `path_hexes[-1] == home` 断言红。
- 分支2：删掉 `alt = self.cities.get(army.to_city)` 回退块
  → `test_branch2_*` 会走到 else（保持 RETREATING 且 to_city 不变）→ 断言红。
- 分支3：把 `army.status = ArmyStatus.RETREATING; return` 改成继续往下走
  → `test_branch3_*` 的「路径未变 / from-to 未换」断言红。
- 分支4：把无路径时的 `self._disband_army_into_city(...)` 改成 `pass`
  → `test_branch4_*` 的「军队已解散 / 守军增加」断言红。
"""

from __future__ import annotations

from typing import List, Tuple

import pytest

from game.constants import FACTIONS
from game.data_loader import load_game_data
from game.engine import GameEngine
from game.models import Army, ArmyStatus, City


@pytest.fixture
def engine() -> GameEngine:
    e = GameEngine(seed=42)
    e.init_game(load_game_data())
    return e


def _pick_pair(engine: GameEngine) -> Tuple[str, City, City]:
    """挑 (势力, 己方城 home, 另一座与 home 六角连通的城 other)。"""
    for f in sorted(FACTIONS):
        own = [c for c in engine.cities.values() if c.faction == f]
        if not own:
            continue
        home = sorted(own, key=lambda c: c.id)[0]
        for other in sorted(engine.cities.values(), key=lambda c: c.id):
            if other.id == home.id:
                continue
            if engine.hex_map is not None and engine.hex_map.find_path(
                other.position, home.position
            ):
                return f, home, other
    raise AssertionError("测试前置失败：找不到一对六角连通的城")


def _army(faction: str, from_city: str, to_city: str, current_hex=None,
          soldiers: int = 500) -> Army:
    return Army(
        id="army_r", faction=faction, general_id="g_r", soldiers=soldiers,
        food=100, food_consumption_per_turn=50, morale=60,
        status=ArmyStatus.BESIEGING, from_city=from_city, to_city=to_city,
        progress=1.0, total_distance=1,
        current_hex=current_hex,
        path_hexes=[],
    )


# ============================================================
# 分支 1：正常战败撤退 → 回程路径重算
# ============================================================

def test_branch1_recomputes_return_path(engine: GameEngine):
    f, home, other = _pick_pair(engine)
    army = _army(f, from_city=home.id, to_city=other.id, current_hex=other.position)
    engine.armies[army.id] = army

    engine._redirect_army_home(army)

    assert army.status == ArmyStatus.RETREATING
    # 语义换向：to_city 变为自家出发城
    assert army.to_city == home.id
    # 关键：回程路径被重算，且终点指向 home（不是去程路径）
    assert army.path_hexes, "回程路径未重算（path_hexes 为空）"
    assert army.path_hexes[-1] == home.position, "回程路径终点不是出发城"
    assert army.path_index == 0
    assert army.progress == 0.0
    assert army.total_distance == max(1, len(army.path_hexes) - 1)


def test_branch1_does_not_keep_outbound_path(engine: GameEngine):
    """回程路径不应等于去程路径（原缺陷：撤退仍沿去程走）。"""
    f, home, other = _pick_pair(engine)
    outbound = engine.hex_map.find_path(home.position, other.position)
    army = _army(f, from_city=home.id, to_city=other.id, current_hex=other.position)
    army.path_hexes = list(outbound)
    engine.armies[army.id] = army

    engine._redirect_army_home(army)

    assert army.path_hexes[-1] == home.position
    assert army.path_hexes[0] == other.position


# ============================================================
# 分支 2：出发城丢失、目标城仍是己方 → home 改为目标城
# ============================================================

def test_branch2_falls_back_to_target_city(engine: GameEngine):
    f, home, other = _pick_pair(engine)
    # from_city 指向一座**非己方**城（模拟出发城已丢失）
    enemy = sorted(
        (c for c in engine.cities.values() if c.faction not in (f, home.faction)),
        key=lambda c: c.id,
    )[0]
    assert enemy.faction != f

    army = _army(f, from_city=enemy.id, to_city=home.id)
    engine.armies[army.id] = army

    engine._redirect_army_home(army)

    assert army.status == ArmyStatus.RETREATING
    # home 回退为目标城（仍是己方）
    assert army.to_city == home.id


# ============================================================
# 分支 3：出发城与目标城都不是己方 → 保持 RETREATING
# ============================================================

def test_branch3_keeps_retreating_when_no_own_city(engine: GameEngine):
    f, home, other = _pick_pair(engine)
    enemies = [
        c for c in sorted(engine.cities.values(), key=lambda c: c.id)
        if c.faction != f and c.faction != "neutral"
    ]
    assert len(enemies) >= 2
    e1, e2 = enemies[0], enemies[1]

    army = _army(f, from_city=e1.id, to_city=e2.id)
    army.path_hexes = []
    engine.armies[army.id] = army

    engine._redirect_army_home(army)

    # 保持撤退，不换向、不重算路径
    assert army.status == ArmyStatus.RETREATING
    assert army.from_city == e1.id
    assert army.to_city == e2.id
    assert army.path_hexes == []


# ============================================================
# 分支 4：无可行回程路径 → 残部归建
# ============================================================

def test_branch4_disbands_when_no_return_path(engine: GameEngine, monkeypatch):
    f, home, other = _pick_pair(engine)
    army = _army(f, from_city=home.id, to_city=other.id, current_hex=other.position)
    engine.armies[army.id] = army
    garrison_before = home.garrison

    # 令回程寻路无解
    monkeypatch.setattr(engine.hex_map, "find_path", lambda *a, **k: [])

    called: List[str] = []
    original = engine._disband_army_into_city

    def spy(a, c):  # noqa: ANN001
        called.append(a.id)
        return original(a, c)

    monkeypatch.setattr(engine, "_disband_army_into_city", spy)

    engine._redirect_army_home(army)

    assert called == [army.id], "_disband_army_into_city 未被调用（残部会变成野外僵尸）"
    assert army.id not in engine.armies, "残军未解散"
    assert home.garrison == garrison_before + 500, "残部兵力未并入守军（凭空蒸发）"
