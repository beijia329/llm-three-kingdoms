#!/bin/bash
# 起后端 + 跑「终局文案注入矩阵」（同一进程树内）
set -u
cd /Users/dongsheng/Documents/llm-sanguo-project
PORT=8011
PY=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3
OUT=${1:-docs/qa/screenshots-2026-10-04-baseline}
MODE=${2:-standard}

OLD=$(lsof -nP -iTCP:${PORT} -sTCP:LISTEN -t 2>/dev/null)
if [ -n "$OLD" ]; then echo "[run] 端口 ${PORT} 被占用，先杀: $OLD"; kill $OLD 2>/dev/null; sleep 1; fi

export GAME_SEED=42 GAME_MAX_TURNS=48 GAME_MODE=${MODE}
"$PY" -m uvicorn api.server:app --host 127.0.0.1 --port ${PORT} > /tmp/qa-server-${PORT}.log 2>&1 &
SPID=$!
READY=0
for i in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:${PORT}/api/state" -o /dev/null; then READY=1; break; fi
  sleep 1
done
if [ "$READY" != "1" ]; then echo "[run] 后端未就绪"; tail -40 /tmp/qa-server-${PORT}.log; kill $SPID 2>/dev/null; exit 1; fi
echo "[run] 后端就绪"

node web/qa-endstate-matrix.mjs "http://127.0.0.1:${PORT}" "$OUT"
STATUS=$?
kill $SPID 2>/dev/null
echo "[run] 终局矩阵完成 status=${STATUS}"
exit ${STATUS}
