"""Этап 7: экспорт конспекта в Markdown / DOCX / PDF."""

import io
import os
import re
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ExportData:
    title: str
    summary: str
    created_at: datetime | None = None
    # S5: Приложение с постраничными источниками
    sources: list[dict] | None = None


def _plain(text: str) -> str:
    """Убираем markdown-разметку для текстовых форматов."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    return text.strip()


@dataclass
class _Line:
    text: str
    kind: str  # title | heading | bullet | paragraph | space


def _parse(summary: str, title: str, sources: list[dict] | None = None) -> list[_Line]:
    lines: list[_Line] = [_Line(title, "title")]
    for raw in (summary or "").splitlines():
        line = raw.rstrip()
        if not line.strip():
            lines.append(_Line("", "space"))
        elif re.match(r"^#{1,6}\s", line):
            lines.append(_Line(_plain(re.sub(r"^#{1,6}\s+", "", line)), "heading"))
        elif re.match(r"^\s*([-*+]|\d+[.)])\s+", line):
            lines.append(_Line(_plain(re.sub(r"^\s*([-*+]|\d+[.)])\s+", "", line)), "bullet"))
        else:
            lines.append(_Line(_plain(line), "paragraph"))

    if sources:
        lines.append(_Line("", "space"))
        lines.append(_Line("Источники по страницам", "heading"))
        for source in sources:
            label = (
                f"Стр. {source.get('page', '?')} ({source.get('extraction_method', 'text_layer')})"
            )
            snippet = str(source.get("snippet", ""))[:300]
            lines.append(_Line(f"{label}: {snippet}", "bullet"))
    return lines


def render_markdown(data: ExportData) -> bytes:
    header = f"# {data.title}\n"
    if data.created_at:
        header += f"\n_Создан: {data.created_at.strftime('%Y-%m-%d %H:%M')}_\n"
    body = header + "\n" + (data.summary or "") + "\n"
    if data.sources:
        body += "\n## Источники по страницам\n\n"
        for source in data.sources:
            body += (
                f"- Стр. {source.get('page', '?')} "
                f"({source.get('extraction_method', 'text_layer')}): "
                f"{str(source.get('snippet', ''))[:300]}\n"
            )
    return body.encode("utf-8")


def render_docx(data: ExportData) -> bytes:
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    for line in _parse(data.summary, data.title, data.sources):
        if line.kind == "title":
            doc.add_heading(line.text, level=0)
        elif line.kind == "heading":
            doc.add_heading(line.text, level=2)
        elif line.kind == "bullet":
            doc.add_paragraph(line.text, style="List Bullet")
        elif line.kind == "paragraph":
            p = doc.add_paragraph(line.text)
            for run in p.runs:
                run.font.size = Pt(11)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _find_font() -> str | None:
    candidates = [
        os.environ.get("EXPORT_FONT", ""),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/DejaVuSans.ttf",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def _wrap(text: str, font, fontsize: float, max_width: float) -> list[str]:
    words = re.split(r"\s+", text.strip())
    if not words or words == [""]:
        return [""]
    out: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if font.text_length(candidate, fontsize=fontsize) <= max_width or not current:
            current = candidate
        else:
            out.append(current)
            current = word
    if current:
        out.append(current)
    return out


def render_pdf(data: ExportData) -> bytes:
    from app.services.pymupdf_compat import fitz

    font_path = _find_font()
    doc = fitz.open()
    page = doc.new_page()
    width, height = page.rect.width, page.rect.height
    margin_x, margin_y = 50, 50
    max_width = width - 2 * margin_x
    y = margin_y

    fontname = "f0"
    if font_path:
        page.insert_font(fontname=fontname, fontfile=font_path)
        font = fitz.Font(fontfile=font_path)
    else:
        fontname = "helv"
        font = fitz.Font(fontname="helv")

    def new_page_if_needed(step: float) -> None:
        nonlocal page, y
        if y + step > height - margin_y:
            page = doc.new_page()
            if font_path:
                page.insert_font(fontname=fontname, fontfile=font_path)
            y = margin_y

    for line in _parse(data.summary, data.title, data.sources):
        if line.kind == "space":
            y += 6
            continue
        fontsize = 20 if line.kind == "title" else (14 if line.kind == "heading" else 11)
        prefix = "• " if line.kind == "bullet" else ""
        chunks = _wrap(prefix + line.text, font, fontsize, max_width)
        for chunk in chunks:
            new_page_if_needed(fontsize + 6)
            page.insert_text(
                (margin_x, y + fontsize),
                chunk,
                fontname=fontname,
                fontsize=fontsize,
                color=(0, 0, 0),
            )
            y += fontsize + 6
        y += 3

    return doc.tobytes(garbage=3, deflate=True)
