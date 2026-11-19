"""T6: перевод по смысловым блокам с защитой чисел/дат/терминов."""

import re

from app.core.cache import get_cached_translation, set_cached_translation
from app.core.config import settings
from app.core.logging import log
from app.core.metrics import LLM_CALLS, TRANSLATION_LATENCY
from app.core.prompts import render
from app.services.ai_service import _resilient_call, client, llm_breaker

# Tx: плейсхолдеры, чтобы числа/даты/суммы/ИНН не менялись моделью
_PROTECT_PATTERNS = [
    r"\b\d{1,3}(?:[\s\u00a0]\d{3})+(?:[.,]\d+)?\b",  # 1 000 000
    r"\b\d+[.,]\d+%?\b",  # 12.5%
    r"\b\d{2}[./-]\d{2}[./-]\d{2,4}\b",  # даты
    r"\b\d{10,12}\b",  # ИНН/номера
    r"\b[А-ЯЁA-Z]{2,}\d{2,}\b",  #: A12-34
]


def protect_placeholders(text: str) -> tuple[str, dict[str, str]]:
    mapping: dict[str, str] = {}
    result = text

    def make_repl(prefix: str):
        def repl(match: re.Match) -> str:
            key = f"{prefix}{len(mapping)}§"
            mapping[key] = match.group(0)
            return key

        return repl

    for idx, pattern in enumerate(_PROTECT_PATTERNS):
        result = re.sub(pattern, make_repl(f"§P{idx}_"), result)
    return result, mapping


def restore_placeholders(text: str, mapping: dict[str, str]) -> str:
    for key, value in mapping.items():
        text = text.replace(key, value)
    return text


async def translate_block(
    text: str,
    target_language: str,
    *,
    glossary: dict[str, str] | None = None,
    preserve_markdown: bool = False,
) -> str:
    """Переводит один блок; возвращает оригинал при ошибке (fail-safe)."""
    import time

    if not text or not text.strip():
        return text
    started = time.perf_counter()
    cached = await get_cached_translation(text, target_language, preserve_markdown)
    if cached is not None:
        return cached
    protected, mapping = protect_placeholders(text)
    glossary_part = "\n".join(f"{src} → {dst}" for src, dst in (glossary or {}).items())
    try:
        response = await _resilient_call(
            llm_breaker,
            "translate",
            client.chat.completions.create,
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": render("translate_system")},
                {
                    "role": "user",
                    "content": render(
                        "translate_user",
                        target=target_language,
                        glossary=glossary_part or "—",
                        markdown="Сохраняй Markdown-разметку таблиц и списков."
                        if preserve_markdown
                        else "",
                        text=protected,
                    ),
                },
            ],
            temperature=0.1,
            max_tokens=2000,
        )
        translated = response.choices[0].message.content or ""
        result = restore_placeholders(translated.strip(), mapping)
        await set_cached_translation(text, target_language, result, preserve_markdown)
        return result
    except Exception as exc:
        LLM_CALLS.labels("translate", "error").inc()
        log.warning("translation.block_failed", error=str(exc))
        return text
    finally:
        TRANSLATION_LATENCY.observe(time.perf_counter() - started)


async def translate_blocks(
    texts: list[str],
    target_language: str,
    *,
    glossary: dict[str, str] | None = None,
    preserve_markdown: bool = False,
) -> list[str]:
    """Переводит список блоков последовательно (лимит конкуренции — в ai_service)."""
    results: list[str] = []
    for text in texts:
        results.append(
            await translate_block(
                text,
                target_language,
                glossary=glossary,
                preserve_markdown=preserve_markdown,
            )
        )
    return results
