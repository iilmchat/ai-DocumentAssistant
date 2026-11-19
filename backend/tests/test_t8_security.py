"""T8: PII, CSRF, RBAC, cookie-аутентификация."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core import csrf, pii
from app.core.config import settings
from app.core.database import get_db
from app.core.rbac import ROLE_LEVELS, require_role
from app.main import app

client = TestClient(app)


def test_pii_redaction():
    text = "Пишите на ivan@example.com или +7 999 123-45-67, карта 4111 1111 1111 1111, ИНН 7700000000."
    redacted = pii.redact_pii(text)
    assert "ivan@example.com" not in redacted
    assert "999 123" not in redacted
    assert "[EMAIL_1]" in redacted
    assert "[PHONE_1]" in redacted
    assert "[CARD_1]" in redacted or "[INN_1]" in redacted


def test_redact_messages():
    messages = [
        {"role": "user", "content": "email a@b.com"},
        {
            "role": "user",
            "content": [{"type": "text", "text": "phone +7 999 123-45-67"}],
        },
    ]
    result = pii.redact_messages(messages)
    assert "[EMAIL_1]" in result[0]["content"]
    assert "[PHONE_1]" in result[1]["content"][0]["text"]


def test_csrf_token_generated():
    token = csrf.generate_csrf_token()
    assert len(token) >= 32
    assert token != csrf.generate_csrf_token()


@pytest.mark.asyncio
async def test_csrf_allows_get_without_token():
    request = MagicMock()
    request.method = "GET"
    request.headers = {}
    await csrf.enforce_csrf(request)  # не должно бросать


@pytest.mark.asyncio
async def test_csrf_rejects_post_without_token():
    from fastapi import HTTPException

    request = MagicMock()
    request.method = "POST"
    request.headers = {}
    request.cookies = {}
    request.url.path = "/api/v1/documents"
    with pytest.raises(HTTPException) as exc:
        await csrf.enforce_csrf(request)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_csrf_allows_bearer():
    request = MagicMock()
    request.method = "POST"
    request.headers = {"authorization": "Bearer abc"}
    await csrf.enforce_csrf(request)


@pytest.mark.asyncio
async def test_csrf_double_submit():
    request = MagicMock()
    request.method = "DELETE"
    request.headers = {settings.CSRF_HEADER_NAME: "token123"}
    request.cookies = {settings.CSRF_COOKIE_NAME: "token123"}
    await csrf.enforce_csrf(request)


def test_rbac_levels():
    assert ROLE_LEVELS["viewer"] < ROLE_LEVELS["editor"] < ROLE_LEVELS["admin"]


@pytest.mark.asyncio
async def test_rbac_checker_denies_viewer():
    from fastapi import HTTPException

    checker = require_role("editor")
    viewer = SimpleNamespace(role="viewer")
    with pytest.raises(HTTPException) as exc:
        await checker(viewer)
    assert exc.value.status_code == 403
    admin = SimpleNamespace(role="admin")
    assert await checker(admin) is admin


def test_me_supports_cookie(monkeypatch):
    """Проверяем, что /me читает токен из cookie, если Bearer не передан."""
    payload = {
        "sub": "123e4567-e89b-12d3-a456-426614174000",
        "jti": "jti",
        "exp": 9999999999,
        "type": "access",
    }
    monkeypatch.setattr("app.api.auth.decode_token", lambda *_a, **_k: payload)
    monkeypatch.setattr("app.api.auth.is_jti_blacklisted", AsyncMock(return_value=False))
    fake_user = SimpleNamespace(
        id="123e4567-e89b-12d3-a456-426614174000",
        email="u@example.com",
        created_at=datetime(2026, 11, 1, tzinfo=UTC),
    )
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = fake_user
    mock_db.execute.return_value = mock_result

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_db
    try:
        response = client.get(
            "/api/v1/auth/me",
            cookies={settings.SESSION_COOKIE_ACCESS: "cookie-token"},
        )
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()
