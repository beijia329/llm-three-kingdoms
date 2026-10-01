"""3 方 LLM 对局验证 runner（DeepSeek）。

用途：验证「LLM 大乱斗」主链路是否真能跑通（prompt → LLM → 解析 → 命令执行 → 外交），
并打印每个势力的「思考」以观察 LLM 的主观智能。

用法：
    ./venv/bin/python tests/llm_3p_run.py --turns 3
    ./venv/bin/python tests/llm_3p_run.py --turns 24 --factions caocao,liubei,sunjian

不打印任何密钥。默认从环境变量 DEEPSEEK_API_KEY 读取，缺失时回退解析 ~/.zshrc。
"""

from __future__ import annotations

import argparse
import os
import sys
import time

_PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJ not in sys.path:
    sys.path.insert(0, _PROJ)

from game.constants import FACTIONS                      # noqa: E402
from game.data_loader import load_game_data              # noqa: E402
from game.engine import GameEngine                       # noqa: E402
from game.random import GameRandom                       # noqa: E402
from players.llm.llm_client import LLMClient             # noqa: E402
from players.llm.llm_player import LLMPlayer             # noqa: E402


def get_deepseek_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    try:
        with open(os.path.expanduser("~/.zshrc"), "r", errors="ignore") as f:
            for line in f:
                if "DEEPSEEK_API_KEY" in line and "=" in line:
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if v:
                        return v
    except Exception:
        pass
    return ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--turns", type=int, default=3, help="要跑的回合数")
    ap.add_argument("--factions", type=str, default="caocao,liubei,sunjian",
                    help="参战势力（逗号分隔，映射魏/蜀/吴）")
    ap.add_argument("--model", type=str, default="deepseek-flash",
                    help="模型名（DeepSeek-V4.1-Flash 的 API id 是 deepseek-flash）")
    ap.add_argument("--provider", type=str, default="deepseek", help="provider")
    ap.add_argument("--tmp", type=float, default=0.7, help="temperature")
    ap.add_argument("--seed", type=int, default=42, help="随机种子")
    ap.add_argument("--quiet", action="store_true", help="不打印每回合明细（批量观察用）")
    args = ap.parse_args()

    key = get_deepseek_key()
    if not key:
        raise SystemExit("未找到 DEEPSEEK_API_KEY（环境变量或 ~/.zshrc）")

    facs = [f.strip() for f in args.factions.split(",") if f.strip()]
    for f in facs:
        if f not in FACTIONS:
            raise SystemExit(f"未知势力: {f}")

    engine = GameEngine(seed=args.seed)
    engine.max_turns = args.turns
    engine.init_game(load_game_data())

    # 中立化非参战势力，形成「3 方争天下」局面
    for c in engine.cities.values():
        if c.faction not in facs:
            c.faction = "neutral"

    client = LLMClient(provider=args.provider, model=args.model, api_key=key)
    players = {
        f: LLMPlayer(faction=f, llm_client=client,
                     rng=GameRandom((args.seed * 131 + i) % 100000))
        for i, f in enumerate(facs)
    }
    # 外交目标只提示本局参战势力，避免 LLM 对已被中立化的势力空喊
    for p in players.values():
        p.faction_keys = facs

    print("=" * 70)
    print(f"  3 方 LLM 对局  模型={args.model}  回合={args.turns}")
    print(f"  参战: " + " / ".join(f"{f}({FACTIONS.get(f, f)})" for f in facs))
    print(f"  初始城数: " + str({f: sum(1 for c in engine.cities.values() if c.faction == f) for f in facs}))
    print("=" * 70)

    battle_total = 0
    msg_total = 0
    rejected_total = 0
    reasoning_total = 0
    while not engine.game_over and engine.turn <= args.turns:
        for f in facs:
            if engine.game_over:
                break
            obs = engine.get_observation(f)
            t0 = time.time()
            cmds = players[f].get_commands(obs)
            dt = time.time() - t0
            msg_total += sum(1 for c in cmds if type(c).__name__ == "MessageCommand")
            reasoning = (getattr(players[f], "last_reasoning", "") or "").strip()
            if reasoning:
                reasoning_total += 1
            if not args.quiet:
                print(f"\n--- T{engine.turn} {FACTIONS.get(f, f)} ({dt:.1f}s) ---")
                print(f"  [策略] {reasoning[:400] if reasoning else '(空)'}")
                print(f"  [命令] {[type(c).__name__ for c in cmds]}")
            for c in cmds:
                r = engine.execute_command(c)
                if not getattr(r, "success", True):
                    rejected_total += 1
                    if not args.quiet:
                        print(f"     ! 命令被拒: {type(c).__name__} {getattr(r, 'message', '')}")
        res = engine.process_turn()
        battle_total += res.get("battles_fought", 0)
        counts = {f: sum(1 for c in engine.cities.values() if c.faction == f) for f in facs}
        counts["neutral"] = sum(1 for c in engine.cities.values() if c.faction == "neutral")
        print(f"  >> 第{res['turn']}回合结束: 战斗{res['battles_fought']}场 城数={counts}")

    print("\n" + "=" * 70)
    print("  成本/用量:", client.get_cost_summary())
    print("  胜者:", engine.winner)
    print("=" * 70)
    import json
    print("SUMMARY " + json.dumps({
        "seed": args.seed, "turns": engine.turn, "winner": engine.winner,
        "final": {f: sum(1 for c in engine.cities.values() if c.faction == f) for f in facs},
        "neutral": sum(1 for c in engine.cities.values() if c.faction == "neutral"),
        "battles_total": battle_total, "messages_total": msg_total,
        "rejected_total": rejected_total,
        "reasoning_nonempty_total": reasoning_total,
        "cost_usd": round(client.get_cost_summary()["total_cost"], 5),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
