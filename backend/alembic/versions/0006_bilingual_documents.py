"""T6: двуязычные документы и перевод

Revision ID: 0006_bilingual_documents
Revises: 0005_token_usage
Create Date: 2026-11-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

from app.core.config import settings

revision = "0006_bilingual_documents"
down_revision = "0005_token_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("language", sa.String(8), nullable=True))

    op.add_column("document_pages", sa.Column("text_translated", sa.Text(), nullable=True))
    op.add_column("document_pages", sa.Column("translation_language", sa.String(8), nullable=True))

    op.add_column("document_chunks", sa.Column("content_translated", sa.Text(), nullable=True))
    op.add_column(
        "document_chunks",
        sa.Column("embedding_translated", Vector(settings.EMBEDDING_DIM), nullable=True),
    )
    op.add_column("document_chunks", sa.Column("translation_language", sa.String(8), nullable=True))
    op.add_column(
        "document_chunks",
        sa.Column(
            "translation_status",
            sa.String(20),
            nullable=False,
            server_default="none",
        ),
    )

    op.create_table(
        "glossaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_term", sa.String(255), nullable=False),
        sa.Column("target_term", sa.String(255), nullable=False),
        sa.Column("source_language", sa.String(8), nullable=True),
        sa.Column("target_language", sa.String(8), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "source_term", "target_language", name="uq_glossary_term"),
    )
    op.create_index("ix_glossaries_user", "glossaries", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_glossaries_user", table_name="glossaries")
    op.drop_table("glossaries")
    op.drop_column("document_chunks", "translation_status")
    op.drop_column("document_chunks", "translation_language")
    op.drop_column("document_chunks", "embedding_translated")
    op.drop_column("document_chunks", "content_translated")
    op.drop_column("document_pages", "translation_language")
    op.drop_column("document_pages", "text_translated")
    op.drop_column("documents", "language")
