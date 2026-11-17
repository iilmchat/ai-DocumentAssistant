from fastapi import FastAPI
from app.core.config import settings
from app.api import documents, chat

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.include_router(documents.router)
app.include_router(chat.router)

@app.get("/")
async def root():
    return {"message": "Welcome to AI Document Assistant API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
