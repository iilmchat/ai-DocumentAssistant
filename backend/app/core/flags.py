"""T7: простые feature flags через Redis с локальным дефолтом.

Позволяют включать/выключать query rewriting и версии промптов без деплоя.
Значения хранятся в Redis (`feature:<name>`), дефолты — в этом модуле.
"""

from app.core.cache import redis_client

DEFAULTS: dict[str, str] = {
    "query_rewriting": "off",
    "prompt_version": "v1",
    "reranker": "on",
}


def _default(name: str) -> str:
    return DEFAULTS.get(name, "off")


async def get_flag(name: str) -> str:
    try:
        return (await redis_client.get(f"feature:{name}")) or _default(name)
    except Exception:
        return _default(name)


async def is_enabled(name: str) -> bool:
    return (await get_flag(name)).lower() in {"1", "true", "on", "yes"}


async def set_flag(name: str, value: str) -> None:
    await redis_client.set(f"feature:{name}", value)
