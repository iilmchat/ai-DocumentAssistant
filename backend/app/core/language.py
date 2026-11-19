"""T6: определение языка текста и валидация языков перевода."""

import re

from langdetect import LangDetectException, detect_langs

from app.core.config import settings


def supported_languages() -> list[str]:
    return [code.strip() for code in settings.SUPPORTED_LANGUAGES.split(",") if code.strip()]


def detect_language(text: str) -> str:
    """Возвращает ISO-код языка ('ru', 'en', ...) или 'unknown'."""
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if len(cleaned) < 20:
        return "unknown"
    try:
        candidates = detect_langs(cleaned[:5000])
        if not candidates:
            return "unknown"
        top = candidates[0]
        return top.lang if top.prob >= 0.5 else "unknown"
    except LangDetectException:
        return "unknown"


def validate_language(code: str) -> str:
    normalized = code.strip().lower()[:2]
    if normalized not in supported_languages():
        raise ValueError(f"Unsupported language: {code}")
    return normalized
