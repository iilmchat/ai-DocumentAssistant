"""T9: инкрементальная индексация

Revision ID: 0010_incremental_index
Revises: 0009_multitenancy
Create Date: 2026-11-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_incremental_index"
down_revision = "0009_multitenancy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("document_chunks", sa.Column("content_hash", sa.String(64), nullable=True))
    op.create_index("ix_document_chunks_content_hash", "document_chunks", ["content_hash"])


def downgrade() -> None:
    op.drop_index("ix_document_chunks_content_hash", table_name="document_chunks")
    op.drop_column("document_chunks", "content_hash")
