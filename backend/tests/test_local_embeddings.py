"""Тесты офлайн-эмбеддингов и Ollama-адаптера."""

from unittest.mock import MagicMock, patch

from app.core import config
from app.services import ai_service


def test_ollama_embeddings_adapter():
    import asyncio

    fake_response = MagicMock()
    fake_response.json.return_value = {"embeddings": [[0.1] * config.settings.EMBEDDING_DIM]}
    fake_response.raise_for_status.return_value = None

    class FakeClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *_args, **_kwargs):
            return fake_response

    with patch("httpx.AsyncClient", FakeClient):
        result = asyncio.run(ai_service._ollama_embeddings(["hello"]))
    assert len(result.data) == 1
    assert len(result.data[0].embedding) == config.settings.EMBEDDING_DIM


def test_local_embeddings_shape():
    old = config.settings.LOCAL_EMBEDDINGS
    config.settings.LOCAL_EMBEDDINGS = True
    try:
        vectors = ai_service._local_embeddings(["hello", "привет"])
        assert len(vectors) == 2
        assert all(len(v) == config.settings.EMBEDDING_DIM for v in vectors)
        assert vectors[0] == ai_service._local_embeddings(["hello"])[0]  # детерминизм
    finally:
        config.settings.LOCAL_EMBEDDINGS = old


def test_local_embeddings_call():
    import asyncio

    # прямой вызов _embeddings_call с включённым флагом
    old = config.settings.LOCAL_EMBEDDINGS
    config.settings.LOCAL_EMBEDDINGS = True
    try:
        result = asyncio.run(ai_service._embeddings_call(["x"]))
        assert len(result.data) == 1
        assert len(result.data[0].embedding) == config.settings.EMBEDDING_DIM
    finally:
        config.settings.LOCAL_EMBEDDINGS = old


def test_offline_summary():
    import asyncio

    old = config.settings.LOCAL_EMBEDDINGS
    config.settings.LOCAL_EMBEDDINGS = True
    try:
        result = asyncio.run(ai_service.generate_document_summary("Строка один\nСтрока два"))
        assert "Строка один" in result
        assert "офлайн" in result.lower()
    finally:
        config.settings.LOCAL_EMBEDDINGS = old
