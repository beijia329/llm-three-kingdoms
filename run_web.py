#!/usr/bin/env python3
"""乱斗三国 Web 启动器

一键启动后端 FastAPI 与前端 Vite 开发服务器，并自动打开浏览器。

用法：
    python run_web.py
    python run_web.py --seed 42 --max-turns 48 --no-browser
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.absolute()
WEB_DIR = PROJECT_ROOT / "web"
PYTHON = sys.executable
FRONTEND_PORT = 5173
BACKEND_PORT = 8000
FRONTEND_URL = f"http://localhost:{FRONTEND_PORT}"


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="启动 乱斗三国 Web 服务")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--max-turns", type=int, default=192, help="最大回合数（默认 192；无限模式下为软上限/兜底）")
    parser.add_argument("--mode", choices=["standard", "infinite"], default="infinite", help="游戏模式（默认 infinite：无限 + 僵局熔断）")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--no-frontend", action="store_true", help="仅启动后端")
    return parser.parse_args()


def wait_for_service(url: str, timeout: float = 30.0) -> bool:
    """等待服务就绪

    Args:
        url: 服务 URL
        timeout: 最大等待秒数

    Returns:
        是否成功
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def open_browser(url: str) -> None:
    """自动打开浏览器"""
    print(f"正在打开浏览器: {url}")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"自动打开浏览器失败: {e}")
        print(f"请手动访问: {url}")


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
        "--port", str(BACKEND_PORT),
        "--reload",
    ]
    print(f"[后端] {' '.join(backend_cmd)}")
    backend_proc = subprocess.Popen(backend_cmd, env=backend_env)

    frontend_proc = None
    if not args.no_frontend:
        # 等待后端就绪
        if not wait_for_service(f"http://127.0.0.1:{BACKEND_PORT}/api/state"):
            print("[错误] 后端启动失败")
            backend_proc.terminate()
            sys.exit(1)

        # 启动前端
        frontend_cmd = ["npm", "run", "dev"]
        print(f"[前端] cd web && {' '.join(frontend_cmd)}")
        frontend_proc = subprocess.Popen(frontend_cmd, cwd=WEB_DIR)

        # 等待前端就绪
        if not wait_for_service(FRONTEND_URL):
            print("[错误] 前端启动失败")
            backend_proc.terminate()
            frontend_proc.terminate()
            sys.exit(1)

        # 自动打开浏览器
        if not args.no_browser:
            open_browser(FRONTEND_URL)

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

    print("")
    print("=" * 50)
    print("  乱斗三国 Web 服务已启动")
    print("=" * 50)
    print(f"  后端: http://localhost:{BACKEND_PORT}")
    if not args.no_frontend:
        print(f"  前端: {FRONTEND_URL}")
    print("")
    print("  按 Ctrl+C 停止")
    print("=" * 50)
    print("")

    # 等待进程
    try:
        backend_proc.wait()
    except KeyboardInterrupt:
        shutdown(None, None)


if __name__ == "__main__":
    main()
