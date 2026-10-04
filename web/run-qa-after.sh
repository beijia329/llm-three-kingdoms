#!/bin/bash
# 改后复测：两种口径各跑一遍真实对局（standard/48 对比基线；infinite/192 新默认）
set -u
cd /Users/dongsheng/Documents/llm-sanguo-project
PORT=8011
PY=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3
BASE=http://127.0.0.1:${PORT}
AFTER=${1:-docs/qa/screenshots-2026-10-04-after}

echo "[after] 重建 dist（保证与 HEAD 一致）"
( cd web && npm run build > /tmp/qa-after-build.log 2>&1 ) || { echo "build 失败"; tail -30 /tmp/qa-after-build.log; exit 1; }

kill_port() { OLD=$(lsof -nP -iTCP:${PORT} -sTCP:LISTEN -t 2>/dev/null); [ -n "$OLD" ] && kill $OLD 2>/dev/null; sleep 1; }

start_server() { # $1 mode $2 max_turns $3 stalemate
  kill_port
  GAME_MODE=$1 GAME_MAX_TURNS=$2 GAME_STALEMATE_TURNS=$3 "$PY" -m uvicorn api.server:app --host 127.0.0.1 --port ${PORT} > /tmp/qa-server-${PORT}.log 2>&1 &
  SPID=$!
  for i in $(seq 1 60); do curl -sf ${BASE}/api/state -o /dev/null && { echo "[after] 后端就绪 mode=$1 max_turns=$2 stalemate=$3"; return 0; }; sleep 1; done
  echo "[after] 后端未就绪"; tail -40 /tmp/qa-server-${PORT}.log; return 1
}

echo "=========== 口径 A：standard / max_turns=48（对比基线）==========="
start_server standard 48 6 || exit 1
mkdir -p "$AFTER/standard48"
echo "seed=42 mode=standard max_turns=48" > "$AFTER/standard48/RUN-口径.txt"
node web/qa-baseline-playtest.mjs $BASE "$AFTER/standard48"
kill $SPID 2>/dev/null

echo "=========== 口径 B：infinite / max_turns=192 / stalemate=6（新默认）==========="
start_server infinite 192 6 || exit 1
mkdir -p "$AFTER/infinite"
echo "seed=42 mode=infinite max_turns=192 stalemate_turns=6" > "$AFTER/infinite/RUN-口径.txt"
node web/qa-baseline-playtest.mjs $BASE "$AFTER/infinite"
kill $SPID 2>/dev/null

echo "[after] 完成"
echo "--- standard48 end-state ---"; cat "$AFTER/standard48/end-api-state.json" 2>/dev/null; echo
echo "--- infinite end-state ---"; cat "$AFTER/infinite/end-api-state.json" 2>/dev/null; echo
