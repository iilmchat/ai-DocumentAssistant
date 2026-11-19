import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    TIMESTAMP,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID

from app.core.config import settings
from app.core.database import Base


class User(Base):
    """Этап 4 (заготовка): владелец документов. Пока используется демо-аккаунт."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    # T8: RBAC — admin / editor / viewer
    role = Column(String(32), nullable=False, default="editor", server_default="editor")
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP"))


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    # Этап 4: идемпотентность по хешу — повторная загрузка того же файла не жжёт OCR/эмбеддинги
    sha256 = Column(String(64), nullable=True, index=True)
    mime_type = Column(String(100), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    status = Column(String(50), nullable=False, default="pending")
    # pending -> processing -> embedding -> completed | failed | duplicate
    summary = Column(Text, nullable=True)
    # Этап 4: прогресс по страницам для SSE/поллинга на фронте
    total_pages = Column(Integer, nullable=True)
    processed_pages = Column(Integer, nullable=False, default=0)
    page_count_estimate = Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    # S4: мягкое удаление — файл живёт grace-период, потом очищается retention-задачей
    deleted_at = Column(TIMESTAMP(timezone=True), nullable=True)
    # T6: язык оригинала
    language = Column(String(8), nullable=True)


class DocumentPage(Base):
    """Этап 1: постраничное хранение с методом извлечения и уверенностью."""

    __tablename__ = "document_pages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_number = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    extraction_method = Column(
        String(20), nullable=False, default="text_layer"
    )  # text_layer|ocr|vision
    confidence = Column(
        Integer, nullable=False, default=100
    )  # 0..100, храним целым для переносимости
    # T6: постраничный перевод
    text_translated = Column(Text, nullable=True)
    translation_language = Column(String(8), nullable=True)
    __table_args__ = (
        UniqueConstraint("document_id", "page_number", name="uq_document_page"),
        Index("ix_document_pages_document", "document_id"),
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(settings.EMBEDDING_DIM), nullable=False)
    # Этап 1: цитирование со ссылками на страницы в RAG-ответах
    page_numbers = Column(JSONB, nullable=True)  # [1, 2, ...]
    headings = Column(JSONB, nullable=True)  # ["Раздел 1", ...]
    extraction_method = Column(String(50), nullable=True)
    # Этап 5: полнотекстовый индекс под русскую конфигурацию Postgres
    search_vector = Column(TSVECTOR, nullable=True)
    # T6: двуязычный поиск
    content_translated = Column(Text, nullable=True)
    embedding_translated = Column(Vector(settings.EMBEDDING_DIM), nullable=True)
    translation_language = Column(String(8), nullable=True)
    translation_status = Column(
        String(20), nullable=False, default="none"
    )  # none|pending|done|failed
    __table_args__ = (Index("ix_document_chunks_search", "search_vector", postgresql_using="gin"),)


class Glossary(Base):
    """T6: пользовательский глоссарий терминов перевода."""

    __tablename__ = "glossaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    source_term = Column(String(255), nullable=False)
    target_term = Column(String(255), nullable=False)
    source_language = Column(String(8), nullable=True)
    target_language = Column(String(8), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    __table_args__ = (
        UniqueConstraint("user_id", "source_term", "target_language", name="uq_glossary_term"),
        Index("ix_glossaries_user", "user_id"),
    )


class TokenUsage(Base):
    """S5: учёт токенов и стоимости LLM на запрос."""

    __tablename__ = "token_usages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    operation = Column(String(32), nullable=False)
    model = Column(String(128), nullable=False)
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    cost_usd = Column(String(32), nullable=True)  # строка для переносимости
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    __table_args__ = (
        Index("ix_token_usages_user", "user_id"),
        Index("ix_token_usages_created", "created_at"),
    )


class AuditLog(Base):
    """S1: журнал действий пользователя (кто/что/когда/откуда)."""

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    action = Column(String(64), nullable=False)
    resource_type = Column(String(64), nullable=True)
    resource_id = Column(String(64), nullable=True)
    ip_address = Column(String(64), nullable=True)
    details = Column(JSONB, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    __table_args__ = (
        Index("ix_audit_logs_user", "user_id"),
        Index("ix_audit_logs_created", "created_at"),
    )


class SummaryVersion(Base):
    """Этап 7: история версий сгенерированного конспекта."""

    __tablename__ = "summary_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    version = Column(Integer, nullable=False)
    summary = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=text("CURRENT_TIMESTAMP"))
    __table_args__ = (
        UniqueConstraint("document_id", "version", name="uq_summary_version"),
        Index("ix_summary_versions_document", "document_id"),
    )
