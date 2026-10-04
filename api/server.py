"""FastAPI 后端服务

提供：
- 静态文件服务（前端构建产物）
- REST API：获取状态、执行命令、推进回合
- WebSocket：实时游戏状态流
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import os
import threading
import weakref
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, Optional, TypeVar

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.game_manager import GameConfig, GameManager, MAX_REASONING_HISTORY

logger = logging.getLogger(__name__)

# 全局游戏管理器（单例，后续可扩展为多房间）
_manager: Optional[GameManager] = None

T = TypeVar("T")


# ============================================================
# 回合执行闸门（A4：把同步回合挪出事件循环）
# ============================================================
#
# 🔴 为什么需要闸门：`GameManager.process_turn()` / `execute_command()` 是**同步**
# 函数，且直接读写引擎内部状态（`engine.cities` / `armies` / `generals` …）。
# 在此之前它们直接在 `async def` 里调用 —— LLM 模式单回合 12 方约 40 秒
# （`api/game_manager.py` `parallel_players` 字段自述），这 40 秒里 asyncio 事件
# 循环**完全停摆**：WS 收不到「停止自动推进」、ping 无响应、同进程其它 HTTP
# 请求排队饿死。改为 `run_in_executor` 后引擎写操作发生在**工作线程**上，
# 于是必须有把互斥量把「写引擎」这件事串起来，否则两个回合会并发改同一份状态。
#
# 为什么按事件循环分桶而不是一个模块级 `asyncio.Lock`：
# `asyncio.Lock` 在首次 await 时绑定当时的 event loop（`_LoopBoundMixin`），
# 换 loop 再用会抛 "is bound to a different event loop"。而每个 `TestClient(app)`
# / 每次 uvicorn 重启都是一个新 loop —— 模块级单例会直接炸测试。
# WeakKeyDictionary 让 loop 被回收时锁一起消失，也不会泄漏。
_turn_locks: "weakref.WeakKeyDictionary[Any, asyncio.Lock]" = weakref.WeakKeyDictionary()
_turn_locks_guard = threading.Lock()


def _get_turn_lock() -> asyncio.Lock:
    """取当前事件循环的回合互斥锁（不存在则建）。"""
    loop = asyncio.get_running_loop()
    with _turn_locks_guard:
        lock = _turn_locks.get(loop)
        if lock is None:
            lock = asyncio.Lock()
            _turn_locks[loop] = lock
        return lock


async def _run_exclusive(lock: asyncio.Lock, fn: Callable[..., T], *args: Any) -> T:
    """在 executor 里跑同步阻塞函数，**全程持锁**。

    🔴 锁的释放时机是本函数最容易写错的地方：绝不能写在 `await` 之后
    （`async with` 的隐式释放）。原因是 `auto_task.cancel()` 会在 await 点抛
    CancelledError，但**工作线程不可中断、仍会把整个回合跑完**。若此时锁已释放，
    下一个 tick 会看到「锁空闲」而并发进入引擎 —— 于是我们亲手制造了
    「两个回合同时改一份状态」的 corruption。
    正确做法：把释放挂到 executor future 的 done 回调上（= 线程真正结束的时刻），
    并用 `asyncio.shield` 保证 await 被取消时 future 不被连带取消。
    """
    loop = asyncio.get_running_loop()
    try:
        fut = loop.run_in_executor(None, functools.partial(fn, *args))
    except BaseException:
        # 提交失败（executor 已关闭等）：没有线程会跑，锁必须就地释放，否则永久死锁
        lock.release()
        raise
    fut.add_done_callback(lambda _f: lock.release())
    # shield：await 点被 cancel 时，fut 继续跑完，回调在真实结束点释放锁
    return await asyncio.shield(fut)


async def _run_in_executor_unlocked(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """把同步函数挪进 executor，**不加闸门**。

    仅用于**只读或与对局状态无关**的调用：`get_state`（读快照）、`GameManager(...)`
    构造（建新局，不碰旧局）。凡是会写引擎的（process_turn / execute_command）
    必须走 `_run_exclusive`，否则会绕开互斥。
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, functools.partial(fn, *args, **kwargs))


