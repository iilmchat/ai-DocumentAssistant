"""Worker-пайплайн (Этапы 1, 3, 4).

Две очереди:
- default  — быстрые форматы (TXT, PDF с текстовым слоем);
- ocr      — документы со сканами, отдельный контейнер воркера, чтобы
             медленный OCR не блокировал очередь default.

Обработка постраничная: каждая страница пишется в document_pages с
extraction_method/confidence, прогресс processed_pages/total_pages
обновляется в БД (фронт читает через SSE / поллинг). Идемпотентность по
SHA-256 проверяется ещё на этапе загрузки (api/documents.py).
"""
import asyncio
import os

from celery import Celery
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.future import select
from sqlalchemy import delete

from app.core.config import settings
from app.models.models import Document, DocumentChunk, DocumentPage
from app.services.document_parser import extract_text_from_file, split_text_into_chunks
from app.services.text_extraction import extract_pages, chunk_pages
from app.services.ai_service import generate_embeddings, generate_document_summary

celery_app = Celery(
    "worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.task_routes = {
    "process_document_task": {"queue": "default"},
    "process_scanned_document_task": {"queue": settings.CELERY_OCR_QUEUE},
}
# одна тяжёлая OCR-задача за раз на воркер, чтобы не забить память
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.task_acks_late = True
celery_app.conf.task_time_limit = settings.PARSE_TIMEOUT_SECONDS * 4

engine = create_async_engine(settings.DATABASE_URL, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def _embed_and_store_chunks(session, doc_id, chunks: list[dict]):
    batch_size = 50
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        texts = [c["content"] for c in batch]
        embeddings = await generate_embeddings(texts)
        for idx, (c, emb) in enumerate(zip(batch, embeddings)):
            session.add(DocumentChunk(
                document_id=doc_id,
                chunk_index=i + idx,
                content=c["content"],
                embedding=emb,
                page_numbers=c.get("page_numbers"),
                headings=c.get("headings"),
                extraction_method=c.get("extraction_method"),
            ))
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

            if ext == ".pdf":
                # Этап 1: гибридное постраничное извлечение (текстовый слой или OCR)
                pages = await asyncio.to_thread(extract_pages, file_path)
                doc.total_pages = len(pages)
                doc.processed_pages = 0
                await session.commit()

                for p in pages:
                    session.add(DocumentPage(
                        document_id=doc.id,
                        page_number=p.page_number,
                        text=p.text,
                        extraction_method=p.extraction_method,
                        confidence=int(round(p.confidence * 100)),
                    ))
                    doc.processed_pages = p.page_number
                    # коммитим каждую страницу — фронт видит живой прогресс
                    await session.commit()

                # Этап 3: семантический чанкинг со ссылками на страницы
                chunks = await asyncio.to_thread(chunk_pages, pages)
                full_text = "\n\n".join(p.text for p in pages)
            else:
                # TXT / DOCX — старый путь, без постраничности
                full_text = await asyncio.to_thread(extract_text_from_file, file_path, ext)
                chunk_texts = split_text_into_chunks(full_text)
                chunks = [
                    {"content": t, "page_numbers": [], "extraction_method": "text_layer", "headings": []}
                    for t in chunk_texts
                ]
                doc.total_pages = 1
                doc.processed_pages = 1

            # пересоздание: чистим старые чанки (идемпотентность при retry)
            await session.execute(delete(DocumentChunk).where(DocumentChunk.document_id == doc.id))
            await session.execute(delete(DocumentPage).where(DocumentPage.document_id == doc.id))
            await session.commit()

            doc.status = "embedding"
            await session.commit()

            if chunks:
                await _embed_and_store_chunks(session, doc.id, chunks)

            doc.summary = await generate_document_summary(full_text)
            doc.status = "completed"
            await session.commit()
            print(f"Документ {document_id} обработан: {len(chunks)} чанков.")
        except Exception as e:
            print(f"Ошибка обработки документа {document_id}: {e}")
            if doc:
                doc.status = "failed"
                await session.commit()
            raise


@celery_app.task(name="process_document_task", bind=True, max_retries=2)
def process_document_task(self, document_id: str, file_path: str):
    try:
        asyncio.run(async_process_document(document_id, file_path))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="process_scanned_document_task", bind=True, max_retries=2)
def process_scanned_document_task(self, document_id: str, file_path: str):
    """OCR-документы — в отдельную очередь ocr (см. task_routes)."""
    try:
        asyncio.run(async_process_document(document_id, file_path))
    except Exception as exc:
        raise self.retry(exc=exc, countdown=120)
