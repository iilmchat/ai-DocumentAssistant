# T9: масштабирование

## Хранилище

`STORAGE_BACKEND=local` (по умолчанию) или `s3`. При `s3` файлы уходят в MinIO/AWS
(`S3_ENDPOINT_URL`, `S3_BUCKET`, ключи). MinIO поднимается в compose на `127.0.0.1:9000`,
консоль — `:9001`. Локальная копия остаётся для OCR-воркера.

## K8s / Helm

```bash
helm upgrade --install ai-doc ./deploy/helm \
  --set image.tag=<tag> \
  --set storage.backend=s3 \
  --set autoscaling.enabled=true
```

- Отдельные Deployments: backend, default-worker, ocr-worker, translation-worker.
- HPA масштабирует default-worker по кастомной метрике `celery_queue_length` (цель 20/под).
- Readiness/liveness через `/health/ready` и `/health/live`.
- Секреты — через `ai-document-assistant-secrets` (Sealed Secrets / Vault).

## Rate limiting

`RATE_LIMIT_REDIS=true` переключает slowapi на общий Redis storage — лимиты действуют
одинаково для всех реплик backend (in-memory считал бы каждую отдельно).

## Мультитенантность

- `Organization` + `users.org_id`; участники одной организации видят общие квоты.
- `POST /organizations` создаёт tenant и привязывает текущего пользователя.
- `GET /organizations/me` — документы и объём хранилища организации.
- `POST /organizations/{id}/members/{user_id}` — добавить участника (admin).
- `MULTITENANT_ENABLED=false` отключает API (для одиночных установок).

## Новые форматы

XLSX, PPTX, EML парсятся в общий текстовый пайплайн; MP3/WAV/M4A/OGG уходят в
Whisper (`transcribe_audio`). Все они проходят обычные чанкинг и эмбеддинги.

## Инкрементальная индексация

Каждый чанк хранит `content_hash` (SHA-256 текста). При повторной обработке воркер
передаёт старые хеши в `_embed_and_store_chunks` и вызыва LLM только для изменившихся
чанков — экономит время и стоимость при правках документа.

## Что осталось `[?]`

- Партиционирование таблиц по месяцам и read replica — включать при реальном объёме.
- Реальный Helm-прогон и замер HPA — на стейдже.
