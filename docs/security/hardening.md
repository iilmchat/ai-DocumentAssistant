# T8: безопасность сессии и данных

## Сессия (httpOnly cookie + CSRF)

- `/auth/login`, `/auth/register`, `/auth/refresh` выставляют `access_token` и `refresh_token`
  в **httpOnly/Secure/SameSite** cookie. JS не имеет доступа к токенам.
- Запросы из браузера отправляются с `credentials: 'include'`.
- Для altering-запросов (POST/PUT/PATCH/DELETE) сервер требует заголовок `X-CSRF-Token`,
  равный значению не-httpOnly cookie `csrf_token` (double-submit).
- `GET /auth/csrf` выдаёт свежий CSRF-токен.
- Bearer-токены продолжают работать — для API-клиентов и нагрузочных тестов CSRF не требуется.
- `POST /auth/logout` отзывает jti и очищает cookie.

> Локально с HTTP задайте `SESSION_COOKIE_SECURE=false`.

## PII-redaction

Перед каждым вызовом LLM (`app/services/ai_service.py::_resilient_call`) все строковые
`content` в сообщениях проходят маскировку: email, телефон, банковская карта, ИНН, паспорт
заменяются на `[EMAIL_1]`, `[PHONE_1]` и т.д. Оригинал остаётся в БД и в чанках.
Отключается флагом `PII_REDACTION_ENABLED=false`.

## RBAC

| Роль | Права |
| :--- | :--- |
| viewer | чтение документов, чат, экспорт |
| editor | + загрузка, перевод, регенерация конспекта |
| admin | + удаление документов |

Роль назначается при регистрации (`DEFAULT_USER_ROLE`), миграция `0008`.

## Сканирование

- `.github/workflows/security.yml`: Semgrep SAST (SARIF → GitHub Security) и OWASP ZAP baseline
  по расписанию на staging (`STAGING_URL`).
- `.zap/rules.tsv` — временные исключения для informational-правил.

## Аудит и секреты

- `AUDIT_WEBHOOK_URL` — best-effort отправка событий аудита в SIEM.
- `SECRETS_PROVIDER=vault|aws` — опциональный доступ к секретам; без него используется env.

## Что осталось за рамками

- Pentest и реальные провайдеры секретов (Vault/AWS) — отдельные задачи.
- Хранение PII маской в UI/экспорте (сейчас маскируется только то, что уходит в LLM).
