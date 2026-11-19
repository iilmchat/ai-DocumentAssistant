"""T8: маскировка персональных данных перед отправкой в LLM.

Оригинал остаётся в БД; в промпт уходят плейсхолдеры вида [EMAIL_1], [PHONE_1].
"""

import re

from app.core.config import settings

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    # телефоны: +7 999 123-45-67, (495) 123-45-67, 8 800 123 45 67
    ("PHONE", re.compile(r"(?:\+7|8)[\s(]*(?:\d[\s()-]*){10,12}")),
    ("CARD", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
    ("INN", re.compile(r"\b\d{10,12}\b")),
    # паспорт: 4510 123456
    ("PASSPORT", re.compile(r"\b\d{4}\s?\d{6}\b")),
]


def redact_pii(text: str) -> str:
    if not settings.PII_REDACTION_ENABLED or not text:
        return text

    def make_repl(label: str):
        counter = 0

        def repl(match: re.Match) -> str:
            nonlocal counter
            counter += 1
            return f"[{label}_{counter}]"

        return repl

    result = text
    for label, pattern in _PATTERNS:
        result = pattern.sub(make_repl(label), result)
    return result


def redact_messages(messages: list[dict]) -> list[dict]:
    """Рекурсивно маскирует строковое поле content в сообщениях OpenAI."""
    cleaned: list[dict] = []
    for message in messages:
        item = dict(message)
        content = item.get("content")
        if isinstance(content, str):
            item["content"] = redact_pii(content)
        elif isinstance(content, list):
            item["content"] = [
                {**part, "text": redact_pii(part["text"])}
                if isinstance(part, dict) and isinstance(part.get("text"), str)
                else part
                for part in content
            ]
        cleaned.append(item)
    return cleaned
