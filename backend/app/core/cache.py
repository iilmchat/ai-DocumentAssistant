"""Redis-клиент для auth-утилит (чёрный список токенов, блокировки логина)."""

import logging
import time

import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)

redis_client = redis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)


async def blacklist_jti(jti: str, expires_at: int) -> None:
    """Помечаем access-токен отозванным до момента его естественного истечения."""
    ttl = max(1, int(expires_at - time.time()))
    await redis_client.setex(f"auth:blacklist:{jti}", ttl, "1")


async def is_jti_blacklisted(jti: str) -> bool:
    try:
        return bool(await redis_client.exists(f"auth:blacklist:{jti}"))
    except Exception as exc:  # Redis недоступен — не блокируем авторизацию целиком
        logger.warning("Redis blacklist unavailable: %s", exc)
        return False


async def register_failed_login(key: str) -> int:
    """Возвращает число неудачных попыток за окно блокировки."""
    try:
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, settings.LOGIN_LOCKOUT_MINUTES * 60)
        return int(count)
    except Exception as exc:
        logger.warning("Redis login lockout unavailable: %s", exc)
        return 0


async def clear_failed_logins(key: str) -> None:
    try:
        await redis_client.delete(key)
    except Exception as exc:
        logger.warning("Redis login lockout unavailable: %s", exc)


# --- S3: кэш эмбеддингов с версионированием для инвалидации ---
CACHE_VERSION_KEY = "embedding:cache_version"


def _embedding_key(text: str) -> str:
    import hashlib

    digest = hashlib.sha256(f"{settings.EMBEDDING_MODEL}:{text}".encode()).hexdigest()
    return f"embedding:{digest}"


async def get_embedding_version() -> str:
    try:
        return await redis_client.get(CACHE_VERSION_KEY) or "0"
    except Exception as exc:
        logger.warning("Redis embedding cache unavailable: %s", exc)
        return "0"


async def get_cached_embedding(text: str) -> list[float] | None:
    try:
        version = await get_embedding_version()
        raw = await redis_client.get(f"{_embedding_key(text)}:{version}")
        if not raw:
            return None
        import json

        return json.loads(raw)
    except Exception as exc:
        logger.warning("Redis embedding cache unavailable: %s", exc)
        return None


async def set_cached_embedding(text: str, vector: list[float]) -> None:
    try:
        import json

        version = await get_embedding_version()
        await redis_client.setex(
            f"{_embedding_key(text)}:{version}",
            settings.EMBEDDING_CACHE_TTL_SECONDS,
            json.dumps(vector),
        )
    except Exception as exc:
        logger.warning("Redis embedding cache unavailable: %s", exc)


async def invalidate_embedding_cache() -> None:
    """Инкремент версии — все старые ключи становятся недосягаемыми."""
    try:
        new_version = await redis_client.incr(CACHE_VERSION_KEY)
        await redis_client.expire(CACHE_VERSION_KEY, 60 * 60 * 24 * 30)
        logger.info("embedding.cache_invalidated version=%s", new_version)
    except Exception as exc:
        logger.warning("Redis embedding cache unavailable: %s", exc)
