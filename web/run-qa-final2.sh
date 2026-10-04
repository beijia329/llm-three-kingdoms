#!/bin/bash
# v4.3.0 复验（@682f206）：真实对局两口径 + 终局矩阵 + M2/M4 补拍 + 图标断言
set -u
cd /Users/dongsheng/Documents/llm-sanguo-project
F2="${1:-docs/qa/screenshots-2026-10-04-final2}"
PORT=8011
PY=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3

kill_port() { local OLD; OLD=$(lsof -nP -iTCP:${PORT} -sTCP:LISTEN -t 2>/dev/null || true); if [ -n "${OLD:-}" ]; then kill $OLD 2>/dev/null || true; sleep 1; fi }

echo "########## 1/4 AFTER (rebuild + standard48 + infinite) ##########"
bash web/run-qa-after.sh "$F2" 2>&1 | tail -25

echo "########## 2/4 ENDSTATE (A1-A6) ##########"
bash web/run-qa-endstate.sh "$F2" infinite 2>&1 | tail -26

echo "########## 3/4 CLOSEUPS (M2/M4) ##########"
bash web/run-qa-closeups.sh "$F2/m2-m4" 2>&1 | tail -20

echo "########## 4/4 ICONPROBE (mask 修复断言 + 放大帧) ##########"
kill_port
GAME_SEED=42 GAME_MAX_TURNS=48 GAME_MODE=standard "$PY" -m uvicorn api.server:app --host 127.0.0.1 --port ${PORT} > /tmp/qa-server-${PORT}.log 2>&1 &
SPID=$!
for i in $(seq 1 60); do curl -sf "http://127.0.0.1:${PORT}/api/state" -o /dev/null && break; sleep 1; done
node web/qa-iconprobe.mjs "http://127.0.0.1:${PORT}" "$F2/icons" 2>&1 | tail -25
kill $SPID 2>/dev/null

echo "########## 汇总 ##########"
echo "--- standard48 end ---"; cat "$F2/standard48/end-api-state.json" 2>/dev/null; echo
echo "--- infinite end ---"; cat "$F2/infinite/end-api-state.json" 2>/dev/null; echo
echo "--- endstate verdict ---"; head -1 "$F2/endstate-verdict.txt" 2>/dev/null
echo "--- icons ---"; ls "$F2/icons" 2>/dev/null
kill_port
