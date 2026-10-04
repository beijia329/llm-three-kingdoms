#!/bin/bash
# 起后端 + 跑试玩基线截图（同一进程树内，避免跨轮次进程不保活）
set -u
cd /Users/dongsheng/Documents/llm-sanguo-project

PORT=8011
PY=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3
OUT=docs/qa/screenshots-2026-10-04-baseline

# 0. 确保端口干净（历史坑：连到旧版本）
OLD=$(lsof -nP -iTCP:${PORT} -sTCP:LISTEN -t 2>/dev/null)
if [ -n "$OLD" ]; then echo "[run] 端口 ${PORT} 被占用，先杀: $OLD"; kill $OLD 2>/dev/null; sleep 1; fi

# 1. 起后端（系统 python；显式 seed/max_turns/mode 保证可复现）
export GAME_SEED=42
export GAME_MAX_TURNS=48
export GAME_MODE=standard
echo "[run] 启动后端 :${PORT} (seed=$GAME_SEED max_turns=$GAME_MAX_TURNS mode=$GAME_MODE)"
"$PY" -m uvicorn api.server:app --host 127.0.0.1 --port ${PORT} > /tmp/qa-server-${PORT}.log 2>&1 &
SPID=$!
echo "[run] uvicorn pid=$SPID"

# 2. 等就绪
READY=0
for i in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:${PORT}/api/state" -o /tmp/qa-state-probe.json; then READY=1; break; fi
  sleep 1
done
if [ "$READY" != "1" ]; then echo "[run] 后端未就绪，日志:"; tail -40 /tmp/qa-server-${PORT}.log; kill $SPID 2>/dev/null; exit 1; fi
echo "[run] 后端就绪"
"$PY" - <<'EOF'
import json
d=json.load(open('/tmp/qa-state-probe.json'))
print('[run] 开局确认: turn=%s max_turns=%s mode=%s llm_active=%s' % (d.get('turn'), d.get('max_turns'), d.get('game_mode'), d.get('llm_active')))
EOF

# 3. 跑试玩脚本
node web/qa-baseline-playtest.mjs "http://127.0.0.1:${PORT}" "$OUT"
STATUS=$?

# 4. 收尾
kill $SPID 2>/dev/null
echo "[run] 截图完成，status=${STATUS}，产物在 ${OUT}"
ls -la "$OUT"
exit ${STATUS}
