#!/usr/bin/env python3
"""LLM三国志 - 程序入口

运行方式：
    python main.py                          # CLI自动对战
    python main.py --mode ai-vs-ai          # AI对战
    python main.py --mode human-vs-ai       # 人机对战（TODO）
    python main.py --mode replay --file x.json  # 观看回放（TODO）

参考设计文档：
    - docs/design/architecture.md
    - docs/specs/deployment-guide.md
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import os

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game.engine import GameEngine, TurnResult
from game.data_loader import load_game_data
from game.constants import FACTIONS
from game.random import GameRandom
from players.cli_player import CLIPlayer
from players.llm.llm_client import LLMClient
from players.llm.llm_player import LLMPlayer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="LLM三国志 - 多模型策略对战平台"
    )
    parser.add_argument(
        "--mode",
        choices=["ai-vs-ai", "human-vs-ai", "replay", "gui", "infinite"],
        default="ai-vs-ai",
        help="运行模式",
    )
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--file", type=str, help="回放文件路径")
    parser.add_argument("--max-turns", type=int, default=192, help="最大回合数")
    parser.add_argument("--start-year", type=int, default=184, help="起始年份（默认184年黄巾起义）")
    parser.add_argument("--faction", type=str, default="", help="人类玩家势力（human-vs-ai模式）")
    parser.add_argument("--llm", action="store_true", help="使用LLM玩家（默认使用CLI AI）")
    parser.add_argument("--model", type=str, default="deepseek-v4-flash", help="LLM模型名称")
    parser.add_argument("--api-key", type=str, default="", help="API密钥（默认从环境变量读取）")
    return parser.parse_args()


def run_ai_vs_ai(
    seed: int = 42, max_turns: int = 192,
    use_llm: bool = False, model: str = "deepseek-v4-flash",
    api_key: str = "",
) -> None:
    """运行 AI vs AI 自动对战

    Args:
        seed: 随机种子
        max_turns: 最大回合数
        use_llm: 是否使用LLM玩家
        model: LLM模型名称
        api_key: API密钥
    """
    title = "LLM三国志 - LLM vs CLI 对战" if use_llm else "LLM三国志 - AI vs AI 自动对战"
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)

    # 初始化引擎
    engine = GameEngine(seed=seed)
    engine.max_turns = max_turns
    data = load_game_data()
    if not data["cities"]:
        logger.error("无法加载游戏数据")
        sys.exit(1)
    engine.init_game(data)

    # 创建玩家（全部LLM 或 全部CLI）
    players = {}
    if use_llm:
        llm_client = LLMClient(provider="deepseek", model=model, api_key=api_key)
        for faction in FACTIONS:
            players[faction] = LLMPlayer(faction=faction, llm_client=llm_client)
        print(f"  🤖 全势力 LLM 对战: {model}")
    else:
        for faction in FACTIONS:
            players[faction] = CLIPlayer(faction=faction, rng=GameRandom(seed + hash(faction) % 10000))
        print(f"  👤 全势力 CLI AI 对战")

    print(f"\n初始状态: {len(engine.cities)} 城市, {len(engine.generals)} 将领")
    print(f"势力分布:")
    for f_name, f_label in FACTIONS.items():
        count = sum(1 for c in engine.cities.values() if c.faction == f_name)
        if count > 0:
            print(f"  {f_label}: {count} 城")

    print("\n--- 战斗开始 ---\n")

    # 游戏主循环
    while not engine.game_over:
        turn = engine.turn
        print(f"\n📅 第 {turn} 回合")

        # 每个玩家轮流执行命令
        for faction in FACTIONS:
            obs = engine.get_observation(faction)
            player = players[faction]
            commands = player.get_commands(obs)

            for cmd in commands:
                result = engine.execute_command(cmd)
                if result.success:
                    print(f"  [{FACTIONS[faction]}] {result.description}")
                else:
                    logger.debug("命令失败: %s - %s", cmd.type, result.description)

        # 处理回合
        turn_result = engine.process_turn()
        # 显示各势力城市数
        faction_counts = {}
        for c in engine.cities.values():
            if c.faction != "neutral":
                faction_counts[c.faction] = faction_counts.get(c.faction, 0) + 1
        summary_parts = []
        for f, cnt in sorted(faction_counts.items(), key=lambda x: -x[1])[:5]:
            summary_parts.append(f"{FACTIONS.get(f,f)}{cnt}")
        print(f"  → 回合结束: {' '.join(summary_parts)} ⚔️{turn_result['battles_fought']}场战斗")

        if engine.game_over:
            break

    # 游戏结束
    print("\n" + "=" * 60)
    print(f"  🏆 游戏结束！第 {engine.turn} 回合")
    if engine.winner:
        winner_name = FACTIONS.get(engine.winner, engine.winner)
        print(f"  胜利者: {winner_name}")
    else:
        print("  结果: 平局！")

    # 最终统计
    print("\n最终势力分布:")
    for f_name, f_label in FACTIONS.items():
        count = engine.map.get_faction_cities(f_name)
        print(f"  {f_label}: {len(count)} 城")
    print("=" * 60)


def run_gui_mode(
    seed: int = 42, max_turns: int = 192,
    use_llm: bool = False, model: str = "deepseek-v4-flash",
    api_key: str = "",
    human_faction: str = "",
) -> None:
    """运行GUI模式

    Args:
        seed: 随机种子
        max_turns: 最大回合数
        use_llm: 是否使用LLM玩家
        model: LLM模型名称
        api_key: API密钥
        human_faction: 人类玩家势力（空则全AI）
    """
    engine = GameEngine(seed=seed)
    engine.max_turns = max_turns
    data = load_game_data()
    engine.init_game(data)

    # 显示可用势力
    print("=" * 50)
    print("  184年 黄巾之乱 — 12方诸侯")
    print("=" * 50)
    for f, name in FACTIONS.items():
        cities_n = sum(1 for c in engine.cities.values() if c.faction == f)
        if cities_n > 0:
            marker = " ◀ 玩家" if f == human_faction else ""
            print(f"  [{f:12s}] {name:6s} — {cities_n}城{marker}")
    print()

    # 创建玩家
    players = {}
    if use_llm:
        llm_client = LLMClient(provider="deepseek", model=model, api_key=api_key)
        for faction in FACTIONS:
            players[faction] = LLMPlayer(faction=faction, llm_client=llm_client)
    else:
        for faction in FACTIONS:
            players[faction] = CLIPlayer(faction=faction, rng=GameRandom(seed + hash(faction) % 10000))

    if human_faction and human_faction in FACTIONS:
        title = f"LLM三国志 — 扮演{FACTIONS[human_faction]}"
    else:
        title = "LLM三国志 — 184年黄巾之乱"
    
    from renderer.game_renderer import GameRenderer
    renderer = GameRenderer(engine, title=title)
    renderer.run(players=players, auto_run=True)


def run_infinite_mode(
    seed: int = 42,
    use_llm: bool = False,
    model: str = "deepseek-v4-flash",
    api_key: str = "",
    start_year: int = 184,
) -> None:
    """运行无限模式

    Args:
        seed: 随机种子
        use_llm: 是否使用LLM玩家
        model: LLM模型名称
        api_key: API密钥
        start_year: 起始年份
    """
    from game.game_mode import GameMode

    engine = GameEngine(seed=seed)
    engine.game_mode = GameMode.INFINITE
    engine.max_turns = 9999
    engine.start_year = start_year

    data = load_game_data()
    if not data["cities"]:
        logger.error("无法加载游戏数据")
        sys.exit(1)
    engine.init_game(data)

    # 创建玩家
    players = {}
    if use_llm:
        llm_client = LLMClient(provider="deepseek", model=model, api_key=api_key)
        for faction in FACTIONS:
            players[faction] = LLMPlayer(faction=faction, llm_client=llm_client)
    else:
        for faction in FACTIONS:
            players[faction] = CLIPlayer(faction=faction, rng=GameRandom(seed + hash(faction) % 10000))

    from renderer.game_renderer import GameRenderer
    renderer = GameRenderer(engine, title="LLM三国志 - 无限模式")
    renderer.run(players=players, auto_run=True)


def main() -> None:
    """主入口"""
    args = parse_args()

    # 获取 API Key
    api_key = args.api_key or os.environ.get("OPENROUTER_API_KEY") or ""

    if args.mode == "ai-vs-ai":
        run_ai_vs_ai(
            seed=args.seed, max_turns=args.max_turns,
            use_llm=args.llm, model=args.model, api_key=api_key,
        )
    elif args.mode == "gui":
        run_gui_mode(seed=args.seed, max_turns=args.max_turns,
                     use_llm=args.llm, model=args.model, api_key=api_key,
                     human_faction=args.faction)
    elif args.mode == "infinite":
        run_infinite_mode(
            seed=args.seed,
            use_llm=args.llm, model=args.model, api_key=api_key,
            start_year=args.start_year,
        )
    elif args.mode == "human-vs-ai":
        print("人机对战模式尚在开发中...")
    elif args.mode == "replay":
        print("回放模式尚在开发中...")


if __name__ == "__main__":
    main()
