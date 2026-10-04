"""游戏会话管理器

管理一个 GameEngine 实例，处理前端命令与状态序列化。
"""

from __future__ import annotations

import json
import logging
import os
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from game.constants import FACTIONS
from game.data_loader import load_game_data
from game.engine import GameEngine
from game.models import (
    Command,
    GameObservation,
)
from game.random import GameRandom
from players.base_player import BasePlayer
from players.cli_player import CLIPlayer
from players.llm.llm_client import LLMClient
from players.llm.llm_player import LLMPlayer

logger = logging.getLogger(__name__)

MODEL_RECORDS_PATH: Path = Path(__file__).resolve().parents[1] / "data" / "model_records.json"
"""跨局「模型战绩」落盘位置（v4.0.1 新增）

🔴 为什么需要跨局累计：单局有随机性（地图、性格、初始位置），
一局分不出高低。而「LLM 大乱斗」的核心价值恰恰是回答
「**哪个大模型更会玩这个游戏**」——那必须跨局统计。
本文件已被 .gitignore 忽略（运行时数据，不进版本库）。
"""

MAX_RECORDS_KEPT: int = 200
"""战绩文件最多保留的对局数（防止无限增长）"""

MAX_EVENTS_KEPT: int = 200
"""内部事件日志 ``self._events`` 的上限（防止长局内存无界增长）

前端只展示最后 20 条（``get_state`` 里 ``list(self._events[-20:])``），
取 200 = 10 倍余量：既留足回看空间，又给无限增长的列表一个安全阀。
**只裁剪内部列表，不改变 ``get_state()`` 的输出切片行为**（仍是最后 20 条）。
"""

MAX_REASONING_HISTORY: int = 400
"""决策理由 ``self._reasoning`` 的上限

「决策」tab 是围观台的核心：观众要看的是"这个模型怎么一步步走下坡路"，
早期决策被丢弃 = 回看不到演化过程（产品级缺陷，原上限 40）。
取 400 ≈ 覆盖 3 方整局（48 回合 × 3 = 144，余量充足）；
12 方长局（576 条）仍会截断，但**有界**、不会无界增长。
"""

