#!/usr/bin/env python3
"""示例 mod 的**可运行验收脚本**。

证明三件事（缺一不可）：
  1. 相位钩子确实在生产 `process_turn` 里被调用（不是只在测试里能跑）
  2. 新命令确实被生产 `execute_command` 分发（不是只注册进表里）
  3. 装了 mod 之后**确定性不破**：同 seed 两次跑出完全相同的指纹

运行：
    PYTHONHASHSEED=0 ./venv/bin/python examples/run_mod_demo.py
"""

from __future__ import annotations

import hashlib
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from game.command_registry import is_registered, registered_command_types  # noqa: E402
from game.data_loader import load_game_data  # noqa: E402
from game.engine import GameEngine  # noqa: E402

import examples.mods.harvest_festival as festival  # noqa: E402  ← 导入即注册


def fingerprint(engine: GameEngine) -> str:
    """对局指纹：城市/军队/回合的可比较快照（确定性检查用）。"""
    parts = [f"turn={engine.turn}"]
    for cid in sorted(engine.cities):
        c = engine.cities[cid]
        parts.append(
            f"{cid}:{c.faction}:{c.gold}:{c.food}:{c.morale}:{c.garrison}:{c.wall_hp}"
        )
    for aid in sorted(engine.armies):
        a = engine.armies[aid]
        parts.append(f"{aid}:{a.faction}:{a.soldiers}:{a.status.value}:{a.progress:.4f}")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def play(seed: int, turns: int) -> tuple[GameEngine, str]:
    """跑一局（用启发式玩家，零成本）。"""
    sys.path.insert(0, os.path.join(_ROOT, "tests", "balance"))
    import pacing_lib as P  # noqa: PLC0415

    engine = GameEngine(seed=seed)
    engine.init_game(load_game_data())
    engine.max_turns = turns
    players = P.make_players(seed)
    while not engine.game_over:
        for f in P.FACTION_KEYS:
            obs = engine.get_observation(f)
            for cmd in players[f].get_commands(obs):
                engine.execute_command(cmd)
        engine.process_turn()
    return engine, fingerprint(engine)


def main() -> int:
    print("=" * 74)
    print("示例 mod：丰年祭（harvest_festival）—— 可运行验收")
    print("=" * 74)

    # ---- 0. 注册检查 ----
    print("\n[0] 注册是否生效")
    print(f"  命令 'festival' 已注册: {is_registered('festival')}")
    print(f"  当前已注册命令: {registered_command_types()}")

    # ---- 1. 相位钩子在真实 process_turn 中被调用 ----
    print("\n[1] 相位钩子是否在生产 process_turn 中被调用")
    festival.booms_applied = 0
    festival.ruins_applied = 0
    engine, fp1 = play(seed=42, turns=24)
    print(f"  丰年加成命中次数: {festival.booms_applied}")
    print(f"  民不聊生扣款次数: {festival.ruins_applied}")
    hook_ok = (festival.booms_applied + festival.ruins_applied) > 0
    print(f"  → 钩子被执行: {hook_ok}")

    # ---- 2. 新命令被真实 execute_command 分发 ----
    print("\n[2] 新命令是否被生产 execute_command 分发")
    city = next(iter(engine.cities.values()))
    city.faction = "caocao"
    city.gold = 1000
    before_morale = city.morale
    cmd = festival.FestivalCommand(
        type="festival", faction="caocao", turn=engine.turn, params={}, city=city.id
    )
    res = engine.execute_command(cmd)
    print(f"  提交 festival 命令 → success={res.success}  desc={res.description}")
    print(f"  民心 {before_morale} → {city.morale}")

    # 反例：资金不足时应当失败（证明不是无脑 return success）
    city.gold = 0
    res2 = engine.execute_command(
        festival.FestivalCommand(
            type="festival", faction="caocao", turn=engine.turn, params={}, city=city.id
        )
    )
    print(f"  金=0 时同命令 → success={res2.success}  desc={res2.description}")

    cmd_ok = res.success and not res2.success

    # ---- 3. 确定性 ----
    print("\n[3] 装 mod 后确定性是否保持（同 seed 跑两次）")
    _, fp2 = play(seed=42, turns=24)
    _, fp3 = play(seed=42, turns=24)
    print(f"  run A 指纹: {fp2}")
    print(f"  run B 指纹: {fp3}")
    det_ok = fp2 == fp3
    print(f"  → 一致: {det_ok}")

    # ---- 汇总 ----
    print("\n" + "=" * 74)
    print("结论")
    print("=" * 74)
    print(f"  [1] 相位钩子在生产链被执行 : {'✅' if hook_ok else '❌'}")
    print(f"  [2] 新命令被生产链分发     : {'✅' if cmd_ok else '❌'}")
    print(f"  [3] 确定性保持             : {'✅' if det_ok else '❌'}")
    all_ok = hook_ok and cmd_ok and det_ok
    print(f"\n  总体: {'✅ 三个扩展点均可用' if all_ok else '🔴 有不通过项'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
