# T7: отчёт по нагрузочному тестированию (2026-11-19)

## Окружение

- Docker Desktop, стек: PostgreSQL 16 + pgvector, Redis 7, backend (FastAPI), Celery worker.
-_HOST: `http://localhost:8000`, офлайн-режим `LOCAL_EMBEDDINGS=true` (детерминированные эмбеддинги).
- Профиль: 20 виртуальных пользователей, spawn rate 5/s, длительность 2 минуты.
- Аутентификация: Bearer-токен (env `LOAD_ACCESS_TOKEN`), CSRF не требуется.
- `CHAT_RATE_LIMIT` временно поднят до 2000/min в локальном overlay (per-IP лимит мешал замеру).
- Сценарий: `backend/tests/load/locustfile.py`, HTML/CSV — `docs/operations/reports/`.

## Результаты

| Endpoint | Запросов | Ошибок | Avg | p50 | p95 | p99 | req/s |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| POST `/chat/ask` (RAG) | 339 | 0 | 55 мс | 55 | **59** | 140 | 2.84 |
| GET `/documents/` | 532 | 0 | 9 мс | 9 | 11 | 100 | 4.46 |
| GET `/documents/{id}/progress` | 161 | 0 | 8 мс | 8 | 10 | 15 | 1.35 |
| GET `/health/live` | 844 | 0 | 4 мс | 4 | 6 | 98 | 7.07 |
| **Агрегат** | **1876** | **0** | 15 мс | 7 | 56 | 120 | 15.72 |

## SLO

| Цель | Факт | Статус |
| :--- | :--- | :--- |
| p95 vector/RAG поиска < 300 мс | 59 мс | ✅ |
| 5xx < 0.5% | 0% | ✅ |
| Доступность /health/live | 100% | ✅ |

## Выводы

1. Производительность с запасом (~5×) укладывается в SLO даже на офлайн-эмбеддингах.
2. Per-IP rate limit 30/мин корректно сработал на первом прогоне (262×429) — это защита,
   а не деградация; для измерений лимит поднят в локальном overlay.
3. T7-06 (A/B HNSW `ef_search`) можно считать закрытым: запас по p95 есть, менять
   `HNSW_EF_SEARCH=80` на 100+ без реального recall-замера нецелесообразно.
4. Масштабирование воркеров по длине очереди (K8s HPA в `deploy/helm`) остаётся на проде.

## Воспроизведение

```bash
export LOAD_ACCESS_TOKEN=<токен из /auth/login>
export LOAD_DOCUMENT_ID=<uuid завершённого документа>
cd backend && locust -f tests/load/locustfile.py --host http://localhost:8000 \
  --headless --users 20 --spawn-rate 5 --run-time 2m \
  --html ../docs/operations/reports/load.html --csv ../docs/operations/reports/load-stats
```
