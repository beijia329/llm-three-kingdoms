"""WS 处理器异步化（A4）+ 自动推进状态对齐（A5）回归测试

为什么需要这层测试
------------------
A4 之前，`/ws/game` 的三个调用点（auto_loop / command / next_turn）在 `async def`
里**直接**调用同步的 `GameManager.process_turn()`。LLM 模式单回合 12 方约 40 秒
（`api/game_manager.py` `parallel_players` 字段自述），这 40 秒里 asyncio 事件
循环完全停摆：点「停止自动推进」要等一整个回合、ping 无响应、同进程其它请求饿死。

A5 之前，auto_loop 在 `if game_over: break` 处**不发任何消息**就退出，前端的
`auto` 布尔恒为 true → 「下一回合」被永久禁用，而后端一步都没在推进。
界面显示「自动推进中」而实际没推进 = 直接骗观众。

本文件把这两条锁死。全部用 CLI 规则 AI（`use_llm=False`）+ monkeypatch 注入延迟：
不联网、不调真实 LLM、不花钱。

运行环境
--------
需要 fastapi + starlette（TestClient）。项目 `./venv` 未安装 fastapi，
请用系统解释器：

    export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy PYTHONHASHSEED=0
    /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \\
        -m pytest tests/integration/test_ws_async_and_auto_state.py -q
"""

from __future__ import annotations

import asyncio
import queue
import threading
import time

import pytest

_tc = pytest.importorskip(
    "fastapi.testclient",
    reason="需要 fastapi（./venv 未安装，请用系统 python3.12 运行本文件）",
)
TestClient = _tc.TestClient

from api import server as server_mod  # noqa: E402
from api.game_manager import GameManager  # noqa: E402
from api.server import app  # noqa: E402

# 小规模对局：2 方、6 回合 —— 快、确定、不涉及任何真实 LLM
_PARTICIPANTS = ["caocao", "yuanshao"]
_BASE_CFG = {"use_llm": False, "factions": _PARTICIPANTS, "max_turns": 6, "seed": 42}

# 注入延迟：必须 > 0 且足够大，让「事件循环是否被冻结」在毫秒级计时上可分辨。
# 2.0s：比测试开销大一个数量级，又不至于让整套测试变慢到不可接受。
SLOW_TURN_S = 2.0


@pytest.fixture()
def client():
    """每个测试独立的 TestClient（进入 lifespan 建立全局 _manager）。"""
    with TestClient(app) as c:
        yield c


def _reset(client, **overrides) -> dict:
    cfg = dict(_BASE_CFG)
    cfg.update(overrides)
    r = client.post("/api/reset", json=cfg)
    assert r.status_code == 200, r.text
    return r.json()


def _live_manager() -> GameManager:
    mgr = server_mod._manager
    assert mgr is not None, "lifespan 未建立 _manager"
    return mgr


def _slow_process_turn(mgr: GameManager, seconds: float = SLOW_TURN_S) -> dict:
    """把 process_turn 换成「先睡 N 秒再真跑」。

    用来在**不联网、不花钱**的前提下复现 LLM 模式的阻塞特征（单回合数十秒）。
    注意 sleep 发生在真回合**之前**：这样即便闸门写错，也只是多跑一个真回合，
    不会把测试拖成分钟级。
    """
    real = mgr.process_turn

    def slow() -> dict:
        time.sleep(seconds)
        return real()

    mgr.process_turn = slow  # type: ignore[method-assign]
    return slow


