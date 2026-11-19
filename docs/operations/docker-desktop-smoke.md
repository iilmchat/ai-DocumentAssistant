# Живой smoke-прогон на Docker Desktop (2026-11-19)

Локально поднят реальный стек: PostgreSQL+pgvector, Redis, backend, worker, backup.
Использован некоммитируемый `docker-compose.local.yml` (!override портов), чтобы не конфликтовать
с посторонними контейнерами (workflow-builder Redis на 6379).

## Результаты

| Проверка | Результат |
| :--- | :--- |
| Alembic: 11 миграций (до `0011_doc_translation_lang`) | ✅ применены, `smoke_check OK: tables=10` |
| `/health/live`, `/health/ready` (db+redis) | ✅ 200 |
| Register → httpOnly cookie → `/auth/me` → CSRF-mutation | ✅ полный флоу |
| Загрузка TXT → Celery → `completed`, 1 страница | ✅ |
| RAG-чат по документу | ✅ 200, 4 цитата (офлайн-режим) |
| Backup pg_dump + restore во временную БД | ✅ 3 документа восстановлены |

## Найденные и исправленные баги (только проявились на живом стеке)

1. **Dockerfile CMD**: `python scripts/smoke_check.py` → `ModuleNotFoundError: No module named 'app'`
   (Python добавлял `/app/scripts` в sys.path). Добавлен `PYTHONPATH=/app`.
2. **CSRF на `/auth/register`**: 403 до получения CSRF-cookie. Auth-пути исключены из CSRF.
3. **`Secure` cookie на HTTP**: `/me` возвращал 401 — cookie не отправлялся. Для локалки
   `SESSION_COOKIE_SECURE=false` (в проде оставить true).
4. **Celery/redis**: kombu требует `redis-py>=6.1`, был 5.0.1 → обновлён до 6.4.0.
5. **sniff_mime UTF-8**: чтение 4096 байт обрывало кириллический символ → TXT отклонялся.
   Использован инкрементальный decoder + регрессионный тест.
6. **Event loop affinity в воркере**: engine с пулом привязывал asyncpg к первому loop →
   «Future attached to a different loop». Возвращён `NullPool`.
7. **HNSW `SET LOCAL`**: PostgreSQL не принимает bind-параметры → `SET LOCAL hnsw.ef_search = 80`.
8. **T6 колонка**: `documents.translation_language` использовалась, но отсутствовала → миграция 0011
   (короткий ID — `alembic_version` VARCHAR(32)).
9. **Backup**: контейнеру не хватало `PGPASSWORD` для pg_dump → добавлен в compose.
10. **Внешнее**: модель `gemini-2.5-flash` и embedding `text-embedding-004` более недоступны
    провайдером. Добавлен офлайн-режим `LOCAL_EMBEDDINGS=true` с детерминированными
    эмбеддингами и ответами — для разработки/smoke без внешнего API.

## Статус инфраструктурных пунктов

- T7-01 (load-test) — по-прежнему требует отдельного headless Locust-прогона.
- T9-02/T10-01 (Helm, e2e в браузере) — не прогонялись.
- Restore drill — выполнен вручную (скрипт `ops/scripts/restore_drill.sh` готов).
