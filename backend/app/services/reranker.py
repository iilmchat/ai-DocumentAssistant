"""S5: LLM-as-judge reranker поверх гибридного поиска."""

import json
import re

from app.core.config import settings
from app.core.logging import log
from app.core.metrics import RERANK_LATENCY
from app.core.prompts import render
from app.services.ai_service import _resilient_call, client, llm_breaker


def _extract_scores(text: str, count: int) -> list[float]:
    """Достаёт оценки из ответа модели; при ошибке возвращает нейтральные."""
    fallback = [5.0] * count
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return fallback
    try:
        data = json.loads(match.group(0))
        scores = fallback[:]
        for item in data:
            idx = int(item["index"])
            if 0 <= idx < count:
                scores[idx] = float(item["score"])
        return scores
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return fallback


async def rerank_chunks(question: str, chunks: list, top_k: int) -> list:
    """Переоценивает кандидатов и возвращает топ-K (аналог cross-encoder)."""
    import time

    if not chunks or top_k <= 0:
        return []
    started = time.perf_counter()
    try:
        numbered = "\n\n".join(f"[{i}] {row[1][:600]}" for i, row in enumerate(chunks))
        response = await _resilient_call(
            llm_breaker,
            "rerank",
            client.chat.completions.create,
            model=settings.RERANK_MODEL or settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": render("rerank_system")},
                {
                    "role": "user",
                    "content": render("rerank_user", question=question, chunks=numbered),
                },
            ],
            temperature=0,
            max_tokens=500,
        )
        text = response.choices[0].message.content or ""
        scores = _extract_scores(text, len(chunks))
        ranked = sorted(zip(chunks, scores, strict=True), key=lambda pair: pair[1], reverse=True)
        return [row for row, _ in ranked[:top_k]]
    except Exception as exc:
        log.warning("rerank.failed", error=str(exc))
        return list(chunks[:top_k])
    finally:
        RERANK_LATENCY.observe(time.perf_counter() - started)
