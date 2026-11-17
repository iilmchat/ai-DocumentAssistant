"""Движок OCR.

Этап 1-2 плана: гибридное извлечение текста + абстракция OCREngine,
чтобы движок можно было менять per-document (Tesseract baseline,
при необходимости PaddleOCR / Surya / vision-модель).
"""
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class PageResult:
    """Постраничный результат извлечения (Этап 1)."""
    page_number: int          # 1-based
    text: str
    extraction_method: str    # "text_layer" | "ocr" | "vision"
    confidence: float         # 0..1


class OCREngine(ABC):
    """Абстрактный интерфейс OCR-движка. Реализации меняются через настройки."""

    @abstractmethod
    def available(self) -> bool:
        ...

    @abstractmethod
    def ocr_pdf_page(self, pdf_path: str, page_index: int) -> tuple[str, float]:
        """Распознать одну страницу PDF (0-based). Возвращает (текст, confidence 0..1)."""


class TesseractEngine(OCREngine):
    """Baseline: Tesseract 5 с rus+eng. Предобработка (deskew/denoise) — через ocrmypdf,
    если он установлен в образе воркера; иначе — прямой pytesseract по растру страницы."""

    LANGUAGES = "rus+eng"

    def __init__(self, languages: str | None = None):
        if languages:
            self.LANGUAGES = languages

    def available(self) -> bool:
        return shutil.which("tesseract") is not None

    def ocr_pdf_page(self, pdf_path: str, page_index: int) -> tuple[str, float]:
        import fitz  # PyMuPDF

        doc = fitz.open(pdf_path)
        try:
            page = doc.load_page(page_index)
            pix = page.get_pixmap(dpi=300, colorspace=fitz.csGRAY)
            image_bytes = pix.tobytes("png")
        finally:
            doc.close()

        try:
            import pytesseract
            from PIL import Image
            import io

            img = Image.open(io.BytesIO(image_bytes))
            data = pytesseract.image_to_data(
                img, lang=self.LANGUAGES, output_type=pytesseract.Output.DICT
            )
            words: list[str] = []
            confs: list[float] = []
            for word, conf in zip(data["text"], data["conf"]):
                word = (word or "").strip()
                if not word:
                    continue
                words.append(word)
                try:
                    c = float(conf)
                    if c >= 0:  # -1 означает "не слово", не учитываем
                        confs.append(c)
                except (TypeError, ValueError):
                    pass

            text = " ".join(words)
            confidence = (sum(confs) / len(confs) / 100.0) if confs else 0.0
            return text, round(confidence, 3)
        except ImportError:
            # pytesseract недоступен — зовём бинарь tesseract напрямую
            import tempfile, os

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(image_bytes)
                tmp_path = tmp.name
            try:
                proc = subprocess.run(
                    ["tesseract", tmp_path, "stdout", "-l", self.LANGUAGES, "--psm", "3"],
                    capture_output=True, text=True, timeout=120,
                )
                if proc.returncode != 0:
                    raise RuntimeError(f"tesseract failed: {proc.stderr[:300]}")
                text = proc.stdout.strip()
                # без image_to_data уверенность оценить нельзя — ставим умеренную
                return text, 0.7 if text else 0.0
            finally:
                os.unlink(tmp_path)


def get_ocr_engine(name: str | None = None) -> OCREngine:
    """Фабрика движков. Этап 2: интерфейс абстрактный, реализацию выбираем настройкой."""
    name = (name or "tesseract").lower()
    if name == "tesseract":
        return TesseractEngine()
    # сюда позже добавляются paddle / surya / vision — per-document переключение
    raise ValueError(f"Неизвестный OCR-движок: {name}")
