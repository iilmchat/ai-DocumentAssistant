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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
