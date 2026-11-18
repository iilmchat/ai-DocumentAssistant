import asyncio
import os
import re
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import NotFoundError
from app.models.models import Document, DocumentChunk, DocumentPage, SummaryVersion, User
from app.schemas.schemas import (
    DocumentProgress,
    DocumentResponse,
    PageResponse,
    SummaryVersionResponse,
)
from app.services.ai_service import generate_document_summary
from app.services.audit import log_action
from app.services.export import ExportData, render_docx, render_markdown, render_pdf
from app.services.file_validation import (
    IMAGE_MIMES,
    ValidationError,
    compute_sha256,
    count_pdf_pages,
    validate_upload,
)
from app.worker import process_document_task, process_scanned_document_task, save_summary_version

router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])

# Каталог для загруженных файлов. Внутри Docker-контейнера это /app/storage
# (именно этот путь монтируется в volume shared_storage). При локальном запуске
# из корня backend/ файлы попадают в ./storage.
UPLOAD_DIR = settings.UPLOAD_DIR or os.environ.get("STORAGE_PATH") or "storage"
os.makedirs(UPLOAD_DIR, exist_ok=True)

CHUNK_READ = 1024 * 1024  # 1 МБ — читаем файл на диск потоково, не держим в памяти


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


async def _get_owned_document(
    db: AsyncSession, document_id: uuid.UUID, user_id: uuid.UUID
) -> Document:
    """Этап 4: документ виден только владельцу."""
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == user_id)
    )
    doc = result.scalars().first()
    if not doc:
        raise NotFoundError("Документ не найден.")
    return doc


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = current_user

    # S1: квоты на число документов и суммарный объём
    count_res = await db.execute(
        select(func.count()).select_from(Document).where(Document.user_id == user.id)
    )
    if (count_res.scalar() or 0) >= settings.MAX_DOCUMENTS_PER_USER:
        raise HTTPException(status_code=429, detail="Достигнут лимит числа документов")
    size_res = await db.execute(
        select(func.coalesce(func.sum(Document.size_bytes), 0)).where(Document.user_id == user.id)
    )
    if (size_res.scalar() or 0) + (file.size or 0) > settings.MAX_STORAGE_BYTES_PER_USER:
        raise HTTPException(status_code=413, detail="Превышена квота хранилища")

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
                    raise HTTPException(
                        status_code=413, detail=f"Файл больше {settings.MAX_UPLOAD_SIZE_MB} МБ."
                    )
                f.write(chunk)

        # Безопасность: MIME по содержимому, а не по расширению
        try:
            mime = validate_upload(file_path)
        except ValidationError as e:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail=str(e)) from e

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

        page_count = (
            count_pdf_pages(file_path)
            if canonical_ext == ".pdf"
            else (1 if mime in IMAGE_MIMES else None)
        )
        if page_count and page_count > settings.OCR_MAX_PAGES:
            os.remove(file_path)
            raise HTTPException(
                status_code=400,
                detail=f"Слишком много страниц: {page_count} > {settings.OCR_MAX_PAGES}.",
            )

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
        await log_action(
            db,
            user.id,
            "document.upload",
            resource_type="document",
            resource_id=str(new_doc.id),
            ip_address=_client_ip(request),
            details={"filename": new_doc.title, "size_bytes": size, "mime_type": mime},
        )
        await db.commit()
        await db.refresh(new_doc)
    except HTTPException:
        raise
    except Exception:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise

    # Этап 4: маршрутизация по очередям — PDF со сканами и изображения уходят в ocr-очередь
    if canonical_ext == ".pdf" or mime in IMAGE_MIMES:
        process_scanned_document_task.delay(str(new_doc.id), file_path)
    else:
        process_document_task.delay(str(new_doc.id), file_path)

    return new_doc


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{document_id}/progress", response_model=DocumentProgress)
async def document_progress(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Поллинг прогресса обработки."""
    doc = await _get_owned_document(db, document_id, current_user.id)
    return DocumentProgress(
        id=doc.id,
        status=doc.status,
        total_pages=doc.total_pages,
        processed_pages=doc.processed_pages,
    )


@router.get("/{document_id}/progress/stream")
async def document_progress_sse(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Этап 4: SSE — живой прогресс без нагрузки поллингом."""
    await _get_owned_document(db, document_id, current_user.id)
    user_id = current_user.id

    async def gen():
        from app.core.database import AsyncSessionLocal

        last = None
        while True:
            async with AsyncSessionLocal() as session:
                res = await session.execute(
                    select(Document).where(Document.id == document_id, Document.user_id == user_id)
                )
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
async def document_pages(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Этап 1: постраничный текст с методом извлечения и уверенностью."""
    await _get_owned_document(db, document_id, current_user.id)
    result = await db.execute(
        select(DocumentPage)
        .where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number)
    )
    return result.scalars().all()


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    request: Request,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await _get_owned_document(db, document_id, current_user.id)
    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)
    await log_action(
        db,
        current_user.id,
        "document.delete",
        resource_type="document",
        resource_id=str(doc.id),
        ip_address=_client_ip(request),
    )
    await db.delete(doc)
    await db.commit()


# ---------------------------------------------------------------------------
# Этап 7: экспорт конспекта и история версий
# ---------------------------------------------------------------------------


@router.get("/{document_id}/export")
async def export_summary(
    document_id: uuid.UUID,
    format: str = Query("md", pattern="^(md|docx|pdf)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await _get_owned_document(db, document_id, current_user.id)
    if not doc.summary:
        raise HTTPException(status_code=404, detail="Конспект ещё не сгенерирован.")

    data = ExportData(title=doc.title, summary=doc.summary, created_at=doc.created_at)
    media_types = {
        "md": "text/markdown; charset=utf-8",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
    }
    renderers = {"md": render_markdown, "docx": render_docx, "pdf": render_pdf}
    content = renderers[format](data)
    safe_name = re.sub(r"[^\w\- ]+", "_", doc.title)[:80] or "summary"
    return Response(
        content=content,
        media_type=media_types[format],
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.{format}"'},
    )


@router.get("/{document_id}/versions", response_model=list[SummaryVersionResponse])
async def list_summary_versions(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_owned_document(db, document_id, current_user.id)
    result = await db.execute(
        select(SummaryVersion)
        .where(SummaryVersion.document_id == document_id)
        .order_by(SummaryVersion.version.desc())
    )
    return result.scalars().all()


async def _collect_document_text(db: AsyncSession, doc_id: uuid.UUID) -> str:
    pages = await db.execute(
        select(DocumentPage)
        .where(DocumentPage.document_id == doc_id)
        .order_by(DocumentPage.page_number)
    )
    texts = [p.text for p in pages.scalars().all()]
    if not texts:
        chunks = await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc_id))
        texts = [c.content for c in chunks.scalars().all()]
    return "\n\n".join(texts)


@router.post("/{document_id}/summarize", response_model=SummaryVersionResponse)
async def regenerate_summary(
    request: Request,
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await _get_owned_document(db, document_id, current_user.id)
    full_text = await _collect_document_text(db, doc.id)
    if not full_text.strip():
        raise HTTPException(status_code=400, detail="Нет текста для суммаризации.")

    summary = await generate_document_summary(full_text)
    doc.summary = summary
    version = await save_summary_version(db, doc.id, summary)
    await log_action(
        db,
        current_user.id,
        "summary.regenerate",
        resource_type="document",
        resource_id=str(doc.id),
        ip_address=_client_ip(request),
    )
    await db.commit()
    return version


@router.post("/{document_id}/versions/{version_id}/restore", response_model=DocumentResponse)
async def restore_summary_version(
    request: Request,
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await _get_owned_document(db, document_id, current_user.id)
    result = await db.execute(
        select(SummaryVersion).where(
            SummaryVersion.id == version_id,
            SummaryVersion.document_id == doc.id,
        )
    )
    version = result.scalars().first()
    if not version:
        raise HTTPException(status_code=404, detail="Версия конспекта не найдена.")

    doc.summary = version.summary
    # история append-only: восстановление тоже фиксируется новой версией
    await save_summary_version(db, doc.id, version.summary)
    await log_action(
        db,
        current_user.id,
        "summary.restore",
        resource_type="document",
        resource_id=str(doc.id),
        ip_address=_client_ip(request),
        details={"restored_version": version.version},
    )
    await db.commit()
    await db.refresh(doc)
    return doc
