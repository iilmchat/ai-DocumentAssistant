import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
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

@router.post("/ask")
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
        async def empty_stream():
            yield f"data: {json.dumps({'type': 'token', 'content': 'Не удалось найти релевантную информацию в документе.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        return StreamingResponse(empty_stream(), media_type="text/event-stream")

    context = "\n\n---\n\n".join(relevant_chunks)
    prompt = (
        f"Используя следующий контекст из документа, ответь на вопрос пользователя. "
        f"Если ответа нет в контексте, честно скажи об этом.\n\n"
        f"Контекст:\n{context}\n\n"
        f"Вопрос: {payload.question}"
    )

    async def event_stream():
        # 1. Сначала отправляем источники (чтобы фронтенд мог их показать сразу)
        yield f"data: {json.dumps({'type': 'sources', 'sources': relevant_chunks})}\n\n"
        
        try:
            # 2. Запускаем потоковую генерацию от OpenAI
            stream = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Ты полезный AI-ассистент, который отвечает на вопросы строго по предоставленным фрагментам документов."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                stream=True
            )
            
            # 3. Транслируем каждый токен на фронтенд
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    yield f"data: {json.dumps({'type': 'token', 'content': content})}\n\n"
            
            # 4. Отправляем сигнал завершения
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")