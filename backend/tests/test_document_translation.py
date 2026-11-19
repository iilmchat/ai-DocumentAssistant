"""T10: покрытие оркестратора перевода документа."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import document_translation as dt


@pytest.mark.asyncio
async def test_get_glossary():

    term = SimpleNamespace(source_term="Заказчик", target_term="Customer")
    db = AsyncMock()
    db.execute.return_value = MagicMock(scalars=lambda: MagicMock(all=lambda: [term]))
    result = await dt.get_glossary(db, uuid.uuid4(), "en")
    assert result == {"Заказчик": "Customer"}


@pytest.mark.asyncio
async def test_translate_document_full_flow():
    doc_id, user_id = uuid.uuid4(), uuid.uuid4()
    doc = SimpleNamespace(id=doc_id, translation_language=None)
    page = SimpleNamespace(text="Текст страницы", text_translated=None, translation_language=None)
    chunk = SimpleNamespace(
        content="Чанк текста",
        content_translated=None,
        embedding_translated=None,
        translation_language=None,
        translation_status="none",
    )
    db = AsyncMock()
    db.get.return_value = doc
    # execute: pages, chunks, (update status нет), record_usage flush
    db.execute.side_effect = [
        MagicMock(scalars=lambda: MagicMock(all=lambda: [page])),
        MagicMock(scalars=lambda: MagicMock(all=lambda: [chunk])),
    ]
    db.scalar = AsyncMock(return_value=None)

    with (
        patch.object(dt, "get_glossary", new=AsyncMock(return_value={})),
        patch.object(
            dt, "translate_blocks", new=AsyncMock(side_effect=[["Page text"], ["Chunk text"]])
        ),
        patch.object(dt, "generate_embeddings", new=AsyncMock(return_value=[[0.1] * 768])),
        patch.object(dt, "ensure_embedding_dim", side_effect=lambda x: x),
        patch.object(dt, "record_usage", new=AsyncMock()),
    ):
        count = await dt.translate_document(db, doc_id, "en", user_id)

    assert count == 1
    assert page.text_translated == "Page text"
    assert chunk.content_translated == "Chunk text"
    assert chunk.translation_status == "done"
    assert doc.translation_language == "en"


@pytest.mark.asyncio
async def test_translate_document_not_found():
    db = AsyncMock()
    db.get.return_value = None
    with pytest.raises(ValueError, match="not found"):
        await dt.translate_document(db, uuid.uuid4(), "en", uuid.uuid4())


@pytest.mark.asyncio
async def test_translate_document_invalid_language():
    db = AsyncMock()
    db.get.return_value = SimpleNamespace(id=uuid.uuid4())
    with pytest.raises(ValueError, match="Unsupported"):
        await dt.translate_document(db, uuid.uuid4(), "xx", uuid.uuid4())
