# T10: Release checklist

## Перед релизом

- [ ] `make check` зелёный (ruff, mypy, pytest ≥70%, pip-audit, ESLint/Prettier, build, npm audit)
- [ ] `python -m eval.rag_eval --offline` ≥ 0.7
- [ ] `docker compose config` и `alembic history` без ошибок
- [ ] Миграции применены на стейдже, `smoke_check.py` прошёл
- [ ] `./ops/scripts/smoke_stage.sh` зелёный
- [ ] E2E (Playwright) зелёный в CI
- [ ] Semgrep/Trivy без HIGH/CRITICAL
- [ ] Секреты не в git (gitleaks), `.env` не отслеживается
- [ ] Изменения API отражены в `docs/openapi/endpoints.md`
- [ ] CHANGELOG обновлён (release-please создаст PR автоматически)

## Деплой

1. Тег версии создаётся release-please (`backend/__version__.py`).
2. Staging: `make staging-up` → smoke → e2e → load-test (T7-01).
3. Prod: `helm upgrade --install ai-doc ./deploy/helm --set image.tag=<tag>`.
4. Проверка: `/health/ready` = 200, дашборд Grafana показывает метрики.

## Откат

- `helm rollback ai-doc <revision>` или `docker compose up -d --force-recreate` на предыдущем теге.
- При проблемах с БД — restore по `docs/operations/backup-restore.md` во временную БД сначала.

## После релиза

- [ ] Метрики 24ч: 5xx < 0.5%, p95 < 500 мс, алерты не горят
- [ ] `/auth/usage`: стоимость в рамках `LLM_MONTHLY_BUDGET_USD`
- [ ] Отчёты load-test и restore добавлены в `docs/operations/reports/`
