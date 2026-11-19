import asyncio
import time
from contextvars import ContextVar

from openai import AsyncOpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.cache import get_cached_embedding, set_cached_embedding
from app.core.circuit_breaker import CircuitBreaker, CircuitOpenError
from app.core.config import settings
from app.core.metrics import LLM_CALLS, LLM_LATENCY, LLM_TOKENS
from app.core.prompts import render

client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY,
    base_url=settings.OPENAI_BASE_URL,
    timeout=30.0,
)

llm_breaker = CircuitBreaker("llm", failure_threshold=5, cooldown_seconds=60)

# S5: последнее usage каждого LLM-вызова (для учёта стоимости в роутере)
_last_usage: ContextVar[dict | None] = ContextVar("llm_last_usage", default=None)


def get_last_usage() -> dict | None:
    return _last_usage.get()


# Semaphore привязан к event loop: воркер создаёт новый loop на задачу
_llm_semaphores: dict[int, asyncio.Semaphore] = {}


def _get_llm_semaphore() -> asyncio.Semaphore:
    loop_id = id(asyncio.get_running_loop())
    if loop_id not in _llm_semaphores:
        _llm_semaphores[loop_id] = asyncio.Semaphore(settings.LLM_MAX_CONCURRENCY)
    return _llm_semaphores[loop_id]


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(Exception) & retry_if_not_exception_type(CircuitOpenError),
    reraise=True,
)
async def _resilient_call(breaker: CircuitBreaker, operation: str, func, *args, **kwargs):
    """S2: timeout + backoff + circuit breaker + метрики для внешних API."""
    started = time.perf_counter()
    # T8: маскируем PII во всех сообщениях, уходящих в LLM
    if "messages" in kwargs:
        from app.core.pii import redact_messages

        kwargs["messages"] = redact_messages(kwargs["messages"])
    try:
        async with _get_llm_semaphore():
            result = await breaker.call(func, *args, **kwargs)
        usage = getattr(result, "usage", None)
        tokens = getattr(usage, "total_tokens", None) if usage else None
        if tokens:
            LLM_TOKENS.labels(operation).inc(tokens)
            _last_usage.set(
                {
                    "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                    "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
                    "total_tokens": tokens,
                    "model": getattr(result, "model", settings.LLM_MODEL),
                }
            )
        LLM_CALLS.labels(operation, "success").inc()
        return result
    except CircuitOpenError:
        LLM_CALLS.labels(operation, "circuit_open").inc()
        raise
    except Exception:
        LLM_CALLS.labels(operation, "error").inc()
        raise
    finally:
        LLM_LATENCY.labels(operation).observe(time.perf_counter() - started)


async def _embeddings_call(texts: list[str]):
    try:
        return await client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=texts,
            dimensions=settings.EMBEDDING_DIM,
        )
    except Exception as exc:
        # Некоторые OpenAI-совместимые провайдеры (например, Gemini) не
        # поддерживают параметр dimensions — повторяем без него.
        if "dimension" not in str(exc).lower() and "400" not in str(exc):
            raise
        return await client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=texts,
        )


