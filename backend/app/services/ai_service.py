from openai import AsyncOpenAI
from app.core.config import settings

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

async def generate_embeddings(texts: list[str]) -> list[list[float]]:
    response = await client.embeddings.create(
        model=settings.EMBEDDING_MODEL,
        input=texts,
        dimensions=settings.EMBEDDING_DIM,  # фиксируем размерность под колонку vector(N)
    )
    return [item.embedding for item in response.data]

async def generate_document_summary(full_text: str) -> str:
    prompt = (
        "Проанализируй следующий текст документа и составь подробный умный конспект. "
        "Выдели главные тезисы, ключевые выводы и основные понятия.\n\n"
        f"Текст документа:\n{full_text[:15000]}..."
    )
    
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Ты профессиональный аналитик, который умеет делать четкие структурированные конспекты."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    return response.choices[0].message.content
