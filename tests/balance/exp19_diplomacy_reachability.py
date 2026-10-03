#!/usr/bin/env python3
"""实验 19：同盟 / 停战在生产环境是否可达（外交机制可达性实测）

⚠️ 本实验的存在本身就是一条发现：**实验台与产品路径不等价**
--------------------------------------------------------------
第一版本实验用 `tests/balance/pacing_lib.py` 驱动，测得「同盟 0 次」。
但复查时发现：`receive_message`（投递外交消息给玩家对象）**全仓只有 1 个生产调用点**
——`main.py:136`。而：

| 路径 | 是否投递 `receive_message` |
|---|---|
| `main.py` CLI `--mode ai-vs-ai` | ✅ 投递（`main.py:134-136`） |
| `api/game_manager.py`（Web 围观台） | ❌ **不投递** |
| `tests/balance/pacing_lib.py`（全部平衡实验） | ❌ **不投递** |

而 `CLIPlayer`（启发式玩家）**只能**通过 `receive_message` 得知"有人提议结盟"：
它在那里设 `_pending_alliance`（`cli_player.py:71-77`），
下一回合据此回发 `ProposeAllianceCommand`（`cli_player.py:93-99`）。

→ 所以第一版测到的 0 次同盟，**在「未投递」的那条路径上确实是结构性不可能**，
但那不是产品全貌。本实验改为**两种驱动方式都测**，把差异量化出来：

  - 变体 A「裸实验台」：不投递（= 现行所有平衡实验的口径）
  - 变体 B「对齐 CLI」：投递（= `main.py` 真实路径）

两变体的差值 = **实验台与产品路径的偏差**，这才是本条最该被记录的东西。

另一条独立疑点（阈值）
----------------------
`cli_player.py:93` 用**严格大于**：`self._diplomacy > 0.3`。
而 `game/personality.py:46-59` 的 diplomacy 值：

    han 0.5 | liubei 0.5 | liubiao 0.4          ← 通过
    yuanshao 0.3 | liuyan 0.3 | yuanshu 0.3     ← **恰好 0.3，被严格大于排除**
    caocao/sunjian/mateng 0.2
    zhangjiao/dongzhuo/gongsunzan 0.1

→ 仅 3/12 可接受盟约。该阈值是否会成为第二道瓶颈，由变体 B 的数据回答。

运行：
    PYTHONHASHSEED=0 ./venv/bin/python tests/balance/exp19_diplomacy_reachability.py --games 5 --turns 48
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict, List, Set, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import pacing_lib as P  # noqa: E402
from game.data_loader import load_game_data  # noqa: E402
from game.engine import GameEngine  # noqa: E402
from game.models import DiplomaticStatus  # noqa: E402
from game.personality import FACTION_PERSONALITY  # noqa: E402

_THRESHOLD = 0.3


def run_probe(game_seed: int, max_turns: int, deliver_messages: bool) -> Dict[str, Any]:
    """跑一局。

    deliver_messages=True 时按 `main.py:134-136` 的做法投递外交消息，
    使 CLIPlayer 能感知"有人提议结盟"。
    """
    engine = GameEngine(seed=game_seed)
    engine.init_game(load_game_data())
    engine.max_turns = int(max_turns)
    players = P.make_players(game_seed)

    seen_alliance: Set[Tuple[str, str]] = set()
    seen_truce: Set[Tuple[str, str]] = set()
    seen_war: Set[Tuple[str, str]] = set()
    peak = {"alliance": 0, "truce": 0, "war": 0}
    n_messages = 0
    n_proposals = 0

    crashed = None
    try:
        while not engine.game_over:
            for f in P.FACTION_KEYS:
                obs = engine.get_observation(f)
                for cmd in players[f].get_commands(obs):
                    res = engine.execute_command(cmd)
                    if cmd.type == "message":
                        n_messages += 1
                        if res.success and deliver_messages:
                            tgt = players.get(getattr(cmd, "to", None))
                            if tgt is not None:
                                tgt.receive_message(
                                    f, str(getattr(cmd, "content", ""))
                                )
                    elif cmd.type == "propose_alliance" and res.success:
                        n_proposals += 1
            engine.process_turn()

            rels = engine._diplomacy_relation_system.get_all_relations()
            cur = {"alliance": 0, "truce": 0, "war": 0}
            for k, r in rels.items():
                if r.status == DiplomaticStatus.ALLIANCE:
                    cur["alliance"] += 1
                    seen_alliance.add(k)
                elif r.status == DiplomaticStatus.TRUCE:
                    cur["truce"] += 1
                    seen_truce.add(k)
                elif r.status == DiplomaticStatus.WAR:
                    cur["war"] += 1
                    seen_war.add(k)
            for key in peak:
                peak[key] = max(peak[key], cur[key])
    except Exception as exc:
        crashed = repr(exc)

    return {
        "seed": game_seed,
        "turns": engine.turn,
        "crashed": crashed,
        "deliver": deliver_messages,
        "n_messages": n_messages,
        "n_proposals": n_proposals,
        "peak_alliance": peak["alliance"],
        "peak_truce": peak["truce"],
        "peak_war": peak["war"],
        "n_alliance_pairs": len(seen_alliance),
        "n_truce_pairs": len(seen_truce),
        "n_war_pairs": len(seen_war),
        "alliance_pairs": sorted(seen_alliance),
    }


def _report(label: str, rows: List[Dict[str, Any]]) -> Dict[str, int]:
    tot = {
        "turns": sum(r["turns"] for r in rows),
        "war": sum(r["n_war_pairs"] for r in rows),
        "truce": sum(r["n_truce_pairs"] for r in rows),
        "alliance": sum(r["n_alliance_pairs"] for r in rows),
        "msg": sum(r["n_messages"] for r in rows),
        "prop": sum(r["n_proposals"] for r in rows),
    }
    print(f"\n【{label}】")
    print(f"  总回合 {tot['turns']}｜外交消息 {tot['msg']} 条｜结盟提议发出 {tot['prop']} 次")
    print(f"  [阳性对照] 曾处于战争的关系对 = {tot['war']}")
    print(f"  曾处于停战的关系对 = {tot['truce']}")
    print(f"  曾处于同盟的关系对 = {tot['alliance']}")
    for r in rows:
        if r["alliance_pairs"]:
            print(f"    seed={r['seed']} 同盟对: {r['alliance_pairs']}")
    return tot


def main() -> int:
    ap = argparse.ArgumentParser(description="同盟/停战可达性实测")
    ap.add_argument("--games", type=int, default=5)
    ap.add_argument("--turns", type=int, default=48)
    ap.add_argument("--seed0", type=int, default=42)
    args = ap.parse_args()

    P.ensure_reproducible()

    print("=" * 78)
    print("实验 19：同盟 / 停战在生产环境是否可达（两变体对照）")
    print(f"games={args.games}  turns={args.turns}  seed0={args.seed0}")
    print("=" * 78)

    can_accept = [f for f, v in FACTION_PERSONALITY.items() if v["diplomacy"] > _THRESHOLD]
    at = [f for f, v in FACTION_PERSONALITY.items() if v["diplomacy"] == _THRESHOLD]
    print(f"\n可接受盟约（diplomacy > {_THRESHOLD}）: {len(can_accept)}/12 -> {sorted(can_accept)}")
    print(f"恰好 = {_THRESHOLD} 被严格大于排除: {sorted(at)}")
    print(f"→ 可结盟对上限 = C({len(can_accept)},2) = {len(can_accept)*(len(can_accept)-1)//2} 对")

    rows_a = [run_probe(args.seed0 + i, args.turns, False) for i in range(args.games)]
    rows_b = [run_probe(args.seed0 + i, args.turns, True) for i in range(args.games)]

    ta = _report("变体 A：裸实验台（不投递 = 现行所有平衡实验口径）", rows_a)
    tb = _report("变体 B：对齐 CLI（投递，= main.py 真实路径）", rows_b)

    print("\n" + "=" * 78)
    print("判定")
    print("=" * 78)

    if ta["war"] == 0 or tb["war"] == 0:
        print("  🔴 阳性对照未命中（某变体连战争都没发生）——本轮不得下结论。")
        return 2

    print(f"  ✅ 阳性对照双变体均命中（战争对 {ta['war']} / {tb['war']}），探针有效。")
    print(f"\n  变体 A（不投递）同盟 = {ta['alliance']} 对，提议发出 {ta['prop']} 次")
    print(f"  变体 B（投递）  同盟 = {tb['alliance']} 对，提议发出 {tb['prop']} 次")

    if ta["alliance"] == 0 and tb["alliance"] == 0:
        print(
            "\n  🔴 结论：**两种路径下同盟均为 0**。\n"
            "     → 这不是实验台缺投递导致的假象，是真瓶颈。\n"
            "     即使按 main.py 投递消息，仍无同盟发生——瓶颈在 `> 0.3` 阈值\n"
            "     （仅 3/12 可接受，且需双方同时愿意）。"
        )
    elif ta["alliance"] == 0 and tb["alliance"] > 0:
        print(
            "\n  🔴 结论：**同盟只在投递路径下发生**。\n"
            f"     变体 A（不投递）= 0 对；变体 B（投递）= {tb['alliance']} 对。\n"
            "     → 意味着 `tests/balance/` 下**全部平衡实验**一直在测一个\n"
            "       『启发式玩家不可能结盟』的世界；且 Web 路径同样不投递，\n"
            "       故 Web 的规则-AI 模式也无法结盟。这是实验台/产品不等价问题，\n"
            "       不只是数值平衡问题。"
        )
    else:
        print(f"\n  ✅ 同盟在两种路径下均可发生（A={ta['alliance']} / B={tb['alliance']} 对）。")

    if ta["truce"] == 0 and tb["truce"] == 0:
        print("  ⚠️ 停战在两变体下均为 0 对，同样值得追。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
