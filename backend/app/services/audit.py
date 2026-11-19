"""S1 / T8: сервис аудита действий пользователя + экспорт в SIEM."""

import logging
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import AuditLog

logger = logging.getLogger(__name__)


async def log_action(
    db: AsyncSession,
    user_id,
    action: str,
    *,
    resource_type: str | None = None,
    resource_id: str | None = None,
    ip_address: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            ip_address=ip_address,
            details=details,
        )
    )
    await db.flush()
    await _forward_to_siem(
        {
            "user_id": str(user_id),
            "action": action,
            "resource_type": resource_type,
            "resource_id": str(resource_id) if resource_id else None,
            "ip_address": ip_address,
            "details": details,
        }
    )


async def _forward_to_siem(payload: dict[str, Any]) -> None:
    """T8: best-effort отправка события во внешний SIEM (не блокирует основную операцию)."""
    if not settings.AUDIT_WEBHOOK_URL:
        return
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.post(settings.AUDIT_WEBHOOK_URL, json=payload)
    except Exception as exc:
        logger.warning("audit.siem_forward_failed", extra={"error": str(exc)})
