"""S4: мягкое удаление и data-migration статусов

Revision ID: 0004_retention
Revises: 0003_hnsw_index
Create Date: 2026-11-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_retention"
down_revision = "0003_hnsw_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_documents_deleted_at", "documents", ["deleted_at"])

    # data-migration: старые статусы из локальной ветки ({ocr, vectorizing}) приводим к единым
    op.execute("UPDATE documents SET status = 'processing' WHERE status IN ('ocr', 'vectorizing')")
    op.execute(
        "UPDATE documents SET status = 'completed' "
        "WHERE status IS NULL AND summary IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_documents_deleted_at", table_name="documents")
    op.drop_column("documents", "deleted_at")
