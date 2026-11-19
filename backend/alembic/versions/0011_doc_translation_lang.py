"""T6 fix: язык перевода на документе

Revision ID: 0011_doc_translation_lang
Revises: 0010_incremental_index
Create Date: 2026-11-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_doc_translation_lang"
down_revision = "0010_incremental_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("translation_language", sa.String(8), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "translation_language")
