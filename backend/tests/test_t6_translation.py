"""T6: тесты двуязычного пайплайна."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.language import detect_language, supported_languages, validate_language
from app.services import translation
from app.services.translation import (
    protect_placeholders,
    restore_placeholders,
    translate_block,
)


def test_language_detection():
    assert (
        detect_language("This is an English document about commercial contracts and payments.")
        == "en"
    )
    assert detect_language("Это русский документ о коммерческих договорах и оплате услуг.") == "ru"
    assert detect_language("hi") == "unknown"


def test_validate_language():
    assert validate_language("EN") == "en"
    assert "ru" in supported_languages()
    with pytest.raises(ValueError):
        validate_language("xx")


def test_placeholder_protection():
    text = "Оплата 1 000 000 руб. до 31.12.2026, ИНН 7700000000, лимит 12.5%."
    protected, mapping = protect_placeholders(text)
    assert "1 000 000" not in protected
    assert mapping
    restored = restore_placeholders(protected, mapping)
    assert restored == text


def test_placeholder_restore_keeps_unknown():
    assert restore_placeholders("просто текст", {}) == "просто текст"


@pytest.mark.asyncio
async def test_translate_block_uses_cache(monkeypatch):
    async def cached(_text, _target, _markdown):
        return "кэшированный перевод"

    monkeypatch.setattr(translation, "get_cached_translation", cached)
    result = await translate_block("hello world", "ru")
    assert result == "кэшированный перевод"


@pytest.mark.asyncio
async def test_translate_block_calls_llm_and_caches(monkeypatch):
    async def no_cache(*_args):
        return None

    stored: list[str] = []

    async def store(_text, _target, value, _markdown):
        stored.append(value)

    monkeypatch.setattr(translation, "get_cached_translation", no_cache)
    monkeypatch.setattr(translation, "set_cached_translation", store)

    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Привет мир"))]
    )
    with patch.object(
        translation.client.chat.completions,
        "create",
        new=AsyncMock(return_value=completion),
    ):
        result = await translate_block("hello world", "ru")

    assert result == "Привет мир"
    assert stored == ["Привет мир"]


@pytest.mark.asyncio
async def test_translate_block_fail_safe(monkeypatch):
    async def no_cache(*_args):
        return None

    monkeypatch.setattr(translation, "get_cached_translation", no_cache)
    with patch.object(
        translation.client.chat.completions,
        "create",
        new=AsyncMock(side_effect=RuntimeError("provider down")),
    ):
        result = await translate_block("original text", "ru")
    assert result == "original text"
