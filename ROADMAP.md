# Roadmap — следующий горизонт (после S0–S5)

> Обновлено: 2026-11-19. Базовое состояние: спринты **S0–S5 завершены и запушены** (`b10edee`).
> 72 pytest-теста, coverage 61%, RAG-eval 0.983, Alembic-миграции 0001–0005, CI зелёный.
> Идентификаторы вида `T6-03` продолжают нумерацию `TODO.md` (там — архив закрытых спринтов).

## Легенда

| Маркер | Значение |
| :--- | :--- |
| `[x]` | сделано |
| `[ ]` | запланировано |
| `[~]` | в работе |
| `[!]` | блокер / критично |
| `[?]` | требует решения или оценки |
| `P0` | сначала — закрываем в первую очередь |
| `P1` | важно в этом горизонте |
| `P2` | улучшение по возможности |

---

## Сводка: чего не хватает по best industry practices

| Область | Сейчас | Что добавить |
| :--- | :--- | :--- |
| **Перевод документов** | Нет | Двуязычный RAG: оригинал + перевод, глоссарий, экспорт, цитаты на целевом языке |
| RAG-качество | RRF + LLM-reranker, offline-eval 0.983 | Online-оценка, query rewriting, A/B промптов, self-RAG |
| Безопасность | JWT в localStorage (XSS-риск), нет ролей и PII-краснения | httpOnly cookie, RBAC, PII-redaction, SAST/DAST |
| Масштаб | Docker Compose, volume-хранилище, in-memory rate limiter | K8s/Helm, S3, автоподбор воркеров, мультитенантность (кроме демо) |
| Тесты | Unit + smoke e2e, coverage 61% | Реальный e2e-прогон, контрактные и mutation-тесты, coverage 80% |
| Эксплуатация | S3-06/S4-01 не прогонялись | Load-test и restore-учения на стейдже — обязательно |
| Документация | `KNOWN_ISSUES.md` устарел (PyPDF2, «нет OCR») | Обновить под текущее состояние, единый указатель на Runbook |

---

## Этап G — Спринт 6: Двуязычные документы и перевод `[!]`

**Цель:** пользователь загружает документ на одном языке, получает конспект, чат и экспорт на другом — **без потери цитат и структуры**.

**Ключевое решение (моя рекомендация):** переводить **не весь файл простыней**, а по тем же смысловым блокам, что уже использует чанкер (`StructuredBlock`: heading/paragraph/list/table). Таблицы переводятся построчно с сохранением Markdown-разметки; числа, даты, суммы, ИНН и имена proprietary-терминов не трогаются. Оригинал остаётся источником истины, перевод хранится рядом — это позволяет искать по обоим языкам и показывать обе версии в UI.

- `[x] P0` **T6-01** `langdetect` + эвристика; поле `language` в `documents`, язык определяется воркером после извлечения текста. Миграция `0006`.
- `[x] P0` **T6-02** Схема: `content_translated`, `embedding_translated`, `translation_status`, `translation_language` в `document_chunks`; `text_translated` в `document_pages`; таблица `glossaries`.
- `[x] P0` **T6-03** `TranslationService`: перевод по блокам, защита чисел/дат/ИНН через плейсхолдеры, глоссарий, промпты в `core/prompts.py`.
- `[x] P0` **T6-04** Двуязычный поиск: `_vector_search(translated=True)` по `embedding_translated` + RRF с оригинальным и FTS.
- `[x] P1` **T6-05** Очередь `translation` + отдельный воркер в compose, кэш переводов в Redis с версионированием; учёт стоимости через `record_usage(operation="translate")`.
- `[x] P1` **T6-06** API: `POST/GET/DELETE /documents/{id}/translation`, `GET/POST /documents/{id}/glossary`.
- `[x] P1` **T6-07** UI: вкладка «Перевести», выбор языка, прогресс, глоссарий; `PagesViewer` с переключателем оригинал/перевод/оба.
- `[x] P2` **T6-08** Экспорт `?translated=true` в MD/DOCX/PDF с пометкой `[MT]` и переведёнными цитатами.
- `[~] P2` **T6-09** Eval-набор и LLM-as-judge на точность терминов — базовые тесты защитных плейсхолдеров есть (`test_t6_translation.py`), полный eval-набор в T7.

> Риск: юридические и медицинские документы требуют **human-in-the-loop** — пометка «машинный перевод» в UI/экспорте обязательна (P0 в T6-08 поднять при необходимости).

**DoD:** документ на EN даёт RU-конспект, RU-чат с цитатами и RU-экспорт; original доступен переключателем; стоимость перевода видна в `/auth/usage`.

---

## Этап H — Спринт 7: Качество ответов и измеримость

**Цель:** от «работает» к «измеримо улучшается».

- `[~] P0` **T7-01** Скрипты готовы (`ops/scripts/smoke_stage.sh`, `load_test.sh`, `restore_drill.sh`), чек-лист в `docs/operations/stage-runbook.md`; фактический прогон — на стейдже `[?]`
- `[x] P1` **T7-02** Онлайн RAG-оценка (лёгкие эвристики вместо тяжёлого RAGAS): `rag_faithfulness`, `rag_answer_relevance`, `rag_low_quality_total`, алерт `LowRagFaithfulness`
- `[x] P1` **T7-03** Query rewriting через LLM (`rewrite_query`), включается фича-флагом `query_rewriting`, fallback на исходный вопрос
- `[x] P1` **T7-04** Feature flags в Redis (`app/core/flags.py`): `query_rewriting`, `prompt_version`, `reranker`; A/B-прогон на реальных запросах — следующий шаг
- `[x] P2` **T7-05** Context compression (`build_context`) — обрезка длинных чанков, меньше токенов; self-RAG отложен до реальных замеров
- `[~] P2` **T7-06** A/B-тест HNSW `ef_search` — зависит от фактического load-test (T7-01)

