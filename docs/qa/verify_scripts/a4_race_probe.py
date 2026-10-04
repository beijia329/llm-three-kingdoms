"""A4 安全性实验：process_turn 跑在**线程**里时，并发 get_state 会不会炸。

背景：A4 要把同步的 process_turn 挪进 executor。一旦挪走，事件循环在回合
期间是可响应的，于是 `GET /api/state`（REST）会与正在跑的回合**并发**读引擎。
若两者会互相踩坏，这个改动就是引入新缺陷，必须先量化。

方法：起 1 个后台线程连续 process_turn，主线程高频 get_state，
记录异常类型与出现次数。CLI 规则 AI 单回合 ~12ms → 并发窗口远比
LLM 模式（单回合 40s、但写操作集中在同一批系统调用）密集，是更严苛的压测。
"""
import os
import sys
import threading
import time
import traceback
from pathlib import Path

# 直接运行本脚本时 sys.path[0] 是 docs/qa/verify_scripts，不是项目根。
# 本文件路径 = <root>/docs/qa/verify_scripts/<file> → 项目根 = parents[3]。
_PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from api.game_manager import GameConfig, GameManager  # noqa: E402


def main() -> None:
    mgr = GameManager(config=GameConfig(seed=42, max_turns=9999,
                                        factions=["caocao", "yuanshao", "liubei"],
                                        use_llm=False))
    stop = threading.Event()
    errors: list[str] = []
    reads = [0]
    turns = [0]

    def writer() -> None:
        while not stop.is_set():
            try:
                mgr.process_turn()
                turns[0] += 1
            except Exception:  # noqa: BLE001
                errors.append("writer:\n" + traceback.format_exc())
                return

    def reader() -> None:
        while not stop.is_set():
            try:
                mgr.get_state()
                mgr.get_state(known_hex_map_version="deadbeef")
                reads[0] += 1
            except Exception:  # noqa: BLE001
                errors.append("reader:\n" + traceback.format_exc())
                return

    threads = [threading.Thread(target=writer, daemon=True) for _ in range(2)]
    threads.append(threading.Thread(target=reader, daemon=True))
    for t in threads:
        t.start()
    time.sleep(12)
    stop.set()
    for t in threads:
        t.join(timeout=10)

    print(f"turns={turns[0]} reads={reads[0]} errors={len(errors)}")
    for e in errors[:3]:
        print(e)
    print("VERDICT:", "RACE FOUND" if errors else "no race observed")


if __name__ == "__main__":
    main()
