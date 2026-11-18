"""Проверка и нормализация входных файлов.

Безопасность: MIME определяем по СОДЕРЖИМОМУ (magic bytes), а не по расширению;
ограничиваем размер; для DOCX защищаемся от ZIP-бомб лимитом распаковки.
"""

import hashlib
import os
import zipfile

from app.core.config import settings

# сигнатуры форматов
_MAGIC = {
    b"%PDF-": "application/pdf",
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"II*\x00": "image/tiff",
    b"MM\x00*": "image/tiff",
}


def compute_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def sniff_mime(path: str) -> str | None:
    """Определение типа по содержимому, а не по расширению."""
    with open(path, "rb") as f:
        head = f.read(8)
    for sig, mime in _MAGIC.items():
        if head.startswith(sig):
            return mime
    if head[:4] == b"PK\x03\x04":
        # zip — проверяем, что это OOXML (docx), а не произвольный архив
        try:
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
                if "word/document.xml" in names:
                    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                total_uncompressed = sum(i.file_size for i in z.infolist())
                compressed = max(os.path.getsize(path), 1)
                if total_uncompressed > 200 * compressed:  # ZIP-бомба
                    return "application/zip-bomb"
        except zipfile.BadZipFile:
            return None
    # txt: отказываемся от бинарных данных
    with open(path, "rb") as f:
        sample = f.read(4096)
    if b"\x00" not in sample:
        try:
            sample.decode("utf-8")
            return "text/plain"
        except UnicodeDecodeError:
            pass
    return None


ALLOWED_MIMES = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/tiff": ".tiff",
}

# Изображения распознаются целиком как одна страница и идут в OCR-очередь
IMAGE_MIMES = {"image/jpeg", "image/png", "image/tiff"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif"}


class ValidationError(Exception):
    pass


def validate_upload(file_path: str) -> str:
    """Возвращает канонический MIME или бросает ValidationError."""
    size = os.path.getsize(file_path)
    if size == 0:
        raise ValidationError("Пустой файл.")
    if size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"Файл больше лимита {settings.MAX_UPLOAD_SIZE_MB} МБ.")

    mime = sniff_mime(file_path)
    if mime == "application/zip-bomb":
        raise ValidationError("Архив с аномальной степенью сжатия (ZIP-бомба?).")
    if mime not in ALLOWED_MIMES:
        raise ValidationError(f"Неподдерживаемый или подозрительный тип файла: {mime!r}")
    return mime


def count_pdf_pages(path: str) -> int | None:
    try:
        from app.services.pymupdf_compat import fitz

        doc = fitz.open(path)
        try:
            return doc.page_count
        finally:
            doc.close()
    except Exception:
        return None
