"""T6: оркестратор перевода документа — страницы + чанки + вектора."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.language import validate_language
from app.core.logging import log
from app.core.metrics import CELERY_TASKS
from app.models.models import Document, DocumentChunk, DocumentPage, Glossary
from app.services.ai_service import ensure_embedding_dim, generate_embeddings
from app.services.translation import translate_blocks
from app.services.usage import record_usage


async def get_glossary(db: AsyncSession, user_id, target: str) -> dict[str, str]:
    rows = (
        (
            await db.execute(
                select(Glossary).where(
                    Glossary.user_id == user_id,
                    (Glossary.target_language == target) | (Glossary.target_language.is_(None)),
                )
            )
        )
        .scalars()
        .all()
    )
    return {row.source_term: row.target_term for row in rows}


async def translate_document(
    db: AsyncSession,
    document_id: uuid.UUID,
    target_language: str,
    user_id,
) -> int:
    """Переводит документ. Возвращает число переведённых чанков."""
    target = validate_language(target_language)
    doc = await db.get(Document, document_id)
    if not doc:
        raise ValueError(f"Document {document_id} not found")

    glossary = await get_glossary(db, user_id, target)

    # 1. Постраничный перевод (источник цитат)
    pages = (
        (
            await db.execute(
                select(DocumentPage)
                .where(DocumentPage.document_id == document_id)
                .order_by(DocumentPage.page_number)
            )
        )
        .scalars()
        .all()
    )
    page_texts = await translate_blocks([p.text for p in pages], target, glossary=glossary)
    for page, page_text in zip(pages, page_texts, strict=True):
        page.text_translated = page_text
        page.translation_language = target

    # 2. Чанки: перевод + вектор перевода для двуязычного поиска
    chunks = (
        (
            await db.execute(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == document_id)
                .order_by(DocumentChunk.chunk_index)
            )
        )
        .scalars()
        .all()
    )

    for chunk in chunks:
        chunk.translation_status = "pending"
    await db.commit()

    for i in range(0, len(chunks), 20):
        batch = chunks[i : i + 20]
        translated_texts = await translate_blocks(
            [c.content for c in batch],
            target,
            glossary=glossary,
            preserve_markdown=True,
        )
        vectors = await generate_embeddings(translated_texts)
        for chunk, text, vector in zip(batch, translated_texts, vectors, strict=True):
            chunk.content_translated = text
            chunk.embedding_translated = ensure_embedding_dim(vector)
            chunk.translation_language = target
            chunk.translation_status = "done"
        await record_usage(db, user_id, document_id, "translate")
        await db.commit()

    doc.translation_language = target
    await db.commit()
    CELERY_TASKS.labels(task="translate_document", status="success").inc()
    log.info(
        "document.translated",
        document_id=str(document_id),
        target=target,
        chunks=len(chunks),
        pages=len(pages),
    )
    return len(chunks)
