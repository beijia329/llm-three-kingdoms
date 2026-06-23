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
        choices=["ai-vs-ai", "human-vs-ai", "replay", "gui"],
        default="ai-vs-ai",
        help="运行模式",
    )
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--file", type=str, help="回放文件路径")
    parser.add_argument("--max-turns", type=int, default=24, help="最大回合数")
    parser.add_argument("--llm", action="store_true", help="使用LLM玩家（默认使用CLI AI）")
    parser.add_argument("--model", type=str, default="deepseek-v4-flash", help="LLM模型名称")
    parser.add_argument("--api-key", type=str, default="", help="API密钥（默认从环境变量读取）")
    return parser.parse_args()


def run_ai_vs_ai(
    seed: int = 42, max_turns: int = 24,
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

    # 创建玩家
    players = {}
    if use_llm:
        # 只让第一个势力（魏国）用LLM，其余用CLI
        llm_client = LLMClient(
            provider="deepseek",
            model=model,
            api_key=api_key,
        )
        players["wei"] = LLMPlayer(
            faction="wei", llm_client=llm_client,
        )
        for f in ["shu", "wu"]:
            players[f] = CLIPlayer(
                faction=f, rng=GameRandom(seed + hash(f) % 10000),
            )
        print(f"  🤖 魏国: {model}")
        print(f"  👤 蜀国: CLI AI")
        print(f"  👤 吴国: CLI AI")
    else:
        for faction in FACTIONS:
            players[faction] = CLIPlayer(
                faction=faction,
                rng=GameRandom(seed + hash(faction) % 10000),
            )

    print(f"\n初始状态: {len(engine.cities)} 城市, {len(engine.generals)} 将领")
    print(f"势力分布:")
    for f_name, f_label in FACTIONS.items():
        count = engine.map.get_faction_cities(f_name)
        print(f"  {f_label}: {len(count)} 城")

    print(f"\n初始状态: {len(engine.cities)} 城市, {len(engine.generals)} 将领")
    print(f"势力分布:")
    for f_name, f_label in FACTIONS.items():
        count = engine.map.get_faction_cities(f_name)
        print(f"  {f_label}: {len(count)} 城")

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
        print(f"  → 回合结束: "
              f"🏙️{sum(1 for c in engine.cities.values() if c.faction=='wei')}魏 "
              f"{sum(1 for c in engine.cities.values() if c.faction=='shu')}蜀 "
              f"{sum(1 for c in engine.cities.values() if c.faction=='wu')}吴 "
              f"⚔️{turn_result['battles_fought']}场战斗"
        )

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
    seed: int = 42, max_turns: int = 24,
    use_llm: bool = False, model: str = "deepseek-v4-flash",
    api_key: str = "",
) -> None:
    """运行GUI模式

    Args:
        seed: 随机种子
        max_turns: 最大回合数
        use_llm: 是否使用LLM玩家
        model: LLM模型名称
        api_key: API密钥
    """
    engine = GameEngine(seed=seed)
    engine.max_turns = max_turns
    data = load_game_data()
    engine.init_game(data)

    # 创建玩家
    players = {}
    for faction in FACTIONS:
        if use_llm and faction == "wei":
            llm_client = LLMClient(
                provider="deepseek", model=model, api_key=api_key,
            )
            players[faction] = LLMPlayer(faction=faction, llm_client=llm_client)
        else:
            players[faction] = CLIPlayer(
                faction=faction,
                rng=GameRandom(seed + hash(faction) % 10000),
            )

    from renderer.game_renderer import GameRenderer
    renderer = GameRenderer(engine, title="LLM三国志 - 三国策略对战")
    renderer.run(players=players, auto_run=True)
    """执行一个回合

    Args:
        engine: 游戏引擎
        players: 玩家字典
    """
    for faction in FACTIONS:
        obs = engine.get_observation(faction)
        player = players.get(faction)
        if player:
            commands = player.get_commands(obs)
            for cmd in commands:
                engine.execute_command(cmd)

    result = engine.process_turn()
    logger.info("第%d回合完成: %s", result.get("turn"), result)


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
                     use_llm=args.llm, model=args.model, api_key=api_key)
    elif args.mode == "human-vs-ai":
        print("人机对战模式尚在开发中...")
    elif args.mode == "replay":
        print("回放模式尚在开发中...")


if __name__ == "__main__":
    main()
