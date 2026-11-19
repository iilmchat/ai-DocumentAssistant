"""T10: тесты основного пайплайна воркера (async_process_document) с моками."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import worker
from app.services.text_extraction import PageExtraction, StructuredBlock


def _session_mock(doc):
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = doc
    session.execute.return_value = result
    return session


@pytest.mark.asyncio
async def test_process_document_txt_pipeline():
    doc = SimpleNamespace(id=uuid.uuid4(), status="pending", file_path="/tmp/a.txt", summary=None)
    session = _session_mock(doc)
    session.get = AsyncMock(return_value=None)

    with (
        patch.object(
            worker,
            "AsyncSessionLocal",
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=session), __aexit__=AsyncMock()
            ),
        ),
        patch.object(worker, "extract_text_from_file", return_value="Текст документа."),
        patch.object(worker, "split_text_into_chunks", return_value=["Текст документа."]),
        patch.object(worker, "_embed_and_store_chunks", new=AsyncMock()) as embed,
        patch.object(worker, "generate_document_summary", new=AsyncMock(return_value="Конспект")),
        patch.object(worker, "save_summary_version", new=AsyncMock()),
        patch.object(worker, "invalidate_embedding_cache", new=AsyncMock()),
    ):
        await worker.async_process_document(str(doc.id), doc.file_path)

    embed.assert_awaited_once()
    assert doc.status == "completed"
    assert doc.summary == "Конспект"
    assert doc.total_pages == 1


@pytest.mark.asyncio
async def test_process_document_pdf_pages():
    doc = SimpleNamespace(id=uuid.uuid4(), status="pending", file_path="/tmp/a.pdf", summary=None)
    session = _session_mock(doc)
    pages = [
        PageExtraction(
            page_number=1,
            blocks=[StructuredBlock("paragraph", "Текст страницы", page_number=1)],
            extraction_method="text_layer",
            confidence=1.0,
        )
    ]
    with (
        patch.object(
            worker,
            "AsyncSessionLocal",
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=session), __aexit__=AsyncMock()
            ),
        ),
        patch.object(worker, "extract_pages", return_value=pages),
        patch.object(
            worker,
            "chunk_pages",
            return_value=[
                {
                    "content": "Текст страницы",
                    "page_numbers": [1],
                    "headings": [],
                    "extraction_method": "text_layer",
                }
            ],
        ),
        patch.object(worker, "_embed_and_store_chunks", new=AsyncMock()),
        patch.object(worker, "generate_document_summary", new=AsyncMock(return_value="Конспект")),
        patch.object(worker, "save_summary_version", new=AsyncMock()),
        patch.object(worker, "invalidate_embedding_cache", new=AsyncMock()),
    ):
        await worker.async_process_document(str(doc.id), doc.file_path)

    assert doc.total_pages == 1
    assert doc.processed_pages == 1
    assert doc.status == "completed"


@pytest.mark.asyncio
async def test_process_document_image():
    doc = SimpleNamespace(id=uuid.uuid4(), status="pending", file_path="/tmp/a.png", summary=None)
    session = _session_mock(doc)
    pages = [
        PageExtraction(
            page_number=1,
            blocks=[StructuredBlock("paragraph", "Текст со скана", page_number=1)],
            extraction_method="ocr",
            confidence=0.8,
        )
    ]
    with (
        patch.object(
            worker,
            "AsyncSessionLocal",
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=session), __aexit__=AsyncMock()
            ),
        ),
        patch.object(worker, "extract_pages_from_image", return_value=pages),
        patch.object(
            worker,
            "chunk_pages",
            return_value=[
                {
                    "content": "Текст со скана",
                    "page_numbers": [1],
                    "headings": [],
                    "extraction_method": "ocr",
                }
            ],
        ),
        patch.object(worker, "_embed_and_store_chunks", new=AsyncMock()),
        patch.object(worker, "generate_document_summary", new=AsyncMock(return_value="Конспект")),
        patch.object(worker, "save_summary_version", new=AsyncMock()),
        patch.object(worker, "invalidate_embedding_cache", new=AsyncMock()),
    ):
        await worker.async_process_document(str(doc.id), doc.file_path)
    assert doc.status == "completed"


@pytest.mark.asyncio
async def test_process_document_skips_completed():
    doc = SimpleNamespace(id=uuid.uuid4(), status="completed")
    session = _session_mock(doc)
    with patch.object(
        worker,
        "AsyncSessionLocal",
        return_value=AsyncMock(__aenter__=AsyncMock(return_value=session), __aexit__=AsyncMock()),
    ):
        await worker.async_process_document(str(doc.id), "/tmp/a.pdf")
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_document_failure_marks_failed():
    doc = SimpleNamespace(id=uuid.uuid4(), status="pending", file_path="/tmp/a.txt", summary=None)
    session = _session_mock(doc)
    with (
        patch.object(
            worker,
            "AsyncSessionLocal",
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=session), __aexit__=AsyncMock()
            ),
        ),
        patch.object(worker, "extract_text_from_file", side_effect=RuntimeError("parse failed")),
    ):
        await worker.async_process_document(str(doc.id), doc.file_path)
    assert doc.status == "failed"
    session.commit.assert_awaited()
