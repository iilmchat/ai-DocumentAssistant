"""S4: smoke-проверка схемы после `alembic upgrade head`.

Запускается автоматически в CMD backend-образа и вручную: `make smoke`.
"""

import asyncio

from sqlalchemy import text

from app.core.database import engine

REQUIRED_TABLES = {
    "users",
    "documents",
    "document_pages",
    "document_chunks",
    "summary_versions",
    "audit_logs",
    "token_usages",
    "glossaries",
    "organizations",
    "alembic_version",
}


async def check() -> None:
    async with engine.begin() as conn:
        version = await conn.scalar(text("SELECT version_num FROM alembic_version"))
        tables = set(
            (
                await conn.execute(
                    text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
                )
            )
            .scalars()
            .all()
        )
    missing = REQUIRED_TABLES - tables
    if missing:
        raise SystemExit(f"Smoke check failed: missing tables {sorted(missing)}")
    print(f"Smoke check OK: alembic={version}, tables={len(tables)}")


if __name__ == "__main__":
    asyncio.run(check())
