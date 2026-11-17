from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

class DocumentResponse(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    summary: Optional[str] = None
    total_pages: Optional[int] = None
    processed_pages: int = 0
    sha256: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentProgress(BaseModel):
    id: uuid.UUID
    status: str
    total_pages: Optional[int] = None
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


class SourceCitation(BaseModel):
    """Этап 1: цитата со ссылкой на страницы — пользователь может проверить утверждение модели."""
    page_numbers: list[int] = []
    headings: list[str] = []
    snippet: str
    extraction_method: Optional[str] = None
