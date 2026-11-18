# Threat model (S1)

## Активы
- Учётные данные пользователей (email, bcrypt-хеш пароля).
- Загруженные документы и сгенерированные конспекты.
- JWT и refresh-токены.

## Границы доверия
Браузер → Nginx → FastAPI → PostgreSQL / Redis / Celery / LLM-провайдер.

## Угрозы и контрмеры

| Угроза | Контрмера |
| :--- | :--- |
| Подбор пароля | Rate limit `/auth/login` (5/мин), блокировка после 5 неудач на 15 мин (Redis), bcrypt |
| Массовая регистрация | Rate limit `/auth/register` (3/мин) |
| Кража access-токена (XSS) | Короткий TTL 15 мин, refresh-ротация, чёрный список в Redis, logout отзывает jti |
| Несанкционированный доступ к чужим документам | Фильтр `Document.user_id == current_user.id` во всех эндпоинтах |
| Перегрузка chat API | Rate limit 30/мин на `/chat/ask` и `/chat/stream` |
| ZIP-бомба / подмена MIME | MIME по magic bytes, лимит распаковки, `validate_image_limits` |
| Decompression bomb изображения | `MAX_IMAGE_PIXELS` (40 Мп) и `MAX_IMAGE_SIDE_PX` (20000) |
| Исчерпание хранилища | Квоты: 100 документов и 2 ГБ на пользователя |
| Эскалация контейнера | Образы backend/worker запускаются от пользователя `appuser` (uid 10001) |
| Утечка секретов в git | `.env` не отслеживаются, gitleaks в pre-commit и CI, Dependabot + Trivy |
| Нет следа действий | Audit log: регистрация, логин, refresh, загрузка/удаление документа, регенерация/восстановление конспекта |

## Остаточные риски / не сделано
- Токены по-прежнему хранятся в `localStorage` (XSS-риск). Полный перевод на httpOnly cookie — отдельная задача.
- In-memory rate limiter не разделён между несколькими процессами uvicorn (в compose один процесс).
- Verify email и password reset требуют SMTP-инфраструктуры — отложено.
- Redis недоступен → чёрный список и блокировки логина работают по fail-open (логируется warning).
