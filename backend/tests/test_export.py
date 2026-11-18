from datetime import datetime

from app.services.export import ExportData, render_docx, render_markdown, render_pdf

SAMPLE = """# Обзор документа

Ключевые тезисы:*важны*.

- Первый пункт
- Второй пункт

## Выводы
**Итог:** всё хорошо."""


def _data() -> ExportData:
    return ExportData(title="Тестовый отчёт", summary=SAMPLE, created_at=datetime(2026, 11, 18))


def test_markdown_contains_title_and_summary():
    content = render_markdown(_data()).decode("utf-8")
    assert "# Тестовый отчёт" in content
    assert "Первый пункт" in content


def test_docx_is_valid_zip():
    content = render_docx(_data())
    assert content.startswith(b"PK")
    assert len(content) > 1000


def test_pdf_is_valid():
    content = render_pdf(_data())
    assert content.startswith(b"%PDF")
    assert len(content) > 1000
