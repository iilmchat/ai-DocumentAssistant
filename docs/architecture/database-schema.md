# Схема базы данных

Схема управляется Alembic (`backend/alembic/versions/0001_initial.py`). Postgres + расширение `vector`.

## `users` — Этап 4
| Поле | Тип | Описание |
| :--- | :--- | :--- |
| `id` | `UUID` (PK) | Идентификатор пользователя |
| `email` | `VARCHAR(255)` UNIQUE | Логин |
| `password_hash` | `VARCHAR(255)` | bcrypt-хеш пароля |
| `created_at` | `TIMESTAMPTZ` | Дата регистрации |

## `documents`
| Поле | Тип | Описание |
| :--- | :--- | :--- |
| `id` | `UUID` (PK) | Идентификатор документа |
| `user_id` | `UUID` FK → users | Владелец (каскадное удаление) |
| `title` | `VARCHAR(255)` | Оригинальное имя файла |
| `file_path` | `VARCHAR(512)` | Путь в `shared_storage` |
| `sha256` | `VARCHAR(64)` (index) | Идемпотентность загрузки |
| `mime_type`, `size_bytes` | — | Метаданные файла |
| `status` | `VARCHAR(50)` | `pending → processing → embedding → completed / failed / duplicate` |
| `summary` | `TEXT` | Текущий конспект |
| `total_pages`, `processed_pages`, `page_count_estimate` | `INTEGER` | Прогресс обработки |
| `created_at` | `TIMESTAMPTZ` | Дата загрузки |

## `document_pages` — Этап 1
Постраничный текст с методом извлечения (`text_layer` / `ocr` / `vision`) и confidence 0..100. Уникальность `(document_id, page_number)`.

## `document_chunks` — Этапы 3 и 5
| Поле | Тип | Описание |
| :--- | :--- | :--- |
| `id` | `UUID` (PK) | Идентификатор чанка |
| `document_id` | `UUID` FK → documents | Документ |
| `chunk_index` | `INTEGER` | Порядок |
| `content` | `TEXT` | Текст фрагмента |
| `embedding` | `VECTOR(settings.EMBEDDING_DIM)` | Вектор (768 для Gemini text-embedding-004) |
| `page_numbers`, `headings` | `JSONB` | Обратные ссылки для цитирования |
| `extraction_method` | `VARCHAR(50)` | Метод извлечения страницы |
| `search_vector` | `TSVECTOR` (GIN index) | Полнотекстовый поиск (`russian`), обновляется триггером |

## `summary_versions` — Этап 7
Append-only история конспектов: `id`, `document_id`, `version`, `summary`, `created_at`. Уникальность `(document_id, version)`.

## Обслуживание
```bash
cd backend
alembic upgrade head        # применить миграции
alembic revision -m "..."   # новая ревизия
alembic downgrade -1        # откат одной ревизии
```

Для существующего volume со старой схемой (созданной через `create_all`) выполните `alembic stamp head` перед первой миграцией.
