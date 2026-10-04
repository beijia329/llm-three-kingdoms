"""A4 硬证据：慢回合进行中，别的 HTTP 请求的响应耗时（改前 / 改后对比）。

用法（必须先 build 前端，因为 dist 挂载是 import 时判断的）::

    cd /Users/dongsheng/Documents/llm-sanguo-project/web && npm run build
    cd /Users/dongsheng/Documents/llm-sanguo-project
    /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \\
        docs/qa/verify_scripts/a4_slow_turn_probe.py

设计要点
--------
1. **不用真实 LLM**（key 不可靠且要花钱）：用 CLI 规则 AI + 把 `process_turn`
   monkeypatch 成「先睡 N 秒再真跑」，复现 LLM 模式单回合数十秒的阻塞特征。
2. **起服务 + 发请求在同一条命令内**：本项目后台进程不跨轮次保活，
   脚本内用 uvicorn Server 跑在独立线程，避免依赖 shell 的进程编排。
3. 探测 WS 的 auto 路径（真正的 A4 现场：auto_loop 里跑回合），
   在回合进行中并发打 GET /api/state，测响应耗时。
"""
from __future__ import annotations

import asyncio
import json
import os
import statistics
import sys
import threading
import time
import urllib.request
from pathlib import Path

# 直接 `python3 docs/qa/verify_scripts/a4_slow_turn_probe.py` 时 sys.path[0]
# 是脚本所在目录（docs/qa/verify_scripts），不是项目根 → 必须手动补，
# 否则 `import api` 失败。本文件路径 = <root>/docs/qa/verify_scripts/<file>，
# 故项目根是 parents[3]（parents[0]=verify_scripts, 1=qa, 2=docs, 3=root）。
_PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import uvicorn  # noqa: E402

from api.game_manager import GameConfig, GameManager  # noqa: E402
from api.server import app  # noqa: E402
import api.server as server_mod  # noqa: E402

PORT = 8137
BASE = f"http://127.0.0.1:{PORT}"
SLOW_TURN_S = 3.0
PROBE_N = 6

# 🔴 采样窗口的硬证据：由「被注入慢延迟的 process_turn」在**进入时**置位。
# 第一版探针只靠 sleep 猜时机，结果 6 次采样全落在回合空档里（改前改后都 ~17ms），
# 是典型的假阴性。现在：探针等到这个 Event 被置位（即确有回合正在执行）才采样，
# 且结束前断言它确实被置过 —— 否则「测了但没测到」会被当成「测了没问题」。
TURN_IN_FLIGHT = threading.Event()
TURNS_STARTED = threading.Event()


def _http_get(path: str, timeout: float = 30.0) -> tuple[int, float]:
    t0 = time.perf_counter()
    with urllib.request.urlopen(BASE + path, timeout=timeout) as resp:
        resp.read()
    dt = time.perf_counter() - t0
    return resp.status, dt


async def _ws_probe(latencies: list[float]) -> None:
    """连 WS、开自动推进，在**回合真正执行期间**连续打 GET /api/state 计时。

    🔴 测量窗口的设计（第一版踩过的坑）：
    第一版先 `await` 收到一个 state 才开始采样，于是 6 次采样**全部落在回合之间的
    空档**里 —— 改前改后都是 ~17ms，完全测不出差别（假阴性，差点据此交差）。
    正确做法：等到 `TURN_IN_FLIGHT` 置位（有回合正在跑）再采样，且覆盖该窗口。
    改前事件循环被冻结，请求排在回合后面 → 出现 ~SLOW_TURN_S 的尖峰；
    改后每次都是十几 ms。
    """
    import websockets

    uri = f"ws://127.0.0.1:{PORT}/ws/game"
    async with websockets.connect(uri, max_size=None) as ws:
        await ws.recv()  # 初始 state

        # 独立协程持续收包（只为把 socket 读干净，避免对端写缓冲塞满）
        async def drain() -> None:
            try:
                while True:
                    await ws.recv()
            except BaseException:  # noqa: BLE001
                pass

        drainer = asyncio.create_task(drain())
        await ws.send(json.dumps({"type": "auto", "enabled": True, "interval_ms": 150}))

        # 等到确有回合在执行（最多等 3 个回合的量级）
        deadline = time.time() + SLOW_TURN_S * 4
        while not TURN_IN_FLIGHT.is_set() and time.time() < deadline:
            await asyncio.sleep(0.02)
        assert TURN_IN_FLIGHT.is_set(), "未观测到回合进入执行状态，测量无效"

        loop = asyncio.get_running_loop()
        try:
            for _ in range(PROBE_N):
                status, dt = await loop.run_in_executor(
                    None, lambda: _http_get("/api/state", timeout=60)
                )
                assert status == 200, f"GET /api/state 返回 {status}"
                latencies.append(dt)
        finally:
            drainer.cancel()
            await ws.send(json.dumps({"type": "auto", "enabled": False}))

    assert TURNS_STARTED.is_set(), "整个采样期间没有任何回合真正开始 → 测量无效"


