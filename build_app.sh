#!/bin/bash
# 乱斗三国 v2.3 — 构建 macOS 自安装 .app
# 首次双击自动 pip install，之后点击即玩
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="乱斗三国"
APP_DIR="$SCRIPT_DIR/release/${APP_NAME}.app"
VENV_DIR="$HOME/.llm-sanguo/venv"
PROJECT_DIR="$SCRIPT_DIR"

echo "========================================"
echo "  构建 ${APP_NAME}.app (自安装版)"
echo "========================================"

rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

# ============================================================
# 1. Info.plist
# ============================================================
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
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>乱斗三国</string>
    <key>CFBundleDisplayName</key>
    <string>乱斗三国</string>
    <key>CFBundleIconFile</key>
    <string>app_icon</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>2.2</string>
    <key>CFBundleVersion</key>
    <string>2</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSUIElement</key>
    <false/>
</dict>
</plist>
PLIST

# ============================================================
# 2. Launcher 脚本（自安装 + 后台启动）
# ============================================================
cat > "$APP_DIR/Contents/MacOS/launcher" << 'LAUNCHER'
#!/bin/bash
# 乱斗三国 自安装启动器
# - 首次运行：创建 venv + pip install（显示进度）
# - 后续运行：直接启动（秒开）
set -e

APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PROJECT_DIR="__PROJECT_DIR__"
VENV_DIR="$HOME/.llm-sanguo/venv"
PID_FILE="$HOME/.llm-sanguo/server.pid"
LOG_FILE="$HOME/.llm-sanguo/server.log"
PORT=8000

# ---- 检测已有实例 ----
if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
    osascript -e 'display notification "服务器已在运行中" with title "乱斗三国" subtitle "http://localhost:'$PORT'"'
    open "http://localhost:$PORT"
    exit 0
fi

# ---- 首次运行：安装依赖 ----
if [ ! -d "$VENV_DIR" ]; then
    # 用 osascript 显示进度对话框
    osascript -e 'display notification "首次启动，正在安装依赖..." with title "乱斗三国" subtitle "约需 1-2 分钟"'
    
    # 查找系统 Python 3
    PYTHON=""
    for py in python3.12 python3.11 python3.10 python3; do
        if command -v $py &>/dev/null && $py -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
            PYTHON=$(command -v $py)
            break
        fi
    done
    
    if [ -z "$PYTHON" ]; then
        osascript -e 'display dialog "需要 Python 3.10+\n\n请先安装: brew install python@3.12" with title "乱斗三国" buttons {"OK"} default button "OK" with icon stop'
        exit 1
    fi
    
    # 创建 venv
    "$PYTHON" -m venv "$VENV_DIR" 2>&1 | tee -a "$LOG_FILE"
    
    # 安装依赖（后台，不阻塞）
    "$VENV_DIR/bin/pip" install -q -r "$PROJECT_DIR/requirements.txt" 2>&1 | tee -a "$LOG_FILE" &
    PIP_PID=$!
    
    # 显示安装进度
    (
        while kill -0 $PIP_PID 2>/dev/null; do
            sleep 2
        done
        # 安装完成，启动服务
        osascript -e 'display notification "依赖安装完成，正在启动..." with title "乱斗三国"'
        "$VENV_DIR/bin/python" -m uvicorn api.server:app --host 0.0.0.0 --port $PORT --log-level warning &
        echo $! > "$PID_FILE"
        sleep 2
        open "http://localhost:$PORT"
    ) &
    
    exit 0
fi

# ---- 正常启动（已有 venv） ----
cd "$PROJECT_DIR"

# 检查是否需要更新依赖（每周检查一次）
LAST_CHECK="$HOME/.llm-sanguo/.last_dep_check"
if [ ! -f "$LAST_CHECK" ] || [ $(find "$LAST_CHECK" -mtime +7 | wc -l) -gt 0 ]; then
    "$VENV_DIR/bin/pip" install -q -r "$PROJECT_DIR/requirements.txt" 2>/dev/null &
    touch "$LAST_CHECK"
fi

# 启动服务
nohup "$VENV_DIR/bin/python" -m uvicorn api.server:app --host 0.0.0.0 --port $PORT --log-level warning > "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"

# 等待服务就绪
for i in $(seq 1 20); do
    if curl -s "http://localhost:$PORT/api/state" > /dev/null 2>&1; then
        break
    fi
    sleep 0.3
done

# 打开浏览器
open "http://localhost:$PORT"

osascript -e 'display notification "服务已启动" with title "乱斗三国" subtitle "http://localhost:'$PORT'"'
LAUNCHER

# 替换项目路径
sed -i '' "s|__PROJECT_DIR__|$PROJECT_DIR|g" "$APP_DIR/Contents/MacOS/launcher"
chmod +x "$APP_DIR/Contents/MacOS/launcher"

# 复制图标
cp "$SCRIPT_DIR/assets/app_icon.icns" "$APP_DIR/Contents/Resources/app_icon.icns"

# ============================================================
# 3. 复制到桌面
# ============================================================
if [ -d ~/Desktop/"${APP_NAME}.app" ]; then
    rm -rf ~/Desktop/"${APP_NAME}.app"
fi
cp -r "$APP_DIR" ~/Desktop/

echo ""
echo "========================================"
echo "  ✅ ${APP_NAME}.app 已构建"
echo "========================================"
echo "  位置: ~/Desktop/${APP_NAME}.app"
echo ""
echo "  首次双击: 自动装依赖 (1-2分钟)"
echo "  之后双击: 秒开即玩"
echo ""
echo "  手动启动也可以:"
echo "    bash start.sh"
echo "========================================"
