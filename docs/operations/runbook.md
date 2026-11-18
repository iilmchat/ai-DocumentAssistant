# S2: SLO и Runbook (наблюдаемость)

## SLO

| Сервис | SLO | Окно |
| :--- | :--- | :--- |
| API доступность (`/health/live`) | 99.5% | 30 дней |
| API p95 latency (экран документа/чат) | < 500 мс | 30 дней |
| Доля 5xx | < 0.5% | 30 дней |
| Обработка документа до `completed` | < 10 мин (типичный PDF) | 30 дней |

Error budget: ~3.6 ч простоев в месяц. При исчерпании — freeze фич, фокус на надёжности.

## Точки входа

| Что | Где |
| :--- | :--- |
| Дашборд | Grafana `http://localhost:3000` (логин `admin`, пароль `GRAFANA_PASSWORD`) |
| Метрики/алерты | Prometheus `http://localhost:9090` (вкладка Alerts) |
| Задачи Celery | Flower `http://localhost:5555` |
| Логи | JSON-строки stdout контейнеров; поле `request_id` связывает API и воркер |
| Health | `/health/live` (процесс жив), `/health/ready` (БД + Redis) |

## Симптом → действие

### Документ «застрял» в `processing`/`embedding`
1. Grafana → панель **Documents by status**: убедиться, что статус держится > 15 мин.
2. Найти `request_id` загрузки в логах backend (`docker logs ai_backend | grep <filename>`).
3. По `request_id` или `document_id` найти запись в логах воркера:
   `docker logs ai_celery_worker 2>&1 | grep <document_id>`.
4. Проверить Flower: задача в `default`/`ocr`, число ретраев, traceback.
5. Если ретраи исчерпаны — задача попала в `dlq`; лог `task.dead_letter` содержит причину.
6. После устранения причины повторить задачу вручную из Flower или перезагрузить документ
   (идемпотентность по SHA-256 не даст дубликата).

### Рост 5xx
1. Панель **5xx errors / sec** и **HTTP p95 latency**.
2. Проверить `High5xxRate` в Prometheus.
3. Проверить `/health/ready` — доступны ли БД и Redis.
4. Проверить circuit breaker: метрика `llm_calls_total{status="circuit_open"}`; если растёт —
   проблема у LLM-провайдера, бэкофф 60 c откроет цепь повторно.

### Очередь Celery растёт
1. Панель **Celery queue length**, алерт `CeleryQueueGrowing`.
2. Проверить, жив ли `ai_celery_worker` / `ai_ocr_worker` (ocr-задачи идут отдельной очередью).
3. Проверить memory limit OCR-воркера (2g) — большие сканы могут убивать процесс.

### SSE-поток обрывается
Heartbeat (`: heartbeat`) отправляется каждые 15 c; таймаут — 30 мин для прогресса и 5 мин для
чата. Если клиент видит обрыв чаще — проверить Nginx `proxy_read_timeout` и логи `http.request`.

## Полезные запросы PromQL

```promql
# застрявшие документы
documents_by_status{status=~"processing|embedding"}

# доля ошибок за 5 минут
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))

# неудачные задачи по типу
sum by (task) (rate(celery_tasks_total{status="failed"}[15m]))
```
