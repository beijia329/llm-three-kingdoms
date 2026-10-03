"""FastAPI 后端服务

提供：
- 静态文件服务（前端构建产物）
- REST API：获取状态、执行命令、推进回合
- WebSocket：实时游戏状态流
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.game_manager import GameConfig, GameManager

logger = logging.getLogger(__name__)

# 全局游戏管理器（单例，后续可扩展为多房间）
_manager: Optional[GameManager] = None


def _env_int(name: str, default: int) -> int:
    """读取整数型环境变量，非法值回退默认值

    run_web.py 会把 --seed/--max-turns/--mode 写进 GAME_SEED/GAME_MAX_TURNS/GAME_MODE
    再拉起 uvicorn。此前本文件从不读这三个变量，等于启动参数全部失效
    （`python run_web.py --seed 42 --max-turns 48` 跑出来的仍是默认 seed=42/192 回合）。
    """
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("环境变量 %s=%r 不是合法整数，回退默认值 %s", name, raw, default)
        return default


def default_config_from_env() -> GameConfig:
    """按环境变量构造默认对局配置

    这是"启动脚本可配置"的唯一生效途径：GameConfig 保持纯默认值 dataclass，
    由本函数负责叠加环境变量。显式 POST /api/reset 传入的参数优先级更高
    （reset 里直接 GameConfig(**config)），不受这里影响。
    """
    mode = os.environ.get("GAME_MODE", "").strip() or "standard"
    if mode not in ("standard", "infinite"):
        logger.warning("GAME_MODE=%r 不是合法模式，回退 standard", mode)
        mode = "standard"
    return GameConfig(
        seed=_env_int("GAME_SEED", GameConfig.seed),
        max_turns=_env_int("GAME_MAX_TURNS", GameConfig.max_turns),
        game_mode=mode,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    global _manager
    cfg = default_config_from_env()
    _manager = GameManager(config=cfg)
    logger.info(
        "FastAPI 服务启动，游戏管理器已初始化: seed=%s max_turns=%s mode=%s",
        cfg.seed, cfg.max_turns, cfg.game_mode,
    )
    yield
    _manager = None
    logger.info("FastAPI 服务关闭")


app = FastAPI(
    title="乱斗三国 Web 服务",
    description="为 乱斗三国 提供 WebSocket 游戏状态流与 REST API",
    version="4.1.0",
    lifespan=lifespan,
)

# 允许前端跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REST API
# ============================================================

@app.get("/api/state")
async def get_state(reasoning_limit: Optional[int] = None) -> Dict[str, Any]:
    """获取当前游戏完整状态

    reasoning_limit（可选）：只返回最近 N 条决策理由；省略则返回全部
    （条数上限由 GameManager.MAX_REASONING_HISTORY 控制）。供前端「决策」面板
    按需拉取，长局下避免一次传回全部历史。
    """
    if _manager is None:
        return {"error": "游戏管理器未初始化"}
    return _manager.get_state(reasoning_limit=reasoning_limit)


@app.get("/api/models")
async def get_models() -> Dict[str, Any]:
    """列出各 provider 的候选模型（前端「模型分配」下拉的数据源）

    v4.0.1 新增。只返回**静态候选清单**，不实时请求外网 ——
    避免前端每次打开设置都打一次 API 请求。
    真实可用性以首次调用为准（填错模型会在对局第一回合报错）。
    """
    from players.llm.llm_client import PROVIDER_BASE_URLS, PROVIDER_MODELS

    return {
        "providers": list(PROVIDER_BASE_URLS.keys()),
        "models": PROVIDER_MODELS,
        "default_provider": "deepseek",
        "default_model": "deepseek-flash",
    }


@app.get("/api/model_records")
async def get_model_records() -> Dict[str, Any]:
    """获取跨局模型战绩排行榜（「LLM 大乱斗」的核心产物）

    单局有随机性，跨局累计才能回答「哪个大模型更会玩」。
    """
    if _manager is None:
        return {"error": "游戏管理器未初始化"}
    return _manager.get_model_records()


@app.post("/api/command")
async def post_command(command: Dict[str, Any]) -> Dict[str, Any]:
    """执行一个命令"""
    if _manager is None:
        return {"error": "游戏管理器未初始化"}
    return _manager.execute_command(command)


@app.post("/api/next-turn")
async def next_turn() -> Dict[str, Any]:
    """推进一回合"""
    if _manager is None:
        return {"error": "游戏管理器未初始化"}
    return _manager.process_turn()


@app.post("/api/reset")
async def reset_game(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """重置游戏

    v4.0.1：非法配置字段返回 **422** 而不是 500。

    🔴 原实现直接 `GameConfig(**(config or {}))`，任一未知字段都会抛 TypeError，
    被 FastAPI 兜成 HTTP 500 —— 前端无法区分「参数写错了」与「服务端崩了」，
    排查成本很高（engineering-lead 写端点测试时实测发现，
    并固化为 test_reset_with_unknown_field_is_not_gracefully_rejected）。
    现在把错误类型与**全部可用字段名**一起回给调用方。
    """
    global _manager
    try:
        cfg = GameConfig(**(config or {}))
    except TypeError as exc:
        valid_fields = sorted(GameConfig.__dataclass_fields__.keys())
        raise HTTPException(
            status_code=422,
            detail=(
                f"非法对局配置：{exc}。"
                f"可用字段：{', '.join(valid_fields)}"
            ),
        ) from exc
    _manager = GameManager(config=cfg)
    return _manager.get_state()


# ============================================================
# WebSocket 实时流
# ============================================================

@app.websocket("/ws/game")
async def game_websocket(websocket: WebSocket) -> None:
    """WebSocket 游戏连接

    客户端消息格式：
    - {"type": "init", "seed": 42, "max_turns": 192}
    - {"type": "command", "command": {...}}
    - {"type": "next_turn"}
    - {"type": "auto", "enabled": true, "interval_ms": 500}

    服务端消息格式：
    - {"type": "state", "data": {...}}
    - {"type": "event", "text": "..."}
    - {"type": "error", "message": "..."}
    """
    global _manager
    await websocket.accept()
    if _manager is None:
        await websocket.send_json({"type": "error", "message": "游戏管理器未初始化"})
        await websocket.close()
        return

    auto_task: Optional[asyncio.Task] = None

    async def send_state() -> None:
        await websocket.send_json({"type": "state", "data": _manager.get_state()})

    async def auto_loop(interval_ms: int) -> None:
        while True:
            await asyncio.sleep(interval_ms / 1000.0)
            if _manager.engine and _manager.engine.game_over:
                break
            _manager.process_turn()
            await send_state()

    # 发送初始状态
    await send_state()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "非法 JSON"})
                continue

            msg_type = msg.get("type", "")

            if msg_type == "init":
                # [前端 LLM 模式入口] 透传 LLM 相关配置。
                # 仅新增字段透传，不改变任何对局逻辑。
                # 缺省值取自环境变量（default_config_from_env），而不是写死 42/192，
                # 否则前端一次 init 就会把 `run_web.py --seed/--max-turns` 的配置冲掉。
                env_cfg = default_config_from_env()
                cfg = GameConfig(
                    seed=msg.get("seed", env_cfg.seed),
                    max_turns=msg.get("max_turns", env_cfg.max_turns),
                    game_mode=msg.get("game_mode") or env_cfg.game_mode,
                    human_faction=msg.get("human_faction"),
                    use_llm=bool(msg.get("use_llm", False)),
                    model=msg.get("model") or GameConfig.model,
                    provider=msg.get("provider") or GameConfig.provider,
                    factions=msg.get("factions") or None,
                )
                _manager = GameManager(config=cfg)
                await send_state()

            elif msg_type == "command":
                result = _manager.execute_command(msg.get("command", {}))
                await websocket.send_json({"type": "command_result", "data": result})
                await send_state()

            elif msg_type == "next_turn":
                turn_result = _manager.process_turn()
                await websocket.send_json({"type": "turn_result", "data": turn_result})
                await send_state()

            elif msg_type == "auto":
                enabled = msg.get("enabled", False)
                if auto_task and not auto_task.done():
                    auto_task.cancel()
                    auto_task = None
                if enabled:
                    interval = msg.get("interval_ms", 500)
                    auto_task = asyncio.create_task(auto_loop(interval))
                await websocket.send_json({"type": "event", "text": f"自动推进: {'开' if enabled else '关'}"})

            else:
                await websocket.send_json({"type": "error", "message": f"未知消息类型: {msg_type}"})

    except WebSocketDisconnect:
        if auto_task and not auto_task.done():
            auto_task.cancel()
        logger.info("WebSocket 客户端断开")


# ============================================================
# 静态文件服务（生产环境前端构建产物）
# ============================================================

WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "dist")

if os.path.isdir(WEB_DIR):
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="static")
else:
    @app.get("/")
    async def root() -> Dict[str, Any]:
        return {
            "message": "乱斗三国 Web 服务运行中",
            "docs": "/docs",
            "state": "/api/state",
        }
