"""游戏会话管理器

管理一个 GameEngine 实例，处理前端命令与状态序列化。
"""

from __future__ import annotations

import logging
import os
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from game.constants import FACTIONS
from game.data_loader import load_game_data
from game.engine import GameEngine
from game.models import (
    AttackCommand,
    Command,
    DeclareWarCommand,
    DevelopCommand,
    ExploreCommand,
    GameObservation,
    MessageCommand,
    ProposeAllianceCommand,
    RecruitCommand,
    RewardCommand,
    RumorCommand,
)
from game.random import GameRandom
from players.base_player import BasePlayer
from players.cli_player import CLIPlayer
from players.llm.llm_client import LLMClient
from players.llm.llm_player import LLMPlayer

logger = logging.getLogger(__name__)


def _stable_hash(text: str) -> int:
    """跨进程稳定的字符串哈希（替代内置 hash()）

    🔴 Python 的 `str.__hash__` 默认按进程随机加盐（PYTHONHASHSEED），
    同一 seed 在不同进程会派生出不同的玩家随机流 → **对局不可复现**。
    design-strategist 与 quality-lead 都独立复现过该现象
    （同一 seed 出征次数 271 vs 245）。

    这里用 CRC32，跨进程恒定，保证「同 seed → 同对局」。

    Args:
        text: 待哈希文本（此处为势力键）

    Returns:
        0 ~ 2^32-1 的稳定整数
    """
    return zlib.crc32(text.encode("utf-8")) & 0xFFFFFFFF


@dataclass
class GameConfig:
    """游戏配置"""

    seed: int = 42
    max_turns: int = 192
    game_mode: str = "standard"
    human_faction: Optional[str] = None
    # ---- LLM 玩家相关（决策理由暴露使用）----
    use_llm: bool = False
    """为参与势力创建 LLMPlayer（真实大模型决策）而非 CLIPlayer"""
    model: str = "deepseek-flash"
    """LLM 模型名（DeepSeek-V4.1-Flash 的 API id 即 deepseek-flash）"""
    provider: str = "deepseek"
    """LLM 提供商（deepseek / openai / openrouter）"""
    factions: Optional[List[str]] = None
    """只给这些势力建玩家；None = 全部 12 方参战"""
    # ---- 并发采集（v4.0）----
    parallel_players: bool = True
    """并发采集各势力决策。

    LLM 模式下 get_commands 是**阻塞网络调用**（实测 3 方串行 27~42 秒/回合），
    12 方串行会到分钟级 → 前端点「下一回合」必然超时。
    并发后单回合耗时约等于最慢的一方，12 方从 ~6 分钟降到 ~40 秒。
    关闭本项可退回串行（用于对照实验/排障）。
    """
    max_workers: int = 12
    """并发决策的最大线程数"""


