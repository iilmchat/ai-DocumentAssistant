# Руководство по Backend (FastAPI + Celery)

## Структура директории `backend/`
```text
backend/
├── app/
│   ├── api/            # Роутеры FastAPI (documents, chat)
│   ├── core/           # Конфигурация (config.py), подключение к БД (database.py)
│   ├── models/         # SQLAlchemy ORM модели
│   ├── schemas/        # Pydantic-схемы запросов и ответов
│   ├── services/       # Бизнес-логика: парсеры, чанкер, RAG-сервис, клиент LLM
│   ├── worker/         # Конфигурация Celery и фоновые задачи (tasks.py)
│   └── main.py         # Точка входа FastAPI и инициализация таблиц
├── Dockerfile
└── requirements.txt
```

## Локальный запуск без Docker (для отладки)
1. Создайте виртуальное окружение и установите зависимости:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # или venv\Scripts\activate на Windows
   pip install -r requirements.txt
   ```
2. Запустите сервер FastAPI с автоперезагрузкой:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
3. В отдельном терминале запустите воркер Celery:
   ```bash
   celery -A app.worker.celery_app worker --loglevel=info
   ```
