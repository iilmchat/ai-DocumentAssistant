from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Document Assistant"

    # --- Инфраструктура ---
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_documents"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    # Этап 4: отдельная очередь под OCR — медленные сканы не блокируют быстрые TXT/PDF
    CELERY_OCR_QUEUE: str = "ocr"
    SECRET_KEY: str = "super_secret_key_change_me_in_production"
    # Запрещаем "*" вместе с credentials: перечисляем конкретные origin-ы через запятую
    CORS_ORIGINS: str = "http://localhost,http://localhost:5173,http://127.0.0.1:5173"

    # --- LLM / OpenAI-совместимый провайдер ---
    # Локально можно указать Gemini: OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str | None = None
    LLM_MODEL: str = "gpt-4o-mini"

    # Каталог для загруженных файлов. По умолчанию соответствует пути,
    # который монтируется как volume shared_storage в Docker-контейнерах.
    UPLOAD_DIR: str = "storage"

    # --- OCR / гибридное извлечение (Этапы 1-2) ---
    OCR_ENGINE: str = "tesseract"  # tesseract | vision
    OCR_LANGUAGES: str = "rus+eng"
    OCR_MIN_CHARS_PER_PAGE: int = 100  # эмпирический порог "мало текста -> в OCR"
    OCR_IMAGE_AREA_THRESHOLD: float = 0.85  # картинка занимает >=85% площади листа
    OCR_MAX_PAGES: int = 500  # лимит на число страниц (безопасность)

    # --- Загрузка / безопасность (S1) ---
    MAX_UPLOAD_SIZE_MB: int = 50
    PARSE_TIMEOUT_SECONDS: int = 300
    MAX_IMAGE_PIXELS: int = 40_000_000  # защита от decompression bomb
    MAX_IMAGE_SIDE_PX: int = 20_000
    MAX_DOCUMENTS_PER_USER: int = 100
    MAX_STORAGE_BYTES_PER_USER: int = 2 * 1024 * 1024 * 1024  # 2 ГБ

    # --- Retention / данные (S4) ---
    RETENTION_DAYS: int = 365  # срок хранения аудита и удалённых документов
    SOFT_DELETE_GRACE_DAYS: int = 7  # отложенная физическая очистка файлов
    SUMMARY_VERSIONS_KEEP: int = 20  # сколько версий конспекта хранить на документ

    # --- JWT / rate limiting (S1) ---
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    LOGIN_RATE_LIMIT: str = "5/minute"
    REGISTER_RATE_LIMIT: str = "3/minute"
    CHAT_RATE_LIMIT: str = "30/minute"
    MAX_FAILED_LOGINS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    # --- Embeddings / поиск (Этап 5 / S3) ---
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    EMBEDDING_DIM: int = 1024  # фиксируем размерность; менять через миграцию
    RERANK_TOP_K: int = 50  # кандидатов перед реранкером
    RRF_K: int = 60  # параметр Reciprocal Rank Fusion
    # HNSW-индекс pgvector (миграция 0003)
    USE_ANN_INDEX: bool = True
    HNSW_M: int = 16
    HNSW_EF_CONSTRUCTION: int = 64
    HNSW_EF_SEARCH: int = 80
    EMBEDDING_CACHE_TTL_SECONDS: int = 3600

    # --- Пул БД и конкуренция LLM (S3) ---
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_PRE_PING: bool = True
    LLM_MAX_CONCURRENCY: int = 4

    # --- S5: реранкинг и стоимость LLM ---
    RERANK_ENABLED: bool = True
    RERANK_MODEL: str = ""  # пусто = LLM_MODEL
    LLM_COST_PER_1K_INPUT: float = 0.0  # USD, заполняется под конкретный тариф
    LLM_COST_PER_1K_OUTPUT: float = 0.0
    LLM_MONTHLY_BUDGET_USD: float = 100.0
    PROMPT_VERSION: str = "v1"

    # --- T6: двуязычные документы ---
    TRANSLATION_ENABLED: bool = True
    TRANSLATION_TARGET_LANGUAGE: str = "ru"  # язык по умолчанию для UI
    TRANSLATION_QUEUE: str = "translation"
    TRANSLATION_MAX_CHARS_PER_REQUEST: int = 4000
    TRANSLATION_CACHE_TTL_SECONDS: int = 86400
    TRANSLATION_COST_LIMIT_USD: float = 20.0  # лимит на документ
    SUPPORTED_LANGUAGES: str = "ru,en,de,fr,es"

    # --- T7: online RAG-оценка ---
    RAG_EVAL_ENABLED: bool = True
    RAG_EVAL_SAMPLE_RATE: float = 0.1  # доля запросов с detailed-оценкой
    RAG_MIN_FAITHFULNESS: float = 0.5
    RAG_MIN_ANSWER_RELEVANCE: float = 0.5

    # --- T8: безопасная сессия (httpOnly cookie + CSRF) ---
    SESSION_COOKIE_SECURE: bool = True  # в проде только HTTPS
    SESSION_COOKIE_SAMESITE: str = "lax"
    SESSION_COOKIE_ACCESS: str = "access_token"
    SESSION_COOKIE_REFRESH: str = "refresh_token"
    CSRF_COOKIE_NAME: str = "csrf_token"
    CSRF_HEADER_NAME: str = "X-CSRF-Token"
    CSRF_ENFORCE: bool = True  # требует double-submit для cookie-аутентификации
    # T8: PII и роли
    PII_REDACTION_ENABLED: bool = True
    DEFAULT_USER_ROLE: str = "editor"
    AUDIT_WEBHOOK_URL: str = ""

    # --- T9: object storage и мультитенантность ---
    RATE_LIMIT_REDIS: bool = False  # включить общий Redis-storage для slowapi
    STORAGE_BACKEND: str = "local"  # local | s3
    S3_ENDPOINT_URL: str | None = None  # для MinIO
    S3_BUCKET: str = "ai-documents"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = "us-east-1"
    S3_PRESIGN_TTL: int = 300  # секунды
    MULTITENANT_ENABLED: bool = True
    MAX_ORG_DOCUMENTS: int = 1000
    MAX_ORG_STORAGE_BYTES: int = 20 * 1024 * 1024 * 1024  # 20 ГБ

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
