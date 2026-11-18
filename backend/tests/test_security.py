from unittest.mock import AsyncMock, patch

import pytest

from app.core import cache
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_password_hash_and_verify():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)
    assert not verify_password("secret123", "not-a-hash")


def test_access_token_roundtrip():
    token = create_access_token("123e4567-e89b-12d3-a456-426614174000")
    assert decode_access_token(token) == "123e4567-e89b-12d3-a456-426614174000"


def test_invalid_token_returns_none():
    assert decode_access_token("garbage") is None


def test_refresh_token_has_correct_type():
    token = create_refresh_token("user-id")
    payload = decode_token(token, "refresh")
    assert payload is not None
    assert payload["sub"] == "user-id"
    assert "jti" in payload
    # access-токен не должен принимать refresh-токен
    assert decode_token(token, "access") is None
    assert decode_access_token(create_access_token("user-id")) == "user-id"


@pytest.mark.asyncio
async def test_blacklist_roundtrip():
    fake = AsyncMock()
    fake.setex.return_value = True
    fake.exists.return_value = 1
    with patch.object(cache, "redis_client", fake):
        await cache.blacklist_jti("jti-1", 9999999999)
        assert await cache.is_jti_blacklisted("jti-1")
    fake.setex.assert_awaited_once()
    assert fake.setex.await_args.args[0] == "auth:blacklist:jti-1"


@pytest.mark.asyncio
async def test_blacklist_fails_open_when_redis_down():
    fake = AsyncMock()
    fake.exists.side_effect = ConnectionError("redis down")
    with patch.object(cache, "redis_client", fake):
        assert await cache.is_jti_blacklisted("jti-1") is False