def _env_int(name: str, default: int) -> int:
    """读取整数型环境变量，非法值回退默认值

    run_web.py 会把 --seed/--max-turns/--mode 写进 GAME_SEED/GAME_MAX_TURNS/GAME_MODE
    再拉起 uvicorn。此前本文件从不读这三个变量，等于启动参数全部失效
    （`python run_web.py --seed 42 --max-turns 96` 跑出来的仍是默认 seed=42、48 回合）。
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
    version="4.1.2",
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
async def get_state(
    reasoning_limit: Optional[int] = None,
    hex_map_version: Optional[str] = None,
) -> Dict[str, Any]:
    """获取当前游戏完整状态

    reasoning_limit（可选）：只返回最近 N 条决策理由；省略或 0 则不下发
    （前端切「决策」Tab 时按需调 /api/reasoning）。第二批起不再默认全量下发：
    自动推进下每帧携带全量会把响应撑到 ~200KB，与「围观台要流畅」冲突。
    条数上限由 GameManager.MAX_REASONING_HISTORY 控制。

    hex_map_version（可选）：客户端已知的 hex_map 版本。与当前版本一致时
    **不再回传** hex_map（响应从 ~2.34 MB 降到 ~30 KB）；不一致则回传完整地图。

    🔴 A4 刻意**不加**回合闸门：读端一旦排队，就是「LLM 回合 40s 内所有
    /api/state 全挂」——那正是本次要消灭的失效模式。读侧与写侧并发的安全性
    已实测（`docs/qa/verify_scripts/a4_race_probe.py`：113 回合并发 239 次
    get_state，0 异常）。最坏情况只是地图比实际慢一个回合，非状态错误。
    """
    if _manager is None:
        return {"error": "游戏管理器未初始化"}
    return _manager.get_state(
        reasoning_limit=reasoning_limit,
        known_hex_map_version=hex_map_version,
    )


@app.get("/api/hex_map")
async def get_hex_map() -> Dict[str, Any]:
    """独立获取完整六角格地图（版本 + 24000 格）

    前端在「版本已变但 WS/state 未携带地图」时回退调用本端点补齐缓存。
    """
    if _manager is None:
        return {"error": "游戏管理器未初始化"}
    return _manager.get_hex_map()


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


@app.get("/api/reasoning")
async def get_reasoning(limit: int = MAX_REASONING_HISTORY) -> Dict[str, Any]:
    """获取决策理由历史（前端「决策」Tab 按需拉取，避免每帧塞进 /api/state）。

    自动推进下如果每次 state 都带全量 reasoning，/api/state 会涨到 ~200KB，
    与围观台要流畅直接冲突。get_state 默认不再下发 reasoning，
    前端切到「决策」Tab 时再调本端点拉取。
    """
    if _manager is None:
        return {"error": "游戏管理器未初始化"}
    return {"reasoning": _manager.get_reasoning(limit)}


@app.post("/api/command")
async def post_command(command: Dict[str, Any]) -> Dict[str, Any]:
    """执行一个命令

    🔴 A4：与 WS 侧共用同一把回合闸门 —— 否则 REST 发出的命令会和自动推进
    正在跑的回合并发改同一份引擎状态。
    """
    lock = _get_turn_lock()
    await lock.acquire()
    mgr = _manager  # 拿锁之后再取实例（与 WS 侧同一口径）
    if mgr is None:
        lock.release()
        return {"error": "游戏管理器未初始化"}
    return await _run_exclusive(lock, mgr.execute_command, command)


@app.post("/api/next-turn")
async def next_turn() -> Dict[str, Any]:
    """推进一回合

    🔴 A4：挪进 executor，LLM 模式单回合 40s 不再冻结整个事件循环
    （期间同进程的 GET /api/state、WS ping 都能立即响应）。
    """
    lock = _get_turn_lock()
    await lock.acquire()
    if _manager is None:
        lock.release()
        return {"error": "游戏管理器未初始化"}
    return await _run_exclusive(lock, _manager.process_turn)


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
    _manager = await _run_in_executor_unlocked(GameManager, config=cfg)
    return _manager.get_state()


# ============================================================
# WebSocket 实时流
# ============================================================

@app.websocket("/ws/game")
async def game_websocket(websocket: WebSocket) -> None:
    """WebSocket 游戏连接

    客户端消息格式：
    - {"type": "init", "seed": 42, "max_turns": 48}
    - {"type": "command", "command": {...}}
    - {"type": "next_turn"}
    - {"type": "auto", "enabled": true, "interval_ms": 500}

    服务端消息格式：
    - {"type": "state", "data": {...}}
    - {"type": "event", "text": "..."}
    - {"type": "error", "message": "..."}
    - {"type": "auto_stopped", "reason": "game_over", "text": "..."}
      （A5 新增：自动推进**真的**停了。前端据此把 auto 置 false，
        否则界面会永久显示「自动推进中」而「下一回合」被永久禁用）

    🔴 A4：所有会写引擎的同步调用（process_turn / execute_command）都经
    `_run_exclusive` 挪进 executor 并串行化；只读调用走 `_run_in_executor_unlocked`。
    """
    global _manager
    await websocket.accept()
    if _manager is None:
        await websocket.send_json({"type": "error", "message": "游戏管理器未初始化"})
        await websocket.close()
        return

    auto_task: Optional[asyncio.Task] = None
    # 连接级 hex_map 版本：首次必发完整地图，之后只在版本变化（占领变城）时再发。
    # 这样自动推进 800ms/回合也只推 ~30 KB 的状态增量，而不是每回合 2.58 MB。
    sent_hex_version: Optional[str] = None
    # 回合闸门：与 REST 侧共用同一把锁，保证「写引擎」全局串行
    turn_lock = _get_turn_lock()

    async def send_state() -> None:
        """推送当前状态。

        `get_state()` 是同步的（含 24000 格 hex_map 的序列化，实测 8~40ms），
        同样挪进 executor —— 它现在是自动推进每 800ms 调一次的高频路径，
        留在事件循环里会持续制造几百 ms 的卡顿。
        """
        nonlocal sent_hex_version
        mgr = _manager
        if mgr is None:
            return
        data = await _run_in_executor_unlocked(mgr.get_state, known_hex_map_version=sent_hex_version)
        sent_hex_version = data.get("hex_map_version")
        await websocket.send_json({"type": "state", "data": data})

    async def auto_loop(interval_ms: int) -> None:
        """自动推进循环。

        🔴 闸门（`turn_lock.locked()`）：上一回合没算完就**跳过本 tick**，绝不排队。
        排队会雪球 —— LLM 模式单回合 40s，而 interval 只有 800ms，
        每 tick 排一个 → 队列只增不减，点「停止」要等几十个回合才生效。
        跳过则天然收敛：算得完就一直推进，算不完就等于自动降速。
        """
        nonlocal auto_task
        while True:
            await asyncio.sleep(interval_ms / 1000.0)
            if _manager is None:
                await _notify_auto_stopped("manager_gone", "游戏管理器已释放，自动推进停止")
                break
            if _manager.engine and _manager.engine.game_over:
                # 🔴 A5：break 前必须通知前端。后端静默退出循环，前端的 auto
                # 布尔却仍为 true → 「下一回合」被 auto 恒真永久禁用，而后端一步
                # 都没在推进 = 界面显示「自动推进中」骗观众。
                await _notify_auto_stopped("game_over", "对局已结束，自动推进停止")
                break
            if turn_lock.locked():
                # 上一回合仍在跑：跳过本 tick（不排队，见上方说明）
                continue
            await turn_lock.acquire()
            # 🔴 `_manager` 是 global，可能在本协程 await 锁期间被 init/reset 换掉。
            # 因此**在拿到锁之后**才取实例快照：回合只作用于当前这一局，
            # 不会把旧局的回合写进新局。
            turn_mgr = _manager
            if turn_mgr is None:
                await _notify_auto_stopped("manager_gone", "游戏管理器已释放，自动推进停止")
                break
            try:
                await _run_exclusive(turn_lock, turn_mgr.process_turn)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                # 单个回合异常不能让 auto_loop 静默死掉（前端会一直显示"推进中"）
                logger.exception("自动推进的单回合执行失败: %r", exc)
                await _notify_auto_stopped("turn_error", f"回合执行异常，自动推进已停止：{exc}")
                break
            if _manager is not turn_mgr:
                # 回合期间用户重开了新局：这次结果属于旧局，不推给前端
                logger.info("回合结束后检测到对局已被重置，丢弃本次状态推送")
                continue
            # 回合本身把对局打结束（达到 max_turns / 某方统一）时，
            # 下一个 tick 才会检查到 game_over 并 break —— 但那要等 interval。
            # 这里立刻发终止事件，让界面第一时间解除「自动推进中」。
            if turn_mgr.engine and turn_mgr.engine.game_over:
                await send_state()
                await _notify_auto_stopped("game_over", "对局已结束，自动推进停止")
                break
            await send_state()

    async def _notify_auto_stopped(reason: str, text: str) -> None:
        """告知前端「自动推进真的停了」及其原因（A5）。

        事件是**新增**的下行消息类型，不改既有 state/event 的语义。
        前端收到即把 auto 置 false —— 于是「下一回合」「空格」恢复可用。
        """
        try:
            await websocket.send_json({
                "type": "auto_stopped",
                "reason": reason,
                "text": text,
            })
        except (WebSocketDisconnect, RuntimeError):
            # 连接已断：前端重连后会自己补发 auto 状态，无需在此兜底
            pass

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
                    # v4.0.1：按势力分配模型/provider（多模型大乱斗）。
                    # WS init 与 REST /api/reset 共用 GameConfig，这里补上透传，
                    # 否则经 WS init 开局时 faction_models 会被静默丢弃、多模型失效。
                    faction_models=msg.get("faction_models"),
                    faction_providers=msg.get("faction_providers"),
                )
                # 建局实测 ~4.2s（建 24000 格地图 + 建 12 方 AI），同步执行会卡死事件循环
                _manager = await _run_in_executor_unlocked(GameManager, config=cfg)
                # 新开一局 = 全新地图，必须重置连接级版本，强制重发完整地图
                sent_hex_version = None
                await send_state()

            elif msg_type == "command":
                # execute_command 走 engine.execute_command → 命令处理器，
                # 全是内存计算（无 LLM 调用，已核对 game/ 下零 llm_client 引用），
                # 单次毫秒级。但它**写引擎**，必须与 process_turn 共用闸门，
                # 否则会和后台正在跑的回合并发改同一份状态。
                await turn_lock.acquire()
                mgr = _manager  # 拿锁之后再取实例（理由同 auto_loop 内注释）
                if mgr is None:
                    turn_lock.release()
                    await websocket.send_json({"type": "error", "message": "游戏管理器未初始化"})
                    continue
                try:
                    result = await _run_exclusive(turn_lock, mgr.execute_command, msg.get("command", {}))
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    logger.exception("命令执行失败: %r", exc)
                    result = {"success": False, "error": str(exc)}
                await websocket.send_json({"type": "command_result", "data": result})
                await send_state()

            elif msg_type == "next_turn":
                # 不像 auto_loop 那样跳过：手动点击是明确意图，等上一回合跑完再执行
                # （前端有 pendingTurn 幂等守卫 + 240s 超时兜底，不会无限等）。
                await turn_lock.acquire()
                mgr = _manager  # 拿锁之后再取实例（理由同 auto_loop 内注释）
                if mgr is None:
                    turn_lock.release()
                    await websocket.send_json({"type": "error", "message": "游戏管理器未初始化"})
                    continue
                try:
                    turn_result = await _run_exclusive(turn_lock, mgr.process_turn)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    logger.exception("回合推进失败: %r", exc)
                    turn_result = {"error": str(exc)}
                await websocket.send_json({"type": "turn_result", "data": turn_result})
                await send_state()

            elif msg_type == "auto":
                enabled = msg.get("enabled", False)
                if auto_task and not auto_task.done():
                    auto_task.cancel()
                    # 等它真正结束再起新的：旧 auto_loop 此刻可能正持锁跑回合。
                    # 用 asyncio.wait 而非 `await auto_task` —— 后者会把子任务的
                    # CancelledError 抛到本协程，在 cancel 竞态下容易误吞外层取消。
                    await asyncio.wait({auto_task})
                    auto_task = None
                if enabled:
                    mgr = _manager
                    if mgr is not None and mgr.engine is not None and mgr.engine.game_over:
                        # 对局已结束还开自动推进 = 假控件：后端只会立刻 break。
                        # 明确告知而不是假装开了。
                        await websocket.send_json({
                            "type": "auto_stopped",
                            "reason": "game_over",
                            "text": "对局已结束，无法开启自动推进",
                        })
                        await websocket.send_json({"type": "event", "text": "自动推进: 开（已拒绝：对局已结束）"})
                        continue
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
