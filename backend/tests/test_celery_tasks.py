"""T10: покрытие celery-задач воркера."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import worker


def test_translate_document_task_success():
    task = MagicMock()
    task.name = "translate_document_task"
    task.request.retries = 0
    task.max_retries = 2
    doc_id, user_id = uuid.uuid4(), uuid.uuid4()
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch.object(worker, "AsyncSessionLocal", return_value=session),
        patch("app.services.document_translation.translate_document", new=AsyncMock()) as translate,
    ):
        worker.translate_document_task.run(str(doc_id), "ru", str(user_id))

    translate.assert_awaited_once()
    task.retry.assert_not_called()


def test_translate_document_task_error_path():
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch.object(worker, "AsyncSessionLocal", return_value=session),
        patch(
            "app.services.document_translation.translate_document",
            new=AsyncMock(side_effect=RuntimeError("llm down")),
        ),
    ):
        # celery retry бросает Retry — ожидаемое поведение
        with pytest.raises(RuntimeError):  # type: ignore[misc]  # прямой .run без celery context
            worker.translate_document_task.run(str(uuid.uuid4()), "ru", str(uuid.uuid4()))


def test_translate_document_task_dead_letter_path():
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    with (
        patch.object(worker, "AsyncSessionLocal", return_value=session),
        patch(
            "app.services.document_translation.translate_document",
            new=AsyncMock(side_effect=RuntimeError("fatal")),
        ),
        patch.object(worker.dead_letter_task, "delay") as dead,
        patch.object(worker.translate_document_task, "max_retries", 0),
    ):
        worker.translate_document_task.run(str(uuid.uuid4()), "ru", str(uuid.uuid4()))
    dead.assert_called_once()


def test_cleanup_retention_task():
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    with (
        patch.object(worker, "AsyncSessionLocal", return_value=session),
        patch.object(worker, "cleanup_retention", new=AsyncMock()) as cleanup,
    ):
        worker.cleanup_retention_task.run()
    cleanup.assert_awaited_once()


def test_dead_letter_task():
    with patch.object(worker.log, "error") as log_error:
        worker.dead_letter_task.run("doc-1", "scan.pdf", "boom", "req-1")
    log_error.assert_called_once()


def test_process_document_task_success():
    task = MagicMock()
    task.name = "process_document_task"
    task.request.retries = 0
    task.max_retries = 2
    with patch.object(worker, "async_process_document", new=AsyncMock()) as process:
        worker.process_document_task.run(str(uuid.uuid4()), "/tmp/a.pdf")
    process.assert_awaited_once()


def test_process_scanned_document_task_success():
    task = MagicMock()
    task.name = "process_scanned_document_task"
    task.request.retries = 0
    task.max_retries = 2
    with patch.object(worker, "async_process_document", new=AsyncMock()) as process:
        worker.process_scanned_document_task.run(str(uuid.uuid4()), "/tmp/a.pdf")
    process.assert_awaited_once()
