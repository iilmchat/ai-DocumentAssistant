"""T10: покрытие cache.py — файловые кэши с фейковым Redis."""

from unittest.mock import patch

import pytest

from app.core import cache


class FakeRedis:
    """Мини-реализация Redis на словаре."""

    def __init__(self, fail=False):
        self.store: dict[str, str] = {}
        self.fail = fail

    async def get(self, key):
        if self.fail:
            raise ConnectionError("redis down")
        return self.store.get(key)

    async def setex(self, key, ttl, value):
        if self.fail:
            raise ConnectionError("redis down")
        self.store[key] = str(value)

    async def exists(self, key):
        if self.fail:
            raise ConnectionError("redis down")
        return int(key in self.store)

    async def incr(self, key):
        if self.fail:
            raise ConnectionError("redis down")
        value = int(self.store.get(key, "0")) + 1
        self.store[key] = str(value)
        return value

    async def expire(self, key, ttl):
        if self.fail:
            raise ConnectionError("redis down")

    async def delete(self, key):
        if self.fail:
            raise ConnectionError("redis down")
        self.store.pop(key, None)


@pytest.fixture
def fake_redis():
    return FakeRedis()


@pytest.mark.asyncio
async def test_blacklist_roundtrip(fake_redis):
    with patch.object(cache, "redis_client", fake_redis):
        await cache.blacklist_jti("jti1", 9999999999)
        assert await cache.is_jti_blacklisted("jti1") is True
        assert await cache.is_jti_blacklisted("other") is False


@pytest.mark.asyncio
async def test_blacklist_fails_open(fake_redis):
    with patch.object(cache, "redis_client", FakeRedis(fail=True)):
        assert await cache.is_jti_blacklisted("jti1") is False


@pytest.mark.asyncio
async def test_login_attempts(fake_redis):
    with patch.object(cache, "redis_client", fake_redis):
        assert await cache.register_failed_login("login:key") == 1
        assert await cache.register_failed_login("login:key") == 2
        await cache.clear_failed_logins("login:key")
        assert await cache.register_failed_login("login:key") == 1


@pytest.mark.asyncio
async def test_login_attempts_fail_open():
    with patch.object(cache, "redis_client", FakeRedis(fail=True)):
        assert await cache.register_failed_login("key") == 0
        await cache.clear_failed_logins("key")


@pytest.mark.asyncio
async def test_embedding_cache_roundtrip(fake_redis):
    with patch.object(cache, "redis_client", fake_redis):
        assert await cache.get_cached_embedding("hello") is None
        await cache.set_cached_embedding("hello", [0.1, 0.2])
        assert await cache.get_cached_embedding("hello") == [0.1, 0.2]
        assert await cache.get_embedding_version() == "0"
        await cache.invalidate_embedding_cache()
        assert await cache.get_embedding_version() == "1"
        assert await cache.get_cached_embedding("hello") is None


@pytest.mark.asyncio
async def test_translation_cache_roundtrip(fake_redis):
    with patch.object(cache, "redis_client", fake_redis):
        assert await cache.get_cached_translation("hello", "ru") is None
        await cache.set_cached_translation("hello", "ru", "привет")
        assert await cache.get_cached_translation("hello", "ru") == "привет"
        assert await cache.get_cached_translation("hello", "de") is None
        await cache.invalidate_translation_cache()
        assert await cache.get_cached_translation("hello", "ru") is None


@pytest.mark.asyncio
async def test_cache_fails_open():
    with patch.object(cache, "redis_client", FakeRedis(fail=True)):
        assert await cache.get_cached_embedding("x") is None
        assert await cache.get_embedding_version() == "0"
        assert await cache.get_cached_translation("x", "ru") is None
        await cache.set_cached_embedding("x", [1.0])
        await cache.set_cached_translation("x", "ru", "y")
        await cache.invalidate_embedding_cache()
        await cache.invalidate_translation_cache()