class WSInbox:
    """把 WebSocket 收包放进队列，供测试按超时安全地读取。

    🔴 为什么需要它：`ws.receive_json()` 在**没有消息可收**时无限阻塞。
    而本文件要测的正是「后端静默退出、一条消息都不发」这个缺陷（旧代码在
    game_over 时直接 break）—— 那样接收会永远挂着，测试以「卡死」而非「失败」
    告终，CI 只能靠全局超时被杀，既慢又看不出哪条坏了。

    🔴 关键：**每条连接只能有一个 reader 线程**。若每调用一次 drain 就新建一个
    线程，多个线程会争抢同一条连接的消息（各自拿到一部分），
    表现为"第二个 drain 收到空列表"——这是本文件实测踩过的坑。
    """

    def __init__(self, ws) -> None:
        self._ws = ws
        self._q: "queue.Queue[object]" = queue.Queue()
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()

    def _reader(self) -> None:
        try:
            while True:
                self._q.put(self._ws.receive_json())
        except BaseException as exc:  # noqa: BLE001
            self._q.put(exc)

    def drain_until(self, predicate, timeout: float = 15.0) -> list[dict]:
        """收包直到 predicate 为真，返回全部已收消息；超时/断连则 pytest.fail。"""
        seen: list[dict] = []
        deadline = time.time() + timeout
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                pytest.fail(
                    f"{timeout}s 内未等到目标消息；实际收到: {[m.get('type') for m in seen]}"
                )
            try:
                item = self._q.get(timeout=remaining)
            except queue.Empty:
                pytest.fail(
                    f"{timeout}s 内未等到目标消息；实际收到: {[m.get('type') for m in seen]}"
                )
            if isinstance(item, BaseException):
                pytest.fail(f"接收中断: {item!r}；已收到: {[m.get('type') for m in seen]}")
            seen.append(item)  # type: ignore[arg-type]
            if predicate(seen[-1]):
                return seen


# ============================================================
# A4：事件循环在回合执行期间必须保持可响应
# ============================================================

class TestEventLoopNotBlocked:
    """A4 的核心判据：慢回合进行中，同进程的别的请求必须**立即**返回。"""

    def test_slow_auto_turn_does_not_block_other_http_requests(self, client):
        """🔴 主判据：走 WS 自动推进（= A4 的真实现场），回合在跑时 GET /api/state 必须秒回。

        改之前：auto_loop 在事件循环里直接跑 process_turn → 整个 loop 冻结 →
        另开线程发的 GET /api/state 也要排队等到回合结束（本测试实测 ~1.7s）。
        改之后：回合在工作线程，loop 空转 → GET /api/state 十几 ms 返回。

        ⚠️ 这里必须走 WS 的 auto 路径。若像第一版那样"另起线程直接调
        mgr.process_turn()"，那测的是**线程级并发**（GIL 能不能让 get_state 活下来），
        根本不是 A4 要修的事件循环阻塞 —— 那种写法在改前的旧代码上也会通过，
        属于假阴性测试（第一版就踩了，已删除）。
        """
        _reset(client)
        _slow_process_turn(_live_manager(), seconds=2.0)

        outcome: dict = {}

        def hit_state() -> None:
            t0 = time.perf_counter()
            r = client.get("/api/state")
            outcome["dt"] = time.perf_counter() - t0
            outcome["status"] = r.status_code

        with client.websocket_connect("/ws/game") as ws:
            inbox = WSInbox(ws)
            inbox.drain_until(lambda m: m.get("type") == "state")  # 初始 state
            ws.send_json({"type": "auto", "enabled": True, "interval_ms": 50})
            time.sleep(0.3)  # 让回合进入 sleep（还剩约 1.7s）
            th = threading.Thread(target=hit_state)
            th.start()
            th.join(timeout=30)
            assert not th.is_alive(), "GET /api/state 卡死 30s（比单回合还久，明显异常）"
            ws.send_json({"type": "auto", "enabled": False})

        assert outcome.get("status") == 200
        assert outcome["dt"] < SLOW_TURN_S * 0.5, (
            f"回合进行中 GET /api/state 耗时 {outcome['dt']:.3f}s，"
            f"超过单回合({SLOW_TURN_S}s)的一半 → 事件循环仍被回合冻结"
        )

    def test_rest_next_turn_does_not_freeze_event_loop(self, client):
        """POST /api/next-turn（慢回合）进行中，GET /api/state 必须能穿插返回。

        这条直接覆盖 REST 侧：/api/next-turn 与 /ws/game 的 auto_loop 是同一类调用点，
        改一个不改另一个就仍会留下冻结路径。
        """
        _reset(client)
        _slow_process_turn(_live_manager())

        state_latency: list[float] = []
        turn_done = threading.Event()

        def run_turn():
            client.post("/api/next-turn")
            turn_done.set()

        th = threading.Thread(target=run_turn)
        th.start()
        time.sleep(0.25)
        t0 = time.perf_counter()
        r = client.get("/api/state")
        state_latency.append(time.perf_counter() - t0)
        assert r.status_code == 200
        th.join(timeout=30)
        assert turn_done.is_set()

        assert state_latency[0] < SLOW_TURN_S * 0.5, (
            f"慢回合期间 GET /api/state 耗时 {state_latency[0]:.3f}s → 事件循环被冻结"
        )

    def test_turn_is_actually_awaited_and_applied(self, client):
        """异步化的反面风险：挪进 executor 后回合**必须真的跑完并生效**。

        只测「不阻塞」是不够的 —— 若 handler 提前返回，回合会静默丢失，
        界面显示"推进成功"而回合号不变。故断言回合号确实 +1。
        """
        _reset(client)
        mgr = _live_manager()
        before = client.get("/api/state").json()["turn"]
        _slow_process_turn(mgr)
        r = client.post("/api/next-turn")
        assert r.status_code == 200
        assert r.json()["turn"] == before, "回合结果未返回"
        assert client.get("/api/state").json()["turn"] == before + 1, (
            "回合没有被真正执行（异步化把它丢了？）"
        )


