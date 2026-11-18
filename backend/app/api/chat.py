"""RAG-чат. Этап 5: гибридный поиск pgvector + Postgres FTS (russian) с Reciprocal Rank Fusion.

Этап 1: ответ сопровождается цитатами с номерами страниц — пользователь может
проверить утверждение модели по первоисточнику.
Этап 6: /stream отдаёт ответ токенами через SSE вместо имитации печати на фронте.
"""

import json
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.api.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import NotFoundError
from app.models.models import Document, User
from app.schemas.schemas import SourceCitation
from app.services.ai_service import client, ensure_embedding_dim, generate_embeddings

router = APIRouter(prefix="/api/v1/chat", tags=["Chat & RAG"])


class ChatRequest(BaseModel):
    document_id: uuid.UUID
    question: str
    top_k: int = 6


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]  # обратная совместимость со старым фронтом
    citations: list[SourceCitation]


async def _vector_search(db: AsyncSession, doc_id: str, q_vec: str, limit: int):
    rows = await db.execute(
        sql_text("""
        SELECT id, content, page_numbers, headings, extraction_method
        FROM document_chunks
        WHERE document_id = :doc_id
        ORDER BY embedding <=> CAST(:q_vec AS vector)
        LIMIT :limit
    """),
        {"doc_id": doc_id, "q_vec": q_vec, "limit": limit},
    )
    return rows.fetchall()


async def _fts_search(db: AsyncSession, doc_id: str, question: str, limit: int):
    """Полнотекстовый поиск под русскую конфигурацию — ловит номера договоров, артикулы, фамилии."""
    try:
        rows = await db.execute(
            sql_text("""
            SELECT id, content, page_numbers, headings, extraction_method,
                   ts_rank(search_vector, websearch_to_tsquery('russian', :q)) AS rank
            FROM document_chunks
            WHERE document_id = :doc_id AND search_vector @@ websearch_to_tsquery('russian', :q)
            ORDER BY rank DESC
            LIMIT :limit
        """),
            {"doc_id": doc_id, "q": question, "limit": limit},
        )
        return rows.fetchall()
    except Exception:
        await db.rollback()
        return []


def reciprocal_rank_fusion(*rankings, k: int = 60) -> list:
    """RRF: score = sum(1 / (k + rank_i)). Объединяем векторный и текстовый ранкинги."""
    scores: dict = {}
    items: dict = {}
    for ranking in rankings:
        for rank, row in enumerate(ranking, start=1):
            key = row[0]  # chunk id
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            items[key] = row
    return sorted(items.values(), key=lambda r: scores[r[0]], reverse=True)


def _build_prompt(context: str, question: str) -> str:
    return (
        "Используя следующий контекст из документа, ответь на вопрос пользователя. "
        "Контекст содержит метки страниц вида [стр. N]. ОБЯЗАТЕЛЬНО указывай ссылки на страницы "
        "в конце каждого утверждения в формате (стр. N). Если ответа в контексте нет — прямо скажи об этом.\n\n"
        f"Контекст:\n{context}\n\nВопрос: {question}"
    )


def _messages(question: str, context: str) -> list[ChatCompletionMessageParam]:
    return [
        {
            "role": "system",
            "content": "Ты внимательный ассистент по документам. Отвечай только по контексту, цитируй страницы.",
        },
        {"role": "user", "content": _build_prompt(context, question)},
    ]


async def _retrieve_context(payload: ChatRequest, db: AsyncSession, current_user: User):
    """Общая часть для /ask и /stream: поиск + сборка контекста и цитат."""
    doc_res = await db.execute(
        select(Document).where(
            Document.id == payload.document_id,
            Document.user_id == current_user.id,
        )
    )
    if not doc_res.scalars().first():
        raise NotFoundError("Документ не найден.")

    fetch_k = max(settings.RERANK_TOP_K // 5, payload.top_k * 3)
    q_embeddings = await generate_embeddings([payload.question])
    question_vector = ensure_embedding_dim(q_embeddings[0])
    vec_rows = await _vector_search(db, str(payload.document_id), str(question_vector), fetch_k)
    fts_rows = await _fts_search(db, str(payload.document_id), payload.question, fetch_k)
    fused = reciprocal_rank_fusion(vec_rows, fts_rows, k=settings.RRF_K)[: payload.top_k]

    if not fused:
        return None

    context_parts, citations = [], []
    for row in fused:
        _, content, page_numbers, headings, method = row[:5]
        pages = page_numbers or []
        ctx_header = f"[стр. {', '.join(map(str, pages))}]" if pages else "[документ]"
        context_parts.append(f"{ctx_header}\n{content}")
        citations.append(
            SourceCitation(
                page_numbers=list(pages),
                headings=list(headings or []),
                snippet=content[:200],
                extraction_method=method,
            )
        )

    return "\n\n---\n\n".join(context_parts), citations


@router.post("/ask", response_model=ChatResponse)
async def ask_question(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    prepared = await _retrieve_context(payload, db, current_user)
    if prepared is None:
        return ChatResponse(
            answer="Не удалось найти релевантную информацию в документе.",
            sources=[],
            citations=[],
        )

    context, citations = prepared
    response = await client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=_messages(payload.question, context),
        temperature=0.2,
    )
    return ChatResponse(
        answer=response.choices[0].message.content or "",
        sources=[c.snippet for c in citations],
        citations=citations,
    )


@router.post("/stream")
async def stream_answer(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Этап 6: стриминг ответа LLM. Сначала шлём цитаты, затем токены, затем done."""
    prepared = await _retrieve_context(payload, db, current_user)

    async def gen():
        if prepared is None:
            yield 'event: error\ndata: "Не удалось найти релевантную информацию в документе."\n\n'
            return

        context, citations = prepared
        yield (
            "event: citations\ndata: "
            + json.dumps([c.model_dump() for c in citations], ensure_ascii=False)
            + "\n\n"
        )

        try:
            stream = await client.chat.completions.create(
                model=settings.LLM_MODEL,
                messages=_messages(payload.question, context),
                temperature=0.2,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    yield (
                        "event: token\ndata: "
                        + json.dumps({"delta": delta}, ensure_ascii=False)
                        + "\n\n"
                    )
        except Exception as exc:
            yield (
                "event: error\ndata: "
                + json.dumps({"message": str(exc)}, ensure_ascii=False)
                + "\n\n"
            )
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
