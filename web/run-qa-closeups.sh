#!/bin/bash
# 起后端 + 跑 M2/M4 证据补拍
set -u
cd /Users/dongsheng/Documents/llm-sanguo-project
PORT=8011
PY=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3
OUT=${1:-docs/qa/screenshots-2026-10-04-after/m2-m4}

OLD=$(lsof -nP -iTCP:${PORT} -sTCP:LISTEN -t 2>/dev/null)
if [ -n "$OLD" ]; then echo "[run] 端口 ${PORT} 被占用，先杀: $OLD"; kill $OLD 2>/dev/null; sleep 1; fi

export GAME_SEED=42 GAME_MAX_TURNS=48 GAME_MODE=standard
"$PY" -m uvicorn api.server:app --host 127.0.0.1 --port ${PORT} > /tmp/qa-server-${PORT}.log 2>&1 &
SPID=$!
for i in $(seq 1 60); do curl -sf "http://127.0.0.1:${PORT}/api/state" -o /dev/null && break; sleep 1; done
echo "[run] 后端就绪"
mkdir -p "$OUT"
node web/qa-closeups.mjs "http://127.0.0.1:${PORT}" "$OUT"
STATUS=$?
kill $SPID 2>/dev/null
echo "[run] 补拍完成 status=${STATUS}"
ls -la "$OUT"
exit ${STATUS}
