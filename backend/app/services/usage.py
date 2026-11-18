"""S5: запись токенов и оценка стоимости запроса."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.metrics import LLM_COST_USD
from app.models.models import TokenUsage
from app.services.ai_service import get_last_usage


def estimate_cost(prompt_tokens: int, completion_tokens: int) -> float:
    return (
        prompt_tokens / 1000 * settings.LLM_COST_PER_1K_INPUT
        + completion_tokens / 1000 * settings.LLM_COST_PER_1K_OUTPUT
    )


async def record_usage(
    db: AsyncSession,
    user_id,
    document_id=None,
    operation: str = "chat",
) -> TokenUsage | None:
    usage = get_last_usage()
    if not usage:
        return None

    prompt = int(usage.get("prompt_tokens", 0))
    completion = int(usage.get("completion_tokens", 0))
    cost = estimate_cost(prompt, completion)
    LLM_COST_USD.inc(cost)

    row = TokenUsage(
        user_id=user_id,
        document_id=document_id,
        operation=operation,
        model=str(usage.get("model", settings.LLM_MODEL)),
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=int(usage.get("total_tokens", prompt + completion)),
        cost_usd=f"{cost:.6f}",
    )
    db.add(row)
    await db.flush()
    return row