**DoD:** есть дашборд с качеством ответов и ценой запроса; каждый change промпта подтверждён метрикой.

---

## Этап I — Спринт 8: Безопасность и соответствие

**Цель:** закрыть XSS-риск и подготовиться к corp-эксплуатации.

- `[x] P0` **T8-01** JWT в httpOnly/Secure/SameSite cookie + CSRF double-submit (`X-CSRF-Token`); Bearer оставлен для API-клиентов; фронт больше не пишет токены в localStorage
- `[x] P0` **T8-02** PII-redaction централизованно в `_resilient_call`: email/телефон/карта/ИНН/паспорт → плейсхолдеры
- `[x] P1` **T8-03** RBAC (`viewer`/`editor`/`admin`), миграция `0008`; мутирующие эндпоинты требуют editor, удаление — admin
- `[x] P1` **T8-04** SAST Semgrep + DAST OWASP ZAP baseline в отдельном workflow `security.yml` (pentest — отдельно)
- `[x] P2` **T8-05** Audit log → SIEM webhook (`AUDIT_WEBHOOK_URL`, best-effort)
- `[x] P2` **T8-06** Абстракция secrets manager (`SECRETS_PROVIDER=vault|aws`), env fallback

> Оговорка: cookie `Secure=true` по умолчанию — для локального HTTP нужно `SESSION_COOKIE_SECURE=false`. Pentest и реальный Vault — отдельные задачи `[?]`.

**DoD:** нет токенов в JS-доступном хранилище; PII не уходит в LLM; отчёт сканеров зелёный.

---

## Этап J — Спринт 9: Масштаб и данные

**Цель:** выйти за пределы одного Docker-хоста.

- `[x] P0` **T9-01** Абстракция `StorageBackend` (local/S3-MinIO), `STORAGE_BACKEND`, MinIO в compose; S3 нужен boto3
- `[x] P1` **T9-02** Helm-чарт в `deploy/helm` с HPA по `celery_queue_length`; Redis-backed rate limiter (`RATE_LIMIT_REDIS`)
- `[~] P1` **T9-03** Партиционирование `token_usages`/`audit_logs` и read replica — depends on реального объёма/стейджа `[?]`
- `[x] P1` **T9-04** Модель `Organization`, поле `org_id`, миграция `0009`, API `/organizations`, tenant-квоты, UI-блок/org API
- `[x] P2` **T9-05** Парсеры XLSX/PPTX/EML и аудио через Whisper, MIME-детекция, новые форматы в UI upload
- `[x] P2` **T9-06** Инкрементальная индексация: `content_hash` (миграция `0010`), переэмбеддим только изменившиеся чанки

**DoD:** стек поднимается в K8s, файлы в S3, воркеры масштабируются по очереди.

---

## Этап K — Спринт 10: Зрелость разработки и документация

**Цель:** снизить стоимость поддержки и сделать релизы рутинными.

- `[~] P1` **T10-01** Playwright e2e: локатор исправлен (`exact: true`) после красного CI; CI-прогон на стейдже — отдельно `[?]`
- `[x] P1` **T10-02** Property-based (`hypothesis`, 4 теста) и контрактные (`schemathesis`, OpenAPI-схема + invalid-input) тесты
- `[x] P2` **T10-03** `mutmut` в dev-зависимостях; запуск на критичных модулях — ручной (медленный)
- `[x] P2` **T10-04** Coverage поднят с 61% до **80.07%**, порог в `pytest.ini` = 80; worker 94%, cache/document_translation/retention/usage 100%
- `[x] P2` **T10-05** `KNOWN_ISSUES.md` обновлён, README ссылается на Roadmap
- `[x] P2` **T10-06** ARIA role/tablist/aria-pressed, keyboard-only навигация, focus-visible, RU/EN i18n; полный WCAG-аудит — отдельно
- `[x] P2` **T10-07** Release checklist `docs/operations/release-checklist.md` + rollback-процедура

**DoD:** `KNOWN_ISSUES.md` актуален, e2e зелёный в CI, покрытие 80%, релиз по чек-листу.

---

## Приоритетная шпаргалка

1. **T6-01…T6-09** — перевод документов (главный запрос).
2. **T7-01** — закрыть load-test и restore-учения (блокеры прода).
3. **T8-01…T8-02** — httpOnly cookie и PII-redaction (безопасность).
4. **T7-02…T7-04** — измеримость качества.
5. **T9-01…T9-02** — S3 + K8s при росте нагрузки.

## Зависимости и риски

| Задача | Зависимость |
| :--- | :--- |
| T6-04 (двуязычный поиск) | T6-01/T6-02 (схема), T6-03 (перевод) |
| T6-05 (очередь перевода) | T6-03, бюджет/учёт из S5 |
| T7-02 (online eval) | T8-02 (PII не должен попадать в логи оценщика) |
| T9-04 (мультитенантность) | T8-03 (RBAC) |
| T9-05 (аудио) | T9-01 (S3 для больших файлов) |

> Главный риск перевода — **стоимость**: перевод длинного PDF через LLM может съесть месячный бюджет (S5). Поэтому T6-05 с кэшем и лимитом — не P2, а обязательная часть эпика.

## Легенда обновления статусов

При закрытии: `[ ]` → `[x]`, в коммит — `ref T6-03`, при снятии вопроса — убрать `[?]`.
