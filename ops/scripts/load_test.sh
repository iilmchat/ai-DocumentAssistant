#!/usr/bin/env bash
# T7-01: автоматический нагрузочный прогон Locust (без веб-UI, headless).
#Usage: LOAD_ACCESS_TOKEN=... LOAD_DOCUMENT_ID=... ./ops/scripts/load_test.sh
set -euo pipefail

HOST="${HOST:-http://localhost:8080}"
USERS="${USERS:-100}"
SPAWN_RATE="${SPAWN_RATE:-10}"
RUN_TIME="${RUN_TIME:-10m}"
REPORT_DIR="${REPORT_DIR:-docs/operations/reports}"

: "${LOAD_ACCESS_TOKEN:?нужен LOAD_ACCESS_TOKEN}"
: "${LOAD_DOCUMENT_ID:?нужен LOAD_DOCUMENT_ID}"

mkdir -p "$REPORT_DIR"
cd "$(dirname "$0")/../../backend"

locust -f tests/load/locustfile.py \
  --host "$HOST" \
  --headless \
  --users "$USERS" \
  --spawn-rate "$SPAWN_RATE" \
  --run-time "$RUN_TIME" \
  --html "../$REPORT_DIR/load-report.html" \
  --csv "../$REPORT_DIR/load-stats" \
  --only-summary

echo "Отчёт: $REPORT_DIR/load-report.html"
