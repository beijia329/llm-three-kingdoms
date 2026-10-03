#!/usr/bin/env python3
"""实验 13：验证「并发采集决策」不改变对局结果（确定性回归）

v4.0 把 process_turn 里 12 方串行 get_commands 改成线程池并发，
必须证明：**并发与串行跑出的对局逐字节一致**，否则会破坏项目的
"同 seed 可复现" 支柱（也是排障的基础）。

方法：同一 seed、同一批玩家，分别用 parallel_players=True / False
各跑 N 回合，逐回合对比状态指纹（城市归属 + 守军 + 兵力 + gold）。

运行：
    PYTHONHASHSEED=0 ./venv/bin/python tests/balance/exp13_parallel_determinism.py --turns 12
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from typing import Any, Dict

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


def fingerprint(manager) -> str:
    """对局状态指纹：城市归属/守军 + 军队 + 势力金粮 + 回合。"""
    eng = manager.engine
    payload: Dict[str, Any] = {"turn": eng.turn, "cities": {}, "armies": {}}
    for cid, c in sorted(eng.cities.items()):
        payload["cities"][cid] = [c.faction, c.garrison, c.gold, c.food, c.wall_hp, c.morale]
    for aid, a in sorted(eng.armies.items()):
        payload["armies"][aid] = [a.faction, a.soldiers, a.status.value, a.to_city, a.path_index]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:16]


def run(parallel: bool, turns: int, seed: int, factions=None) -> Dict[str, Any]:
    from api.game_manager import GameConfig, GameManager

    cfg = GameConfig(
        seed=seed, max_turns=64, use_llm=False,
        factions=factions, parallel_players=parallel,
    )
    gm = GameManager(cfg)
    t0 = time.time()
    per_turn = []
    for _ in range(turns):
        if gm.engine.game_over:
            break
        gm.process_turn()
        per_turn.append(fingerprint(gm))
    return {
        "parallel": parallel,
        "elapsed": round(time.time() - t0, 2),
        "per_turn": per_turn,
        "final": per_turn[-1] if per_turn else "",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--turns", type=int, default=12)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--factions", default="")
    args = ap.parse_args()

    factions = [f for f in args.factions.split(",") if f] or None

    print(f"=== 同一 seed={args.seed} 跑 {args.turns} 回合，对比并发/串行 ===")
    a = run(True, args.turns, args.seed, factions)
    b = run(False, args.turns, args.seed, factions)

    print(f"  并发(parallel=True) : {a['elapsed']}s  终局指纹 {a['final']}")
    print(f"  串行(parallel=False): {b['elapsed']}s  终局指纹 {b['final']}")
    print()

    same = a["per_turn"] == b["per_turn"]
    diffs = [i for i, (x, y) in enumerate(zip(a["per_turn"], b["per_turn"])) if x != y]

    if same:
        print(f"✅ 逐回合指纹完全一致（{len(a['per_turn'])} 回合）→ 并发不破坏确定性")
    else:
        print(f"❌ 有 {len(diffs)} 个回合不一致，首个分歧在第 {diffs[0]+1} 回合：")
        print(f"   并发 {a['per_turn'][diffs[0]]}")
        print(f"   串行 {b['per_turn'][diffs[0]]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
