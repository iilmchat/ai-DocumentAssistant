"""T7: тесты онлайн-оценки, сжатия контекста и feature flags."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core import flags
from app.services import query_rewrite
from app.services.ai_service import llm_breaker
from app.services.context import compress_context
from app.services.rag_eval import answer_relevance, evaluate_answer, faithfulness


@pytest.fixture(autouse=True)
def _reset_breaker():
    llm_breaker.reset()


def test_faithfulness_and_relevance():
    context = "Договор оплачивается в течение 5 банковских дней после подписания акта."
    answer = "Оплата в течение 5 банковских дней (стр. 1)."
    assert faithfulness(answer, context) > 0.5
    assert answer_relevance("Каковы сроки оплаты по договору?", answer) >= 0.0
    report = evaluate_answer("Каковы сроки оплаты?", answer, context)
    assert 0 <= report["faithfulness"] <= 1
    assert 0 <= report["answer_relevance"] <= 1


def test_empty_answers():
    assert faithfulness("", "context") == 0.0
    assert answer_relevance("вопрос", "") == 0.0


def test_compress_context():
    chunks = ["a" * 5000, "b" * 100]
    result = compress_context(chunks, max_chars=1000)
    assert len(result[0]) < 5000
    assert "…" in result[0]
    assert result[1] == "b" * 100


@pytest.mark.asyncio
async def test_flags_default_and_set():
    fake = AsyncMock()
    fake.get.return_value = None
    with patch.object(flags, "redis_client", fake):
        assert await flags.is_enabled("query_rewriting") is False
        assert await flags.get_flag("prompt_version") == "v1"


@pytest.mark.asyncio
async def test_rewrite_query_fallback():
    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="переписанный запрос"))]
    )
    with patch.object(
        query_rewrite.client.chat.completions,
        "create",
        new=AsyncMock(return_value=completion),
    ):
        assert await query_rewrite.rewrite_query("的原 вопрос") == "переписанный запрос"


@pytest.mark.asyncio
async def test_rewrite_query_on_error_returns_original():
    with patch.object(
        query_rewrite.client.chat.completions,
        "create",
        new=AsyncMock(side_effect=RuntimeError("down")),
    ):
        assert await query_rewrite.rewrite_query("исходный вопрос") == "исходный вопрос"
