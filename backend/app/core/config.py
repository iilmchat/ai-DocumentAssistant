from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Document Assistant"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_documents"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "super_secret_key_change_me"
    OPENAI_API_KEY: str = ""
    # Каталог для загруженных файлов. По умолчанию соответствует пути,
    # который монтируется как volume shared_storage в Docker-контейнерах.
    UPLOAD_DIR: str = "storage"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
