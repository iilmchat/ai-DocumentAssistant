# Спецификация REST API (`/api/v1`)

Базовый префикс всех маршрутов: `/api/v1`. Интерактивная документация Swagger UI доступна по адресу `/docs` на порту бэкенда.

Все эндпоинты `/documents` и `/chat` требуют заголовок `Authorization: Bearer <access_token>`.

## 0. Аутентификация (`/auth`)

### `POST /api/v1/auth/register` / `POST /api/v1/auth/login`
Тело: `{"email": "...", "password": "..."}`. Ответ: `{"access_token": "...", "token_type": "bearer"}`.

### `POST /api/v1/auth/refresh` / `POST /api/v1/auth/logout`
Обновление пары токенов (ротация refresh) и отзыв access-токена через чёрный список Redis.

### `GET /api/v1/auth/me`
Возвращает текущего пользователя (`id`, `email`, `created_at`).

### `GET /api/v1/auth/audit-log?limit=50`
Журнал действий пользователя (вход, загрузка/удаление документа, регенерация/восстановление конспекта).

## 1. Документы (`/documents`)

### `GET /api/v1/documents/`
Пагинированный список документов (новые сверху). Параметры: `limit` (1–100, по умолчанию 20),
`offset`, `status`. Ответ: `{"items": [...], "total": N, "limit": 20, "offset": 0}`.
- **Ответ `200 OK`:**
  ```json
  [
    {
      "id": 1,
      "filename": "contract_2026.pdf",
      "status": "completed",
      "created_at": "2026-11-17T06:30:00Z"
    }
  ]
  ```

### `POST /api/v1/documents/upload`
Загружает новый документ и запускает фоновую задачу индексации.
- **Тело запроса:** `multipart/form-data`, поле `file` (`.pdf`, `.docx`, `.txt`).
- **Ответ `200 OK`:** объект созданного документа со статусом `pending`.

### `GET /api/v1/documents/{document_id}`
Возвращает полную информацию о документе, включая сгенерированный конспект (`summary`).

### `DELETE /api/v1/documents/{document_id}`
Удаляет запись о документе из БД, все его векторные чанки и физический файл из хранилища.

---

## 2. RAG-чат (`/chat`)

### `POST /api/v1/chat/ask`
Выполняет семантический поиск по чанкам документа и генерирует ответ на вопрос.
- **Тело запроса:**
  ```json
  {
    "document_id": 1,
    "question": "Какие сроки оплаты указаны в договоре?"
  }
  ```
- **Ответ `200 OK`:**
  ```json
  {
    "answer": "Согласно пункту 4.2 договора, оплата производится в течение 5 банковских дней...",
    "sources": ["4.2. Заказчик обязуется оплатить услуги в течение 5 (пяти) банковских дней..."],
    "citations": [
      {
        "page_numbers": [3],
        "headings": ["Раздел 4. Порядок расчетов"],
        "snippet": "4.2. Заказчик обязуется оплатить услуги ...",
        "extraction_method": "text_layer"
      }
    ]
  }
  ```

### `POST /api/v1/chat/stream`
То же, что `/ask`, но ответ стримится через SSE: события `citations` (массив цитат), `token` (`{"delta": "..."}`), `done` / `error`.

### `GET /api/v1/documents/{id}/pages`
Постраничный текст с методом извлечения и confidence (используется вкладкой «Страницы» и цитатами).

### `GET /api/v1/auth/usage`
Сводка токенов и оценочной стоимости LLM за текущего пользователя (`requests`, `total_tokens`, `estimated_cost_usd`, `over_budget`, `last`).

### `POST /api/v1/documents/{id}/summarize/stream`
S3: стриминг генерации конспекта. События `token` (`{"delta": "..."}`) и `done`. После завершения
сохраняется новая версия конспекта.
