from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

class DocumentResponse(BaseModel):
    id: uuid.UUID
    title: str
    status: str
    summary: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
