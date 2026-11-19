"""RAG-чат. Этап 5: гибридный поиск pgvector + Postgres FTS (russian) с Reciprocal Rank Fusion.

Этап 1: ответ сопровождается цитатами с номерами страниц — пользователь может
проверить утверждение модели по первоисточнику.
Этап 6: /stream отдаёт ответ токенами через SSE вместо имитации печати на фронте.
"""

import json
import uuid

from fastapi import APIRouter, Depends, Request
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
from app.core.flags import is_enabled
from app.core.metrics import RAG_QUERIES, SEARCH_LATENCY
from app.core.prompts import render
from app.core.rate_limit import limiter
from app.models.models import Document, User
from app.schemas.schemas import SourceCitation
from app.services.ai_service import (
    _resilient_call,
    client,
    ensure_embedding_dim,
    generate_embeddings,
    llm_breaker,
)
from app.services.context import build_context
from app.services.query_rewrite import rewrite_query
from app.services.rag_eval import evaluate_answer
from app.services.reranker import rerank_chunks
from app.services.usage import record_usage

router = APIRouter(prefix="/api/v1/chat", tags=["Chat & RAG"])


class ChatRequest(BaseModel):
    document_id: uuid.UUID
    question: str
    top_k: int = 6


class ChatResponse(BaseModel):
    answer: str
    sources: list[str]  # обратная совместимость со старым фронтом
    citations: list[SourceCitation]


async def _vector_search(
    db: AsyncSession, doc_id: str, q_vec: str, limit: int, *, translated: bool = False
):
    import time

    started = time.perf_counter()
    if settings.USE_ANN_INDEX:
        await db.execute(
            sql_text("SET LOCAL hnsw.ef_search = :ef"),
            {"ef": settings.HNSW_EF_SEARCH},
        )
    column = "embedding_translated" if translated else "embedding"
    # T6: при поиске по переводу отдаём переведённый текст в колонке content
    content = "content_translated" if translated else "content"
    rows = await db.execute(
        sql_text(f"""
        SELECT id, {content} AS content, page_numbers, headings, extraction_method
        FROM document_chunks
        WHERE document_id = :doc_id AND {column} IS NOT NULL
        ORDER BY {column} <=> CAST(:q_vec AS vector)
        LIMIT :limit
    """),
        {"doc_id": doc_id, "q_vec": q_vec, "limit": limit},
    )
    SEARCH_LATENCY.observe(time.perf_counter() - started)
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
    return render("rag_user", context=context, question=question)


def _messages(question: str, context: str) -> list[ChatCompletionMessageParam]:
    return [
        {"role": "system", "content": render("rag_system")},
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
    doc = doc_res.scalars().first()
    if not doc:
        raise NotFoundError("Документ не найден.")

    RAG_QUERIES.inc()
    fetch_k = max(settings.RERANK_TOP_K // 5, payload.top_k * 3)

    # T7: опциональный query rewriting (управляется фича-флагом)
    search_query = payload.question
    if await is_enabled("query_rewriting"):
        search_query = await rewrite_query(payload.question)

    q_embeddings = await generate_embeddings([search_query])
    question_vector = ensure_embedding_dim(q_embeddings[0])
    vec_rows = await _vector_search(db, str(payload.document_id), str(question_vector), fetch_k)
    fts_rows = await _fts_search(db, str(payload.document_id), payload.question, fetch_k)

    # T6: если у документа есть перевод — ищем и по нему, объединяя RRF
    rankings = [vec_rows, fts_rows]
    if doc and doc.translation_language:
        translated_rows = await _vector_search(
            db, str(payload.document_id), str(question_vector), fetch_k, translated=True
        )
        rankings.append(translated_rows)

    candidates = reciprocal_rank_fusion(*rankings, k=settings.RRF_K)[: settings.RERANK_TOP_K]
    if settings.RERANK_ENABLED and len(candidates) > payload.top_k:
        fused = await rerank_chunks(payload.question, candidates, payload.top_k)
    else:
        fused = candidates[: payload.top_k]

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

    return build_context(context_parts), citations


@router.post("/ask", response_model=ChatResponse)
@limiter.limit(settings.CHAT_RATE_LIMIT)
async def ask_question(
    request: Request,
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
    response = await _resilient_call(
        llm_breaker,
        "chat",
        client.chat.completions.create,
        model=settings.LLM_MODEL,
        messages=_messages(payload.question, context),
        temperature=0.2,
    )
    answer = response.choices[0].message.content or ""
    evaluate_answer(payload.question, answer, context)
    await record_usage(db, current_user.id, payload.document_id, "chat")
    await db.commit()
    return ChatResponse(
        answer=answer,
        sources=[c.snippet for c in citations],
        citations=citations,
    )


@router.post("/stream")
@limiter.limit(settings.CHAT_RATE_LIMIT)
async def stream_answer(
    request: Request,
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Этап 6: стриминг ответа LLM. Сначала шлём цитаты, затем токены, затем done."""
    prepared = await _retrieve_context(payload, db, current_user)

    async def gen():
        import time

        started = time.monotonic()
        heartbeat_at = started + 15

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
            stream = await _resilient_call(
                llm_breaker,
                "chat_stream",
                client.chat.completions.create,
                model=settings.LLM_MODEL,
                messages=_messages(payload.question, context),
                temperature=0.2,
                stream=True,
                stream_options={"include_usage": True},
            )
            async for chunk in stream:
                if await request.is_disconnected():
                    return
                if time.monotonic() - started > 300:
                    yield 'event: error\ndata: "stream timeout"\n\n'
                    return
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    yield (
                        "event: token\ndata: "
                        + json.dumps({"delta": delta}, ensure_ascii=False)
                        + "\n\n"
                    )
                usage = getattr(chunk, "usage", None)
                if usage and getattr(usage, "total_tokens", None):
                    from app.services.ai_service import _last_usage

                    _last_usage.set(
                        {
                            "prompt_tokens": usage.prompt_tokens or 0,
                            "completion_tokens": usage.completion_tokens or 0,
                            "total_tokens": usage.total_tokens,
                            "model": settings.LLM_MODEL,
                        }
                    )
                if time.monotonic() >= heartbeat_at:
                    yield ": heartbeat\n\n"
                    heartbeat_at = time.monotonic() + 15
        except Exception as exc:
            yield (
                "event: error\ndata: "
                + json.dumps({"message": str(exc)}, ensure_ascii=False)
                + "\n\n"
            )
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as usage_db:
            await record_usage(usage_db, current_user.id, payload.document_id, "chat_stream")
            await usage_db.commit()
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
