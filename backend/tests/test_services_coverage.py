"""T10: покрытие usage, storage, audit, celery-задач."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.circuit_breaker import CircuitBreaker
from app.services import audit, storage, usage
from app.services.usage import estimate_cost, record_usage


@pytest.mark.asyncio
async def test_record_usage_with_last_usage():
    db = AsyncMock()
    payload = {
        "prompt_tokens": 100,
        "completion_tokens": 50,
        "total_tokens": 150,
        "model": "test-model",
    }
    with patch.object(usage, "get_last_usage", return_value=payload):
        row = await record_usage(db, uuid.uuid4(), uuid.uuid4(), "chat")
    assert row is not None
    assert row.total_tokens == 150
    db.add.assert_called_once()
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_record_usage_without_data():
    db = AsyncMock()
    with patch.object(usage, "get_last_usage", return_value=None):
        row = await record_usage(db, uuid.uuid4())
    assert row is None
    db.add.assert_not_called()


def test_cost_estimation():
    from app.core.config import settings

    assert estimate_cost(0, 0) == 0.0
    old_in, old_out = settings.LLM_COST_PER_1K_INPUT, settings.LLM_COST_PER_1K_OUTPUT
    try:
        settings.LLM_COST_PER_1K_INPUT = 0.01
        settings.LLM_COST_PER_1K_OUTPUT = 0.03
        assert round(estimate_cost(1000, 1000), 4) == 0.04
    finally:
        settings.LLM_COST_PER_1K_INPUT = old_in
        settings.LLM_COST_PER_1K_OUTPUT = old_out


@pytest.mark.asyncio
async def test_audit_forwards_to_siem():
    from app.core.config import settings

    db = AsyncMock()
    old_url = settings.AUDIT_WEBHOOK_URL
    fake_client = AsyncMock()
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=None)
    try:
        settings.AUDIT_WEBHOOK_URL = "https://siem.example.com/hook"
        with patch.object(audit.httpx, "AsyncClient", return_value=fake_client):
            await audit.log_action(db, uuid.uuid4(), "login", ip_address="127.0.0.1")
        fake_client.post.assert_awaited_once()
    finally:
        settings.AUDIT_WEBHOOK_URL = old_url
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_audit_siem_failure_is_best_effort():
    from app.core.config import settings

    db = AsyncMock()
    old_url = settings.AUDIT_WEBHOOK_URL
    fake_client = AsyncMock()
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=None)
    fake_client.post.side_effect = RuntimeError("siem down")
    try:
        settings.AUDIT_WEBHOOK_URL = "https://siem.example.com/hook"
        with patch.object(audit.httpx, "AsyncClient", return_value=fake_client):
            await audit.log_action(db, uuid.uuid4(), "login")
    finally:
        settings.AUDIT_WEBHOOK_URL = old_url


def test_storage_local_presigned_none():
    assert storage.LocalStorage().presigned_url("x") is None


def test_storage_s3_mocked():
    fake_client = MagicMock()
    fake_client.head_bucket.return_value = {}
    with patch("boto3.client", return_value=fake_client):
        backend = storage.S3Storage()
    assert backend.bucket
    fake_client.upload_fileobj.assert_not_called()
    backend.save("key", b"data")
    fake_client.upload_fileobj.assert_called_once()
    fake_client.delete_object.assert_not_called()
    backend.delete("key")
    fake_client.delete_object.assert_called_once()


def test_circuit_breaker_reset():
    breaker = CircuitBreaker("test", failure_threshold=1, cooldown_seconds=99)

    async def fail():
        raise RuntimeError("down")

    import asyncio

    with pytest.raises(RuntimeError):
        asyncio.run(breaker.call(fail))
    assert breaker.is_open
    breaker.reset()
    assert not breaker.is_open