MAX_RECENT_BATTLES: int = 20
"""``recent_battles`` 保留的最近战斗场数上限

战斗可见性（前端画进攻箭头）只需最近若干场；长局（48 回合，可能每回合多场）必须
**有界**，避免内存无界增长（与 MAX_EVENTS_KEPT 同模式）。取 20 ≈ 覆盖最近 1~2 回合。
"""


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
    max_turns: int = 48
    """默认对局回合数（v4.1 决策：192 → 48）

    48 回合 = 184–195 年。依据：实测 192 回合中第 49 回合起零战斗，
    turn 48/96/144/192 的 12 方城分布逐字节相同 → 后 144 回合完全空转，
    默认降到 48 可省 ~75% 时间与成本且画面内容零损失。

    🔴 这是「默认对局长度」，**不是硬上限**。硬上限仍是
    `game.constants.MAX_TURNS = 192`；调用方可显式传 max_turns=192（或更大，
    如 infinite 模式）跑长线观察档 —— 默认值与上限是两件事，勿混。
    """
    game_mode: str = "standard"
    human_faction: Optional[str] = None
    # ---- LLM 玩家相关（决策理由暴露使用）----
    use_llm: bool = False
    """为参与势力创建 LLMPlayer（真实大模型决策）而非 CLIPlayer"""
    model: str = "deepseek-flash"
    """**默认**模型名（未在 faction_models 中单独指定的势力使用它）

    可用 id 见 players/llm/llm_client.py 的 PROVIDER_MODELS，
    或调 GET /api/models 获取。
    """
    provider: str = "deepseek"
    """**默认** LLM 提供商（deepseek / openai / openrouter）"""
    factions: Optional[List[str]] = None
    """只给这些势力建玩家；None = 全部 12 方参战"""

    # ---- 多模型对战（v4.0.1 新增，「LLM 大乱斗」的核心）----
    faction_models: Optional[Dict[str, str]] = None
    """势力键 → 模型名。未列出的势力回退到 config.model。

    🔴 为什么需要这个字段：本项目的定位源自《9 大模型决战三国志》——
    让**不同**的大模型各领一方同台竞技。但 v4.0.0 之前整个 GameManager
    只创建一个 LLMClient，所有势力共用同一个 model，
    实际只能做到"一个模型自己打自己"，核心设定并不成立。
    现在每个势力可以拿到独立的 LLMClient，从而支持：
        {"caocao": "deepseek-v4-pro", "liubei": "deepseek-flash", ...}
    """
    faction_providers: Optional[Dict[str, str]] = None
    """势力键 → provider（可选）。未列出时回退到 config.provider。

    支持跨厂商对战（如 DeepSeek vs OpenRouter 上的其它模型）。
    """
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

    siege_persistent: bool = True
    """围城持续化开关（v4.2.0）

    True（默认）：军队抵达敌城后**保持围城**，逐回合结算（城墙受损 / 断粮守军减员 /
    攻方断粮撤围），仅在总攻条件满足时才发起总攻（见 game/siege.py）。
    False：行为**完全退回 v4.1.2**（抵达即同回合总攻）—— 这是回滚开关。
    """


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
        # 最近战斗报告（供前端在地图上画进攻箭头；由 battle_ended 事件累积，有上限）
        self._recent_battles: List[Dict[str, Any]] = []
        # 决策理由（供前端「决策」面板展示）：每条 = 一次 LLM 决策
        self._reasoning: List[Dict[str, Any]] = []
        # 本局是否已计入模型战绩（幂等标记：process_turn 每回合都会看到 game_over）
        self._match_recorded: bool = False
        # ---- hex_map 缓存（前端性能优化，2026-10-03）----
        # hex_map 有 24000 格、序列化后约 2.58 MB，占 /api/state 体积近 100%；
        # 而它的「地形/州郡/坐标」建图后**恒定不变**，只有势力占领（faction）
        # 与归属城（owner_city_id）会随回合变化（实测：仅城市易手时变）。故：
        #   - _hex_cache_version：只对会变的字段算指纹，未变则不入包；
        #   - _hex_cache_payload：指纹未变时复用已建好的 tiles，省掉重建 24000 dict；
        #   - _hex_prev_state/version：保留上一版格子状态，供**增量下发**——
        #     占领回合只回传「变化的格子」（实测 1~144 格），而不是整图 2.29 MB。
        self._hex_cache_version: str = ""
        self._hex_cache_payload: Optional[Dict[str, Any]] = None
        self._hex_tile_state: Dict[Any, Any] = {}
        self._hex_prev_version: str = ""
        self._hex_prev_state: Optional[Dict[Any, Any]] = None
        self._init_engine()

    def _init_engine(self) -> None:
        """初始化游戏引擎与 AI 玩家"""
        self.engine = GameEngine(
            seed=self.config.seed,
            siege_persistent=self.config.siege_persistent,
        )
        self.engine.max_turns = self.config.max_turns

        if self.config.game_mode == "infinite":
            from game.game_mode import GameMode
            self.engine.game_mode = GameMode.INFINITE
            self.engine.max_turns = 9999

        data = load_game_data()
        if not data.get("cities"):
            raise RuntimeError("无法加载游戏数据")
        self.engine.init_game(data)

        # 🔴 EventBus 的真实订阅者（此前 EventBus 定义 10 类事件却 0 订阅 = 假 Accepted）。
        # 订阅「回合结束」事件：由 _on_turn_ended 产生「建国/称王」「战斗」事件记录，
        # 取代原先 process_turn 末尾的两段手写 _add_event —— 若订阅失效/事件未发布，
        # 这些记录会立刻消失（可观测），而不是静默兜底。
        self.engine.events.subscribe("turn_ended", self._on_turn_ended)
        # 订阅「战斗结束」：累积 recent_battles（前端地图进攻箭头用）
        self.engine.events.subscribe("battle_ended", self._on_battle_ended)

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
        # use_llm=True 时，尽量用 LLMPlayer（真实大模型决策）；
        # 缺少 API Key 时回退为 CLIPlayer，保证游戏仍可运行。
        #
        # v4.0.1：从「单 client 全体共用」改为「每方独立 client」，
        # 以支持 faction_models（不同势力用不同模型 = 真正的大乱斗）。
        # 并发说明见 _collect_decisions（v4.0 已由线程池并发采集决策）。
        llm_clients: Dict[str, LLMClient] = {}
        # 前端「降级提示」用：记录 LLM 实际是否真的启用，以及失败原因。
        # 🔴 历史教训：此前 key 缺失只 logger.warning，前端无任何提示 →
        #    用户以为在跑 LLM，实际已回退 CLIPlayer，决策 tab 恒空，极难排查。
        self.llm_active: bool = False
        self.llm_error: str = ""
        # 势力 → 实际使用的模型名（前端展示「这一方是谁在指挥」）
        self.llm_model_by_faction: Dict[str, str] = {}
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
                faction_models = self.config.faction_models or {}
                faction_providers = self.config.faction_providers or {}
                for faction in participant_factions:
                    if faction == self.config.human_faction:
                        continue
                    model = faction_models.get(faction) or self.config.model
                    provider = faction_providers.get(faction) or self.config.provider
                    llm_clients[faction] = LLMClient(
                        provider=provider,
                        model=model,
                        api_key=api_key,
                    )
                    self.llm_model_by_faction[faction] = model
                self.llm_active = True
                models_in_play = sorted(set(self.llm_model_by_faction.values()))
                logger.info(
                    "LLM 已启用：%d 方参战，使用 %d 个不同模型 %s",
                    len(llm_clients), len(models_in_play), models_in_play,
                )
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
            faction_client = llm_clients.get(faction)
            if faction_client is not None:
                # 每方持有自己的 client（模型可能不同）—— 这是「多模型对战」的落点
                player = LLMPlayer(faction=faction, llm_client=faction_client)
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

    def _hex_map_version(self) -> str:
        """计算 hex_map 的版本指纹。

        🔴 为什么不是「每次回传 2.58 MB」：`hex_map` 有 24000 格，序列化后
        占 `/api/state` 体积近 100%（实测 2,582,900 / 2,339,624 字节，2026-10-03）。
        但它的「地形」「州郡」「坐标」建图后恒定，只有**势力占领**与
        **归属城**随回合变化。所以只对 `faction` / `owner_city_id` 做指纹，
        未变即视为「地图没变」，前端可复用缓存、不重传、不重画。

        指纹用 FNV-1a 混合 CRC32（跨进程稳定，与 `_stable_hash` 同思路），
        遍历 24000 格成本约几毫秒，远低于重新构造并序列化 24000 个 dict。

        Returns:
            8 位十六进制版本串；无地图时为 ``"empty"``
        """
        if self.engine is None or self.engine.hex_map is None:
            return "empty"
        fp = 0x811C9DC5
        for tile in self.engine.hex_map.iter_tiles():
            raw = f"{tile.coord.q},{tile.coord.r},{tile.faction or ''},{tile.owner_city_id or ''}"
            fp ^= zlib.crc32(raw.encode("utf-8"))
            fp = (fp * 0x01000193) & 0xFFFFFFFF
        return f"{fp:08x}"

    def _hex_map_payload(self) -> tuple[str, Dict[str, Any]]:
        """返回 (版本, hex_map 负载)；版本未变时复用缓存，不重建 24000 个 dict。

        版本变化时：把旧版本状态存进 `_hex_prev_*`，供增量下发比对。
        """
        version = self._hex_map_version()
        if self._hex_cache_payload is None or self._hex_cache_version != version:
            hex_tiles: List[Dict[str, Any]] = []
            state: Dict[Any, Any] = {}
            if self.engine is not None and self.engine.hex_map is not None:
                for tile in self.engine.hex_map.iter_tiles():
                    key = (tile.coord.q, tile.coord.r)
                    state[key] = (tile.faction, tile.owner_city_id)
                    hex_tiles.append({
                        "q": tile.coord.q,
                        "r": tile.coord.r,
                        "terrain": tile.terrain.value if hasattr(tile.terrain, 'value') else str(tile.terrain),
                        "faction": tile.faction,
                        "owner_city_id": tile.owner_city_id,
                        "province_id": tile.province_id,
                    })
            hm = self.engine.hex_map if self.engine is not None else None
            # 旧版本状态 → prev（供下一版做增量基线）
            self._hex_prev_version = self._hex_cache_version if self._hex_tile_state else ""
            self._hex_prev_state = dict(self._hex_tile_state) if self._hex_tile_state else None
            self._hex_cache_payload = {
                "width": hm.width if hm else 0,
                "height": hm.height if hm else 0,
                "tiles": hex_tiles,
            }
            self._hex_cache_version = version
            self._hex_tile_state = state
        return self._hex_cache_version, self._hex_cache_payload

    def _hex_map_transition(
        self, known_version: Optional[str], current_version: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """构造下发地图所需的字段：整图 / 增量 / 空。

        - known == current → {}（前端复用缓存，不入包）
        - known == 上一版  → {"hex_map_delta": {version, base_version, tiles}}
        - 其他（未知/跨多版）→ {"hex_map": 完整负载}
        """
        if known_version == current_version:
            return {}
        if (
            known_version
            and known_version == self._hex_prev_version
            and self._hex_prev_state is not None
        ):
            changed = []
            for (q, r), val in self._hex_tile_state.items():
                if self._hex_prev_state.get((q, r)) != val:
                    changed.append({
                        "q": q,
                        "r": r,
                        "faction": val[0],
                        "owner_city_id": val[1],
                    })
            return {
                "hex_map_delta": {
                    "version": current_version,
                    "base_version": known_version,
                    "tiles": changed,
                }
            }
        return {"hex_map": payload}

    def get_hex_map(self) -> Dict[str, Any]:
        """独立端点 ``/api/hex_map`` 的返回值：版本 + 完整地图。

        前端在「版本变了但 WS 未携带 hex_map」时回退调用本方法补齐。
        """
        version, payload = self._hex_map_payload()
        return {"version": version, **payload}

    def get_state(
        self,
        reasoning_limit: Optional[int] = None,
        known_hex_map_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取当前游戏状态（JSON 可序列化）

        Args:
            reasoning_limit: 只返回最近 N 条决策理由；None = **不下发**
                （前端「决策」Tab 按需调 /api/reasoning 拉取）。默认随
                state 全量下发会把自动推进每帧撑到 ~200KB，故改为按需。
            known_hex_map_version: 客户端**已知**的 hex_map 版本。若与当前版本
                一致，则**不再回传** hex_map（响应从 2.34 MB 降到约 30 KB）；
                不一致（或未传）时回传完整地图。默认 None = 回传（行为与旧版
                兼容，`/api/reset` 等一次性调用无需改）。

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
                # v4.0.1：该势力由哪个大模型指挥（多模型对战的关键信息）
                "model": self.llm_model_by_faction.get(fid, ""),
                "is_alive": len(cities) > 0,
            }

        # 补充六角格地图（用于前端地形渲染）
        #
        # 🔴 性能（2026-10-03）：hex_map 只在「占领变城」时变，但此前每次
        # state 都全量回传 2.58 MB。现改为带版本指纹，客户端已知同版本时省略，
        # 响应体积从 2.34 MB 降到约 30 KB。版本始终下发（前端据此判断是否重画）。
        hex_version, hex_payload = self._hex_map_payload()

        # max_turns / year 现在由 GameState 模型自动序列化（B-03 修复后）
        data["faction_stats"] = faction_stats
        # 季节：引擎里一直有 `engine.season`（Season 枚举），但此前从未进 API，
        # 导致前端顶部「Y年 季」的「季」永久空白。转成前端认的小写字符串键。
        if self.engine is not None:
            _season = getattr(self.engine, "season", None)
            data["season"] = (
                _season.value if hasattr(_season, "value") else str(_season or "")
            )
        else:
            data["season"] = ""
        data["events"] = list(self._events[-20:])
        # 最近战斗报告（近 MAX_RECENT_BATTLES 场；前端 BattleOverlay 据此画进攻箭头）
        data["recent_battles"] = list(self._recent_battles)

        # v4.0：为前端补「将道（五行）」与「称号」。
        # 这两项是武将系统的核心信息（五行相克 + 人设），但既不属于 General
        # 数据模型的存储字段（五行由五维推导），也不在 data/generals.json 里
        # （称号来自人设档案）→ 必须在序列化时补，否则界面上完全看不到机制。
        from game.element import ELEMENT_NAMES, element_of
        from game.personality import get_general_title

        for gid, gdata in (data.get("generals") or {}).items():
            general = self.engine.generals.get(gid)
            if general is None:
                continue
            element = element_of(general)
            gdata["element"] = element
            gdata["element_name"] = ELEMENT_NAMES.get(element, "")
            gdata["title"] = get_general_title(gid)

        # 决策理由（前端「决策」面板）：默认**不随状态下发**（按需拉取）。
        # 自动推进下每帧都带全量 reasoning 会把 /api/state 撑到 ~200KB，
        # 与「围观台要流畅」直接冲突。传 reasoning_limit 时才按需返回最近 N 条；
        # 省略或 0 = 不返回（前端切到「决策」Tab 时调 /api/reasoning）。
        if reasoning_limit is not None:
            limit = max(0, int(reasoning_limit))
            data["reasoning"] = list(self._reasoning[-limit:]) if limit > 0 else []
        data["human_faction"] = self.config.human_faction
        # LLM 实际启用状态 + 降级原因（前端要显式提示，不能让用户误以为在跑 LLM）
        data["llm_requested"] = bool(self.config.use_llm)
        data["llm_active"] = bool(self.llm_active)
        data["llm_error"] = self.llm_error
        data["llm_model"] = self.config.model if self.llm_active else ""
        # v4.0.1：势力 → 实际模型（前端据此显示「这一方是谁在指挥」）。
        # 多模型对战时各方模型不同，单靠 llm_model 一个字段表达不了。
        data["llm_model_by_faction"] = dict(self.llm_model_by_faction)
        data["llm_factions"] = list(self._players.keys())
        data["hex_map_version"] = hex_version
        # 客户端已知同版本 → 不入包；已知上一版 → 只回传变化格子（增量）；
        # 否则回传完整地图。占领回合从 2.29 MB 降到几 KB。
        data.update(self._hex_map_transition(known_hex_map_version, hex_version, hex_payload))

        # 州郡元数据（名称、首府）
        provinces_data: Dict[str, Dict[str, Any]] = {}
        for prov in self.engine.provinces.values():
            provinces_data[prov.id] = {
                "name": prov.name,
                "capital_city_id": prov.capital_city_id,
                "color": prov.color,
                "cities": prov.cities,
                # v4.2.0：州郡生产 modifier（前端城市卡 / 州提示展示）
                "modifiers": dict(prov.modifiers),
                "modifier_desc": prov.modifier_desc,
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

    def get_reasoning(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """返回决策理由历史（按需，供 /api/reasoning）。

        默认随 /api/state 全量下发会把自动推进每帧撑到 ~200KB，故 get_state
        改为默认不下发 reasoning；前端切到「决策」Tab 时再调本方法拉取。
        """
        if limit is None:
            return list(self._reasoning)
        limit = max(0, int(limit))
        return list(self._reasoning[-limit:]) if limit > 0 else []

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
            self._deliver_message(command.faction, command, result)
            return {
                "success": result.success,
                "type": result.command_type,
                "description": result.description,
                "data": result.data,
            }
        except Exception as e:
            logger.exception("命令执行失败: %s", cmd_dict)
            return {"success": False, "error": str(e)}

    def _deliver_message(self, sender: str, cmd: Command, result: Any) -> None:
        """把外交消息投递给**目标玩家对象**（与 `main.py:134-136` 的 CLI 路径等价）。

        🔴 为什么必须有这一步：`CLIPlayer` 只能靠 `receive_message` 回调得知
        「有人提议结盟」——它在 `players/cli_player.py:71-77` 里做关键字匹配并设
        `_pending_alliance`，下一回合据此回发 `ProposeAllianceCommand`。
        回调不投递 → `_pending_alliance` 恒为 `None` → 该回调永不触发
        → **规则-AI 模式下同盟在结构上不可能发生**。

        实测（2026-10-03）：同一条对局路径，不投递时同盟 0 对、结盟提议 0 次；
        投递时同盟 47 对、提议 92 次（`tests/balance/exp19_diplomacy_reachability.py`）。

        ⚠️ LLM 模式（`LLMPlayer`）**不依赖**本回调——它读
        `observation.received_messages`（`prompt_builder.py:304`）。
        所以这是「规则-AI 降级路径」与 CLI 路径的一致性修复。
        """
        if getattr(cmd, "type", None) != "message":
            return
        if not getattr(result, "success", False):
            return
        target = self._players.get(getattr(cmd, "to", None))
        if target is not None:
            target.receive_message(sender, str(getattr(cmd, "content", "")))

    @staticmethod
    def _deserialize_command(cmd_dict: Dict[str, Any]) -> Command:
        """将前端命令字典反序列化为 Command 对象"""
        cmd_type = cmd_dict.get("type", "")
        faction = cmd_dict.get("faction", "")
        turn = cmd_dict.get("turn", 1)
        params = cmd_dict.get("params", {})

        # 命令反序列化走注册表（game/command_registry.py）——单一扩展点。
        # 原实现是 9 分支 if/elif，加一条命令必须来这儿同步一次，
        # 漏改的后果是「引擎认这条命令、但前端发来的它反序列化不出正确参数」。
        #
        # 现按 Command 类的 **model_fields** 从 params 里取同名键构造。
        # 之所以可以这样通用化：所有内置命令的 params 键名都与模型字段名一致，
        # 且这条前提由 `tests/unit/test_command_surface_consistency.py` 断言守住
        # （逐条断言「每个已注册命令都能被本方法正确反序列化」）。
        from game.command_registry import get_handler

        entry = get_handler(cmd_type)
        if entry is None:
            # 未注册类型：保持原语义，返回基类 Command（由引擎判定为未知命令）
            return Command(type=cmd_type, faction=faction, turn=turn, params=params)

        cmd_cls, _handler = entry
        kwargs: Dict[str, Any] = {"faction": faction, "turn": turn}
        for field_name in cmd_cls.model_fields:
            if field_name in ("type", "faction", "turn", "params"):
                continue
            if field_name in params:
                kwargs[field_name] = params[field_name]
        # 必填字段若缺失，由 Pydantic 抛 ValidationError，与原先 params["x"]
        # 抛 KeyError 一样会被调用方的 try/except 兜住并返回错误信息。
        return cmd_cls(**kwargs)

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
                # 外交消息投递给目标玩家（CLI 路径同此；见 _deliver_message 说明）
                self._deliver_message(faction, cmd, result)
                if result.success:
                    ai_events.append({
                        "faction": faction,
                        "type": cmd.type,
                        "description": result.description,
                    })

        # 只保留最近 MAX_REASONING_HISTORY 条决策理由（见常量说明）
        if len(self._reasoning) > MAX_REASONING_HISTORY:
            self._reasoning = self._reasoning[-MAX_REASONING_HISTORY:]

        # 推进引擎回合。
        # 「建国/称王」「战斗」两条事件记录由订阅者 _on_turn_ended 在引擎内部广播
        # TurnEndedEvent 时产生（见上方 events.subscribe），此处不再手写——
        # 这样订阅者一旦失效会立刻暴露，而不会静默兜底。
        turn_result = self.engine.process_turn()

        if self.engine.game_over:
            if self.engine.winner:
                w = FACTIONS.get(self.engine.winner, self.engine.winner)
                self._add_event(f"🏆 {w} 一统天下！", "victory")
            else:
                self._add_event("游戏结束：平局", "victory")
            # v4.0.1：对局结束 → 计入跨局模型战绩（幂等，只记一次）
            self._record_match_result()

        return {
            "turn": turn_result.get("turn"),
            "battles_fought": turn_result.get("battles_fought", 0),
            "game_over": self.engine.game_over,
            "winner": self.engine.winner,
            "ai_events": ai_events,
        }

    def _on_turn_ended(self, event) -> None:
        """EventBus 订阅者：回合结束时产生「建国/称王」「战斗」事件记录。

        取代原先 `process_turn` 末尾的两段手写 `_add_event`。触发时机由引擎在
        `process_turn` 末尾 `publish(TurnEndedEvent)` 驱动——此时引擎的 turn 已递增、
        日志已落，与原先「process_turn 返回后再手写」的时序一致，故事件内容与顺序不变。

        参数是 `game.event_bus.TurnEndedEvent`，其 `data` 含 turn / battles_fought 等。
        """
        # 建国/称王（对全部已建国势力逐条记录，与原实现一致）
        ks = getattr(self.engine, "_kingdom_system", None)
        if ks:
            from game.kingdom_system import KINGDOM_TYPE_LABELS

            for f, k in ks.get_all_kingdoms().items():
                label = KINGDOM_TYPE_LABELS.get(k["type"], k["type"])
                self._add_event(
                    f"🏰 {FACTIONS.get(f, f)} 称{label}！国号【{k['name']}】", "kingdom"
                )

        battles = event.data.get("battles_fought", 0)
        if battles > 0:
            self._add_event(
                f"第 {event.data.get('turn')} 回合: {battles} 场战斗", "battle"
            )

    def _on_battle_ended(self, event) -> None:
        """EventBus 订阅者：把每场战斗打包成 BattleReport 累积到 `recent_battles`。

        事件由引擎在战斗结算处（`_apply_battle_result` 之后）发布，携带攻方出发城
        （复数，`attacker_from_cities`）、双方兵力/伤亡、城墙前后耐久、主将名等。
        """
        d = event.data
        self._recent_battles.append({
            "battle_id": d.get("battle_id"),
            "turn": d.get("turn"),
            "attacker_faction": d.get("attacker_faction"),
            "defender_faction": d.get("defender_faction"),
            "attacker_from_cities": list(d.get("attacker_from_cities") or []),
            "defender_city": d.get("defender_city"),
            "attacker_soldiers": d.get("attacker_soldiers", 0),
            "defender_soldiers": d.get("defender_soldiers", 0),
            "attacker_casualties": d.get("attacker_casualties", 0),
            "defender_casualties": d.get("defender_casualties", 0),
            "result": d.get("result", ""),
            "wall_hp_before": d.get("wall_hp_before", 0),
            "wall_hp_after": d.get("wall_hp_after", 0),
            "captured_city": d.get("captured_city"),
            "attacker_general_name": d.get("attacker_general_name", ""),
        })
        # 有界：只保留最近 MAX_RECENT_BATTLES 场
        if len(self._recent_battles) > MAX_RECENT_BATTLES:
            self._recent_battles = self._recent_battles[-MAX_RECENT_BATTLES:]

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

    # ============================================================
    # 模型战绩（跨局累计）
    # ============================================================

    @staticmethod
    def _read_records() -> Dict[str, Any]:
        """读取战绩文件；不存在或损坏时返回空结构（绝不抛异常影响对局）"""
        if not MODEL_RECORDS_PATH.exists():
            return {"matches": []}
        try:
            payload = json.loads(MODEL_RECORDS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("模型战绩文件读取失败，按空处理: %r", exc)
            return {"matches": []}
        if not isinstance(payload, dict):
            return {"matches": []}
        payload.setdefault("matches", [])
        return payload

    def _record_match_result(self) -> None:
        """对局结束时把结果计入「模型战绩」（幂等）

        🔴 为什么需要跨局累计：单局受地图、初始位置、性格随机影响，
        一局分不出模型高低。而本项目的核心价值就是回答
        「**哪个大模型更会玩**」——必须跨局统计才有意义。

        写入失败只记 warning，**绝不影响对局本身**（战绩是附加产物）。
        """
        if self._match_recorded or self.engine is None:
            return
        self._match_recorded = True

        if not self.llm_model_by_faction:
            # 纯 CLI（启发式 AI）对局没有「模型」这一维度，不计入模型战绩，
            # 否则排行榜会被"(未记录模型)"污染，看不出模型之间的差别。
            logger.info("本局无 LLM 参战，跳过模型战绩记录")
            return

        counts: Dict[str, int] = {}
        for city in self.engine.cities.values():
            # 🔴 只统计**本局参战方**（self._players）。
            # 不参战的势力城池仍留在图上但无人指挥 —— 实测把它们计入后，
            # 一局 3 方参战的记录会膨胀成 12 条，其中 9 条 model 为空。
            if city.faction in self._players:
                counts[city.faction] = counts.get(city.faction, 0) + 1

        ranked = sorted(
            ((f, n) for f, n in counts.items() if n > 0),
            key=lambda x: (-x[1], x[0]),  # 城多者先；并列按势力键，保证确定性
        )
        results = [
            {
                "faction": faction,
                "faction_name": FACTIONS.get(faction, faction),
                "model": self.llm_model_by_faction.get(faction, ""),
                "cities": n,
                "rank": rank,
                "winner": faction == self.engine.winner,
            }
            for rank, (faction, n) in enumerate(ranked, start=1)
        ]

        record = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "seed": self.config.seed,
            "max_turns": self.config.max_turns,
            "turns": self.engine.turn,
            "winner": self.engine.winner,
            "results": results,
        }

        try:
            payload = self._read_records()
            payload["matches"].append(record)
            payload["matches"] = payload["matches"][-MAX_RECORDS_KEPT:]
            MODEL_RECORDS_PATH.parent.mkdir(parents=True, exist_ok=True)
            MODEL_RECORDS_PATH.write_text(
                json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
            )
            logger.info("模型战绩已记录：%d 方参战", len(results))
        except OSError as exc:
            logger.warning("模型战绩写入失败（不影响对局）: %r", exc)

    def get_model_records(self) -> Dict[str, Any]:
        """聚合模型战绩排行榜 + 最近对局

        Returns:
            leaderboard: 按胜率（其次平均排名）排序的模型榜
            recent:      最近若干局的明细
            total_matches: 累计对局数
        """
        payload = self._read_records()
        matches = payload.get("matches", [])

        agg: Dict[str, Dict[str, Any]] = {}
        for match in matches:
            for row in match.get("results", []):
                model = row.get("model") or "(未记录模型)"
                slot = agg.setdefault(
                    model, {"matches": 0, "wins": 0, "ranks": [], "cities": []}
                )
                slot["matches"] += 1
                if row.get("winner"):
                    slot["wins"] += 1
                slot["ranks"].append(row.get("rank", 0))
                slot["cities"].append(row.get("cities", 0))

        leaderboard = []
        for model, slot in agg.items():
            n = max(slot["matches"], 1)
            leaderboard.append({
                "model": model,
                "matches": slot["matches"],
                "wins": slot["wins"],
                "win_rate": round(slot["wins"] / n, 3),
                "avg_rank": round(sum(slot["ranks"]) / n, 2),
                "avg_cities": round(sum(slot["cities"]) / n, 2),
            })
        leaderboard.sort(key=lambda x: (-x["win_rate"], x["avg_rank"], x["model"]))

        return {
            "leaderboard": leaderboard,
            "recent": matches[-10:],
            "total_matches": len(matches),
        }

    def _add_event(self, text: str, event_type: str = "info") -> None:
        """添加事件日志"""
        self._events.append({
            "turn": self.engine.turn if self.engine else 0,
            "type": event_type,
            "text": text,
        })
        # 只保留最近 MAX_EVENTS_KEPT 条，防止长局（48 回合 × 12 方）内存无界增长。
        # get_state() 仍只暴露最后 20 条，故此处裁剪对前端零影响。
        if len(self._events) > MAX_EVENTS_KEPT:
            del self._events[:-MAX_EVENTS_KEPT]
