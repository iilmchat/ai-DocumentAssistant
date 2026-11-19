"""T8: RBAC-роли пользователей

Revision ID: 0008_security_hardening
Revises: 0006_bilingual_documents
Create Date: 2026-11-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_security_hardening"
down_revision = "0006_bilingual_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(32), nullable=False, server_default="editor"),
    )


def downgrade() -> None:
    op.drop_column("users", "role")
