# TODO — Best Practices Backlog (AI Document Assistant)

> Обновлено: 2026-11-18. Базовое состояние: Roadmap 1–8 закрыт, hardening-спринт выполнен
> (Alembic, CORS, секреты, валидация эмбеддингов), 20 pytest-тестов, CI pytest + build + e2e.

## Обозначения

| Маркер | Значение |
| :--- | :--- |
| `[x]` | сделано |
| `[ ]` | запланировано |
| `[~]` | в работе |
| `[!]` | критично / блокер |
| `[?]` | требует решения или оценки |
| `P0` | сделать в первую очередь |
| `P1` | важно в ближайшем цикле |
| `P2` | улучшение, когда дойдёт очередь |

Идентификатор вида `S2-03` = Sprint 2, задача 3. Это позволяет ссылаться на пункты в коммитах и PR.

---

## Что не хватает по best industry practices (сводка)

| Область | Текущее состояние | Пробел |
| :--- | :--- | :--- |
| Качество кода | Нет ruff/mypy/ESLint, нет единого форматтера | Нет автоматических gates в CI, нет pre-commit |
| Типизация | Python без аннотаций в части сервисов; TS strict включён | Нет mypy, нет проверки на `Any` |
| Тесты | 20 unit + 2 smoke e2e | Нет интеграционных тестов с БД, API-тестов с JWT, порога coverage, нагрузочных тестов |
| Безопасность | JWT в localStorage, пароли bcrypt, CORS явный | Нет refresh/revocation, rate limit, сканирования секретов и зависимостей, non-root образов |
| Логирование | `print()` в воркере и сервисах | Нет структурированных JSON-логов, корреляционных ID, уровней и централизованного сбора логов |
| Наблюдаемость | `/health` есть, но compose его не использует | Нет метрик, трейсинга, алертов, Celery-мониторинга, readiness/liveness разделения |
| Надёжность | Celery retry 2, простая SSE | Нет DLQ, heartbeat/таймаута SSE, идемпотентных ключей на API, circuit breaker для LLM |
| Производительность | Точный поиск `<=>` без ANN-индекса | Нет HNSW/IVFFlat, пагинации, кэша эмбеддингов, PgBouncer, load-тестов |
| Данные | Alembic-миграции есть | Нет автоматических backup/restore, retention policy, audit log |
| Процессы | README, docs/, CHANGELOG есть | Нет LICENSE, CONTRIBUTING, Dependabot, staging-окружения, автоматизации релизов |
| UX/доступность | Базовый Tailwind UI | Нет error boundary, i18n, a11y-аудита, виртуализации списков |
| AI-пайплайн | RRF гибридный поиск | Нет настоящего реранкера, версионирования промптов, учёта токенов/стоимости, экспорта с цитатами |

---

## Этап A — Спринт 0: Фундамент качества (1 неделя)

**Цель:** сделать качество кода проверяемым автоматически, до появления новых фич.

- `[x] P0` **S0-01** Alembic-миграции и автоприменение в Docker — *готово*
- `[x] P0` **S0-02** Явный CORS и вынесение секретов в env — *готово*
- `[x] P1` **S0-03** Валидация размерности эмбеддингов — *готово*
- `[x] P0` **S0-04** Ruff (lint + format), `ruff.toml`, проверка в CI и `make check`
- `[x] P0` **S0-05** Mypy + SQLAlchemy plugin-конфиг; точечные исключения для старых `Column[...]`-моделей
- `[x] P0` **S0-06** ESLint + Prettier на фронте, `npm run lint` в CI (Vite 8 / Tailwind 4 миграция)
- `[x] P1` **S0-07** `.pre-commit-config.yaml` (whitespace, yaml, ruff, mypy, gitleaks) + gitleaks-action в CI
- `[x] P1` **S0-08** Порог покрытия 60% в `pytest.ini` (сейчас 62%; поднять до 80 после интеграционных тестов)
- `[x] P1` **S0-09** CI: `pip-audit` и `npm audit --omit=dev --audit-level=high` обязательны
- `[x] P2` **S0-10** `AppError`/`NotFoundError` + единый формат `{"detail", "code"}` и обработчик 422

**Definition of Done:** CI красный при любом линтер/type/audit/coverage нарушении; `make check` локально запускает всё то же. ✅

