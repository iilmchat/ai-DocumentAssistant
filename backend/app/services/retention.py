"""S4: retention — мягкое удаление и очистка старых данных."""

import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import log
from app.models.models import AuditLog, Document


async def cleanup_retention(db: AsyncSession) -> dict[str, int]:
    now = datetime.now(UTC)
    grace_cutoff = now - timedelta(days=settings.SOFT_DELETE_GRACE_DAYS)
    audit_cutoff = now - timedelta(days=settings.RETENTION_DAYS)

    expired = (
        (await db.execute(select(Document).where(Document.deleted_at < grace_cutoff)))
        .scalars()
        .all()
    )
    removed_files = 0
    for doc in expired:
        if doc.file_path and os.path.exists(doc.file_path):
            os.remove(doc.file_path)
            removed_files += 1
        await db.delete(doc)

    # оставляем только последние N версий конспекта на документ
    await db.execute(
        text("""
            DELETE FROM summary_versions
            WHERE id IN (
                SELECT id FROM (
                    SELECT id, row_number() OVER (
                        PARTITION BY document_id ORDER BY version DESC
                    ) AS rn
                    FROM summary_versions
                ) ranked WHERE ranked.rn > :keep
            )
        """),
        {"keep": settings.SUMMARY_VERSIONS_KEEP},
    )

    deleted_audit = await db.execute(delete(AuditLog).where(AuditLog.created_at < audit_cutoff))
    await db.commit()

    result = {
        "documents": len(expired),
        "files": removed_files,
        "audit_rows": deleted_audit.rowcount or 0,
    }
    log.info("retention.completed", **result)
    return result
