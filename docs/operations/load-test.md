# S3: нагрузочное тестирование и отчёт

## Цель

Подтвердить SLO: **p95 vector-поиска < 300 мс при 10 000 чанков** и корректную работу при
100 одновременных загрузках / 50 RAG-запросах в секунду.

## Инструмент

Locust (в `backend/requirements-dev.txt`), сценарий — `backend/tests/load/locustfile.py`.

```bash
# на стейдже с поднятым стеком
export LOAD_ACCESS_TOKEN=<access_token>
export LOAD_DOCUMENT_ID=<uuid документа>
make load-test
# открыть http://localhost:8089, выставить 100 пользователей, spawn rate 10/s, длительность 10 мин
```

Метрики во время прогона: Grafana (HTTP p95, 5xx, LLM tokens), `vector_search_duration_seconds`,
`celery_queue_length`, `documents_by_status`.

## Результаты

> Локальный прогон не выполнялся: нет поднятого стека PostgreSQL/pgvector и LLM-провайдера.
> Таблица заполняется по результатам прогона на стейдже — это обязательный шаг перед релизом.

| Сценарий | Целевой RPS | Факт RPS | p95 latency | Ошибки | Статус |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/health/live` | 200 | — | — | — | не прогонялось |
| `/documents/?limit=20` | 100 | — | — | — | не прогонялось |
| `/chat/ask` (50 RPS) | 50 | — | — | — | не прогонялось |
| Vector search (10k чанков) | — | — | < 300 мс | — | не прогонялось |
| 100 одновременных загрузок | — | — | — | — | не прогонялось |

## Что делать при провале

1. p95 поиска > 300 мс → увеличить `HNSW_EF_SEARCH` (80 → 120) и проверить, что индекс
   `ix_document_chunks_embedding_hnsw` создан (миграция `0003`).
2. Рост 5xx при нагрузке → проверить пул (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`) и PgBouncer.
3. Рост LLМ-latency → снизить `LLM_MAX_CONCURRENCY` или увеличить лимиты провайдера;
   circuit breaker и метрика `llm_calls_total{status="circuit_open"}` покажут причину.
4. Очередь растёт → проверить воркеры и memory limit OCR-воркера.
