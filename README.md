# AI Document Assistant («AI Конспект»)

Веб-приложение для автоматического анализа документов (PDF, DOCX, TXT), генерации структурированных конспектов и ответов на вопросы по содержимому файлов в режиме RAG-чата (Retrieval-Augmented Generation).

## Основные возможности

- **Загрузка документов:** `.pdf`, `.docx`, `.txt`, а также изображения `.jpg`, `.png`, `.tiff` с проверкой MIME по содержимому (magic bytes) и защитой от ZIP-бомб.
- **Гибридное извлечение (Этап 1):** текстовый слой PDF через PyMuPDF, а страницы-сканы уходят в OCR (Tesseract или vision-модель). Постраничное хранение с меткой метода и confidence.
- **Семантический чанкинг (Этап 3):** разбивка по заголовкам/абзацам/таблицам с сохранением `heading_path`, ссылками на страницы и дедупликацией колонтитулов.
- **Умный конспект:** Map/Reduce-суммаризация больших документов.
- **RAG-чат с цитатами (Этапы 1 и 5):** гибридный поиск pgvector + PostgreSQL FTS (russian) с Reciprocal Rank Fusion; ответ сопровождается ссылками на страницы.
- **Асинхронная индексация:** две очереди Celery (быстрая и OCR) + Redis, живой прогресс через SSE/поллинг.
- **Многопользовательскость (Этап 4):** JWT-регистрация/логин, документы изолированы по владельцу.
- **Безопасность (S1):** refresh-токены с ротацией и чёрным списком, rate limiting, защита от decompression bomb, квоты и audit log. Threat model — в [`docs/security/threat-model.md`](./docs/security/threat-model.md).
- **Наблюдаемость (S2):** JSON-логи с `X-Request-ID`, Prometheus-метрики, Grafana-дашборд, Flower, SSE heartbeat, DLQ и circuit breaker. SLO и runbook — в [`docs/operations/runbook.md`](./docs/operations/runbook.md).
- **Идемпотентность:** повторная загрузка того же файла (SHA-256) не пересчитывает OCR и эмбеддинги.

## Технологический стек

- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Nginx
- **Backend:** Python 3.11, FastAPI, SQLAlchemy (async), Pydantic
- **Очереди задач:** Celery, Redis
- **База данных:** PostgreSQL 16 + `pgvector` + полнотекстовый индекс
- **AI / LLM:** любой OpenAI-совместимый провайдер (OpenAI, Gemini, OpenRouter, Groq, Ollama)

## Быстрый запуск

1. Скопируйте `backend/.env.example` в `backend/.env` и укажите `OPENAI_API_KEY` (для Gemini также `OPENAI_BASE_URL`, `LLM_MODEL` и `EMBEDDING_DIM=768`):
   ```bash
   cp backend/.env.example backend/.env
   ```
2. Запустите стек (миграции Alembic применяются автоматически при старте backend):
   ```bash
   docker compose up --build -d
   ```
3. Откройте:
   - **Веб-интерфейс:** http://localhost
   - **Swagger API:** http://localhost:8000/docs

Подробная документация — в директории [`docs/`](./docs/README.md). План улучшений по best practices (спринты, приоритеты, статусы) — в [`TODO.md`](./TODO.md).

## Известные проблемы и что было исправлено

- **pgvector**: в `models.py` использовался несуществующий класс `VECTOR` — заменён на `Vector` из `pgvector.sqlalchemy`.
- **PyPDF2** устарел и не читает современные PDF — заменён на `pypdf` / `PyMuPDF`.
- **httpx/openai**: зафиксирован `httpx==0.27.0`, чтобы исключить конфликт `proxies` с новыми версиями httpx.
- **Путь к хранилищу**: путь к файлам был жёстко зашит как относительный `"storage"` — добавлена настройка `UPLOAD_DIR` (`/app/storage` в контейнерах).
- Удалён пустой мусорный `package-lock.json` в корне репозитория.

## Дальнейшее развитие (roadmap)

1. **OCR для сканов и изображений** — добавить поддержку JPG/PNG/TIFF и распознавание текста со сканированных PDF:
   - быстрый вариант: `pytesseract` + `pdf2image` (poppler);
   - современный вариант: `PaddleOCR` или вызов vision-модели (`gpt-4o` / `gemini`) напрямую по страницам PDF.
2. **Реальный чанкинг по смыслу** вместо грубого среза по символам (например, `langchain-text-splitters` по предложениям/разделам).
3. **Мультимодальные ответы и ссылки на страницы** — хранить номер страницы для каждого чанка и показывать цитаты с постраничной привязкой.
4. **Аутентификация и многопользовательскость** — JWT-логин вместо «заглушки» пользователя; сейчас все документы принадлежат одному демо-аккаунту.
5. **Гибридный поиск (BM25 + вектор)** для повышения качества RAG.
6. **Стриминг ответов LLM** (SSE) вместо имитации «печатной машинки» на фронте.
7. **Экспорт конспектов** (Markdown/PDF/DOCX) и история версий документа.
8. **Тесты и CI** — pytest для backend, базовые e2e-тесты фронта.

> Статус: все пункты roadmap реализованы (1 — включая JPG/PNG/TIFF; 7 — экспорт MD/DOCX/PDF и история версий; 8 — pytest + e2e + GitHub Actions CI).

## Тесты и проверки

Все проверки S0 (ruff, mypy, pytest + coverage, pip-audit, ESLint/Prettier, build, npm audit):
```bash
make check
```

Отдельно:
```bash
# Backend
cd backend && python -m pytest -q

# Frontend (e2e, после npm run build)
cd frontend && npm run test:e2e
```

CI (GitHub Actions) при каждом push/PR в `main` прогоняет pytest, сборку фронтенда и smoke e2e-тесты. Для PDF-экспорта на хосте нужен TTF-шрифт с кириллицей (`EXPORT_FONT` или системный DejaVu/Arial); в Docker он ставится через `fonts-dejavu-core`.
