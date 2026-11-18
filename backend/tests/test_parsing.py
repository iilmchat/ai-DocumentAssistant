import hashlib
import os
import tempfile

from app.services.document_parser import extract_text_from_file
from app.services.file_validation import compute_sha256, count_pdf_pages, validate_upload


def _temp_file(data: bytes, suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return path


def test_compute_sha256():
    path = _temp_file(b"hello", ".txt")
    try:
        assert compute_sha256(path) == hashlib.sha256(b"hello").hexdigest()
    finally:
        os.unlink(path)


def test_extract_text_from_txt():
    path = _temp_file("Привет, мир! Это тест.".encode(), ".txt")
    try:
        assert "Привет, мир!" in extract_text_from_file(path, ".txt")
    finally:
        os.unlink(path)


def test_extract_text_from_docx_includes_tables():
    from docx import Document

    path = _temp_file(b"", ".docx")
    doc = Document()
    doc.add_paragraph("Заголовок документа")
    table = doc.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Ячейка A"
    table.cell(0, 1).text = "Ячейка B"
    doc.save(path)

    try:
        text = extract_text_from_file(path, ".docx")
        assert "Заголовок документа" in text
        assert "Ячейка A" in text
    finally:
        os.unlink(path)


def test_extract_text_and_pages_from_pdf():
    from app.services.pymupdf_compat import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Hello PDF document", fontsize=12)
    path = _temp_file(b"", ".pdf")
    doc.save(path)
    doc.close()

    try:
        assert "Hello PDF document" in extract_text_from_file(path, ".pdf")
        assert count_pdf_pages(path) == 1
        assert validate_upload(path) == "application/pdf"
    finally:
        os.unlink(path)


def test_validate_upload_png():
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (10, 10), "white").save(buf, format="PNG")
    path = _temp_file(buf.getvalue(), ".png")
    try:
        assert validate_upload(path) == "image/png"
    finally:
        os.unlink(path)
