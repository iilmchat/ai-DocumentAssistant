# T7-01: стейдж-прогон и учения (запускается на хосте с Docker)

## 1. Подъём стейджа

```bash
make staging-up
./ops/scripts/smoke_stage.sh
# API: http://localhost:8080/docs, UI: http://localhost:8081
```

## 2. Нагрузочный тест Locust

Нужен загруженный документ и access-токен:

```bash
export LOAD_ACCESS_TOKEN=<токен из /api/v1/auth/login>
export LOAD_DOCUMENT_ID=<uuid документа>
HOST=http://localhost:8080 USERS=100 SPAWN_RATE=10 RUN_TIME=10m ./ops/scripts/load_test.sh
```

Headless-прогон пишет `docs/operations/reports/load-report.html` и CSV.
Цель SLO: p95 vector-поиска < 300 мс при 10k чанков, 5xx < 0.5%.

## 3. Учения по restore

```bash
BACKUP=$(docker compose exec -T backup ls -1 /backups | grep -E '\.dump$' | tail -1 | tr -d '\r')
./ops/scripts/restore_drill.sh "$BACKUP"
```

Скрипт восстанавливает дамп во **временную БД**, запускает `smoke_check.py`, сравнивает
число документов/чанков и удаляет временную БД. Прод не трогается.

## 4. Чек-лист перед релизом

- [ ] `smoke_stage.sh` зелёный
- [ ] Load-test: p95 < 300 мс, 5xx < 0.5%, отчёт приложен
- [ ] Restore drill: `RESTORE DRILL OK`, RTO зафиксирован (цель < 30 мин)
- [ ] Grafana: дашборд показывает метрики, алерты не горят

## Статус выполнения

| Шаг | Дата | Результат | Ответственный |
| :--- | :--- | :--- | :--- |
| Load-test | — | не прогонялось (нет стейджа) | — |
| Restore drill | — | не прогонялось (нет стейджа) | — |

> Заполняется при реальном прогоне. Скрипты подготовлены и готовы к запуску.
