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

    page_number: int  # 1-based
    text: str
    extraction_method: str  # "text_layer" | "ocr" | "vision"
    confidence: float  # 0..1


class OCREngine(ABC):
    """Абстрактный интерфейс OCR-движка. Реализации меняются через настройки."""

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def ocr_pdf_page(self, pdf_path: str, page_index: int) -> tuple[str, float]:
        """Распознать одну страницу PDF (0-based). Возвращает (текст, confidence 0..1)."""

    def ocr_image_file(self, image_path: str) -> tuple[str, float]:
        """Распознать файл изображения (JPG/PNG/TIFF) как одну страницу.

        Универсальная реализация: переводим изображение в одностраничный PDF
        через Pillow и используем уже существующий ocr_pdf_page. Работает и для
        Tesseract, и для vision-модели.
        """
        import io
        import os
        import tempfile

        from PIL import Image

        with Image.open(image_path) as img:
            prepared = img if img.mode in ("RGB", "L") else img.convert("RGB")
            buf = io.BytesIO()
            prepared.save(buf, format="PDF")
            image_bytes = buf.getvalue()

        fd, pdf_path = tempfile.mkstemp(suffix=".pdf")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(image_bytes)
            return self.ocr_pdf_page(pdf_path, 0)
        finally:
            if os.path.exists(pdf_path):
                os.unlink(pdf_path)


def detect_language(text: str) -> str:
    """S5: эвристика выбора языков Tesseract по доле кириллицы."""
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return "rus+eng"
    cyrillic = sum(1 for ch in letters if "А" <= ch <= "я" or ch in "Ёё")
    return "rus+eng" if cyrillic / len(letters) > 0.2 else "eng"


class PaddleEngine(OCREngine):
    """S5: альтернатива Tesseract на PaddleOCR (опциональная зависимость)."""

    def __init__(self, languages: str = "rus+eng"):
        self.languages = languages

    def available(self) -> bool:
        try:
            import paddleocr  # noqa: F401

            return True
        except ImportError:
            return False

    def ocr_pdf_page(self, pdf_path: str, page_index: int) -> tuple[str, float]:
        try:
            import numpy as np
            from paddleocr import PaddleOCR

            from app.services.pymupdf_compat import fitz
        except ImportError as exc:
            raise RuntimeError("PaddleOCR не установлен: pip install paddleocr") from exc

        langs = detect_language(self.languages) if self.languages == "auto" else self.languages
        ocr = PaddleOCR(lang="ru" if "rus" in langs else "en")
        doc = fitz.open(pdf_path)
        try:
            pix = doc.load_page(page_index).get_pixmap(dpi=300)
            image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        finally:
            doc.close()
        result = ocr.ocr(image)
        texts = [
            line[1][0] for page in (result or []) for line in (page or []) if line and len(line) > 1
        ]
        text = " ".join(texts).strip()
        return text, (0.8 if text else 0.0)


class SuryaEngine(OCREngine):
    """S5: Surya OCR (опциональная зависимость) — заготовка с понятной ошибкой."""

    def available(self) -> bool:
        try:
            import surya_ocr  # noqa: F401

            return True
        except ImportError:
            return False

    def ocr_pdf_page(self, pdf_path: str, page_index: int) -> tuple[str, float]:
        raise RuntimeError("Surya OCR требует отдельного сервиса/зависимостей — пока не подключён")


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
        from app.services.pymupdf_compat import fitz

        doc = fitz.open(pdf_path)
        try:
            page = doc.load_page(page_index)
            pix = page.get_pixmap(dpi=300, colorspace=fitz.csGRAY)
            image_bytes = pix.tobytes("png")
        finally:
            doc.close()

        languages = self.LANGUAGES
        if languages == "auto":
            # S5: быстрый eng-проход для определения алфавита, затем основной OCR
            probe, _ = self._tesseract_from_image(image_bytes, "eng")
            languages = detect_language(probe)
        return self._tesseract_from_image(image_bytes, languages)

    def _tesseract_from_image(self, image_bytes: bytes, languages: str) -> tuple[str, float]:
        try:
            import io

            import pytesseract
            from PIL import Image

            img = Image.open(io.BytesIO(image_bytes))
            data = pytesseract.image_to_data(
                img, lang=languages, output_type=pytesseract.Output.DICT
            )
            words: list[str] = []
            confs: list[float] = []
            for word, conf in zip(data["text"], data["conf"], strict=False):
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
            import os
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(image_bytes)
                tmp_path = tmp.name
            try:
                proc = subprocess.run(
                    ["tesseract", tmp_path, "stdout", "-l", languages, "--psm", "3"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if proc.returncode != 0:
                    raise RuntimeError(f"tesseract failed: {proc.stderr[:300]}")
                text = proc.stdout.strip()
                # без image_to_data уверенность оценить нельзя — ставим умеренную
                return text, 0.7 if text else 0.0
            finally:
                os.unlink(tmp_path)


class VisionEngine(OCREngine):
    """Современный вариант из roadmap: vision-модель (gpt-4o / gemini) по страницам PDF.

    Работает через OpenAI-совместимый эндпоинт, поэтому подходит и для Gemini
    (OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/).
    Метод синхронный по контракту OCREngine — вызывается в потоке через asyncio.to_thread.
    """

    def __init__(self, model: str | None = None):
        from app.core.config import settings

        self.model = model or settings.LLM_MODEL
        self.api_key = settings.OPENAI_API_KEY
        self.base_url = settings.OPENAI_BASE_URL

    def available(self) -> bool:
        return bool(self.api_key)

    def ocr_pdf_page(self, pdf_path: str, page_index: int) -> tuple[str, float]:
        import asyncio
        import base64
        import io

        from openai import AsyncOpenAI
        from PIL import Image

        from app.services.pymupdf_compat import fitz

        doc = fitz.open(pdf_path)
        try:
            page = doc.load_page(page_index)
            pix = page.get_pixmap(dpi=150)
            image_bytes = pix.tobytes("png")
        finally:
            doc.close()

        # сжимаем до разумного размера, чтобы не раздувать запрос
        img = Image.open(io.BytesIO(image_bytes))
        img.thumbnail((1600, 1600))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        async def _call() -> str:
            client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Извлеки весь текст с этой страницы документа максимально точно. Сохраняй абзацы и структуру. Верни только текст без комментариев.",
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/png;base64,{b64}"},
                            },
                        ],
                    }
                ],
                temperature=0.1,
            )
            return response.choices[0].message.content or ""

        text = asyncio.run(_call()).strip()
        return text, (0.85 if text else 0.0)


def get_ocr_engine(name: str | None = None) -> OCREngine:
    """Фабрика движков: tesseract (baseline) или vision (gpt-4o / gemini)."""
    from app.core.config import settings

    name = (name or settings.OCR_ENGINE or "tesseract").lower()
    if name == "tesseract":
        return TesseractEngine(settings.OCR_LANGUAGES)
    if name == "vision":
        return VisionEngine()
    if name == "paddle":
        return PaddleEngine(settings.OCR_LANGUAGES)
    if name == "surya":
        return SuryaEngine()
    raise ValueError(f"Неизвестный OCR-движок: {name}")
