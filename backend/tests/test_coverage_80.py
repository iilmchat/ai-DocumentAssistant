"""T10: добираем 80%."""

import uuid
from datetime import UTC
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api import documents as api
from app.services import ai_service


@pytest.mark.asyncio
async def test_generate_document_summary_long_path():
    with patch.object(
        ai_service, "generate_document_summary_from_chunks", new=AsyncMock(return_value="Сводка")
    ) as m:
        result = await ai_service.generate_document_summary("слово " * 3000)
    assert result == "Сводка"
    m.assert_awaited_once()


@pytest.mark.asyncio
async def test_regenerate_summary_direct():
    from datetime import datetime

    doc = SimpleNamespace(id=uuid.uuid4(), summary=None, created_at=datetime.now(UTC))
    db = AsyncMock()
    with (
        patch.object(api, "_get_owned_document", new=AsyncMock(return_value=doc)),
        patch.object(api, "_collect_document_text", new=AsyncMock(return_value="Текст")),
        patch.object(api, "generate_document_summary", new=AsyncMock(return_value="Сводка")),
        patch.object(
            api, "save_summary_version", new=AsyncMock(return_value=SimpleNamespace(version=1))
        ),
    ):
        result = await api.regenerate_summary(
            MagicMock(), doc.id, db, SimpleNamespace(id=uuid.uuid4())
        )
    assert result.version == 1
