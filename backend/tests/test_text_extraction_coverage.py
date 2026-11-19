"""T10: покрытие text_extraction и ocr."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services import text_extraction as te
from app.services.ocr import (
    PaddleEngine,
    SuryaEngine,
    TesseractEngine,
    VisionEngine,
    detect_language,
    get_ocr_engine,
)


def test_font_size_of_block():
    block = {
        "lines": [
            {"spans": [{"size": 10}, {"size": 14}]},
            {"spans": [{"size": 12}]},
        ]
    }
    assert te._font_size_of_block(block) == 14
    assert te._font_size_of_block({}) == 0.0
    assert te._font_size_of_block({"lines": "bad"}) == 0.0


def test_block_text_from_dict():
    block = {
        "lines": [
            {"spans": [{"text": "Hello "}, {"text": "World"}]},
            {"spans": [{"text": "Second"}]},
        ]
    }
    assert te._block_text_from_dict(block) == "Hello World\nSecond"


def test_parse_page_structure_classifies_blocks():
    page = MagicMock()
    # find_tables returns no tables
    page.find_tables.return_value = MagicMock(tables=[])
    page.get_text.return_value = {
        "blocks": [
            {
                "type": 0,
                "bbox": (0, 0, 100, 20),
                "lines": [{"spans": [{"text": "Заголовок", "size": 20}]}],
            },
            {
                "type": 0,
                "bbox": (0, 30, 100, 60),
                "lines": [{"spans": [{"text": "- пункт один", "size": 11}]}],
            },
            {
                "type": 0,
                "bbox": (0, 70, 100, 100),
                "lines": [{"spans": [{"text": "обычный текст", "size": 11}]}],
            },
        ]
    }
    blocks = te._parse_page_structure(page, 1)
    kinds = [b.kind for b in blocks]
    assert "heading" in kinds
    assert "list" in kinds


def test_parse_page_structure_with_table():
    page = MagicMock()
    table = MagicMock()
    table.extract.return_value = [["A", "B"], ["1", "2"]]
    table.bbox = (0, 0, 100, 50)
    page.find_tables.return_value = MagicMock(tables=[table])
    page.get_text.return_value = {"blocks": []}
    blocks = te._parse_page_structure(page, 1)
    assert any(b.kind == "table" for b in blocks)


def test_needs_ocr_full_page_image():
    page = MagicMock()
    page.get_text.return_value = "short"
    img = MagicMock()
    page.get_images.return_value = [img]
    page.get_image_bbox.return_value = MagicMock(is_empty=False, get_area=lambda: 90)
    page.rect.width, page.rect.height = 10, 10
    with patch.object(te, "_page_text_coverage", return_value=0.0):
        assert te.needs_ocr(page, 100)


def test_extract_pages_uses_ocr_for_scan():
    """Страница-скан уходит в OCR."""
    fake_doc = MagicMock()
    fake_doc.page_count = 1
    page = MagicMock()
    page.get_text.return_value = ""
    page.get_images.return_value = []
    page.get_pixmap.return_value = MagicMock(tobytes=lambda _fmt: b"png")
    fake_doc.load_page.return_value = page
    fake_fitz = MagicMock()
    fake_fitz.open.return_value = fake_doc

    engine = MagicMock()
    engine.ocr_pdf_page.return_value = ("распознанный текст", 0.8)
    with (
        patch("app.services.pymupdf_compat.fitz", fake_fitz),
        patch.object(te, "get_ocr_engine", return_value=engine),
    ):
        pages = te.extract_pages("scan.pdf")
    assert len(pages) == 1
    assert pages[0].extraction_method == "ocr"
    assert pages[0].confidence == 0.8
    fake_doc.close.assert_called_once()


def test_tesseract_direct_binary_fallback():
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format="PNG")
    engine = TesseractEngine("rus+eng")
    proc = SimpleNamespace(returncode=0, stdout="текст", stderr="")
    with (
        patch("pytesseract.image_to_data", side_effect=ImportError("no pytesseract")),
        patch("subprocess.run", return_value=proc) as run,
    ):
        text, conf = engine._tesseract_from_image(buf.getvalue(), "rus+eng")
    assert text == "текст"
    assert conf == 0.7
    run.assert_called_once()


def test_tesseract_binary_error():
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format="PNG")
    proc = SimpleNamespace(returncode=1, stdout="", stderr="error")
    with (
        patch("pytesseract.image_to_data", side_effect=ImportError()),
        patch("subprocess.run", return_value=proc),
    ):
        with pytest.raises(RuntimeError):
            TesseractEngine()._tesseract_from_image(buf.getvalue(), "eng")


def test_engine_factory_all():
    assert isinstance(get_ocr_engine("tesseract"), TesseractEngine)
    assert isinstance(get_ocr_engine("vision"), VisionEngine)
    assert isinstance(get_ocr_engine("paddle"), PaddleEngine)
    assert isinstance(get_ocr_engine("surya"), SuryaEngine)


def test_language_detection_variants():
    assert detect_language("Это русский текст про оплату и договоры") == "rus+eng"
    assert detect_language("This is an English contract about payment") == "eng"
    assert detect_language("") == "rus+eng"


def test_surya_not_implemented():
    with pytest.raises(RuntimeError, match="Surya"):
        SuryaEngine().ocr_pdf_page("x.pdf", 0)


def test_ocr_dataclass():
    from app.services.ocr import PageResult

    p = PageResult(page_number=1, text="t", extraction_method="ocr", confidence=0.9)
    assert p.page_number == 1
