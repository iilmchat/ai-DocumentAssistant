"""T9: object storage, организации, парсеры новых форматов."""

from unittest.mock import patch

from app.core import config
from app.services import storage
from app.services.extended_parsers import (
    EXTRACTORS,
    extract_text_from_eml,
    extract_text_from_pptx,
    extract_text_from_xlsx,
)


def test_local_storage_roundtrip(tmp_path):
    backend = storage.LocalStorage(str(tmp_path))
    path = backend.save("file.pdf", b"hello")
    assert path.endswith("file.pdf")
    with backend.open("file.pdf") as f:
        assert f.read() == b"hello"
    backend.delete("file.pdf")
    assert not (tmp_path / "file.pdf").exists()


def test_storage_factory_local():
    with patch.object(config.settings, "STORAGE_BACKEND", "local"):
        storage.reset_storage()
        assert isinstance(storage.get_storage(), storage.LocalStorage)
    storage.reset_storage()


def test_new_formats_registered():
    assert ".xlsx" in EXTRACTORS
    assert ".pptx" in EXTRACTORS
    assert ".eml" in EXTRACTORS


def test_eml_parser(tmp_path):
    path = tmp_path / "mail.eml"
    path.write_bytes(
        b"From: a@example.com\nTo: b@example.com\nSubject: Test\n"
        b"Content-Type: text/plain; charset=utf-8\n\nHello body"
    )
    text = extract_text_from_eml(str(path))
    assert "a@example.com" in text
    assert "Test" in text
    assert "Hello body" in text


def test_xlsx_parser(tmp_path):
    from openpyxl import Workbook

    path = tmp_path / "book.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["Имя", "Сумма"])
    ws.append(["Оплата", 100])
    wb.save(path)
    text = extract_text_from_xlsx(str(path))
    assert "Имя" in text
    assert "Оплата" in text
    assert "100" in text


def test_pptx_parser(tmp_path):
    from pptx import Presentation

    path = tmp_path / "slides.pptx"
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[0])
    slide.shapes.title.text = "Заголовок слайда"
    prs.save(path)
    assert "Заголовок слайда" in extract_text_from_pptx(str(path))


def test_org_model_fields():
    from app.models.models import Organization, User

    assert hasattr(Organization, "name")
    assert hasattr(Organization, "slug")
    assert hasattr(User, "org_id")


def test_config_multitenant_defaults():
    assert config.settings.MULTITENANT_ENABLED is True
    assert config.settings.STORAGE_BACKEND in {"local", "s3"}
