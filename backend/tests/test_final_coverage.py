"""T10: финальные тесты для 80% coverage."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.prompts import REGISTRY, render
from app.services import ai_service, context, extended_parsers, rag_eval, translation


def test_all_prompts_render():
    for name, template in REGISTRY.items():
        result = render(
            name, **{k: "x" for k in __import__("string").Template(template).get_identifiers()}
        )
        assert isinstance(result, str)


@pytest.mark.asyncio
async def test_translate_blocks_sequential():
    with patch.object(translation, "translate_block", new=AsyncMock(side_effect=["a", "b"])):
        result = await translation.translate_blocks(["x", "y"], "ru")
    assert result == ["a", "b"]


def test_context_compression_short():
    assert context.compress_context(["short"], max_chars=100) == ["short"]


def test_context_build_with_flag(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "RAG_EVAL_ENABLED", False)
    parts = ["a" * 2000, "b" * 2000]
    result = context.build_context(parts)
    assert "---" in result
    assert len(result) > 4000


@pytest.mark.asyncio
async def test_audio_transcription():
    import os
    import tempfile

    fd, path = tempfile.mkstemp(suffix=".mp3")
    with os.fdopen(fd, "wb") as f:
        f.write(b"audio")
    client = MagicMock()
    client.audio.transcriptions.create = AsyncMock(return_value=SimpleNamespace(text="текст"))
    with patch.object(ai_service, "client", client):
        result = await extended_parsers.transcribe_audio(path)
    os.unlink(path)
    assert result == "текст"


def test_rag_eval_empty_answer():
    report = rag_eval.evaluate_answer("вопрос", "", "контекст")
    assert report["faithfulness"] == 0.0


@pytest.mark.asyncio
async def test_llm_semaphore_per_loop():
    sem = ai_service._get_llm_semaphore()
    assert sem is ai_service._get_llm_semaphore()
    assert sem._value == ai_service.settings.LLM_MAX_CONCURRENCY
