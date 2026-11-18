# Развертывание и эксплуатация (Deployment)

## Продакшн-сборка через Docker Compose
Для развертывания на VDS/VPS (Ubuntu 22.04/24.04):

1. Установите Docker и плагин Docker Compose.
2. Склонируйте репозиторий и создайте `.env` с боевыми паролями БД и API-ключом.
3. Запустите сборку в фоновом режиме:
   ```bash
   docker compose up --build -d
   ```
4. Настройте автоматический перезапуск контейнеров (`restart: unless-stopped` уже задан в `docker-compose.yml`).

## Резервное копирование данных
Критически важные данные хранятся в двух Docker volumes:
- `postgres_data` — таблицы и векторные индексы.
- `shared_storage` — оригиналы загруженных файлов.

Создание дампа БД:
```bash
docker exec -t ai_postgres pg_dump -U postgres doc_assistant > backup_$(date +%F).sql
```
