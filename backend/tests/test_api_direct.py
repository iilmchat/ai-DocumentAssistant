"""T10: прямые вызовы API-функций documents.py (без цикла запроса FastAPI)."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api import documents as api


def _user():
    return SimpleNamespace(id=uuid.uuid4(), email="u@example.com", role="editor", org_id=None)


def _doc(**kwargs):
    base = dict(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="doc.pdf",
        status="completed",
        summary="Сводка",
        file_path="/tmp/doc.pdf",
        size_bytes=100,
        language="en",
        translation_language="ru",
        deleted_at=None,
        created_at=datetime.now(UTC),
        total_pages=3,
        processed_pages=2,
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


def _result(rows=None, scalar=None, doc=None):
    r = MagicMock()
    r.scalars.return_value.all.return_value = rows or []
    r.scalars.return_value.first.return_value = doc
    r.scalar.return_value = scalar
    return r


@pytest.mark.asyncio
async def test_list_documents_direct():
    db = AsyncMock()
    db.scalar.return_value = 1
    db.execute.return_value = _result(rows=[_doc()])
    user = _user()
    result = await api.list_documents(limit=5, offset=0, status=None, db=db, current_user=user)
    assert result.total == 1
    assert len(result.items) == 1
    assert result.limit == 5


@pytest.mark.asyncio
async def test_list_documents_with_status_filter():
    db = AsyncMock()
    db.scalar.return_value = 0
    db.execute.return_value = _result()
    result = await api.list_documents(
        limit=10, offset=5, status="failed", db=db, current_user=_user()
    )
    assert result.total == 0
    assert result.offset == 5


@pytest.mark.asyncio
async def test_progress_direct():
    db = AsyncMock()
    doc = _doc()
    db.execute.return_value = _result(doc=doc)
    with patch.object(api, "_get_owned_document", new=AsyncMock(return_value=doc)):
        result = await api.document_progress(doc.id, db, _user())
    assert result.status == "completed"
    assert result.processed_pages == 2


@pytest.mark.asyncio
async def test_document_pages_direct():
    db = AsyncMock()
    doc = _doc()
    db.execute.return_value = _result(rows=[MagicMock(page_number=1)])
    with patch.object(api, "_get_owned_document", new=AsyncMock(return_value=doc)):
        result = await api.document_pages(doc.id, db, _user())
    assert len(result) == 1


@pytest.mark.asyncio
async def test_translation_status_direct():
    db = AsyncMock()
    doc = _doc()
    db.execute.return_value = _result(doc=doc)
    db.scalar = AsyncMock(side_effect=[10, 7, 0])
    result = await api.get_translation_status(doc.id, None, db, _user())
    assert result["status"] in ("pending", "completed")
    assert result["translated_chunks"] == 7


@pytest.mark.asyncio
async def test_list_glossary_direct():
    db = AsyncMock()
    row = MagicMock()
    row.id = uuid.uuid4()
    row.source_term = "Заказчик"
    row.target_term = "Customer"
    row.source_language = "ru"
    row.target_language = "en"
    db.execute.return_value = _result(rows=[row])
    result = await api.list_glossary(db, _user())
    assert result[0]["source_term"] == "Заказчик"


@pytest.mark.asyncio
async def test_add_glossary_direct():
    db = AsyncMock()
    db.execute.return_value = _result()
    doc = _doc()
    with patch.object(api, "_get_owned_document", new=AsyncMock(return_value=doc)):
        result = await api.add_glossary_term(doc.id, "Term", "Термин", "ru", None, db, _user())
    assert result["source_term"] == "Term"
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_delete_translation_direct():
    db = AsyncMock()
    doc = _doc()
    with patch.object(api, "_get_owned_document", new=AsyncMock(return_value=doc)):
        await api.delete_translation(doc.id, db, _user())
    assert db.execute.await_count == 2
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_versions_direct():
    db = AsyncMock()
    v = MagicMock()
    v.id = uuid.uuid4()
    v.version = 2
    v.summary = "Конспект"
    v.created_at = None
    db.execute.return_value = _result(rows=[v])
    doc = _doc()
    with patch.object(api, "_get_owned_document", new=AsyncMock(return_value=doc)):
        result = await api.list_summary_versions(doc.id, db, _user())
    assert len(result) == 1


@pytest.mark.asyncio
async def test_collect_document_text_direct():
    db = AsyncMock()
    db.execute.return_value = _result(
        rows=[MagicMock(text="Страница 1"), MagicMock(text="Страница 2")]
    )
    text = await api._collect_document_text(db, uuid.uuid4())
    assert "Страница 1" in text
    assert "Страница 2" in text


@pytest.mark.asyncio
async def test_collect_document_text_from_chunks():
    db = AsyncMock()
    db.execute.side_effect = [_result(rows=[]), _result(rows=[MagicMock(content="Чанк")])]
    text = await api._collect_document_text(db, uuid.uuid4())
    assert "Чанк" in text


def test_client_ip():
    request = MagicMock()
    request.client.host = "127.0.0.1"
    assert api._client_ip(request) == "127.0.0.1"


@pytest.mark.asyncio
async def test_start_translation_direct():
    db = AsyncMock()
    doc = _doc(language="en")
    with (
        patch.object(api, "_get_owned_document", new=AsyncMock(return_value=doc)),
        patch.object(api, "translate_document_task") as task,
    ):
        result = await api.translate_document_endpoint(MagicMock(), doc.id, "ru", db, _user())
    assert result["status"] == "pending"
    task.delay.assert_called_once()
