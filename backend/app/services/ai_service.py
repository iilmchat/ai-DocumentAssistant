import asyncio

from openai import AsyncOpenAI

from app.core.config import settings

client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY,
    base_url=settings.OPENAI_BASE_URL,
)


async def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Генерация векторов фиксированной размерности (совпадает с колонкой vector(N))."""
    try:
        response = await client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=texts,
            dimensions=settings.EMBEDDING_DIM,
        )
    except Exception as exc:
        # Некоторые OpenAI-совместимые провайдеры (например, Gemini) не
        # поддерживают параметр dimensions — повторяем без него.
        if "dimension" not in str(exc).lower() and "400" not in str(exc):
            raise
        response = await client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=texts,
        )
    return [item.embedding for item in response.data]


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
    response = await client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": "Ты аналитик. Сожми предоставленный текст в краткую, плотную выжимку (не более 3-4 предложений), сохранив только ключевые факты, цифры и имена.",
            },
            {"role": "user", "content": f"Сделай выжимку из этого текста:\n\n{text_block}"},
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

    response = await client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": "Ты профессиональный редактор. На основе предоставленных выжимок из разных частей документа составь единый, логичный и структурированный умный конспект. Используй маркдаун списки и выделения.",
            },
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
        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "Составь подробный и структурированный умный конспект по предоставленному тексту.",
                },
                {"role": "user", "content": f"Текст документа:\n{full_context}"},
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
