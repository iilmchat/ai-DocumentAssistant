"""S1 / T9: ограничение частоты запросов.

T9: при включённом Redis limiter использует общий storage — лимиты действуют
одинаково для всех процессов uvicorn (in-memory считал бы каждого по отдельности).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings


def _make_limiter() -> Limiter:
    if settings.RATE_LIMIT_REDIS:
        # slowapi принимает storage_uri (redis://...), сам создаст RedisStorage
        return Limiter(
            key_func=get_remote_address,
            storage_uri=settings.CELERY_BROKER_URL,
        )
    return Limiter(key_func=get_remote_address)


limiter = _make_limiter()