> Примечание к S0-09: `npm audit` в CI проверяет **production-зависимости** (`--omit=dev`) — 0 уязвимостей.
> В реестре на текущую дату dev-инструменты (vite/tailwind/typescript-eslint) помечены как уязвимые без
> безопасных апгрейдов (fix = downgrade), поэтому они вынесены за рамки gate и остаются под наблюдением.

---

## Этап B — Спринт 1: Безопасность (1–2 недели)

**Цель:** закрыть пробелы в защите до выхода в прод.

- `[x] P0` **S1-01** Rate limiting (slowapi): login/register/refresh + chat, 429 с кодом `rate_limited`
- `[x] P0` **S1-02** Access 15 мин + refresh 30 дней с ротацией, чёрный список jti в Redis, endpoint logout; фронт обновляет токен при 401
- `[x] P0` **S1-03** `USER appuser` (uid 10001) в backend и OCR-образе
- `[x] P0` **S1-04** Gitleaks в pre-commit и CI (сделано в S0)
- `[x] P1` **S1-05** Dependabot для pip/npm/docker/github-actions
- `[x] P1` **S1-06** Trivy filesystem scan (HIGH/CRITICAL) в CI
- `[x] P1` **S1-07** `MAX_IMAGE_PIXELS` + `MAX_IMAGE_SIDE_PX`, проверка через Pillow `verify()`
- `[x] P1` **S1-08** Квота 100 документов / 2 ГБ на пользователя
- `[x] P2` **S1-09** Audit log (таблица `audit_logs`, эндпоинт `/auth/audit-log`)
- `[~] P2` **S1-10** Блокировка после 5 неудачных логинов сделана; verify email / password reset отложены (нужен SMTP) `[?]`

**Definition of Done:** threat model — `docs/security/threat-model.md`; все P0 закрыты, сканеры зелёные. ✅

> Остаток S1-10 и перевод токенов в httpOnly cookie перенесены в следующий цикл (нужна SMTP/инфраструктура и смена frontend-архитектуры).

---

## Этап C — Спринт 2: Надёжность и наблюдаемость (1–2 недели)

**Цель:** понимать, что происходит в проде, и корректно деградировать.

- `[x] P0` **S2-01** JSON-логи через `structlog`, все `print()` заменены на `log.*`
- `[x] P0` **S2-02** `X-Request-ID` middleware → contextvars → Celery (`request_id` в задаче) → логи
- `[x] P0` **S2-03** `/health/live` + `/health/ready` (БД/Redis + gauge по статусам), healthcheck в compose
- `[x] P1` **S2-04** Prometheus `/metrics`: HTTP, LLM (calls/tokens/latency), OCR, Celery, RAG, документы по статусам
- `[x] P1` **S2-05** Flower в compose + алерт `CeleryQueueGrowing`
- `[x] P1` **S2-06** SSE heartbeat каждые 15 c, таймауты 30 мин/5 мин, `request.is_disconnected()`
- `[x] P1` **S2-07** DLQ: `dead_letter_task`, очередь `dlq`, ретраи исчерпаны → лог `task.dead_letter`
- `[x] P1` **S2-08** `tenacity` backoff + timeout 30 c + circuit breaker для LLM/embeddings
- `[x] P2` **S2-09** Prometheus + Grafana (дашборд `ops/grafana/dashboards`) и 4 алерта
- `[x] P2` **S2-10** SLO/error budget и runbook — `docs/operations/runbook.md`

**Definition of Done:** дашборд показывает документы по статусам, очередь и причины падения; есть алерты и runbook. ✅

---

## Этап D — Спринт 3: Производительность и масштаб (2 недели)

**Цель:** выдержать рост числа документов без линейной деградации поиска.

- `[x] P0` **S3-01** HNSW-индекс (миграция `0003`), `hnsw.ef_search`, метрика `vector_search_duration_seconds`; замер точности — в load-test report
- `[x] P0` **S3-02** Пагинация `limit`/`offset` + фильтр `status`, конверт `{items,total,limit,offset}`, фронт обновлён
- `[x] P1` **S3-03** Redis-кэш эмбеддингов с версионированием, инвалидация после реиндексации
- `[x] P1` **S3-04** Пул SQLAlchemy (`pool_size`/`max_overflow`/`pre_ping`), PgBouncer в compose (`DB_HOST=pgbouncer DB_PORT=6432`)
- `[x] P1` **S3-05** Per-loop `asyncio.Semaphore` для LLM-запросов (`LLM_MAX_CONCURRENCY`) + backoff из S2
- `[~] P1` **S3-06** Locust-сценарий и методология готовы (`tests/load/locustfile.py`, `docs/operations/load-test.md`); прогон на стейдже не выполнялся `[?]`
- `[x] P2` **S3-07** Мемоитация структурно одинаковых страниц в `extract_pages`
- `[x] P2` **S3-08** Стриминг генерации конспекта `POST /summarize/stream` + предпросмотр на фронте

