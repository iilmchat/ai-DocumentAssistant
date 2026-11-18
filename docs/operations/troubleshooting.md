# Устранение неполадок (Troubleshooting)

## 1. Ошибка `502 Bad Gateway` при обращении к `/api/v1/...`
**Причина:** Контейнер `ai_frontend` (Nginx) запущен, но `ai_backend` упал или находится в цикле перезагрузки.
**Решение:**
1. Проверьте логи бэкенда:
   ```bash
   docker logs ai_backend
   ```
2. Наиболее частая причина — отсутствие или невалидный `OPENAI_API_KEY` в `.env`, либо недоступность БД при старте. Исправьте `.env` и перезапустите сервис:
   ```bash
   docker compose up -d --force-recreate backend worker
   ```

## 2. Ошибка `Bind for 0.0.0.0:6379 failed: port is already allocated`
**Причина:** На хост-машине уже запущен другой экземпляр Redis на порту `6379`.
**Решение:** В `docker-compose.yml` измените маппинг портов для сервиса `redis` на `"6380:6379"`.

## 3. Документ зависает в статусе `pending` или `processing`
**Причина:** Остановлен контейнер `ai_celery_worker` / `ai_ocr_worker`, превышен лимит запросов
или закончился баланс API-ключа.
**Решение:**
```bash
docker logs ai_celery_worker
docker logs ai_ocr_worker
```
Подробный разбор — в [runbook.md](./runbook.md) (поиск по `request_id`, DLQ, метрики).

## 4. Backend не стартует: smoke check failed
**Причина:** миграции не применены либо БД создана со старой схемой.
**Решение:**
```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python scripts/smoke_check.py
```
Для старого volume со схемой от `create_all` выполните `alembic stamp head` перед первой миграцией.

## 5. Retention не чистит данные
Проверьте, что запущен `ai_celery_beat` и в логах есть `retention.completed`. Задача
`cleanup_retention_task` видна в Flower. Параметры — `SOFT_DELETE_GRACE_DAYS`,
`SUMMARY_VERSIONS_KEEP`, `RETENTION_DAYS`.

## 6. Grafana/Prometheus пустые
Убедитесь, что backend отдаёт `/metrics`, а prometheus scraping-конфиг смонтирован:
```bash
curl http://localhost:8000/metrics | head
docker logs ai_prometheus
```
