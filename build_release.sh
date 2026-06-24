#!/bin/bash
# LLM三国志 v2.2 发布包构建脚本
# 用法: bash build_release.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT="llm-sanguo"
VERSION="2.2.0"
RELEASE_NAME="${PROJECT}-v${VERSION}"
RELEASE_DIR="$SCRIPT_DIR/release"
DIST_DIR="$RELEASE_DIR/$RELEASE_NAME"

echo "========================================"
echo "  LLM三国志 v${VERSION} 发布包构建"
echo "========================================"
echo ""

# 清理旧的发布目录
rm -rf "$RELEASE_DIR"
mkdir -p "$DIST_DIR"

echo "[1/5] 构建前端..."
(cd "$SCRIPT_DIR/web" && npm run build --silent 2>&1 | tail -1)

echo "[2/5] 复制后端代码..."
# 核心游戏引擎
cp -r "$SCRIPT_DIR/game" "$DIST_DIR/"
# 玩家层
cp -r "$SCRIPT_DIR/players" "$DIST_DIR/"
# 渲染层（pygame fallback）
cp -r "$SCRIPT_DIR/renderer" "$DIST_DIR/"
# API 层
cp -r "$SCRIPT_DIR/api" "$DIST_DIR/"

echo "[3/5] 复制数据和配置..."
cp -r "$SCRIPT_DIR/data" "$DIST_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$DIST_DIR/"
cp "$SCRIPT_DIR/run_web.py" "$DIST_DIR/"
cp "$SCRIPT_DIR/main.py" "$DIST_DIR/"
cp "$SCRIPT_DIR/verify.sh" "$DIST_DIR/"
cp "$SCRIPT_DIR/README.md" "$DIST_DIR/"
cp "$SCRIPT_DIR/AGENTS.md" "$DIST_DIR/"

echo "[4/5] 复制前端产物..."
mkdir -p "$DIST_DIR/web/dist"
cp -r "$SCRIPT_DIR/web/dist/"* "$DIST_DIR/web/dist/"

echo "[5/5] 创建桌面启动器..."

# 创建 production 启动脚本（无需 npm）
cat > "$DIST_DIR/start.sh" << 'STARTSCRIPT'
#!/bin/bash
# LLM三国志 一键启动脚本（发布版）
# 首次使用: pip install -r requirements.txt
cd "$(dirname "$0")"

echo "========================================"
echo "  LLM三国志 v2.2"
echo "========================================"

# 自动查找 Python
PYTHON=""
for py in python3.12 python3.11 python3.10 python3; do
    if command -v $py &>/dev/null; then
        PYTHON=$py
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "错误: 未找到 Python 3.10+，请先安装 Python"
    exit 1
fi

echo "使用: $($PYTHON --version)"

# 启动后端（FastAPI 直接服务预构建的前端）
exec "$PYTHON" -m uvicorn api.server:app --host 0.0.0.0 --port 8000
STARTSCRIPT
chmod +x "$DIST_DIR/start.sh"

# 复制 macOS App
mkdir -p "$DIST_DIR"
cp -r ~/Desktop/LLM三国志.app "$DIST_DIR/" 2>/dev/null || echo "  (macOS App 未找到，跳过)"

# 清理 __pycache__ 和 .pyc
find "$DIST_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$DIST_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true

# 打包
echo ""
echo "打包为 ${RELEASE_NAME}.zip ..."
cd "$RELEASE_DIR"
zip -qr "${RELEASE_NAME}.zip" "$RELEASE_NAME"

# 检查大小
SIZE=$(du -sh "${RELEASE_NAME}.zip" | cut -f1)
echo ""
echo "========================================"
echo "  ✅ 发布包构建完成"
echo "========================================"
echo "  文件: release/${RELEASE_NAME}.zip"
echo "  大小: $SIZE"
echo ""
echo "  使用方法:"
echo "    unzip ${RELEASE_NAME}.zip"
echo "    cd ${RELEASE_NAME}"
echo "    pip install -r requirements.txt"
echo "    bash start.sh"
echo ""
echo "  然后浏览器访问 http://localhost:8000"
echo "========================================"
