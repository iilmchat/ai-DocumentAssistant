# S4: Backup и Restore

## Backup

- Сервис `backup` (образ `prodrigestivill/postgres-backup-local:16`) делает `pg_dump` каждый день
  в 02:00 UTC и хранит 30 копий в volume `backup_data` (`/backups` внутри контейнера).
- Ручной дамп: `make backup` → файл `/backups/manual_<дата-время>.dump` внутри контейнера.
- Список копий: `docker compose exec backup ls -lh /backups`.
- Для прода обязательна репликация volume `backup_data` во внешнее хранилище (S3 и т.п.) —
  локальный volume не защищает от потери хоста.

## Restore (пошагово)

1. Остановить приложение, чтобы не было записи:
   ```bash
   docker compose stop backend worker ocr-worker beat
   ```
2. Выбрать копию и восстановить:
   ```bash
   docker compose exec backup sh -c \
     "pg_restore -h db -U \${POSTGRES_USER:-postgres} -d \${POSTGRES_DB:-ai_documents} \
      --clean --if-exists /backups/<имя_файла>.dump"
   ```
3. Проверить схему и данные:
   ```bash
   docker compose run --rm backend python scripts/smoke_check.py
   ```
4. Поднять стек обратно:
   ```bash
   docker compose up -d
   curl http://localhost/health/ready
   ```

## Учения по restore (обязательный чек-лист перед релизом)

- [ ] Создан ручной дамп `make backup`.
- [ ] Восстановление выполнено в **отдельный** кластер/БД (не в прод!), покрывая шаги 2–3.
- [ ] `smoke_check.py` прошёл, таблицы и `alembic_version` на месте.
- [ ] Проверена целостность: число документов/чанков совпадает с источником.
- [ ] Время восстановления зафиксировано в отчёте (цель RTO < 30 мин).

> Локальные учения не выполнялись (нет поднятого стека). Чек-лист заполняется на стейдже
> ответственным дежурным; результат прикладывается к релизу.

## Retention (S4)

- Удалённые документы помечаются `deleted_at` и физически очищаются через
  `SOFT_DELETE_GRACE_DAYS` (7 дней) ежедневной задачей `cleanup_retention_task`.
- Версии конспектов: остаётся последняя `SUMMARY_VERSIONS_KEEP` (20) на документ.
- Audit log хранится `RETENTION_DAYS` (365 дней).
- Задача запускается контейнером `beat`; результат виден в логах как `retention.completed`.
