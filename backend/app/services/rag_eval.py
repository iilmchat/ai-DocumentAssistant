"""T7: онлайн-оценка качества ответа без вызова LLM (дешёвые эвристики).

Faithfulness — доля значимых слов ответа, присутствующих в контексте.
Answer relevance — доля значимых слов вопроса, отражённых в ответе.
Обе метрики в [0,1]; триггерят алерт при систематической просадке.
"""

import re

from app.core.config import settings
from app.core.metrics import RAG_ANSWER_RELEVANCE, RAG_FAITHFULNESS, RAG_LOW_QUALITY

_STOPWORDS = {
    "и",
    "в",
    "во",
    "не",
    "что",
    "это",
    "по",
    "на",
    "с",
    "со",
    "как",
    "каковы",
    "или",
    "для",
    "от",
    "до",
    "при",
    "о",
    "об",
    "он",
    "она",
    "оно",
    "ее",
    "его",
    "был",
    "была",
    "the",
    "is",
    "of",
    "to",
    "in",
    "for",
    "a",
    "and",
    "or",
    "on",
    "with",
    "what",
    "how",
}


def _tokens(text: str) -> set[str]:
    return {
        token.lower().strip(".,!?():;«»\"'—-")
        for token in re.split(r"\s+", text or "")
        if len(token) > 3 and token.lower() not in _STOPWORDS
    }


def faithfulness(answer: str, context: str) -> float:
    tokens = _tokens(answer)
    if not tokens:
        return 0.0
    haystack = context.lower()
    return sum(1 for token in tokens if token in haystack) / len(tokens)


def answer_relevance(question: str, answer: str) -> float:
    tokens = _tokens(question)
    if not tokens:
        return 0.0
    haystack = answer.lower()
    return sum(1 for token in tokens if token in haystack) / len(tokens)


def evaluate_answer(question: str, answer: str, context: str) -> dict[str, float]:
    """Считает метрики и обновляет Prometheus. Возвращает словарь с оценками."""
    faithful = round(faithfulness(answer, context), 3)
    relevance = round(answer_relevance(question, answer), 3)
    if settings.RAG_EVAL_ENABLED:
        RAG_FAITHFULNESS.observe(faithful)
        RAG_ANSWER_RELEVANCE.observe(relevance)
        if (
            faithful < settings.RAG_MIN_FAITHFULNESS
            or relevance < settings.RAG_MIN_ANSWER_RELEVANCE
        ):
            RAG_LOW_QUALITY.inc()
    return {"faithfulness": faithful, "answer_relevance": relevance}
