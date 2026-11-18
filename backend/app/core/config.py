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

    # --- Загрузка / безопасность ---
    MAX_UPLOAD_SIZE_MB: int = 50
    PARSE_TIMEOUT_SECONDS: int = 300

    # --- Embeddings / поиск (Этап 5) ---
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    EMBEDDING_DIM: int = 1024  # фиксируем размерность; менять через миграцию
    RERANK_TOP_K: int = 50  # кандидатов перед реранкером
    RRF_K: int = 60  # параметр Reciprocal Rank Fusion

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
