"""Общие fixtures: тесты не должны звать реальные внешние API."""
import pytest

from app.core import config


@pytest.fixture(autouse=True)
def _no_external_llm(monkeypatch):
    monkeypatch.setattr(config.settings, "OLLAMA_EMBED_MODEL", "")
    monkeypatch.setattr(config.settings, "LOCAL_EMBEDDINGS", False)
    monkeypatch.setattr(config.settings, "OPENCODE_CHAT", False)
