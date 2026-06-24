#!/usr/bin/env python3
"""LLM三国志 Web 启动器

一键启动后端 FastAPI 与前端 Vite 开发服务器。

用法：
    python run_web.py
    python run_web.py --seed 42 --max-turns 192
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.absolute()
WEB_DIR = PROJECT_ROOT / "web"
PYTHON = sys.executable


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="启动 LLM三国志 Web 服务")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--max-turns", type=int, default=192, help="最大回合数")
    parser.add_argument("--mode", choices=["standard", "infinite"], default="standard", help="游戏模式")
    parser.add_argument("--no-frontend", action="store_true", help="仅启动后端")
    return parser.parse_args()


def main() -> None:
    """主入口"""
    args = parse_args()

    os.chdir(PROJECT_ROOT)

    # 启动后端
    backend_env = os.environ.copy()
    backend_env["GAME_SEED"] = str(args.seed)
    backend_env["GAME_MAX_TURNS"] = str(args.max_turns)
    backend_env["GAME_MODE"] = args.mode

    backend_cmd = [
        PYTHON, "-m", "uvicorn",
        "api.server:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload",
    ]
    print(f"[后端] {' '.join(backend_cmd)}")
    backend_proc = subprocess.Popen(backend_cmd, env=backend_env)

    frontend_proc = None
    if not args.no_frontend:
        # 等待后端启动
        time.sleep(1.5)

        frontend_cmd = ["npm", "run", "dev"]
        print(f"[前端] cd web && {' '.join(frontend_cmd)}")
        frontend_proc = subprocess.Popen(frontend_cmd, cwd=WEB_DIR)

    def shutdown(signum, frame):
        print("\n[关闭] 正在停止服务...")
        backend_proc.terminate()
        if frontend_proc:
            frontend_proc.terminate()
        try:
            backend_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            backend_proc.kill()
        if frontend_proc:
            try:
                frontend_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                frontend_proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("\n服务已启动:")
    print("  后端: http://localhost:8000")
    if not args.no_frontend:
        print("  前端: http://localhost:5173")
    print("按 Ctrl+C 停止\n")

    # 等待进程
    try:
        backend_proc.wait()
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()
