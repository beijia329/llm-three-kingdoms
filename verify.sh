#!/bin/bash
# LLM三国志 v2.0 验证脚本
# 用法: bash verify.sh
set -e
cd "$(dirname "$0")"
echo "========================================"
echo "  LLM三国志 v2.0 验证"
echo "========================================"
echo ""

# 1. 清除缓存
echo "--- 1. 导入验证 ---"
python3 -c "from game.engine import GameEngine; from renderer.game_renderer import GameRenderer; print('  OK')"

# 2. 单元测试 + 集成测试
echo ""
echo "--- 2. 单元测试 ---"
python3 -m pytest tests/unit/ -q
echo ""

echo "--- 3. 集成测试 ---"
python3 -m pytest tests/integration/ -q
echo ""

# 4. GUI 冒烟测试 (headless)
echo "--- 4. GUI冒烟测试 ---"
python3 tests/test_gui_smoke.py 2>&1 | grep -E "✓|✗|passed"
echo ""

# 5. CLI 对战 (3回合)
echo "--- 5. CLI对战测试(3回合) ---"
python3 main.py --mode ai-vs-ai --seed 42 --max-turns 3 2>&1 | tail -5
echo ""

echo "========================================"
echo "  全部验证通过"
echo "========================================"
echo ""
echo "启动 GUI: python3 main.py --mode gui --seed 42"
echo "LLM对战: python3 main.py --mode gui --seed 42 --llm"
