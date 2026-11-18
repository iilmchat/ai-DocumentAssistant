from unittest.mock import Mock, patch

from app.core.config import settings
from app.services.text_extraction import (
    PageExtraction,
    StructuredBlock,
    _dedup_repeated_headers,
    _looks_like_list_line,
    _page_text_coverage,
    _plain_to_blocks,
    _table_to_markdown,
    build_heading_paths,
    chunk_pages,
    needs_ocr,
)


def test_plain_to_blocks():
    blocks = _plain_to_blocks("Первый абзац\n\nВторой абзац", 3)
    assert len(blocks) == 2
    assert all(b.kind == "paragraph" and b.page_number == 3 for b in blocks)
    assert _plain_to_blocks("  ", 1) == []


def test_table_to_markdown():
    md = _table_to_markdown([["A", "B"], ["1", "2"]])
    assert "| A | B |" in md
    assert "| 1 | 2 |" in md
    assert _table_to_markdown([]) == ""


def test_list_line_detection():
    assert _looks_like_list_line("- пункт")
    assert _looks_like_list_line("1) пункт")
    assert not _looks_like_list_line("обычный абзац")


def test_dedup_repeated_headers():
    pages = []
    for number in (1, 2, 3):
        blocks = [StructuredBlock("paragraph", "Уникальный текст страницы", page_number=number)]
        if number in (1, 2):
            blocks.insert(0, StructuredBlock("paragraph", "© ООО Ромашка", page_number=number))
        pages.append(PageExtraction(page_number=number, blocks=blocks))

    _dedup_repeated_headers(pages)
    assert all(not any("Ромашка" in b.text for b in p.blocks) for p in pages)


def test_heading_paths():
    pages = [
        PageExtraction(
            page_number=1,
            blocks=[
                StructuredBlock("heading", "Раздел 1"),
                StructuredBlock(
                    "heading",
                    "Подраздел с длинным названием, который считается уровнем 2 по эвристике",
                ),
                StructuredBlock("paragraph", "Текст"),
            ],
        )
    ]
    build_heading_paths(pages)
    assert "Раздел 1" in pages[0].blocks[2].heading_path


def test_chunk_pages_keeps_page_numbers_and_headings():
    pages = [
        PageExtraction(
            page_number=1,
            blocks=[
                StructuredBlock("heading", "Введение"),
                StructuredBlock("paragraph", "Текст введения " * 20),
            ],
        ),
        PageExtraction(
            page_number=2,
            blocks=[StructuredBlock("paragraph", "Продолжение " * 20)],
        ),
    ]
    chunks = chunk_pages(pages, chunk_size=300, chunk_overlap=0)
    assert chunks
    assert all(c["content"] and c["page_numbers"] for c in chunks)
    assert any("Введение" in c["headings"] for c in chunks)


def test_chunk_pages_never_splits_table():
    table_md = "| A | B |\n|---|---|\n| 1 | 2 |"
    pages = [PageExtraction(page_number=1, blocks=[StructuredBlock("table", table_md)])]
    chunks = chunk_pages(pages, chunk_size=10)
    assert len(chunks) == 1
    assert chunks[0]["content"] == table_md


def test_needs_ocr_on_short_text():
    page = Mock()
    page.get_text.return_value = "коротко"
    page.get_images.return_value = []
    assert needs_ocr(page, settings.OCR_MIN_CHARS_PER_PAGE)


def test_needs_ocr_on_long_text():
    page = Mock()
    page.get_text.return_value = "достаточно длинный текст " * 20
    page.get_images.return_value = []
    assert not needs_ocr(page, settings.OCR_MIN_CHARS_PER_PAGE)


def test_page_text_coverage():
    page = Mock()
    page.rect.width = 100
    page.rect.height = 100
    page.get_text.return_value = [
        (0, 0, 50, 50, "text", 0, 0),
    ]
    assert 0 < _page_text_coverage(page) <= 1


def test_extract_pages_from_image_uses_engine():
    engine = Mock()
    engine.ocr_image_file.return_value = ("распознанный текст", 0.9)
    with (
        patch("app.services.text_extraction.get_ocr_engine", return_value=engine),
        patch.object(settings, "OCR_ENGINE", "vision"),
    ):
        from app.services.text_extraction import extract_pages_from_image

        pages = extract_pages_from_image("scan.png")
    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert pages[0].extraction_method == "vision"
    assert pages[0].confidence == 0.9
    assert "распознанный текст" in pages[0].text
