"""T10: тесты воркера и retention для покрытия."""

import hashlib
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.retention import cleanup_retention
from app.worker import _embed_and_store_chunks, save_summary_version


@pytest.mark.asyncio
async def test_save_summary_version_increments():
    db = AsyncMock()
    result = MagicMock()
    result.scalar.return_value = 3
    db.execute.return_value = result

    version = await save_summary_version(db, uuid.uuid4(), "summary")
    assert version.version == 4
    db.add.assert_called_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_embed_and_store_chunks_skips_unchanged():
    db = AsyncMock()
    existing = MagicMock()
    existing.scalars.return_value.all.return_value = []
    db.execute.return_value = existing

    chunks = [
        {
            "content": "text one",
            "page_numbers": [1],
            "headings": [],
            "extraction_method": "text_layer",
        },
        {"content": "text two", "page_numbers": [2], "headings": [], "extraction_method": "ocr"},
    ]
    from app.core.config import settings

    dim = settings.EMBEDDING_DIM
    with patch(
        "app.worker.generate_embeddings", new=AsyncMock(return_value=[[0.5] * dim, [0.6] * dim])
    ) as gen:
        await _embed_and_store_chunks(db, uuid.uuid4(), chunks, set())

    gen.assert_awaited_once()
    assert db.add.call_count == 2
    added = db.add.call_args_list[0].args[0]
    assert added.content_hash == hashlib.sha256(b"text one").hexdigest()


@pytest.mark.asyncio
async def test_embed_reuses_embeddings_for_unchanged():
    db = AsyncMock()
    chunks = [{"content": "same text"}]
    old_hash = hashlib.sha256(b"same text").hexdigest()
    with patch("app.worker.generate_embeddings", new=AsyncMock()) as gen:
        await _embed_and_store_chunks(db, uuid.uuid4(), chunks, {old_hash})
    gen.assert_not_awaited()
    from app.core.config import settings

    added = db.add.call_args.args[0]
    assert added.embedding == [0.0] * settings.EMBEDDING_DIM


@pytest.mark.asyncio
async def test_cleanup_retention_deletes_expired():

    doc = SimpleNamespace(
        file_path="/tmp/expired.pdf",
        id=uuid.uuid4(),
    )
    db = AsyncMock()
    db.execute.side_effect = [
        MagicMock(scalars=lambda: MagicMock(all=lambda: [doc])),  # expired docs
        MagicMock(),  # summary versions delete
        MagicMock(rowcount=2),  # audit delete
    ]
    with (
        patch("app.services.retention.os.path.exists", return_value=True),
        patch("app.services.retention.os.remove") as remove,
    ):
        result = await cleanup_retention(db)

    remove.assert_called_once_with("/tmp/expired.pdf")
    db.delete.assert_called_once_with(doc)
    assert result["documents"] == 1
    assert result["files"] == 1
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_cleanup_retention_empty():
    db = AsyncMock()
    db.execute.side_effect = [
        MagicMock(scalars=lambda: MagicMock(all=lambda: [])),
        MagicMock(),
        MagicMock(rowcount=0),
    ]
    result = await cleanup_retention(db)
    assert result["documents"] == 0


def test_retention_config():
    from app.core.config import settings

    assert settings.SOFT_DELETE_GRACE_DAYS > 0
    assert settings.SUMMARY_VERSIONS_KEEP > 0
