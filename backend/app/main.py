from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from app.core.config import settings
from app.core.database import engine, Base
from app.api import documents, chat

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Автоматическая инициализация расширений БД и таблиц при старте
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        # Этап 5: триггер автообновления tsvector под русскую конфигурацию.
        # websearch_to_tsquery устойчив к "мусорным" запросам пользователей.
        await conn.execute(text("""
            CREATE OR REPLACE FUNCTION chunk_search_vector_update() RETURNS trigger AS $$
            BEGIN
                NEW.search_vector :=
                    setweight(to_tsvector('russian', COALESCE(NEW.content, '')), 'A');
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
        """))
        await conn.execute(text("""
            DROP TRIGGER IF EXISTS trg_chunk_search_vector ON document_chunks;
        """))
        await conn.execute(text("""
            CREATE TRIGGER trg_chunk_search_vector
            BEFORE INSERT OR UPDATE OF content ON document_chunks
            FOR EACH ROW EXECUTE FUNCTION chunk_search_vector_update();
        """))
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(chat.router)

@app.get("/")
async def root():
    return {"message": "Welcome to AI Document Assistant API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