**Definition of Done:** p95 поиска < 300 мс при 10k чанков — TARGET, фактический замер на стейдже ожидается; методология и отчёт-шаблон в `docs/operations/load-test.md`.

---

## Этап E — Спринт 4: Эксплуатация и данные (1 неделя)

**Цель:** безопасно обновляться и восстанавливаться.

- `[~] P0` **S4-01** Backup: сервис `pg_dump` по расписанию + volume, `make backup`, инструкция `docs/operations/backup-restore.md`; учения по restore — чек-лист заполняется на стейдже `[?]`
- `[x] P0` **S4-02** Retention: `deleted_at` + grace 7 дней, очистка версий (последние 20) и аудита (365 дней), задача `cleanup_retention_task` + beat
- `[x] P1` **S4-03** Data-migration в `0004` (нормализация статусов) и smoke-check схемы при старте (`scripts/smoke_check.py`, `make smoke`)
- `[x] P1` **S4-04** `docker-compose.staging.yml`, цели `make staging-up/down`, обновлён deployment guide
- `[x] P1` **S4-05** `LICENSE`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, шаблоны issue/PR
- `[x] P2` **S4-06** `release-please` workflow, `backend/__version__.py`, версия в FastAPI
- `[x] P2` **S4-07** Обновлены `rag-pipeline.md`, deployment/troubleshooting, добавлены backup-restore.md и load-test.md

**Definition of Done:** инструкции и автоматизация готовы; фактические учения по restore — на стейдже (локально нет стека). `CONTRIBUTING.md` покрывает подъём проекта с нуля.

---

## Этап F — Спринт 5: Функциональные улучшения (по приоритету продукта)

**Цель:** качество ответов и UX, когда фундамент устойчив.

- `[x] P1` **S5-01** LLM-as-judge reranker (`RERANK_TOP_K` кандидатов → топ-K), метрика `rerank_duration_seconds`, fallback при ошибке
- `[x] P1` **S5-02** Офлайн-оценка RAG: `eval/questions.json`, метрики recall/faithfulness/citations, `python -m eval.rag_eval --offline` в CI (сейчас 0.983)
- `[x] P1` **S5-03** Реестр промптов `app/core/prompts.py` с версией `PROMPT_VERSION`, хардкод убран из chat/ai_service
- `[x] P1` **S5-04** Таблица `token_usages` (миграция `0005`), эндпоинт `/auth/usage`, метрика `llm_cost_usd_total`, бюджет в конфиге
- `[x] P2` **S5-05** Экспорт MD/DOCX/PDF с приложением «Источники по страницам»
- `[~] P2` **S5-06** Error Boundary, i18n RU/EN, ARIA/клавиатура, пагинация списка (виртуализация не потребовалась при limit≤100)
- `[x] P2` **S5-07** Движки PaddleOCR/Surya в фабрике, автодетект языка `OCR_LANGUAGES=auto`; тяжёлые пакеты опциональны
- `[x] P2` **S5-08** Вкладка «Страницы» с предпросмотром; клик по цитате открывает нужную страницу
- `[x] P2` **S5-09** PWA manifest + service worker (offline shell), черновики вопросов в localStorage

---

## Приоритетная шпаргалка (если времени совсем мало)

1. `S0-04…S0-09` — линтеры, типы, coverage, аудит зависимостей ← **начать здесь**
2. `S1-01…S1-04` — rate limit, JWT refresh, non-root, секрет-сканер
3. `S2-01…S2-03` — логи, correlation ID, health-пробы
4. `S3-01…S3-02` — HNSW + пагинация
5. `S4-01…S4-02` — backup и retention

## Легенда обновления статусов

При закрытии задачи: заменить `[ ]` на `[x]`, добавить в коммит идентификатор (`ref S0-04`), при необходимости снять маркер `[!]`/`[?]`.
