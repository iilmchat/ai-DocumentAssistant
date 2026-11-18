# Быстрый старт и настройка окружения

## Предварительные требования
- Docker Desktop (или Docker Engine + Docker Compose v2)
- API-ключ для LLM и эмбеддингов (OpenAI, OpenRouter, Google Gemini или локальная Ollama)

## Шаг 1: Настройка переменных окружения
Создайте файл `.env` в корневой директории проекта:

```env
# База данных PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=doc_assistant
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/doc_assistant

# Брокер Redis
REDIS_URL=redis://redis:6379/0

# Настройки AI-провайдера
OPENAI_API_KEY=ваш_ключ_api
# Опционально: базовый URL для OpenAI-совместимых API (OpenRouter, Groq, Ollama)
# OPENAI_BASE_URL=https://openrouter.ai/api/v1
```

## Шаг 2: Запуск контейнеров
Схема БД управляется Alembic. При запуске через Docker миграции применяются автоматически (`alembic upgrade head` в CMD backend):
```bash
docker compose up --build -d
```

Локальный запуск без Docker:
```bash
cd backend
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

> Если у вас уже есть старый volume с таблицами, созданными через `create_all`, выполните
> `alembic stamp head`, чтобы пометить текущее состояние как базовую ревизию.

## Шаг 3: Проверка работоспособности
- Убедитесь, что все 5 контейнеров (`ai_frontend`, `ai_backend`, `ai_celery_worker`, `ai_postgres`, `ai_redis`) находятся в статусе `Up` / `Healthy`:
  ```bash
  docker compose ps
  ```
- Откройте в браузере `http://localhost`.
