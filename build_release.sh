#!/bin/bash
# 乱斗三国 v4.3.1 发布包构建脚本
# 用法: bash build_release.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT="llm-sanguo"
VERSION="4.3.1"
RELEASE_NAME="${PROJECT}-v${VERSION}"
RELEASE_DIR="$SCRIPT_DIR/release"
DIST_DIR="$RELEASE_DIR/$RELEASE_NAME"
APP_NAME="乱斗三国"

echo "========================================"
echo "  乱斗三国 v${VERSION} 发布包构建"
echo "========================================"
echo ""

# 清理旧的发布目录
rm -rf "$RELEASE_DIR"
mkdir -p "$DIST_DIR"

echo "[1/6] 构建前端..."
(cd "$SCRIPT_DIR/web" && npm run build --silent 2>&1 | tail -1)

echo "[2/6] 复制后端代码..."
cp -r "$SCRIPT_DIR/game" "$DIST_DIR/"
cp -r "$SCRIPT_DIR/players" "$DIST_DIR/"
cp -r "$SCRIPT_DIR/renderer" "$DIST_DIR/"
cp -r "$SCRIPT_DIR/api" "$DIST_DIR/"
cp -r "$SCRIPT_DIR/data" "$DIST_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$DIST_DIR/"
cp "$SCRIPT_DIR/run_web.py" "$DIST_DIR/"
cp "$SCRIPT_DIR/main.py" "$DIST_DIR/"
cp "$SCRIPT_DIR/README.md" "$DIST_DIR/"
cp "$SCRIPT_DIR/AGENTS.md" "$DIST_DIR/"

echo "[3/6] 复制前端产物..."
mkdir -p "$DIST_DIR/web/dist"
cp -r "$SCRIPT_DIR/web/dist/"* "$DIST_DIR/web/dist/"

echo "[4/6] 构建 macOS App（自安装版）..."

# 创建 self-contained .app（项目文件打包在 App 内）
APP_DIR="$DIST_DIR/${APP_NAME}.app"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

# Info.plist
cat > "$APP_DIR/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>zh-CN</string>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleIdentifier</key>
    <string>com.llm-sanguo.launcher</string>
    <key>CFBundleName</key>
    <string>乱斗三国</string>
    <key>CFBundleDisplayName</key>
    <string>乱斗三国</string>
    <key>CFBundleIconFile</key>
    <string>app_icon</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>4.3.1</string>
    <key>CFBundleVersion</key>
    <string>4.3.1</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST

# 自安装启动器（项目文件在 App 内）
cat > "$APP_DIR/Contents/MacOS/launcher" << 'LAUNCHER'
#!/bin/bash
set -e

APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PROJECT_DIR="$APP_DIR/Contents/project"
VENV_DIR="$HOME/.llm-sanguo/venv"
PID_FILE="$HOME/.llm-sanguo/server.pid"
LOG_FILE="$HOME/.llm-sanguo/server.log"
PORT=8000

# 已有实例 → 直接打开浏览器
if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
    open "http://localhost:$PORT"
    exit 0
fi

# 首次运行：安装依赖
if [ ! -d "$VENV_DIR" ]; then
    osascript -e 'display notification "首次启动，正在安装依赖..." with title "乱斗三国" subtitle "约需 1-2 分钟"'
    
    PYTHON=""
    for py in python3.12 python3.11 python3.10 python3; do
        if command -v $py &>/dev/null && $py -c "import sys; exit(0 if sys.version_info>=(3,10) else 1)" 2>/dev/null; then
            PYTHON=$(command -v $py)
            break
        fi
    done
    
    if [ -z "$PYTHON" ]; then
        osascript -e 'display dialog "需要 Python 3.10+\n\n安装方法:\n  brew install python@3.12" with title "乱斗三国" buttons {"OK"} default button "OK" with icon stop'
        exit 1
    fi
    
    "$PYTHON" -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install -q --disable-pip-version-check -r "$PROJECT_DIR/requirements.txt" &
    PIP_PID=$!
    
    (
        while kill -0 $PIP_PID 2>/dev/null; do sleep 2; done
        wait $PIP_PID
        if [ $? -eq 0 ]; then
            osascript -e 'display notification "安装完成，正在启动..." with title "乱斗三国"'
            cd "$PROJECT_DIR"
            nohup "$VENV_DIR/bin/python" -m uvicorn api.server:app --host 0.0.0.0 --port $PORT --log-level warning > "$LOG_FILE" 2>&1 &
            echo $! > "$PID_FILE"
            sleep 2
            open "http://localhost:$PORT"
        else
            osascript -e 'display dialog "依赖安装失败，请检查网络连接后重试" with title "乱斗三国" buttons {"OK"} with icon stop'
            rm -rf "$VENV_DIR"
        fi
    ) &
    exit 0
fi

# 正常启动（已有 venv）
cd "$PROJECT_DIR"

# 每周自动更新依赖
LAST_CHECK="$HOME/.llm-sanguo/.last_dep_check"
if [ ! -f "$LAST_CHECK" ] || [ $(find "$LAST_CHECK" -mtime +7 | wc -l) -gt 0 ]; then
    "$VENV_DIR/bin/pip" install -q --disable-pip-version-check -r "$PROJECT_DIR/requirements.txt" 2>/dev/null &
    touch "$LAST_CHECK"
fi

nohup "$VENV_DIR/bin/python" -m uvicorn api.server:app --host 0.0.0.0 --port $PORT --log-level warning > "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"

for i in $(seq 1 20); do
    if curl -s "http://localhost:$PORT/api/state" > /dev/null 2>&1; then break; fi
    sleep 0.3
done

open "http://localhost:$PORT"
LAUNCHER
chmod +x "$APP_DIR/Contents/MacOS/launcher"

# 复制图标
cp "$SCRIPT_DIR/assets/app_icon.icns" "$APP_DIR/Contents/Resources/app_icon.icns"

# 把项目文件复制进 App 内
echo "[5/6] 打包项目文件到 App..."
mkdir -p "$APP_DIR/Contents/project"
rsync -a --exclude='__pycache__' --exclude='*.pyc' --exclude='.DS_Store' \
    "$DIST_DIR/game" "$DIST_DIR/players" "$DIST_DIR/renderer" \
    "$DIST_DIR/api" "$DIST_DIR/data" "$DIST_DIR/web" \
    "$DIST_DIR/requirements.txt" \
    "$APP_DIR/Contents/project/"

# 清理重复文件（已在 App 内）
rm -rf "$DIST_DIR/game" "$DIST_DIR/players" "$DIST_DIR/renderer" \
       "$DIST_DIR/api" "$DIST_DIR/data" "$DIST_DIR/web" \
       "$DIST_DIR/requirements.txt" "$DIST_DIR/run_web.py" "$DIST_DIR/main.py"

# 创建简单的启动说明
cat > "$DIST_DIR/使用说明.txt" << 'README'
乱斗三国 v4.3.1 — 使用方法
============================

【macOS】双击 乱斗三国.app
  - 首次启动自动安装 Python 依赖（1-2分钟）
  - 之后双击秒开，浏览器自动打开

【通用】终端启动
  pip install -r requirements.txt
  python3 -m uvicorn api.server:app --host 0.0.0.0 --port 8000
  浏览器访问 http://localhost:8000

【开发模式（需要 npm）】
  python3 run_web.py --seed 42
README

# 清理
find "$DIST_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$DIST_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true

# 打包
echo "[6/6] 打包..."
cd "$RELEASE_DIR"
zip -qr "${RELEASE_NAME}.zip" "$RELEASE_NAME"

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
echo "    双击 乱斗三国.app"
echo "========================================"
