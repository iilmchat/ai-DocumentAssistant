"""T7: сжатие контекста — меньше токенов, дешевле ответ."""

from app.core.config import settings


def compress_context(chunks: list[str], max_chars: int = 12000) -> list[str]:
    """Обрезает каждый чанк до максимальной длины, сохраняя начало и конец."""
    per_chunk = max(400, max_chars // max(len(chunks), 1))
    result: list[str] = []
    for chunk in chunks:
        if len(chunk) <= per_chunk:
            result.append(chunk)
            continue
        head = per_chunk * 2 // 3
        tail = per_chunk - head
        result.append(chunk[:head] + "\n…\n" + chunk[-tail:])
    return result


def build_context(context_parts: list[str]) -> str:
    if settings.RAG_EVAL_ENABLED:  # переиспользуем флаг как общий «quality mode»
        context_parts = compress_context(context_parts)
    return "\n\n---\n\n".join(context_parts)
