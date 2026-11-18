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
**Причина:** Остановлен контейнер `ai_celery_worker` или превышен лимит запросов / закончился баланс API-ключа.
**Решение:**
```bash
docker logs ai_celery_worker
```
