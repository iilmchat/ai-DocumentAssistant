from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.services import reranker
from app.services.reranker import _extract_scores, rerank_chunks


def _completion(text: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


def test_extract_scores():
    scores = _extract_scores('[{"index": 0, "score": 9}, {"index": 1, "score": 2}]', 3)
    assert scores[0] == 9.0
    assert scores[1] == 2.0
    assert scores[2] == 5.0
    assert _extract_scores("garbage", 2) == [5.0, 5.0]


@pytest.mark.asyncio
async def test_rerank_orders_candidates():
    chunks = [
        ("a", "мало релевантно", None, None, None),
        ("b", "очень релевантно", None, None, None),
        ("c", "середина", None, None, None),
    ]
    with patch.object(
        reranker.client.chat.completions,
        "create",
        new=AsyncMock(
            return_value=_completion(
                '[{"index": 0, "score": 1}, {"index": 1, "score": 10}, {"index": 2, "score": 5}]'
            )
        ),
    ):
        result = await rerank_chunks("вопрос", chunks, 2)
    assert [row[0] for row in result] == ["b", "c"]


@pytest.mark.asyncio
async def test_rerank_falls_back_on_error():
    chunks = [("a", "x", None, None, None), ("b", "y", None, None, None)]
    with patch.object(
        reranker.client.chat.completions,
        "create",
        new=AsyncMock(side_effect=RuntimeError("llm down")),
    ):
        result = await rerank_chunks("q", chunks, 1)
    assert result == [chunks[0]]


def test_cost_estimation():
    from app.services.usage import estimate_cost

    assert estimate_cost(0, 0) == 0.0
    assert estimate_cost(1000, 1000) >= 0.0
