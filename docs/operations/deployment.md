# Развёртывание и эксплуатация

## Локально / dev

```bash
cp backend/.env.example backend/.env   # указать OPENAI_API_KEY
docker compose up --build -d
```

Backend автоматически применяет Alembic-миграции и выполняет smoke-check (`scripts/smoke_check.py`).

## Staging (S4)

```bash
make staging-up     # docker-compose.staging.yml: отдельные порты и имя проекта
# API: http://localhost:8080/docs, UI: http://8081, Grafana: http://localhost:13000
make staging-down
```

## Сервисы

| Сервис | Порт (dev) | Назначение |
| :--- | :--- | :--- |
| frontend | 80 | UI |
| backend | 8000 | API, `/health/live`, `/health/ready`, `/metrics` |
| worker / ocr-worker | — | Celery: default+dlq и ocr |
| beat | — | ежедневный retention (S4) |
| db | 127.0.0.1:5432 | PostgreSQL + pgvector |
| pgbouncer | 127.0.0.1:6432 | опциональный пул (`DB_HOST=pgbouncer DB_PORT=6432`) |
| redis | 127.0.0.1:6379 | брокер и кэш |
| flower | 127.0.0.1:5555 | мониторинг задач |
| prometheus | 127.0.0.1:9090 | метрики и алерты |
| grafana | 127.0.0.1:3000 | дашборд |
| backup | — | ежедневный pg_dump, хранение 30 дней |

## Резервное копирование и восстановление

См. [`backup-restore.md`](./backup-restore.md). Ежедневный дамп в volume `backup_data`,
ручной — `make backup`.

## Reload / обновление

```bash
git pull
docker compose up --build -d      # миграции применятся при старте backend
docker compose ps
curl http://localhost/health/ready
```

## Переменные окружения

Все секреты — в `.env` (не коммитится). Полный список — `backend/.env.example`.
Для прода обязательно заменить `SECRET_KEY`, `POSTGRES_PASSWORD`, `GRAFANA_PASSWORD`.
