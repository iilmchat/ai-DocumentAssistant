import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from PIL import Image

from app.core.config import settings
from app.services.ocr import TesseractEngine, VisionEngine, get_ocr_engine


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(buf, format="PNG")
    return buf.getvalue()


def test_engine_factory():
    assert isinstance(get_ocr_engine("tesseract"), TesseractEngine)
    assert isinstance(get_ocr_engine("vision"), VisionEngine)
    with pytest.raises(ValueError, match="Неизвестный OCR-движок"):
        get_ocr_engine("unknown")


def test_tesseract_availability():
    with patch("shutil.which", return_value="/usr/bin/tesseract"):
        assert TesseractEngine("rus+eng").available()
    with patch("shutil.which", return_value=None):
        assert not TesseractEngine().available()


def test_image_ocr_delegates_to_pdf_page():
    import os
    import tempfile

    fd, path = tempfile.mkstemp(suffix=".png")
    with os.fdopen(fd, "wb") as f:
        f.write(_png_bytes())

    engine = TesseractEngine()
    try:
        with patch.object(engine, "ocr_pdf_page", return_value=("текст", 0.9)) as delegate:
            assert engine.ocr_image_file(path) == ("текст", 0.9)
        delegate.assert_called_once()
        assert delegate.call_args.args[1] == 0
    finally:
        os.unlink(path)


def test_vision_engine_uses_configured_model():
    with (
        patch.object(settings, "OPENAI_API_KEY", "test-key"),
        patch.object(settings, "LLM_MODEL", "gemini-2.5-flash"),
    ):
        engine = VisionEngine()
    assert engine.model == "gemini-2.5-flash"
    assert engine.available()


def test_vision_engine_recognises_page():
    pdf = _png_bytes()
    pix = Mock()
    pix.tobytes.return_value = pdf
    page = Mock()
    page.get_pixmap.return_value = pix
    doc = Mock()
    doc.load_page.return_value = page
    fake_fitz = Mock()
    fake_fitz.open.return_value = doc

    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="текст со скана"))]
    )
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(return_value=completion)))
    )

    with (
        patch.object(settings, "OPENAI_API_KEY", "test-key"),
        patch("app.services.pymupdf_compat.fitz", fake_fitz),
        patch("openai.AsyncOpenAI", return_value=fake_client),
    ):
        engine = VisionEngine()
        text, confidence = engine.ocr_pdf_page("scan.pdf", 0)

    assert text == "текст со скана"
    assert confidence == 0.85
    doc.close.assert_called_once()
