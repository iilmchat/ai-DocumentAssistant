import asyncio
from typing import List
from openai import AsyncOpenAI
from app.core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

async def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Генерация векторов (остается без изменений)."""
    response = await client.embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=texts,
        dimensions=settings.EMBEDDING_DIM,  # фиксируем размерность под колонку vector(N)
    )
    return [item.embedding for item in response.data]

async def summarize_text_block(text_block: str) -> str:
    """Промежуточный шаг (Map): сжимает большой блок текста в короткую выжимку."""
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Ты аналитик. Сожми предоставленный текст в краткую, плотную выжимку (не более 3-4 предложений), сохранив только ключевые факты, цифры и имена."},
            {"role": "user", "content": f"Сделай выжимку из этого текста:\n\n{text_block}"}
        ],
        temperature=0.1,
        max_tokens=200
    )
    return response.choices[0].message.content

async def combine_summaries(summaries: List[str]) -> str:
    """Финальный шаг (Reduce): собирает все выжимки в один красивый конспект."""
    if not summaries:
        return "Не удалось сгенерировать конспект."
        
    combined_text = "\n\n".join([f"- {s}" for s in summaries])
    
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Ты профессиональный редактор. На основе предоставленных выжимок из разных частей документа составь единый, логичный и структурированный умный конспект. Используй маркдаун списки и выделения."},
            {"role": "user", "content": f"Выжимки из документа:\n{combined_text}\n\nСоставь финальный конспект:"}
        ],
        temperature=0.3,
        max_tokens=1000
    )
    return response.choices[0].message.content

async def generate_document_summary_from_chunks(chunks: List[str]) -> str:
    """
    Главная функция умной суммаризации.
    """
    if not chunks:
        return "Документ пуст."

    # Если документ небольшой (до 5 чанков), суммаризируем всё сразу без промежуточных шагов
    if len(chunks) <= 5:
        full_context = "\n\n---\n\n".join(chunks)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Составь подробный и структурированный умный конспект по предоставленному тексту."},
                {"role": "user", "content": f"Текст документа:\n{full_context}"}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        return response.choices[0].message.content

    # Для больших документов: разбиваем на батчи и запускаем параллельно
    BATCH_SIZE = 8 # Примерно 8 чанков * 1000 символов = 8000 символов на батч
    tasks = []
    
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i+BATCH_SIZE]
        batch_text = "\n\n".join(batch)
        tasks.append(summarize_text_block(batch_text))
    
    # Ждем выполнения всех промежуточных саммари
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Отфильтровываем ошибки
    valid_summaries = [r for r in results if not isinstance(r, Exception) and r.strip()]
    
    if not valid_summaries:
        return "Произошла ошибка при генерации конспекта."
        
    # Финальная сборка
    return await combine_summaries(valid_summaries)