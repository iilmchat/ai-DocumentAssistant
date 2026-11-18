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
