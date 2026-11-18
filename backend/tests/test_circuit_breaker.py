import time

import pytest

from app.core.circuit_breaker import CircuitBreaker, CircuitOpenError


@pytest.mark.asyncio
async def test_breaker_passes_calls_when_healthy():
    breaker = CircuitBreaker("test", failure_threshold=2, cooldown_seconds=60)

    async def ok():
        return "result"

    assert await breaker.call(ok) == "result"
    assert not breaker.is_open


@pytest.mark.asyncio
async def test_breaker_opens_after_threshold_and_resets_after_cooldown():
    breaker = CircuitBreaker("test", failure_threshold=2, cooldown_seconds=60)

    async def fail():
        raise RuntimeError("provider down")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await breaker.call(fail)
    assert breaker.is_open

    with pytest.raises(CircuitOpenError):
        await breaker.call(fail)

    # имитируем истечение cooldown — цепь закроется при следующем обращении
    breaker._opened_at = time.monotonic() - 61
    assert not breaker.is_open
