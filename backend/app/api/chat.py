"""RAG-чат. Этап 5: гибридный поиск pgvector + Postgres FTS (russian) с Reciprocal Rank Fusion.

Этап 1: ответ сопровождается цитатами с номерами страниц — пользователь может
проверить утверждение модели по первоисточнику.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text as sql_text

from app.core.config import settings
from app.core.database import get_db
from app.models.models import Document
from app.schemas.schemas import SourceCitation
from app.services.ai_service import generate_embeddings, client

router = APIRouter(prefix="/api/v1/chat", tags=["Chat & RAG"])


class ChatRequest(BaseModel):
    document_id: uuid.UUID
    question: str
    top_k: int = 6


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]

@router.post("/ask", response_model=ChatResponse)
async def ask_question(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    doc_res = await db.execute(select(Document).where(Document.id == payload.document_id))
    doc = doc_res.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден.")

    fetch_k = max(settings.RERANK_TOP_K // 5, payload.top_k * 3)

    q_embeddings = await generate_embeddings([payload.question])
    question_vector = q_embeddings[0]

    vec_rows = await _vector_search(db, str(payload.document_id), str(question_vector), fetch_k)
    fts_rows = await _fts_search(db, str(payload.document_id), payload.question, fetch_k)

    fused = reciprocal_rank_fusion(vec_rows, fts_rows, k=settings.RRF_K)[: payload.top_k]

    if not relevant_chunks:
        return ChatResponse(answer="Не удалось найти релевантную информацию в документе.", sources=[])

    context_parts, citations = [], []
    for row in fused:
        _, content, page_numbers, headings, method = row[:5]
        pages = page_numbers or []
        ctx_header = f"[стр. {', '.join(map(str, pages))}]" if pages else "[документ]"
        context_parts.append(f"{ctx_header}\n{content}")
        citations.append(SourceCitation(
            page_numbers=list(pages),
            headings=list(headings or []),
            snippet=content[:200],
            extraction_method=method,
        ))

    context = "\n\n---\n\n".join(context_parts)
    prompt = (
        "Используя следующий контекст из документа, ответь на вопрос пользователя. "
        "Контекст содержит метки страниц вида [стр. N]. ОБЯЗАТЕЛЬНО указывай ссылки на страницы "
        "в конце каждого утверждения в формате (стр. N). Если ответа в контексте нет — прямо скажи об этом.\n\n"
        f"Контекст:\n{context}\n\nВопрос: {payload.question}"
    )

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Ты полезный AI-ассистент, который отвечает на вопросы строго по предоставленным фрагментам документов."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )
    
    answer = response.choices[0].message.content
    return ChatResponse(answer=answer, sources=relevant_chunks)
