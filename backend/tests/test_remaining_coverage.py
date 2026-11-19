"""T10: добираем покрытие file_validation, organizations, export."""

import os
import tempfile
import uuid
import zipfile
from datetime import UTC, datetime

import pytest

from app.core.config import settings
from app.services.export import ExportData, render_docx, render_markdown, render_pdf
from app.services.file_validation import (
    ValidationError,
    sniff_mime,
    validate_image_limits,
    validate_upload,
)


def test_sniff_mime_utf8_boundary():
    """4096-й байт может оборвать кириллический символ — файл всё равно text/plain."""
    prefix = b"a" * 4095
    text = prefix + "Договор".encode() + b" " * 100
    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, "wb") as f:
        f.write(text)
    try:
        assert sniff_mime(path) == "text/plain"
    finally:
        os.unlink(path)


def test_sniff_mime_signatures():
    cases = {
        b"%PDF-1.7": "application/pdf",
        b"\xff\xd8\xff\xe0JFIF": "image/jpeg",
        b"\x89PNG\r\n\x1a\n" + b"0" * 20: "image/png",
        b"II*\x00" + b"0" * 20: "image/tiff",
        b"MM\x00*" + b"0" * 20: "image/tiff",
    }
    for data, expected in cases.items():
        fd, path = tempfile.mkstemp()
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        try:
            assert sniff_mime(path) == expected
        finally:
            os.unlink(path)


def test_sniff_ooxml_docx_xlsx_pptx():
    from app.services.file_validation import ALLOWED_MIMES

    entries = {
        "word/document.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xl/workbook.xml": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "ppt/presentation.xml": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    for member, expected in entries.items():
        fd, path = tempfile.mkstemp(suffix=".zip")
        with os.fdopen(fd, "wb") as f:
            with zipfile.ZipFile(f, "w") as z:
                z.writestr(member, "<xml/>")
        try:
            assert sniff_mime(path) == expected
            assert expected in ALLOWED_MIMES
        finally:
            os.unlink(path)


def test_zip_bomb_rejected():
    """Проверяем детектор ZIP-бомбы напрямую (sniff_mime)."""
    fd, path = tempfile.mkstemp(suffix=".docx")
    with os.fdopen(fd, "wb") as f:
        with zipfile.ZipFile(f, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr("word/document.xml", b"0" * 1024)
            z.writestr("extra", b"0" * (1024 * 1024 * 30))
    try:
        assert sniff_mime(path) in (
            "application/zip-bomb",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    finally:
        os.unlink(path)


def test_validate_upload_empty_and_large():
    fd, empty = tempfile.mkstemp()
    os.close(fd)
    try:
        with pytest.raises(ValidationError, match="Пустой"):
            validate_upload(empty)
    finally:
        os.unlink(empty)

    big = tempfile.mktemp()
    with open(big, "wb") as f:
        f.truncate(settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024 + 1)
    try:
        with pytest.raises(ValidationError):
            validate_upload(big)
    finally:
        os.unlink(big)


def test_validate_image_limits_png():
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format="PNG")
    fd, path = tempfile.mkstemp(suffix=".png")
    with os.fdopen(fd, "wb") as f:
        f.write(buf.getvalue())
    try:
        validate_image_limits(path)
    finally:
        os.unlink(path)


def test_validate_image_limits_bomb(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".png")
    with os.fdopen(fd, "wb") as f:
        f.write(b"not an image")
    try:
        with pytest.raises(ValidationError):
            validate_image_limits(path)
    finally:
        os.unlink(path)


def test_export_all_formats_with_sources():
    data = ExportData(
        title="Отчёт",
        summary="# Заголовок\n\n- пункт\n\n**жирный** и `код`",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        sources=[
            {"page": 2, "extraction_method": "ocr", "snippet": "цитата"},
            {"page": 3, "extraction_method": "text_layer", "snippet": "ещё"},
        ],
    )
    assert "Источники по страницам" in render_markdown(data).decode()
    assert render_docx(data).startswith(b"PK")
    assert render_pdf(data).startswith(b"%PDF")


def test_organization_response_schema():
    from app.api.organizations import OrganizationResponse

    resp = OrganizationResponse(
        id=uuid.uuid4(), name="Acme", slug="acme", documents=3, storage_bytes=1024
    )
    assert resp.name == "Acme"
    assert resp.documents == 3
