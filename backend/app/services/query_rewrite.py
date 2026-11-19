"""T7: query rewriting и multi-query retrieval для сложных вопросов."""

from app.core.config import settings
from app.core.metrics import LLM_CALLS, LLM_LATENCY
from app.core.prompts import render
from app.services.ai_service import _resilient_call, client, llm_breaker


async def rewrite_query(question: str) -> str:
    """Переформулирует вопрос в более поисковый вид (векторизация точнее)."""
    import time

    started = time.perf_counter()
    try:
        response = await _resilient_call(
            llm_breaker,
            "query_rewrite",
            client.chat.completions.create,
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": render("rewrite_system")},
                {"role": "user", "content": render("rewrite_user", question=question)},
            ],
            temperature=0,
            max_tokens=200,
        )
        return (response.choices[0].message.content or "").strip() or question
    except Exception:
        LLM_CALLS.labels("query_rewrite", "error").inc()
        return question
    finally:
        LLM_LATENCY.labels("query_rewrite").observe(time.perf_counter() - started)
