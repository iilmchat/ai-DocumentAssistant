from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import settings
from app.services import ai_service


@pytest.fixture(autouse=True)
def _no_redis(monkeypatch):
    """Тесты не должны стучаться в Redis."""

    async def cached(_text):
        return None

    async def store(_text, _vector):
        return None

    monkeypatch.setattr(ai_service, "get_cached_embedding", cached)
    monkeypatch.setattr(ai_service, "set_cached_embedding", store)


def _embedding_response():
    return SimpleNamespace(data=[SimpleNamespace(embedding=[0.0] * settings.EMBEDDING_DIM)])


def _completion(text: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])


@pytest.mark.asyncio
async def test_generate_embeddings_uses_configured_dimension():
    with patch.object(
        ai_service.client.embeddings, "create", new=AsyncMock(return_value=_embedding_response())
    ) as mock:
        result = await ai_service.generate_embeddings(["question"])
    assert len(result[0]) == settings.EMBEDDING_DIM
    mock.assert_awaited_once()
    assert mock.await_args.kwargs["dimensions"] == settings.EMBEDDING_DIM


@pytest.mark.asyncio
async def test_generate_embeddings_uses_cache():
    vector = [0.1] * settings.EMBEDDING_DIM

    async def cached(_text):
        return vector

    with (
        patch.object(ai_service, "get_cached_embedding", cached),
        patch.object(ai_service.client.embeddings, "create", new=AsyncMock()) as create,
    ):
        result = await ai_service.generate_embeddings(["cached text"])
    assert result == [vector]
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_generate_embeddings_retries_without_dimensions():
    with patch.object(
        ai_service.client.embeddings,
        "create",
        new=AsyncMock(
            side_effect=[Exception("unknown parameter: dimensions"), _embedding_response()]
        ),
    ) as mock:
        result = await ai_service.generate_embeddings(["question"])
    assert len(result) == 1
    assert mock.await_count == 2
    assert "dimensions" not in mock.await_args.kwargs


@pytest.mark.asyncio
async def test_ensure_embedding_dim_raises_on_mismatch():
    with pytest.raises(ValueError, match="dimension mismatch"):
        ai_service.ensure_embedding_dim([0.0])


@pytest.mark.asyncio
async def test_small_document_summary_is_single_call():
    with patch.object(
        ai_service.client.chat.completions,
        "create",
        new=AsyncMock(return_value=_completion("Короткий конспект")),
    ) as mock:
        result = await ai_service.generate_document_summary_from_chunks(["a", "b"])
    assert result == "Короткий конспект"
    assert mock.await_count == 1


@pytest.mark.asyncio
async def test_large_document_summary_uses_map_reduce():
    calls = 0

    async def side_effect(**_kwargs):
        nonlocal calls
        calls += 1
        if calls <= 4:  # 30 чанков / BATCH_SIZE=8 → 4 батча
            return _completion(f"выжимка {calls}")
        return _completion("Финальный конспект")

    chunks = [f"чанк {i}" for i in range(30)]
    with patch.object(
        ai_service.client.chat.completions, "create", new=AsyncMock(side_effect=side_effect)
    ):
        result = await ai_service.generate_document_summary_from_chunks(chunks)
    assert result == "Финальный конспект"
    assert calls == 5  # 4 map-вызова + 1 reduce


@pytest.mark.asyncio
async def test_generate_document_summary_empty():
    assert await ai_service.generate_document_summary("") == "Документ пуст."


@pytest.mark.asyncio
async def test_generate_document_summary_splits_long_text():
    with patch.object(
        ai_service.client.chat.completions,
        "create",
        new=AsyncMock(return_value=_completion("Конспект")),
    ):
        result = await ai_service.generate_document_summary("слово " * 3000)
    assert result == "Конспект"
