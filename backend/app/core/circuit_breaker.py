"""S2: простой async circuit breaker для внешних LLM/embedding API."""

import asyncio
import time


class CircuitOpenError(Exception):
    """Вызывается, когда движок временно открыт из-за серии ошибок."""


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5, cooldown_seconds: int = 60):
        self.name = name
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._failures = 0
        self._opened_at = 0.0
        self._lock = asyncio.Lock()

    @property
    def is_open(self) -> bool:
        if self._opened_at == 0.0:
            return False
        if time.monotonic() - self._opened_at >= self.cooldown_seconds:
            self._opened_at = 0.0
            self._failures = 0
            return False
        return True

    async def call(self, func, *args, **kwargs):
        if self.is_open:
            raise CircuitOpenError(f"Circuit '{self.name}' is open")
        try:
            return await func(*args, **kwargs)
        except CircuitOpenError:
            raise
        except Exception:
            async with self._lock:
                self._failures += 1
                if self._failures >= self.failure_threshold:
                    self._opened_at = time.monotonic()
            raise
        else:
            async with self._lock:
                self._failures = 0
