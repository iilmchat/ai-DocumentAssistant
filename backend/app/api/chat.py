from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text
from app.core.database import get_db
from app.models.models import Document
from app.services.ai_service import generate_embeddings, client

router = APIRouter(prefix="/api/v1/chat", tags=["Chat & RAG"])

class ChatRequest(BaseModel):
    document_id: uuid.UUID
    question: str

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

    q_embeddings = await generate_embeddings([payload.question])
    question_vector = q_embeddings[0]

    query = text("""
        SELECT content 
        FROM document_chunks 
        WHERE document_id = :doc_id 
        ORDER BY embedding <=> :q_vec 
        LIMIT 4;
    """)
    
    result = await db.execute(query, {"doc_id": str(payload.document_id), "q_vec": str(question_vector)})
    relevant_chunks = [row[0] for row in result.fetchall()]

    if not relevant_chunks:
        return ChatResponse(answer="Не удалось найти релевантную информацию в документе.", sources=[])

    context = "\n\n---\n\n".join(relevant_chunks)
    prompt = (
        f"Используя следующий контекст из документа, ответь на вопрос пользователя. "
        f"Если ответа нет в контексте, честно скажи об этом.\n\n"
        f"Контекст:\n{context}\n\n"
        f"Вопрос: {payload.question}"
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