# ============================================================
# A4 续：闸门必须真的串行化「写引擎」
# ============================================================

class TestTurnGateSerializesWrites:
    """闸门存在的原因：两个回合并发跑会同时改同一份引擎状态。"""

    def test_concurrent_turns_do_not_interleave(self, client):
        """并发发两次 next_turn：引擎的回合推进必须严格 +1 +1，不能出现跳号/丢号。"""
        _reset(client)
        mgr = _live_manager()
        _slow_process_turn(mgr, seconds=0.4)

        before = client.get("/api/state").json()["turn"]
        results: list[int] = []
        lock = threading.Lock()

        def hit():
            r = client.post("/api/next-turn")
            with lock:
                results.append(r.json()["turn"])

        threads = [threading.Thread(target=hit) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
            assert not t.is_alive()

        assert sorted(results) == [before, before + 1], (
            f"两个并发回合的结果应各占一个回合号，实际 {results}"
        )
        after = client.get("/api/state").json()["turn"]
        assert after == before + 2, f"引擎回合号应 +2，实际 {before} → {after}"


# ============================================================
# A5：自动推进「真的停了」必须让前端知道
# ============================================================

class TestAutoStoppedNotification:
    """A5 判据：auto_loop 退出前必须发消息，否则前端 auto 恒真 → 假控件。"""

    def test_auto_stopped_sent_when_game_reaches_game_over(self, client):
        """推进到终局时，前端必须收到 auto_stopped（原因 game_over）。"""
        _reset(client, max_turns=2)
        with client.websocket_connect("/ws/game") as ws:
            inbox = WSInbox(ws)
            inbox.drain_until(lambda m: m.get("type") == "state")  # 初始 state
            ws.send_json({"type": "auto", "enabled": True, "interval_ms": 50})
            msgs = inbox.drain_until(lambda m: m.get("type") == "auto_stopped")
        stopped = [m for m in msgs if m["type"] == "auto_stopped"][-1]
        assert stopped["reason"] == "game_over", stopped
        assert stopped.get("text"), "必须带人类可读原因，不能只给机器字段"
        # 终局状态本身也要推给前端（否则界面不知道游戏结束了）
        assert any(m["type"] == "state" and m["data"].get("game_over") for m in msgs)

    def test_auto_toggle_off_confirmed_by_event(self, client):
        """关自动推进仍回 event（前端 toggleAuto 依赖它做用户反馈）。"""
        _reset(client)
        with client.websocket_connect("/ws/game") as ws:
            ws.receive_json()
            ws.send_json({"type": "auto", "enabled": False})
            msg = ws.receive_json()
        assert msg["type"] == "event"
        assert "自动推进" in msg["text"]

    def test_turn_keeps_advancing_under_auto(self, client):
        """自动推进必须真的在推进（防止「闸门写太严，一个 tick 都不跑」）。"""
        _reset(client, max_turns=6)
        with client.websocket_connect("/ws/game") as ws:
            inbox = WSInbox(ws)
            inbox.drain_until(lambda m: m.get("type") == "state")
            ws.send_json({"type": "auto", "enabled": True, "interval_ms": 50})
            inbox.drain_until(
                lambda m: m.get("type") == "state" and m.get("data", {}).get("turn", 0) >= 3
            )
        # 至少推进了 2 个回合
        assert _live_manager().engine.turn >= 3

    def test_stopping_auto_prevents_further_turns(self, client):
        """点「停止」后不得再有回合推进（验证 auto_loop 真的被 cancel 干净）。"""
        _reset(client, max_turns=999)
        with client.websocket_connect("/ws/game") as ws:
            # 🔴 inbox 必须**先于**任何 ws.receive_json() 创建：它的 reader 线程
            # 启动即开始收包，若之后再调 ws.receive_json()，初始 state 会被
            # reader 抢走，主线程永久阻塞（本文件实测踩过：整个文件跑 13 分钟不结束）。
            inbox = WSInbox(ws)
            inbox.drain_until(lambda m: m.get("type") == "state")  # 初始 state
            ws.send_json({"type": "auto", "enabled": True, "interval_ms": 30})
            inbox.drain_until(
                lambda m: m.get("type") == "state" and m.get("data", {}).get("turn", 0) >= 2
            )
            ws.send_json({"type": "auto", "enabled": False})
            # 等关指令的回执到达（此时在途回合已跑完）
            inbox.drain_until(
                lambda m: m.get("type") == "event" and "自动推进" in m.get("text", "")
            )
            turn_at_stop = _live_manager().engine.turn
            time.sleep(0.5)  # 原本够跑 ~16 个 tick
        assert _live_manager().engine.turn == turn_at_stop, (
            f"停止后引擎仍在推进：{turn_at_stop} → {_live_manager().engine.turn}"
        )

    def test_enabling_auto_on_finished_game_is_rejected_visibly(self, client):
        """对局已结束后再开自动推进必须被**明确拒绝**，不能假装开了。

        改之前：后端建了 auto_task → 下一 tick 立刻 break → 前端的 auto 却为 true，
        永远等不到任何通知（这正是 A5 要消灭的失效模式）。
        """
        _reset(client, max_turns=1)
        mgr = _live_manager()
        while not mgr.engine.game_over:
            mgr.process_turn()
        assert mgr.engine.game_over is True

        with client.websocket_connect("/ws/game") as ws:
            inbox = WSInbox(ws)
            inbox.drain_until(lambda m: m.get("type") == "state")
            ws.send_json({"type": "auto", "enabled": True, "interval_ms": 50})
            msgs = inbox.drain_until(lambda m: m.get("type") == "event")
        rejected = [m for m in msgs if m["type"] == "auto_stopped"]
        assert rejected, "对局结束后开启自动推进必须回 auto_stopped（前端据此置 auto=false）"
        assert rejected[-1]["reason"] == "game_over"
        assert "已结束" in rejected[-1]["text"]


# ============================================================
# A4 续：锁的跨 loop 复用不能炸（TestClient 每用例一个新 loop）
# ============================================================

class TestTurnLockAcrossEventLoops:
    """`_get_turn_lock` 按 loop 分桶的实现是否真的安全。"""

    def test_lock_usable_from_two_different_event_loops(self):
        """同一进程内两个不同 event loop 各取一次锁，都必须可用。

        若用模块级单个 asyncio.Lock，第二个 loop 会抛
        "is bound to a different event loop" —— 每次 uvicorn 重启/每个
        TestClient 用例都会踩。这条把该实现细节锁死。
        """
        async def use_lock():
            lock = server_mod._get_turn_lock()
            await lock.acquire()
            lock.release()
            return "ok"

        assert asyncio.run(use_lock()) == "ok"
        assert asyncio.run(use_lock()) == "ok"

    def test_exclusive_helper_releases_lock_after_completion(self):
        """_run_exclusive 正常返回后锁必须已释放（否则第二个回合永久等待）。"""
        async def scenario():
            lock = server_mod._get_turn_lock()
            await lock.acquire()
            await server_mod._run_exclusive(lock, lambda: 42)
            assert not lock.locked(), "_run_exclusive 返回后锁仍是锁定的"
            # 释放后应能再次获取
            await asyncio.wait_for(lock.acquire(), timeout=1.0)
            lock.release()

        asyncio.run(scenario())

    def test_exclusive_helper_releases_lock_on_submit_failure(self):
        """executor 提交失败时就地释放锁，不能永久死锁后续回合。"""

        async def main():
            lock = server_mod._get_turn_lock()
            await lock.acquire()
            loop = asyncio.get_running_loop()

            def boom(*_a, **_k):
                raise RuntimeError("模拟 executor 已关闭")

            loop.run_in_executor = boom  # type: ignore[method-assign]
            with pytest.raises(RuntimeError):
                await server_mod._run_exclusive(lock, lambda: 1)
            assert not lock.locked(), "提交失败后锁未释放 → 后续所有回合永久卡死"

        asyncio.run(main())
