#!/usr/bin/env python3
"""实验 18：城市的「民心自然变化」是否在生产环境生效

发现过程（记录在此，避免后人重走）
----------------------------------
最初怀疑「围城标记泄漏」→ 实验 17 用阳性对照实测，**否证**（标记每回合都被正确清 0）。
但实验 17 顺带暴露了真正的疑点：标记在行军相位写入、战斗结算清 0，
而在它之前运行的资源产出相位里，`is_besieged` 恒为 False ——
于是 `city_system.py:376` 的 `-3 民心` 可能永远不执行。

进一步核查调用链，发现**比"围城惩罚没生效"严重得多**的事：

    game/engine.py:859-891
    for city in self.cities.values():
        if self.hex_map is not None:
            ... ResourceSystem.calculate_resources(...)   # ← 生产走这条
            city.gold/food/population += ...
        else:
            self._city_system.update_city(city, ...)      # ← 只有无六角地图时走这条
        result["cities_updated"] += 1

`CitySystem.update_city`（`city_system.py:287`）是 **`CitySystem._calculate_morale_change`
的唯一调用者**（`:314`），而 `_calculate_morale_change`（`:357`）承载**全部四条民心自然规则**：

    1. 被围困      → -3 / 回合
    2. 粮草为 0    → -5 / 回合
    3. 粮草充足盈余 → +1 / 回合
    4. 民心向 50 回归（>70 微降 / <30 微升）   ← **全局唯一的自校正项**

`self.hex_map` 由 `engine.py:280` 在生成六角地图时赋值（成功即非 None），
**生产环境有地图**（否则前端无图可渲染）→ 恒走 `if` 分支 →
`update_city` 与 `_calculate_morale_change` **永不执行**。

在生产的其他地方，`city.morale` 只有这些写入点：
    - `engine.py:1087` 失城 `-20`（下限 20）
    - `engine.py:1234` 人设代价 `-NATURE_STRAIN_MORALE_PENALTY`
    - `city_system.py:172` `develop("culture")` `+CULTURE_MORALE_BONUS`（玩家主动操作）
→ 即：**除「文化发展」这一主动操作外，民心在生产环境中只降不升，
  且完全没有向 50 回归的自校正**。

本实验的证伪条件（缺一不可）
----------------------------
- 阳性对照：`ResourceSystem.calculate_resources` 必须被大量调用
  （证明 `if hex_map is not None` 确是生产分支）；
- 观测值：`CitySystem._calculate_morale_change` 的调用次数；
- 前提断言：`engine.hex_map is not None`。

若阳性对照为 0，则本实验**不得**下任何结论。

运行：
    PYTHONHASHSEED=0 ./venv/bin/python tests/balance/exp18_siege_morale_reachability.py --games 5 --turns 48
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
from typing import Any, Dict, List

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import pacing_lib as P  # noqa: E402
from game.data_loader import load_game_data  # noqa: E402
from game.engine import GameEngine  # noqa: E402
from game.systems.city_system import CitySystem  # noqa: E402
from game.systems.resource_system import ResourceSystem  # noqa: E402


def run_probe(game_seed: int, max_turns: int) -> Dict[str, Any]:
    c = {
        "calc_resources_calls": 0,     # 阳性对照
        "update_city_calls": 0,
        "morale_change_calls": 0,      # 观测值
        "besieged_at_morale_time": 0,  # 即便调用了，看到的 is_besieged 次数
    }

    orig_calc = ResourceSystem.calculate_resources
    orig_update = CitySystem.update_city
    orig_morale = CitySystem._calculate_morale_change

    def patched_calc(self, *a, **kw):  # type: ignore[no-untyped-def]
        c["calc_resources_calls"] += 1
        return orig_calc(self, *a, **kw)

    def patched_update(self, city, generals=None):  # type: ignore[no-untyped-def]
        c["update_city_calls"] += 1
        if city.is_besieged:
            c["besieged_at_morale_time"] += 1
        return orig_update(self, city, generals)

    def patched_morale(city):  # type: ignore[no-untyped-def]
        c["morale_change_calls"] += 1
        return orig_morale(city)

    ResourceSystem.calculate_resources = patched_calc  # type: ignore[assignment]
    CitySystem.update_city = patched_update  # type: ignore[assignment]
    CitySystem._calculate_morale_change = staticmethod(patched_morale)  # type: ignore[assignment]

    try:
        engine = GameEngine(seed=game_seed)
        engine.init_game(load_game_data())
        engine.max_turns = int(max_turns)
        has_hex_map = engine.hex_map is not None
        players = P.make_players(game_seed)
        crashed = None
        try:
            while not engine.game_over:
                for f in P.FACTION_KEYS:
                    obs = engine.get_observation(f)
                    for cmd in players[f].get_commands(obs):
                        engine.execute_command(cmd)
                engine.process_turn()
        except Exception as exc:
            crashed = repr(exc)
    finally:
        ResourceSystem.calculate_resources = orig_calc  # type: ignore[assignment]
        CitySystem.update_city = orig_update  # type: ignore[assignment]
        CitySystem._calculate_morale_change = orig_morale  # type: ignore[assignment]

    morales = [city.morale for city in engine.cities.values()]
    return {
        "seed": game_seed,
        "turns": engine.turn,
        "crashed": crashed,
        "has_hex_map": has_hex_map,
        **c,
        "final_morale_min": min(morales) if morales else None,
        "final_morale_median": statistics.median(morales) if morales else None,
        "final_morale_max": max(morales) if morales else None,
        "final_morale_zero": sum(1 for m in morales if m == 0),
        "n_cities": len(morales),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="民心自然变化在生产的可达性")
    ap.add_argument("--games", type=int, default=5)
    ap.add_argument("--turns", type=int, default=48)
    ap.add_argument("--seed0", type=int, default=42)
    args = ap.parse_args()

    P.ensure_reproducible()

    print("=" * 78)
    print("实验 18：城市「民心自然变化」是否在生产环境生效")
    print(f"games={args.games}  turns={args.turns}  seed0={args.seed0}")
    print("=" * 78)

    rows = []
    for i in range(args.games):
        seed = args.seed0 + i
        r = run_probe(seed, args.turns)
        rows.append(r)
        crash = f"  ⚠️ {r['crashed']}" if r["crashed"] else ""
        print(f"\n--- seed={seed} ---{crash}")
        print(f"  hex_map 存在: {r['has_hex_map']}")
        print(f"  [阳性对照] calculate_resources 调用 {r['calc_resources_calls']} 次")
        print(f"  [观测]     update_city           调用 {r['update_city_calls']} 次")
        print(f"  [观测]     _calculate_morale_change 调用 {r['morale_change_calls']} 次")
        print(
            f"  终局民心 min/中位/max = {r['final_morale_min']}/"
            f"{r['final_morale_median']}/{r['final_morale_max']}"
            f"（=0 的城 {r['final_morale_zero']}/{r['n_cities']}）"
        )

    print("\n" + "=" * 78)
    print("汇总与证伪判定")
    print("=" * 78)

    pos_total = sum(r["calc_resources_calls"] for r in rows)
    obs_total = sum(r["morale_change_calls"] for r in rows)
    upd_total = sum(r["update_city_calls"] for r in rows)
    hex_ok = all(r["has_hex_map"] for r in rows)

    print(f"  前提：全部对局 hex_map 非 None          = {hex_ok}")
    print(f"  阳性对照：calculate_resources 总调用     = {pos_total}")
    print(f"  观测：update_city 总调用                 = {upd_total}")
    print(f"  观测：_calculate_morale_change 总调用    = {obs_total}")

    if pos_total == 0 or not hex_ok:
        print("\n  🔴 探针无效（阳性对照未命中）——本轮**不得**下结论，先修探针。")
        return 2

    print("\n  终局民心（逐局 min/中位/max）:")
    for r in rows:
        print(
            f"    seed={r['seed']}: {r['final_morale_min']}/"
            f"{r['final_morale_median']}/{r['final_morale_max']}"
        )
    print(
        f"  终局民心为 0 的城市总数: {sum(r['final_morale_zero'] for r in rows)}"
        f" / {sum(r['n_cities'] for r in rows)}"
    )

    if obs_total == 0:
        print(
            "\n  🔴 结论：`CitySystem._calculate_morale_change` 在"
            f" {args.games} 局 × {args.turns} 回合中**一次都没执行**。"
        )
        print("     而它承载全部四条民心自然规则（围城 -3 / 断粮 -5 / 盈余 +1 / 向 50 回归）。")
        print("     根因：`engine.py:891` 的 `update_city` 位于 `else`（无六角地图）分支，")
        print("     生产环境恒有地图 → 恒走 `if`（`calculate_resources`）分支 → 整段逻辑从未执行。")
        print("     后果：民心除「文化发展」这一主动操作外只降不升，且无自校正。")
    else:
        print("\n  ✅ 该函数确实在生产中被调用，非死机制。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
