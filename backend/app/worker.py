"""Worker-пайплайн (Этапы 1, 3, 4).

Две очереди:
- default  — быстрые форматы (TXT, DOCX, PDF с текстовым слоем);
- ocr      — документы со сканами, отдельный контейнер воркера, чтобы
             медленный OCR не блокировал очередь default.

Обработка постраничная: каждая страница пишется в document_pages с
extraction_method/confidence, прогресс processed_pages/total_pages
обновляется в БД (фронт читает через SSE / поллинг).
"""

import asyncio
import os
import time

import structlog.contextvars
from celery import Celery
from sqlalchemy import delete, func
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.future import select
from sqlalchemy.pool import NullPool

from app.core.cache import invalidate_embedding_cache
from app.core.config import settings
from app.core.logging import configure_logging, log
from app.core.metrics import CELERY_LATENCY, CELERY_TASKS
from app.models.models import Document, DocumentChunk, DocumentPage, SummaryVersion
from app.services.ai_service import (
    ensure_embedding_dim,
    generate_document_summary,
    generate_embeddings,
)
from app.services.document_parser import extract_text_from_file, split_text_into_chunks
from app.services.extended_parsers import EXTRACTORS, transcribe_audio
from app.services.file_validation import AUDIO_EXTENSIONS, IMAGE_EXTENSIONS
from app.services.retention import cleanup_retention
from app.services.text_extraction import chunk_pages, extract_pages, extract_pages_from_image

configure_logging()

celery_app = Celery(
    "worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.task_routes = {
    "process_document_task": {"queue": "default"},
    "process_scanned_document_task": {"queue": settings.CELERY_OCR_QUEUE},
    "translate_document_task": {"queue": settings.TRANSLATION_QUEUE},
    "dead_letter_task": {"queue": "dlq"},
}
# одна тяжёлая OCR-задача за раз на воркер, чтобы не забить память
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.task_acks_late = True
celery_app.conf.task_time_limit = settings.PARSE_TIMEOUT_SECONDS * 4
# S4: ежедневная уборка (запускается отдельным контейнером celery beat)
celery_app.conf.beat_schedule = {
    "cleanup-retention-daily": {
        "task": "cleanup_retention_task",
        "schedule": 86400.0,
    }
}

