"""S3: ANN-индекс HNSW для vector-поиска

Revision ID: 0003_hnsw_index
Revises: 0002_security_audit
Create Date: 2026-11-18
"""
from alembic import op

from app.core.config import settings

revision = "0003_hnsw_index"
down_revision = "0002_security_audit"
branch_labels = None
depends_on = None

INDEX_NAME = "ix_document_chunks_embedding_hnsw"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE INDEX IF NOT EXISTS {INDEX_NAME}
        ON document_chunks USING hnsw (embedding vector_cosine_ops)
        WITH (m = {settings.HNSW_M}, ef_construction = {settings.HNSW_EF_CONSTRUCTION});
        """
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
