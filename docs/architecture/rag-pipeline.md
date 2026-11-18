# RAG-пайплайн (актуальное состояние)

## Этап 1: Индексация

1. **Загрузка.** `POST /api/v1/documents/upload`: MIME определяется по magic bytes, проверяется
   размер, ZIP-бомбы и лимиты изображений; дубликаты отсекаются по SHA-256.
2. **Маршрутизация.** PDF и изображения → очередь `ocr` (отдельный воркер), TXT/DOCX → `default`.
3. **Извлечение.** PyMuPDF: текстовый слой или OCR (Tesseract / vision-модель) для страниц-сканов.
   Результат — `document_pages` с `extraction_method` и `confidence`; колонтитулы дедуплицируются,
   структурно одинаковые страницы мемоизируются (S3).
4. **Чанкинг.** По заголовкам/абзацам/таблицам, таблицы не разрываются; каждый чанк несёт
   `page_numbers`, `headings`, `extraction_method`.
5. **Эмбеддинги.** OpenAI-совместимый провайдер, фиксированная размерность `EMBEDDING_DIM`;
   кэш в Redis с инвалидацией после реиндексации (S3).
6. **Конспект.** Map/Reduce суммаризация; доступна потоковая генерация `POST /summarize/stream`.

## Этап 2: Поиск и генерация

1. Вопрос → эмбеддинг (с кэшем).
2. **Гибридный поиск**: pgvector HNSW (косинус, `hnsw.ef_search`) + PostgreSQL FTS
   (`websearch_to_tsquery('russian')`), результаты объединяются Reciprocal Rank Fusion.
3. Топ-K чанков попадают в промпт с метками `[стр. N]`; модель обязана цитировать страницы.
4. Ответ отдаётся синхронно (`/chat/ask`) или потоково (`/chat/stream`, SSE: citations → token → done).
5. Метрики: `vector_search_duration_seconds`, `rag_queries_total`, `llm_*` (Grafana-дашборд S2).

## Надёжность (S2/S3)

- LLM-вызовы: timeout 30 c, exponential backoff, circuit breaker, semaphore на конкуренцию.
- Celery: ретраи, DLQ после исчерпания, таймауты, structured логи с `request_id`.
- SSE: heartbeat каждые 15 c и таймауты.

## Устаревшие упоминания

Раньше в документации фигурировали `PyPDF2` и `Vector(1536)` / `text-embedding-3-small`.
Сейчас используются `pypdf`/PyMuPDF и `EMBEDDING_DIM` из конфигурации
(768 для Gemini `text-embedding-004`, 1024 для `text-embedding-3-large`).