# Celery prefork: каждая задача выполняется в новом event loop. Обычный пул
# привязывает asyncpg-соединение к первому loop → "Future attached to a different loop".
# NullPool создаёт соединение заново для каждого task — безопасно.
engine = create_async_engine(
    settings.DATABASE_URL,
    future=True,
    poolclass=NullPool,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def save_summary_version(session, doc_id, summary: str) -> SummaryVersion:
    """Этап 7: append-only история версий конспекта."""
    result = await session.execute(
        select(func.max(SummaryVersion.version)).where(SummaryVersion.document_id == doc_id)
    )
    next_version = (result.scalar() or 0) + 1
    version = SummaryVersion(document_id=doc_id, version=next_version, summary=summary)
    session.add(version)
    await session.commit()
    return version


async def _embed_and_store_chunks(session, doc_id, chunks: list[dict], old_hashes: set[str]):
    import hashlib

    batch_size = 50
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        new_hashes = [hashlib.sha256(chunk["content"].encode()).hexdigest() for chunk in batch]
        to_embed = [
            chunk for chunk, h in zip(batch, new_hashes, strict=True) if h not in old_hashes
        ]
        embedded: dict[int, list[float]] = {}
        if to_embed:
            embeddings = await generate_embeddings([c["content"] for c in to_embed])
            embedded = {
                id(c): ensure_embedding_dim(emb)
                for c, emb in zip(to_embed, embeddings, strict=True)
            }

        for idx, (chunk, content_hash) in enumerate(zip(batch, new_hashes, strict=True)):
            session.add(
                DocumentChunk(
                    document_id=doc_id,
                    chunk_index=i + idx,
                    content=chunk["content"],
                    content_hash=content_hash,
                    embedding=embedded.get(id(chunk), [0.0] * settings.EMBEDDING_DIM),
                    page_numbers=chunk.get("page_numbers"),
                    headings=chunk.get("headings"),
                    extraction_method=chunk.get("extraction_method"),
                )
            )
        await session.commit()


async def async_process_document(document_id: str, file_path: str):
    async with AsyncSessionLocal() as session:
        doc = None
        try:
            result = await session.execute(select(Document).where(Document.id == document_id))
            doc = result.scalars().first()
            if not doc or doc.status in ("completed", "duplicate"):
                return

            ext = os.path.splitext(file_path)[1].lower()
            doc.status = "processing"
            await session.commit()

            chunks: list[dict] = []
            pages = None

            if ext == ".pdf":
                # Этап 1: гибридное постраничное извлечение (текстовый слой или OCR)
                pages = await asyncio.to_thread(extract_pages, file_path)
            elif ext in IMAGE_EXTENSIONS:
                # Изображение (JPG/PNG/TIFF) — одна страница, всегда через OCR
                pages = await asyncio.to_thread(extract_pages_from_image, file_path)

            if pages is not None:
                doc.total_pages = len(pages)
                doc.processed_pages = 0
                await session.commit()

                for p in pages:
                    session.add(
                        DocumentPage(
                            document_id=doc.id,
                            page_number=p.page_number,
                            text=p.text,
                            extraction_method=p.extraction_method,
                            confidence=int(round(p.confidence * 100)),
                        )
                    )
                    doc.processed_pages = p.page_number
                    # коммитим каждую страницу — фронт видит живой прогресс
                    await session.commit()

                # Этап 3: семантический чанкинг со ссылками на страницы
                chunks = await asyncio.to_thread(chunk_pages, pages)
                full_text = "\n\n".join(p.text for p in pages)
            else:
                # T9: XLSX/PPTX/EML — новые парсеры, аудио — транскрибация
                if ext in AUDIO_EXTENSIONS:
                    full_text = await transcribe_audio(file_path)
                elif ext in EXTRACTORS:
                    full_text = await asyncio.to_thread(EXTRACTORS[ext], file_path)
                else:
                    # TXT / DOCX — путь без постраничности
                    full_text = await asyncio.to_thread(extract_text_from_file, file_path, ext)
                chunk_texts = split_text_into_chunks(full_text)
                chunks = [
                    {
                        "content": text,
                        "page_numbers": [],
                        "extraction_method": "text_layer",
                        "headings": [],
                    }
                    for text in chunk_texts
                ]
                doc.total_pages = 1
                doc.processed_pages = 1

            # T9: сохраняем старые хеши до удаления — неизменившиеся чанки не переэмбеддим
            old_hashes = set(
                (
                    await session.execute(
                        select(DocumentChunk.content_hash).where(
                            DocumentChunk.document_id == doc.id
                        )
                    )
                )
                .scalars()
                .all()
            )

            # пересоздание: чистим старые чанки (идемпотентность при retry)
            await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
            await session.execute(delete(DocumentPage).where(DocumentPage.document_id == doc.id))
            await session.commit()

            doc.status = "embedding"
            await session.commit()

            if chunks:
                await _embed_and_store_chunks(session, doc.id, chunks, old_hashes)
                # S3: после реиндексации старый кэш эмбеддингов запросов неактуален
                await invalidate_embedding_cache()

            # T6: определяем язык оригинала после извлечения текста
            from app.core.language import detect_language

            doc.language = detect_language(full_text)

            summary = await generate_document_summary(full_text)
            doc.summary = summary
            await save_summary_version(session, doc.id, summary)
            doc.status = "completed"
            await session.commit()
            log.info("document.processed", document_id=document_id, chunks=len(chunks))
        except Exception:
            log.exception("document.failed", document_id=document_id)
            if doc:
                doc.status = "failed"
                await session.commit()
            raise


@celery_app.task(name="translate_document_task", bind=True, max_retries=2)
def translate_document_task(
    self, document_id: str, target_language: str, user_id: str, request_id: str | None = None
):
    """T6: перевод документа в отдельной очереди."""
    import uuid

    from app.services.document_translation import translate_document

    token = structlog.contextvars.bind_contextvars(
        request_id=request_id or "system", document_id=document_id, task=self.name
    )
    started = time.perf_counter()
    CELERY_TASKS.labels(task=self.name, status="started").inc()
    try:

        async def _run():
            async with AsyncSessionLocal() as session:
                await translate_document(
                    session,
                    uuid.UUID(document_id),
                    target_language,
                    uuid.UUID(user_id),
                )

        asyncio.run(_run())
        CELERY_TASKS.labels(task=self.name, status="success").inc()
    except Exception as exc:
        CELERY_TASKS.labels(task=self.name, status="failed").inc()
        log.exception("translation.failed", error=str(exc))
        if self.request.retries >= self.max_retries:
            dead_letter_task.delay(document_id, target_language, str(exc), request_id)
            return
        raise self.retry(exc=exc, countdown=60) from exc
    finally:
        CELERY_LATENCY.labels(task=self.name).observe(time.perf_counter() - started)
        structlog.contextvars.reset_contextvars(**token)


@celery_app.task(name="cleanup_retention_task")
def cleanup_retention_task() -> None:
    """S4: ежедневная очистка просроченных документов, версий и аудита."""
    import asyncio

    async def _run():
        async with AsyncSessionLocal() as session:
            await cleanup_retention(session)

    asyncio.run(_run())


@celery_app.task(name="dead_letter_task")
def dead_letter_task(
    document_id: str, file_path: str, error: str, request_id: str | None = None
) -> None:
    """S2: последняя инстанция для задач, исчерпавших повторы."""
    CELERY_TASKS.labels(task="dead_letter", status="failed").inc()
    log.error(
        "task.dead_letter",
        document_id=document_id,
        file_path=file_path,
        error=error,
        request_id=request_id,
    )


def _run_processing_task(
    task_self, document_id: str, file_path: str, request_id: str | None, countdown: int
) -> None:
    task_name = task_self.name
    token = structlog.contextvars.bind_contextvars(
        request_id=request_id or "system", document_id=document_id, task=task_name
    )
    started = time.perf_counter()
    CELERY_TASKS.labels(task=task_name, status="started").inc()
    try:
        asyncio.run(async_process_document(document_id, file_path))
    except Exception as exc:
        CELERY_TASKS.labels(task=task_name, status="failed").inc()
        log.exception("task.failed", error=str(exc))
        if task_self.request.retries >= task_self.max_retries:
            log.error("task.retries_exhausted", error=str(exc))
            dead_letter_task.delay(document_id, file_path, str(exc), request_id)
            return
        raise task_self.retry(exc=exc, countdown=countdown) from exc
    else:
        CELERY_TASKS.labels(task=task_name, status="success").inc()
    finally:
        CELERY_LATENCY.labels(task=task_name).observe(time.perf_counter() - started)
        structlog.contextvars.reset_contextvars(**token)


@celery_app.task(name="process_document_task", bind=True, max_retries=2)
def process_document_task(self, document_id: str, file_path: str, request_id: str | None = None):
    _run_processing_task(self, document_id, file_path, request_id, countdown=30)


@celery_app.task(name="process_scanned_document_task", bind=True, max_retries=2)
def process_scanned_document_task(
    self, document_id: str, file_path: str, request_id: str | None = None
):
    """OCR-документы — в отдельную очередь ocr (см. task_routes)."""
    _run_processing_task(self, document_id, file_path, request_id, countdown=120)
