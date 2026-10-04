#!/bin/bash
# 图标放大帧重拍（crown / army 补齐）
set -u
cd /Users/dongsheng/Documents/llm-sanguo-project
F2="${1:-docs/qa/screenshots-2026-10-04-final2}"
PORT=8011
PY=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3
O=$(lsof -nP -iTCP:${PORT} -sTCP:LISTEN -t 2>/dev/null || true)
if [ -n "${O:-}" ]; then kill $O 2>/dev/null; sleep 1; fi
GAME_SEED=42 GAME_MAX_TURNS=48 GAME_MODE=standard "$PY" -m uvicorn api.server:app --host 127.0.0.1 --port ${PORT} > /tmp/qa-icons.log 2>&1 &
SPID=$!
for i in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:${PORT}/api/state" -o /dev/null; then break; fi
  sleep 1
done
node web/qa-iconprobe.mjs "http://127.0.0.1:${PORT}" "$F2/icons" 2>&1 | tail -20
kill $SPID 2>/dev/null
echo "--- icons ---"
ls "$F2/icons"
