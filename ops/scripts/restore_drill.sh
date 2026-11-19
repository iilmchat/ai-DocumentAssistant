#!/usr/bin/env bash
# T7-01: учения по восстановлению из backup (НЕ на проде!).
# Восстанавливает дамп во ВРЕМЕННУЮ БД, проверяет схемы и данные, затем удаляет её.
set -euo pipefail

BACKUP_FILE="${1:-}"
if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: $0 /backups/<file>.dump" >&2
  exit 1
fi

DB_USER="${POSTGRES_USER:-postgres}"
DB_PASS="${POSTGRES_PASSWORD:-postgres}"
TEST_DB="ai_docs_restore_drill_$(date +%s)"

echo "==> создаём временную БД $TEST_DB"
docker compose exec -T db psql -U "$DB_USER" -d postgres -c "CREATE DATABASE $TEST_DB;"

echo "==> восстанавливаем дамп $BACKUP_FILE"
docker compose exec -T backup sh -c \
  "pg_restore -h db -U $DB_USER -d $TEST_DB --no-owner --no-privileges /backups/$(basename "$BACKUP_FILE")" \
  || echo "WARN: pg_restore вернул код != 0 (проверьте логи)"

echo "==> проверяем схему и данные"
docker compose exec -T backend sh -c \
  "DATABASE_URL=postgresql+asyncpg://$DB_USER:$DB_PASS@db:5432/$TEST_DB python scripts/smoke_check.py"

TABLES=$(docker compose exec -T db psql -U "$DB_USER" -d "$TEST_DB" -Atc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';")
DOCS=$(docker compose exec -T db psql -U "$DB_USER" -d "$TEST_DB" -Atc \
  "SELECT count(*) FROM documents;")
CHUNKS=$(docker compose exec -T db psql -U "$DB_USER" -d "$TEST_DB" -Atc \
  "SELECT count(*) FROM document_chunks;")
echo "Результат: tables=$TABLES documents=$DOCS chunks=$CHUNKS"
if [ "${TABLES:-0}" -lt 8 ] || [ "${DOCS:-0}" -lt 1 ]; then
  echo "FAIL: восстановление некорректно" >&2
  exit 1
fi

echo "==> удаляем временную БД"
docker compose exec -T db psql -U "$DB_USER" -d postgres -c "DROP DATABASE $TEST_DB;"
echo "RESTORE DRILL OK"
