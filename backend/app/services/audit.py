"""S1: сервис аудита действий пользователя."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AuditLog


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
