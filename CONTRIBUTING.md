# Как внести вклад

Спасибо! Этот документ — быстрый старт для разработчика.

## 1. Подготовка

- Docker Desktop (Compose v2), Python 3.11+, Node.js 20+.
- `cp backend/.env.example backend/.env` — укажите `OPENAI_API_KEY` (для Gemini ещё
  `OPENAI_BASE_URL`, `LLM_MODEL`, `EMBEDDING_DIM=768`). Файл `.env` не коммитится.

## 2. Поднять стек

```bash
docker compose up --build -d
```

Backend при старте применяет миграции Alembic и выполняет smoke-check схемы.
API: `http://localhost:8000/docs`, интерфейс: `http://localhost`.

## 3. Локальная разработка без Docker

```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate   # Windows
pip install -r requirements-dev.txt
alembic upgrade head
python scripts/smoke_check.py
uvicorn app.main:app --reload --port 8000
# в другом терминале:
celery -A app.worker.celery_app worker --loglevel=info -Q default,dlq
```

Фронтенд:

```bash
cd frontend
npm ci
npm run dev
```

## 4. Проверки перед PR

Обязательно зелёным:

```bash
make check
```

Это ruff, mypy, pytest (порог покрытия 60%), pip-audit, ESLint/Prettier, build и npm audit.
CI повторяет то же самое и добавляет gitleaks, Trivy, Alembic-check и e2e (Playwright).

## 5. Правила коммитов

- Одна задача — один коммит; ссылка на идентификатор из `TODO.md`, например `ref S3-02`.
- Не коммитьте `.env`, ключи, токены, `__pycache__`, `node_modules`, `dist`.
- Новые эндпоинты — с тестами и обновлённым `docs/openapi/endpoints.md`.
- Изменения схемы БД — только через Alembic-миграцию в `backend/alembic/versions/`.

## 6. Ветки и PR

`main` защищён: PR → CI → review → squash-merge. Dependabot присылает обновления зависимостей.

## 7. Полезное

- Архитектура — [`docs/README.md`](./docs/README.md)
- Roadmap/спринты — [`TODO.md`](./TODO.md)
- SLO и разбор инцидентов — [`docs/operations/runbook.md`](./docs/operations/runbook.md)
- Нагрузочные тесты — [`docs/operations/load-test.md`](./docs/operations/load-test.md)