def main() -> None:
    # ---- 慢模式：只睡 3 秒，够慢到能分辨「排队 vs 立即返回」 ----
    real_init = GameManager.__init__

    def slow_init(self, config=None) -> None:  # noqa: ANN001
        real_init(self, config)
        real_pt = self.process_turn

        def slow_pt() -> dict:
            # 进入即置位：让探针知道「现在确有回合在跑」，杜绝测到空档
            TURNS_STARTED.set()
            TURN_IN_FLIGHT.set()
            try:
                time.sleep(SLOW_TURN_S)
                return real_pt()
            finally:
                TURN_IN_FLIGHT.clear()

        self.process_turn = slow_pt  # type: ignore[method-assign]

    GameManager.__init__ = slow_init  # type: ignore[method-assign]

    # 注意：不手动建 _manager —— lifespan 会用 default_config_from_env() 建一个，
    # 手工建的会被 lifespan 覆盖（而覆盖后的那个同样带慢注入，因为注入点在类上）。
    # 用环境变量把对局规模钉死（3 方），避免 12 方让 get_state 变慢、干扰计时。
    os.environ["GAME_SEED"] = "42"
    os.environ["GAME_MAX_TURNS"] = "999"

    config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="error")
    server = uvicorn.Server(config)
    th = threading.Thread(target=server.run, daemon=True)
    th.start()

    # 等端口就绪
    for _ in range(200):
        try:
            _http_get("/api/models", timeout=1.0)
            break
        except Exception:  # noqa: BLE001
            time.sleep(0.1)
    else:
        raise SystemExit("后端未能在 20s 内启动")

    print(f"后端已启动: {BASE}（单回合作为 {SLOW_TURN_S}s）")
    print(f"字段数自检: /api/state 字段数 = {len(json.loads(urllib.request.urlopen(BASE + '/api/state', timeout=30).read()))}"
          f"（含 season 则为 27）")

    latencies: list[float] = []
    try:
        asyncio.run(_ws_probe(latencies))
    finally:
        server.should_exit = True
        th.join(timeout=15)
        GameManager.__init__ = real_init  # type: ignore[method-assign]

    assert latencies, "未采集到任何样本"
    print()
    print(f"回合进行中 GET /api/state 耗时（{len(latencies)} 次，"
          f"确认有回合在跑: TURNS_STARTED={TURNS_STARTED.is_set()}）:")
    for i, dt in enumerate(latencies, 1):
        print(f"  #{i}: {dt * 1000:8.1f} ms")
    print(f"  min={min(latencies) * 1000:.1f}ms  "
          f"median={statistics.median(latencies) * 1000:.1f}ms  "
          f"max={max(latencies) * 1000:.1f}ms")
    verdict = (
        "✅ 事件循环未被阻塞（响应远小于单回合）"
        if max(latencies) < SLOW_TURN_S * 0.5
        else f"❌ 事件循环仍被阻塞（响应接近单回合 {SLOW_TURN_S}s）"
    )
    print(f"\n判定: {verdict}")
    # 留给调用方 grep 的机器可读行
    print(
        f"A4_PROBE max_ms={max(latencies) * 1000:.1f} "
        f"median_ms={statistics.median(latencies) * 1000:.1f} n={len(latencies)}"
    )


if __name__ == "__main__":
    main()
