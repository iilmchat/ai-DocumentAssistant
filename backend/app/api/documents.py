import asyncio
import os
import uuid

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.database import get_db
from app.models.models import Document, User, DocumentPage
from app.schemas.schemas import DocumentResponse, DocumentProgress, PageResponse
from app.services.file_validation import (
    validate_upload, compute_sha256, count_pdf_pages, ValidationError,
)
from app.worker import process_document_task, process_scanned_document_task

router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])

# Каталог для загруженных файлов. Внутри Docker-контейнера это /app/storage
# (именно этот путь монтируется в volume shared_storage). При локальном запуске
# из корня backend/ файлы попадают в ./storage.
UPLOAD_DIR = settings.UPLOAD_DIR or os.environ.get("STORAGE_PATH") or "storage"
os.makedirs(UPLOAD_DIR, exist_ok=True)

CHUNK_READ = 1024 * 1024  # 1 МБ — читаем файл на диск потоково, не держим в памяти


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()
    if not user:
        user = User(email="test@example.com", password_hash="hashed_dummy")
        db.add(user)
        await db.commit()
        await db.refresh(user)

    file_ext = os.path.splitext(file.filename or "")[1].lower()
    file_name = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, file_name)

    # пишем на диск потоком с ограничением размера
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    size = 0
    try:
        with open(file_path, "wb") as f:
            while True:
                chunk = await file.read(CHUNK_READ)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(status_code=413, detail=f"Файл больше {settings.MAX_UPLOAD_SIZE_MB} МБ.")
                f.write(chunk)

        # Безопасность: MIME по содержимому, а не по расширению
        try:
            mime = validate_upload(file_path)
        except ValidationError as e:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail=str(e))

        # каноническое расширение из определённого MIME
        from app.services.file_validation import ALLOWED_MIMES
        canonical_ext = ALLOWED_MIMES[mime]
        if canonical_ext != file_ext:
            new_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}{canonical_ext}")
            os.rename(file_path, new_path)
            file_path = new_path

        sha256 = compute_sha256(file_path)

        # Этап 4: идемпотентность — тот же файл уже есть, не жжём OCR и эмбеддинги
        existing = await db.execute(
            select(Document).where(Document.sha256 == sha256, Document.user_id == user.id)
        )
        dup = existing.scalars().first()
        if dup:
            os.remove(file_path)
            return dup  # frontend увидит существующий документ со статусом

        page_count = count_pdf_pages(file_path) if canonical_ext == ".pdf" else None
        if page_count and page_count > settings.OCR_MAX_PAGES:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail=f"Слишком много страниц: {page_count} > {settings.OCR_MAX_PAGES}.")

        new_doc = Document(
            user_id=user.id,
            title=file.filename or file_name,
            file_path=file_path,
            status="pending",
            sha256=sha256,
            mime_type=mime,
            size_bytes=size,
            total_pages=page_count,
            page_count_estimate=page_count,
        )
        db.add(new_doc)
        await db.commit()
        await db.refresh(new_doc)
    except HTTPException:
        raise
    except Exception:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise

    # Этап 4: маршрутизация по очередям — PDF потенциально со сканами уходит в ocr-очередь
    if canonical_ext == ".pdf":
        process_scanned_document_task.delay(str(new_doc.id), file_path)
    else:
        process_document_task.delay(str(new_doc.id), file_path)

    return new_doc


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).order_by(Document.created_at.desc()))
    return result.scalars().all()


@router.get("/{document_id}/progress", response_model=DocumentProgress)
async def document_progress(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Поллинг прогресса обработки."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден.")
    return DocumentProgress(
        id=doc.id, status=doc.status,
        total_pages=doc.total_pages, processed_pages=doc.processed_pages,
    )


@router.get("/{document_id}/progress/stream")
async def document_progress_sse(document_id: uuid.UUID):
    """Этап 4: SSE — живой прогресс без нагрузки поллингом."""
    async def event_stream():
        import aiosqlite  # noqa: F401  (не используется; защита от случайного импорта)
    async def gen():
        from app.core.database import AsyncSessionLocal
        last = None
        while True:
            async with AsyncSessionLocal() as session:
                res = await session.execute(select(Document).where(Document.id == document_id))
                doc = res.scalars().first()
            if not doc:
                yield "event: error\ndata: document not found\n\n"
                return
            payload = f'{{"status":"{doc.status}","processed_pages":{doc.processed_pages or 0},"total_pages":{doc.total_pages or 0}}}'
            if payload != last:
                yield f"data: {payload}\n\n"
                last = payload
            if doc.status in ("completed", "failed"):
                yield "event: done\ndata: end\n\n"
                return
            await asyncio.sleep(1)

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/{document_id}/pages", response_model=list[PageResponse])
async def document_pages(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Этап 1: постраничный текст с методом извлечения и уверенностью."""
    result = await db.execute(
        select(DocumentPage)
        .where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number)
    )
    return result.scalars().all()


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден.")
    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)
    await db.delete(doc)
    await db.commit()