async def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Вектора фиксированной размерности с Redis-кэшем (S3)."""
    cached: list[list[float] | None] = [await get_cached_embedding(text) for text in texts]
    missing = [text for text, vector in zip(texts, cached, strict=True) if vector is None]
    if missing:
        response = await _resilient_call(llm_breaker, "embeddings", _embeddings_call, missing)
        vectors: list[list[float]] = [item.embedding for item in response.data]
        for text, vector in zip(missing, vectors, strict=True):
            await set_cached_embedding(text, vector)
        iterator = iter(vectors)
        cached = [vector if vector is not None else next(iterator) for vector in cached]
    return [vector for vector in cached if vector is not None]


def ensure_embedding_dim(embedding: list[float]) -> list[float]:
    """Ранняя проверка: неверная размерность ломает вставку в vector(N)."""
    expected = settings.EMBEDDING_DIM
    if len(embedding) != expected:
        raise ValueError(
            f"Embedding dimension mismatch: got {len(embedding)}, expected {expected}. "
            "Проверьте EMBEDDING_MODEL и EMBEDDING_DIM."
        )
    return embedding


async def summarize_text_block(text_block: str) -> str:
    """Промежуточный шаг (Map): сжимает большой блок текста в короткую выжимку."""
    response = await _resilient_call(
        llm_breaker,
        "chat",
        client.chat.completions.create,
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": render("summary_map_system")},
            {"role": "user", "content": render("summary_user", text=text_block)},
        ],
        temperature=0.1,
        max_tokens=500,
    )
    return response.choices[0].message.content or ""


async def combine_summaries(summaries: list[str]) -> str:
    """Финальный шаг (Reduce): собирает все выжимки в один красивый конспект."""
    if not summaries:
        return "Не удалось сгенерировать конспект."

    combined_text = "\n\n".join([f"- {s}" for s in summaries])

    response = await _resilient_call(
        llm_breaker,
        "chat",
        client.chat.completions.create,
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": render("summary_reduce_system")},
            {
                "role": "user",
                "content": f"Выжимки из документа:\n{combined_text}\n\nСоставь финальный конспект:",
            },
        ],
        temperature=0.3,
        max_tokens=2000,
    )
    return response.choices[0].message.content or ""


async def generate_document_summary_from_chunks(chunks: list[str]) -> str:
    """Умная суммаризация по чанкам: маленькие документы — сразу, большие — Map/Reduce."""
    if not chunks:
        return "Документ пуст."

    # Если документ небольшой (до 5 чанков), суммаризируем всё сразу без промежуточных шагов
    if len(chunks) <= 5:
        full_context = "\n\n---\n\n".join(chunks)
        response = await _resilient_call(
            llm_breaker,
            "chat",
            client.chat.completions.create,
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": render("summary_direct_system")},
                {"role": "user", "content": render("summary_direct_user", text=full_context)},
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        return response.choices[0].message.content or ""

    # Для больших документов: разбиваем на батчи и запускаем параллельно
    BATCH_SIZE = 8  # ~8 чанков * 1200 символов = ~9600 символов на батч
    tasks = [
        summarize_text_block("\n\n".join(chunks[i : i + BATCH_SIZE]))
        for i in range(0, len(chunks), BATCH_SIZE)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)
    valid_summaries = [r for r in results if isinstance(r, str) and r.strip()]

    if not valid_summaries:
        return "Произошла ошибка при генерации конспекта."

    return await combine_summaries(valid_summaries)


async def stream_document_summary(full_text: str):
    """S3-08: стриминг конспекта токенами (маленькие документы — сразу, большие — Map/Reduce)."""
    if not full_text or not full_text.strip():
        yield "Документ пуст."
        return

    context = full_text[:15000]
    if len(full_text) > 12000:
        parts = [full_text[i : i + 4000] for i in range(0, min(len(full_text), 48000), 4000)]
        maps = await asyncio.gather(*[summarize_text_block(part) for part in parts])
        context = "\n\n".join(part for part in maps if isinstance(part, str) and part.strip())

    stream = await _resilient_call(
        llm_breaker,
        "summary_stream",
        client.chat.completions.create,
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": render("summary_stream_system")},
            {"role": "user", "content": render("summary_stream_user", text=context)},
        ],
        temperature=0.3,
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta


async def generate_document_summary(full_text: str) -> str:
    """Совместимая обёртка для воркера: режет текст на чанки и зовёт Map/Reduce."""
    if not full_text or not full_text.strip():
        return "Документ пуст."

    chunk_size = 4000
    overlap = 200
    chunks: list[str] = []
    start = 0
    while start < len(full_text):
        chunks.append(full_text[start : start + chunk_size])
        start += chunk_size - overlap
    return await generate_document_summary_from_chunks(chunks)
