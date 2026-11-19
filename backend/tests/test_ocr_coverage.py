"""T10: покрытие OCR-движков."""

import io
import os
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image

from app.services.ocr import TesseractEngine, VisionEngine


def _png():
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(buf, format="PNG")
    return buf.getvalue()


def _fitz_mock():
    page = MagicMock()
    pix = MagicMock()
    pix.tobytes.return_value = _png()
    page.get_pixmap.return_value = pix
    doc = MagicMock()
    doc.load_page.return_value = page
    fake = MagicMock()
    fake.open.return_value = doc
    return fake, doc


def test_tesseract_image_to_data_path():
    data = {
        "text": ["Привет", "", "мир", "123"],
        "conf": ["90", "-1", "80", "95"],
    }
    fake, doc = _fitz_mock()
    with (
        patch("app.services.pymupdf_compat.fitz", fake),
        patch("pytesseract.image_to_data", return_value=data),
    ):
        text, conf = TesseractEngine("rus+eng").ocr_pdf_page("scan.pdf", 0)
    assert "Привет" in text and "мир" in text
    assert 0.85 < conf < 0.9
    doc.close.assert_called_once()


def test_tesseract_auto_language():
    fake, _ = _fitz_mock()
    data = {"text": ["This", "is", "English"], "conf": ["90", "90", "90"]}
    with (
        patch("app.services.pymupdf_compat.fitz", fake),
        patch("pytesseract.image_to_data", return_value=data),
    ):
        engine = TesseractEngine("auto")
        text, conf = engine.ocr_pdf_page("scan.pdf", 0)
    assert text
    assert 0 <= conf <= 1


def test_tesseract_no_words():
    fake, _ = _fitz_mock()
    data = {"text": ["", ""], "conf": ["-1", "-1"]}
    with (
        patch("app.services.pymupdf_compat.fitz", fake),
        patch("pytesseract.image_to_data", return_value=data),
    ):
        text, conf = TesseractEngine().ocr_pdf_page("scan.pdf", 0)
    assert text == ""
    assert conf == 0.0


def test_vision_unavailable_without_key():
    with patch("app.core.config.settings.OPENAI_API_KEY", ""):
        assert VisionEngine().available() is False


def test_vision_empty_response():
    fake, _ = _fitz_mock()
    completion = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=""))])
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock(return_value=completion)))
    )
    with (
        patch("app.core.config.settings.OPENAI_API_KEY", "key"),
        patch("app.services.pymupdf_compat.fitz", fake),
        patch("openai.AsyncOpenAI", return_value=client),
    ):
        text, conf = VisionEngine().ocr_pdf_page("scan.pdf", 0)
    assert text == ""
    assert conf == 0.0


def test_vision_with_model_override():
    engine = VisionEngine(model="custom-model")
    assert engine.model == "custom-model"


def test_image_file_conversion():
    fd, path = tempfile.mkstemp(suffix=".png")
    with os.fdopen(fd, "wb") as f:
        f.write(_png())
    engine = TesseractEngine()
    with patch.object(engine, "ocr_pdf_page", return_value=("текст", 0.9)) as ocr:
        result = engine.ocr_image_file(path)
    assert result == ("текст", 0.9)
    ocr.assert_called_once()
    os.unlink(path)
