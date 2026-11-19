"""T9: парсеры дополнительных форматов (XLSX/PPTX/EML/аудио)."""

from email import policy
from email.parser import BytesParser


def extract_text_from_xlsx(path: str) -> str:
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    parts: list[str] = []
    for ws in wb.worksheets:
        parts.append(f"# Лист: {ws.title}")
        for row in ws.iter_rows(values_only=True):
            values = [str(cell) for cell in row if cell is not None]
            if values:
                parts.append(" | ".join(values))
    wb.close()
    return "\n".join(parts)


def extract_text_from_pptx(path: str) -> str:
    from pptx import Presentation

    prs = Presentation(path)
    parts: list[str] = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text_frame.text.strip():
                parts.append(shape.text_frame.text.strip())
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    parts.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(parts)


def extract_text_from_eml(path: str) -> str:
    with open(path, "rb") as f:
        msg = BytesParser(policy=policy.default).parse(f)
    parts = [
        f"From: {msg.get('from', '')}",
        f"To: {msg.get('to', '')}",
        f"Subject: {msg.get('subject', '')}",
    ]
    for part in msg.walk():
        if part.get_content_type() == "text/plain" and not part.is_multipart():
            payload = part.get_payload(decode=True) or b""
            charset = part.get_content_charset() or "utf-8"
            parts.append(bytes(payload).decode(charset, errors="replace"))
    return "\n\n".join(parts)


async def transcribe_audio(path: str) -> str:
    """S9: транскрибация через OpenAI-совместимый whisper endpoint."""
    from app.services.ai_service import client

    with open(path, "rb") as f:
        result = await client.audio.transcriptions.create(model="whisper-1", file=f)
    return str(result.text)


EXTRACTORS = {
    ".xlsx": extract_text_from_xlsx,
    ".pptx": extract_text_from_pptx,
    ".eml": extract_text_from_eml,
}
