#!/usr/bin/env bash
# T7-01: smoke-проверка стейджа после подъёма/деплоя.
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8080}"
echo "==> health/live: $BASE_URL/health/live"
curl -fsS "$BASE_URL/health/live"
echo
echo "==> health/ready"
curl -fsS "$BASE_URL/health/ready"
echo
echo "==> metrics (наличие ключевых метрик)"
METRICS=$(curl -fsS "$BASE_URL/metrics")
for key in http_requests_total vector_search_duration_seconds rag_queries_total rerank_duration_seconds; do
  if echo "$METRICS" | grep -q "$key"; then
    echo "  OK $key"
  else
    echo "  WARN $key пока не зафиксирован (нет запросов)"
  fi
done
echo "==> API docs"
curl -fsS -o /dev/null -w "  /docs -> %{http_code}\n" "$BASE_URL/docs"