class GameManager:
    """游戏会话管理器

    封装单个 GameEngine 实例，提供前端友好的接口：
    - 初始化游戏
    - 执行命令
    - 推进回合
    - 获取可序列化状态
    """

    def __init__(self, config: Optional[GameConfig] = None) -> None:
        """初始化游戏管理器

        Args:
            config: 游戏配置，默认标准模式 seed=42
        """
        self.config = config or GameConfig()
        self.engine: Optional[GameEngine] = None
        self._players: Dict[str, BasePlayer] = {}
        self._events: List[Dict[str, Any]] = []
        # 决策理由（供前端「决策」面板展示）：每条 = 一次 LLM 决策
        self._reasoning: List[Dict[str, Any]] = []
        self._init_engine()

    def _init_engine(self) -> None:
        """初始化游戏引擎与 AI 玩家"""
        self.engine = GameEngine(seed=self.config.seed)
        self.engine.max_turns = self.config.max_turns

        if self.config.game_mode == "infinite":
            from game.game_mode import GameMode
            self.engine.game_mode = GameMode.INFINITE
            self.engine.max_turns = 9999

        data = load_game_data()
        if not data.get("cities"):
            raise RuntimeError("无法加载游戏数据")
        self.engine.init_game(data)

        # 创建 AI 玩家（人类势力如有则不创建 AI）
        # 参与势力：config.factions 指定则只用这些，None = 全部 12 方
        participant_factions = (
            list(self.config.factions) if self.config.factions else list(FACTIONS.keys())
        )

        # use_llm=True 时，尽量用 LLMPlayer（真实大模型决策）；
        # 缺少 API Key 时回退为 CLIPlayer，保证游戏仍可运行。
        #
        # ⚠️ 权衡（本次未做并发改造）：LLMPlayer.get_commands 内部是对
        #   LLM API 的**阻塞网络调用**，在 process_turn 的势力循环中逐个
        #   串行执行。势力越多、延迟越高，单回合耗时线性增长。后续可考虑
        #   并发/异步化，本次仅打通「决策理由」链路，不做并发。
        llm_client: Optional[LLMClient] = None
        # 前端「降级提示」用：记录 LLM 实际是否真的启用，以及失败原因。
        # 🔴 历史教训：此前 key 缺失只 logger.warning，前端无任何提示 →
        #    用户以为在跑 LLM，实际已回退 CLIPlayer，决策 tab 恒空，极难排查。
        self.llm_active: bool = False
        self.llm_error: str = ""
        if self.config.use_llm:
            api_key = (
                os.environ.get("LLM_API_KEY")
                or os.environ.get("DEEPSEEK_API_KEY")
                or ""
            ).strip()
            # 占位符检测：.env 里若残留 sk-你的key 之类，会"存在但必失败"
            _PLACEHOLDER_HINTS = ("你的", "your", "yourkey", "xxx", "<", "你的key")
            if api_key and any(h in api_key.lower() for h in _PLACEHOLDER_HINTS):
                self.llm_error = (
                    f"检测到 LLM_API_KEY 是占位符（{api_key[:12]}…），"
                    "请在环境变量中注入真实 key（见 .env 注释）"
                )
                logger.error("use_llm=True 但 key 为占位符: %s", self.llm_error)
            elif api_key:
                llm_client = LLMClient(
                    provider=self.config.provider,
                    model=self.config.model,
                    api_key=api_key,
                )
                self.llm_active = True
            else:
                self.llm_error = (
                    "未找到 LLM_API_KEY / DEEPSEEK_API_KEY 环境变量，"
                    "已回退为 CLI AI（决策理由不可用）"
                )
                logger.warning("use_llm=True 但未找到 key：%s", self.llm_error)

        self._players = {}
        for faction in participant_factions:
            if faction == self.config.human_faction:
                continue
            if llm_client is not None:
                player = LLMPlayer(faction=faction, llm_client=llm_client)
                # 仅把参战势力作为外交目标提示，避免对不存在的势力发消息
                player.faction_keys = list(participant_factions)
                self._players[faction] = player
            else:
                self._players[faction] = CLIPlayer(
                    faction=faction,
                    # 🔴 必须用稳定哈希：内置 hash() 按进程随机加盐，
                    #    会让同一 seed 在不同进程跑出不同对局（不可复现）。
                    rng=GameRandom(self.config.seed + _stable_hash(faction) % 10000),
                )

        self._add_event("游戏开始：184年 黄巾之乱", "info")
        logger.info("GameManager 初始化完成: seed=%s, mode=%s", self.config.seed, self.config.game_mode)

    # ============================================================
    # 状态序列化
    # ============================================================

    def get_state(self) -> Dict[str, Any]:
        """获取当前游戏状态（JSON 可序列化）

        Returns:
            包含 cities、armies、generals、turn、game_over 等字段的字典
        """
        if self.engine is None:
            return {}

        snapshot = self.engine.get_state_snapshot()
        data = snapshot.model_dump(mode="json")

        # 补充 factions 列表与统计
        faction_stats = {}
        for fid, fname in FACTIONS.items():
            cities = [c for c in self.engine.cities.values() if c.faction == fid]
            faction_stats[fid] = {
                "name": fname,
                "cities": len(cities),
                "garrison": sum(c.garrison for c in cities),
                "gold": sum(c.gold for c in cities),
                "food": sum(c.food for c in cities),
                "population": sum(c.population for c in cities),
            }

        # 补充六角格地图（用于前端地形渲染）
        hex_tiles = []
        if self.engine.hex_map is not None:
            for tile in self.engine.hex_map.iter_tiles():
                hex_tiles.append({
                    "q": tile.coord.q,
                    "r": tile.coord.r,
                    "terrain": tile.terrain.value if hasattr(tile.terrain, 'value') else str(tile.terrain),
                    "faction": tile.faction,
                    "owner_city_id": tile.owner_city_id,
                    "province_id": tile.province_id,
                })

        # max_turns / year 现在由 GameState 模型自动序列化（B-03 修复后）
        data["faction_stats"] = faction_stats
        data["events"] = list(self._events[-20:])
        # 决策理由（前端「决策」面板）：最近若干条 LLM 决策
        data["reasoning"] = list(self._reasoning)
        data["human_faction"] = self.config.human_faction
        # LLM 实际启用状态 + 降级原因（前端要显式提示，不能让用户误以为在跑 LLM）
        data["llm_requested"] = bool(self.config.use_llm)
        data["llm_active"] = bool(self.llm_active)
        data["llm_error"] = self.llm_error
        data["llm_model"] = self.config.model if self.llm_active else ""
        data["llm_factions"] = list(self._players.keys())
        data["hex_map"] = {
            "width": self.engine.hex_map.width if self.engine.hex_map else 0,
            "height": self.engine.hex_map.height if self.engine.hex_map else 0,
            "tiles": hex_tiles,
        }

        # 州郡元数据（名称、首府）
        provinces_data: Dict[str, Dict[str, Any]] = {}
        for prov in self.engine.provinces.values():
            provinces_data[prov.id] = {
                "name": prov.name,
                "capital_city_id": prov.capital_city_id,
                "color": prov.color,
                "cities": prov.cities,
            }
        data["provinces"] = provinces_data

        # 外交数据
        if self.engine._diplomacy_relation_system is not None:
            relations = self.engine._diplomacy_relation_system.get_all_relations()
            data["faction_relations"] = [
                {
                    "faction_a": r.faction_a,
                    "faction_b": r.faction_b,
                    "status": r.status.value,
                    "trust": r.trust,
                    "truce_end_turn": r.truce_end_turn,
                    "alliance_end_turn": r.alliance_end_turn,
                }
                for r in relations.values()
            ]
        else:
            data["faction_relations"] = []

        # 外交消息
        data["messages"] = [
            {
                "id": m.id,
                "from_faction": m.from_faction,
                "to_faction": m.to_faction,
                "content": m.content,
                "turn": m.turn,
                "is_read": m.is_read,
            }
            for m in self.engine._messages
        ]

        # 回合日志
        data["turn_logs"] = [
            {
                "turn": tl.turn,
                "battles_fought": sum(1 for e in tl.events if isinstance(e, dict) and e.get("type") == "battle"),
                "armies_moved": sum(1 for e in tl.events if isinstance(e, dict) and e.get("type") == "army_moved"),
                "cities_captured": [e.get("city_id") for e in tl.events if isinstance(e, dict) and e.get("type") == "city_captured"],
            }
            for tl in self.engine.turn_logs[-10:]
        ]

        return data

    # ============================================================
    # 命令执行
    # ============================================================

    def execute_command(self, cmd_dict: Dict[str, Any]) -> Dict[str, Any]:
        """执行一个命令

        Args:
            cmd_dict: 前端传来的命令字典，必须包含 type/faction/turn/params

        Returns:
            执行结果摘要
        """
        if self.engine is None:
            return {"success": False, "error": "引擎未初始化"}

        try:
            command = self._deserialize_command(cmd_dict)
            result = self.engine.execute_command(command)
            return {
                "success": result.success,
                "type": result.command_type,
                "description": result.description,
                "data": result.data,
            }
        except Exception as e:
            logger.exception("命令执行失败: %s", cmd_dict)
            return {"success": False, "error": str(e)}

    @staticmethod
    def _deserialize_command(cmd_dict: Dict[str, Any]) -> Command:
        """将前端命令字典反序列化为 Command 对象"""
        cmd_type = cmd_dict.get("type", "")
        faction = cmd_dict.get("faction", "")
        turn = cmd_dict.get("turn", 1)
        params = cmd_dict.get("params", {})

        if cmd_type == "develop":
            return DevelopCommand(
                faction=faction, turn=turn,
                city=params["city"], develop_type=params["develop_type"],
            )
        elif cmd_type == "recruit":
            return RecruitCommand(
                faction=faction, turn=turn,
                city=params["city"], troops=params["troops"],
            )
        elif cmd_type == "attack":
            return AttackCommand(
                faction=faction, turn=turn,
                from_city=params["from_city"], to_city=params["to_city"],
                troops=params["troops"], general=params["general"],
            )
        elif cmd_type == "reward":
            return RewardCommand(
                faction=faction, turn=turn,
                general=params["general"], gold=params["gold"],
            )
        elif cmd_type == "explore":
            return ExploreCommand(
                faction=faction, turn=turn,
                city=params["city"], general=params.get("general"),
            )
        elif cmd_type == "message":
            return MessageCommand(
                faction=faction, turn=turn,
                to=params["to"], content=params["content"],
            )
        elif cmd_type == "rumor":
            return RumorCommand(
                faction=faction, turn=turn,
                city=params["city"],
                target_general=params.get("target_general"),
                spy_general=params.get("spy_general"),
            )
        elif cmd_type == "propose_alliance":
            return ProposeAllianceCommand(
                faction=faction, turn=turn,
                to=params["to"],
            )
        elif cmd_type == "declare_war":
            return DeclareWarCommand(
                faction=faction, turn=turn,
                to=params["to"], reason=params.get("reason", ""),
            )
        else:
            return Command(type=cmd_type, faction=faction, turn=turn, params=params)

    # ============================================================
    # 回合推进
    # ============================================================

    def _collect_decisions(
        self, observations: Dict[str, GameObservation]
    ) -> Dict[str, List[Command]]:
        """并发采集各势力的本回合决策（v4.0）

        并发边界的设计（很重要，关系到确定性）：
        - 「取观察」在主线程串行完成，**不在并发区里调用 engine**，
          避免多线程同时读引擎内部可变状态；
        - 「做决策」在并发区 —— LLM 模式下 get_commands 是阻塞网络调用，
          12 方串行会让单回合到分钟级，前端必然超时；
        - 结果按势力键写回 dict，调用方仍按固定顺序遍历执行命令，
          因此**对局结果与串行版本一致**（CLIPlayer 每个势力持有独立 RNG，
          其随机流只取决于自己被调用的次数，与线程调度无关）。

        Args:
            observations: 势力键 → 该势力的观察（主线程已生成）

        Returns:
            势力键 → 命令列表
        """
        factions = list(observations.keys())

        if not self.config.parallel_players or len(factions) <= 1:
            return {
                f: self._players[f].get_commands(observations[f]) for f in factions
            }

        decisions: Dict[str, List[Command]] = {}
        workers = max(1, min(self.config.max_workers, len(factions)))
        with ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="sanguo-decide"
        ) as pool:
            future_map = {
                pool.submit(self._players[f].get_commands, observations[f]): f
                for f in factions
            }
            for future in as_completed(future_map):
                faction = future_map[future]
                try:
                    decisions[faction] = future.result()
                except Exception as exc:  # noqa: BLE001
                    # 单个势力决策失败绝不能让整回合崩掉（LLM 超时/解析异常都可能）：
                    # 记为该方本回合按兵不动，其余势力照常推进。
                    logger.error("势力 %s 决策失败，本回合按兵不动: %r", faction, exc)
                    decisions[faction] = []

        for f in factions:
            decisions.setdefault(f, [])
        return decisions

    def process_turn(self) -> Dict[str, Any]:
        """推进一回合（执行 AI 命令 + 引擎回合处理）

        Returns:
            回合结果摘要
        """
        if self.engine is None:
            return {"error": "引擎未初始化"}

        # 执行 AI 玩家命令
        ai_events = []
        turn_no = self.engine.turn  # 本回合号（决策归属回合）

        # 1. 主线程统一取观察（并发区里不碰引擎状态）
        observations = {
            faction: self.engine.get_observation(faction)
            for faction in self._players
        }

        # 2. 并发采集决策（LLM 模式下这是耗时大头）
        decisions = self._collect_decisions(observations)

        # 3. 按固定顺序执行命令 → 保证确定性
        for faction, player in self._players.items():
            commands = decisions.get(faction, [])

            # 收集本回合的决策理由（仅 LLMPlayer 会设置 last_reasoning；
            # CLIPlayer 无此属性，getattr 回退为空串 → 不记录噪声）
            reasoning = getattr(player, "last_reasoning", "") or ""
            if reasoning.strip():
                self._reasoning.append({
                    "turn": turn_no,
                    "faction": faction,
                    "reasoning": reasoning,
                    "commands": [type(cmd).__name__ for cmd in commands],
                })

            for cmd in commands:
                result = self.engine.execute_command(cmd)
                if result.success:
                    ai_events.append({
                        "faction": faction,
                        "type": cmd.type,
                        "description": result.description,
                    })

        # 只保留最近 40 条决策理由
        if len(self._reasoning) > 40:
            self._reasoning = self._reasoning[-40:]

        # 推进引擎回合
        turn_result = self.engine.process_turn()

        # 记录建国事件
        ks = getattr(self.engine, '_kingdom_system', None)
        if ks:
            for f, k in ks.get_all_kingdoms().items():
                self._add_event(f"🏰 {FACTIONS.get(f, f)} 称{k['type']}！国号【{k['name']}】", "kingdom")

        if turn_result.get("battles_fought", 0) > 0:
            self._add_event(f"第 {turn_result['turn']} 回合: {turn_result['battles_fought']} 场战斗", "battle")

        if self.engine.game_over:
            if self.engine.winner:
                w = FACTIONS.get(self.engine.winner, self.engine.winner)
                self._add_event(f"🏆 {w} 一统天下！", "victory")
            else:
                self._add_event("游戏结束：平局", "victory")

        return {
            "turn": turn_result.get("turn"),
            "battles_fought": turn_result.get("battles_fought", 0),
            "game_over": self.engine.game_over,
            "winner": self.engine.winner,
            "ai_events": ai_events,
        }

    def run_ai_only_turns(self, max_turns: int = 1) -> List[Dict[str, Any]]:
        """连续运行若干纯 AI 回合（观战/回放模式用）

        Args:
            max_turns: 最大执行回合数

        Returns:
            每回合结果列表
        """
        results = []
        for _ in range(max_turns):
            if self.engine is None or self.engine.game_over:
                break
            results.append(self.process_turn())
        return results

    def _add_event(self, text: str, event_type: str = "info") -> None:
        """添加事件日志"""
        self._events.append({
            "turn": self.engine.turn if self.engine else 0,
            "type": event_type,
            "text": text,
        })
