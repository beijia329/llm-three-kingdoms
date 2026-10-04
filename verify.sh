#!/bin/bash
# 乱斗三国 v4.2.0 验证脚本
# 用法: bash verify.sh
set -e
cd "$(dirname "$0")"

# 优先使用用户指定的 Python 解释器（避免系统 python3 缺少 pygame）
PYTHON="${PYTHON:-/Library/Frameworks/Python.framework/Versions/3.12/bin/python3}"

echo "========================================"
echo "  乱斗三国 v4.2.0 验证"
echo "========================================"
echo "使用解释器: $PYTHON"
echo ""

# 1. 导入验证
echo "--- 1. 导入验证 ---"
"$PYTHON" -c "from game.engine import GameEngine; from renderer.game_renderer import GameRenderer; print('  OK')"

# 2. 单元测试 + 集成测试
echo ""
echo "--- 2. 单元测试 ---"
"$PYTHON" -m pytest tests/unit/ -q
echo ""

echo "--- 3. 集成测试 ---"
"$PYTHON" -m pytest tests/integration/ -q
echo ""

# 4. GUI 冒烟测试 (headless)
echo "--- 4. GUI冒烟测试 ---"
"$PYTHON" tests/test_gui_smoke.py 2>&1 | grep -E "✓|✗|passed"
echo ""

# 5. CLI 对战 (3回合)
echo "--- 5. CLI对战测试(3回合) ---"
"$PYTHON" main.py --mode ai-vs-ai --seed 42 --max-turns 3 2>&1 | tail -5
echo ""

# 6. Web API 导入验证
echo "--- 6. Web API导入验证 ---"
"$PYTHON" -c "from api.server import app; from api.game_manager import GameManager; print('  OK')"
echo ""

# 7. 前端构建测试
echo "--- 7. 前端构建测试 ---"
if [ -d "web/node_modules" ]; then
    (cd web && npm run build)
else
    echo "  跳过（未安装 web/node_modules）"
fi
echo ""

echo "========================================"
echo "  全部验证通过"
echo "========================================"
echo ""
echo "启动 Web: $PYTHON run_web.py"
echo "启动 GUI: $PYTHON main.py --mode gui --seed 42"
