import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    summary: str | None = None
    total_pages: int | None = None
    processed_pages: int = 0
    sha256: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentList(BaseModel):
    items: list[DocumentResponse]
    total: int
    limit: int
    offset: int


class DocumentProgress(BaseModel):
    id: uuid.UUID
    status: str
    total_pages: int | None = None
    processed_pages: int = 0

    class Config:
        from_attributes = True


class PageResponse(BaseModel):
    page_number: int
    text: str
    extraction_method: str
    confidence: int

    class Config:
        from_attributes = True


class SummaryVersionResponse(BaseModel):
    id: uuid.UUID
    version: int
    summary: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SourceCitation(BaseModel):
    """Этап 1: цитата со ссылкой на страницы — пользователь может проверить утверждение модели."""

    page_numbers: list[int] = []
    headings: list[str] = []
    snippet: str
    extraction_method: str | None = None
