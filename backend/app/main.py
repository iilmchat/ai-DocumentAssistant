import time
import uuid
from contextlib import asynccontextmanager

import structlog.contextvars
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from slowapi.errors import RateLimitExceeded
from sqlalchemy import func, select, text

from app.api import auth, chat, documents
from app.core.cache import redis_client
from app.core.config import settings
from app.core.errors import AppError
from app.core.logging import configure_logging, log
from app.core.metrics import (
    HTTP_LATENCY,
    HTTP_REQUESTS,
    set_doc_status_gauge,
)
from app.core.rate_limit import limiter
from app.models.models import Document

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Схема и расширения управляются Alembic: `alembic upgrade head`.
    log.info("service.started", project=settings.PROJECT_NAME)
    yield
    log.info("service.stopped")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    token = structlog.contextvars.bind_contextvars(request_id=request_id)
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception:
        log.exception("http.unhandled_error", method=request.method, path=request.url.path)
        raise
    finally:
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        HTTP_REQUESTS.labels(request.method, path, str(status)).inc()
        HTTP_LATENCY.labels(request.method, path).observe(time.perf_counter() - started)
        log.info("http.request", method=request.method, path=path, status=status)
        structlog.contextvars.reset_contextvars(**token)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(_request: Request, _exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "Слишком много запросов. Попробуйте позже.", "code": "rate_limited"},
    )


@app.exception_handler(AppError)
async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": exc.code},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Некорректный запрос",
            "code": "validation_error",
            "errors": exc.errors(),
        },
    )


app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(chat.router)


@app.get("/")
async def root():
    return {"message": "Welcome to AI Document Assistant API"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/health/live")
async def live():
    return {"status": "alive"}


@app.get("/health/ready")
async def ready():
    from app.core.database import engine

    checks: dict[str, str] = {}
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            rows = (
                await conn.execute(select(Document.status, func.count()).group_by(Document.status))
            ).all()
        checks["db"] = "ok"
        set_doc_status_gauge({str(status): int(count) for status, count in rows})
    except Exception as exc:
        checks["db"] = f"unavailable: {exc}"

    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"unavailable: {exc}"

    healthy = all(value == "ok" for value in checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ready" if healthy else "unavailable", "checks": checks},
    )


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
