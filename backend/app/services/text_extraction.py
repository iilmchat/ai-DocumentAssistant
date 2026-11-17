"""Этап 1 + Этап 3: гибридное постраничное извлечение текста и структурированные чанки.

- PyMuPDF (fitz) открывает страницу, считает символы и покрытие площади текстом.
  Если символов < OCR_MIN_CHARS_PER_PAGE (~100) или страница — картинка на весь лист,
  страница уходит в OCR, иначе берётся текстовый слой.
- Результат постраничный, с флагом extraction_method и confidence -> цитаты с номерами страниц.
- Чанкинг по семантическим границам (заголовки/абзацы), таблицы конвертируются в Markdown
  и не разрываются между чанками; повторяющиеся колонтитулы дедуплицируются.
"""
import re
from dataclasses import dataclass, field

from app.core.config import settings
from app.services.ocr import PageResult, get_ocr_engine


@dataclass
class StructuredBlock:
    """Семантический блок страницы: абзац, заголовок, список или таблица."""
    kind: str            # heading | paragraph | list | table
    text: str
    heading_path: str = ""   # "Раздел 1 > Подраздел 1.2" — для контекста чанка
    page_number: int = 1


@dataclass
class PageExtraction:
    page_number: int
    blocks: list[StructuredBlock] = field(default_factory=list)
    extraction_method: str = "text_layer"
    confidence: float = 1.0

    @property
    def text(self) -> str:
        return "\n\n".join(b.text for b in self.blocks)


# ---------------------------------------------------------------------------
# Гибридное извлечение (Этап 1)
# ---------------------------------------------------------------------------

def _page_text_coverage(page) -> float:
    """Доля площади страницы, покрытая текстовыми блоками (0..1)."""
    try:
        rect = page.rect
        area = float(rect.width * rect.height) or 1.0
        covered = 0.0
        for block in page.get_text("blocks"):
            x0, y0, x1, y1 = block[:4]
            covered += max(0.0, (x1 - x0)) * max(0.0, (y1 - y0))
        return min(covered / area, 1.0)
    except Exception:
        return 0.0


def _is_full_page_image(page) -> bool:
    """Страница-скан: одна картинка занимает почти весь лист, текста нет."""
    try:
        images = page.get_images(full=True)
        if not images:
            return False
        rect = page.rect
        for img in images:
            xref = img[0]
            try:
                bbox = page.get_image_bbox(img)
            except Exception:
                continue
            if bbox.is_empty:
                continue
            coverage = abs(bbox.get_area()) / (float(rect.get_area()) or 1.0)
            if coverage >= settings.OCR_IMAGE_AREA_THRESHOLD:
                return True
        return False
    except Exception:
        return False


def needs_ocr(page, min_chars: int) -> bool:
    raw = page.get_text("text") or ""
    stripped = re.sub(r"\s+", "", raw)
    if len(stripped) < min_chars:
        return True
    if _is_full_page_image(page) and _page_text_coverage(page) < 0.05:
        return True
    return False


def extract_pages(pdf_path: str) -> list[PageExtraction]:
    """Постранично: текстовый слой или OCR. Возвращает блоки со структурой."""
    import fitz  # PyMuPDF

    engine = get_ocr_engine(settings.OCR_ENGINE)
    results: list[PageExtraction] = []

    doc = fitz.open(pdf_path)
    try:
        for idx in range(doc.page_count):
            page = doc.load_page(idx)
            page_no = idx + 1

            if needs_ocr(page, settings.OCR_MIN_CHARS_PER_PAGE):
                try:
                    text, conf = engine.ocr_pdf_page(pdf_path, idx)
                    results.append(PageExtraction(
                        page_number=page_no,
                        blocks=_plain_to_blocks(text, page_no),
                        extraction_method="ocr",
                        confidence=conf,
                    ))
                    continue
                except Exception as e:
                    # OCR недоступен/упал — падаем обратно на текстовый слой
                    print(f"OCR failed on page {page_no}: {e}")

            blocks = _parse_page_structure(page, page_no)
            raw_len = len(re.sub(r"\s+", "", page.get_text("text") or ""))
            conf = 1.0 if raw_len else 0.0
            results.append(PageExtraction(
                page_number=page_no, blocks=blocks,
                extraction_method="text_layer", confidence=conf,
            ))
    finally:
        doc.close()

    _dedup_repeated_headers(results)
    return results


# ---------------------------------------------------------------------------
# Структура страницы (Этап 3): заголовки, списки, таблицы -> Markdown
# ---------------------------------------------------------------------------

_LIST_RE = re.compile(r"^\s*((?:[-•▪◦*])|(\d+[.)]?)|(?:[а-яa-z]{1,3}[.)]))\s+")

def _looks_like_list_line(line: str) -> bool:
    return bool(_LIST_RE.match(line))

def _font_size_of_block(block) -> float:
    """Максимальный размер шрифта в текстовом блоке."""
    sizes = []
    try:
        for line in block["lines"]:
            for span in line["spans"]:
                sizes.append(span["size"])
    except Exception:
        pass
    return max(sizes) if sizes else 0.0

def _block_text_from_dict(block: dict) -> str:
    lines = []
    for line in block.get("lines", []):
        parts = [span["text"] for span in line.get("spans", [])]
        lines.append("".join(parts))
    return "\n".join(lines).strip()


def _table_to_markdown(table: list[list[str]]) -> str:
    rows = [[re.sub(r"\s+", " ", (c or "").strip()) for c in row] for row in table if row]
    rows = [r for r in rows if any(r)]
    if not rows:
        return ""
    ncols = max(len(r) for r in rows)
    rows = [r + [""] * (ncols - len(r)) for r in rows]
    md = ["| " + " | ".join(rows[0]) + " |",
          "|" + "---|" * ncols]
    for r in rows[1:]:
        md.append("| " + " | ".join(r) + " |")
    return "\n".join(md)


def _parse_page_structure(page, page_no: int) -> list[StructuredBlock]:
    """Блоки PyMuPDF dict -> heading/paragraph/list/table с сохранением иерархии."""
    blocks: list[StructuredBlock] = []

    # Таблицы через finder (PyMuPDF >= 1.23)
    table_ranges: list[tuple[float, float]] = []
    try:
        finder = page.find_tables()
        for t in finder.tables:
            md = _table_to_markdown(t.extract())
            if md:
                blocks.append(StructuredBlock(kind="table", text=md, page_number=page_no))
                bb = t.bbox
                table_ranges.append((bb[1], bb[3]))
    except Exception:
        pass

    data = page.get_text("dict")
    # медианный размер шрифта как базовый
    all_sizes = sorted(
        s["size"] for b in data["blocks"] if b["type"] == 0
        for l in b["lines"] for s in l["spans"] if s["text"].strip()
    )
    base_size = all_sizes[len(all_sizes) // 2] if all_sizes else 11.0

    for b in data["blocks"]:
        if b["type"] != 0:
            continue
        y0, y1 = b["bbox"][1], b["bbox"][3]
        if any(y0 < ty1 and ty0 < y1 for ty0, ty1 in table_ranges):
            continue  # этот текст уже покрыт таблицей
        text = _block_text_from_dict(b)
        if not text:
            continue
        size = _font_size_of_block(b)
        first_line = text.split("\n", 1)[0].strip()

        if size >= base_size * 1.25 and len(first_line) < 120 and len(text) < 240:
            blocks.append(StructuredBlock(kind="heading", text=first_line, page_number=page_no))
        elif all(_looks_like_list_line(ln) for ln in text.split("\n") if ln.strip()):
            items = [ln.strip() for ln in text.split("\n") if ln.strip()]
            norm = [re.sub(_LIST_RE, "- ", it) if _LIST_RE.match(it) else f"- {it}" for it in items]
            blocks.append(StructuredBlock(kind="list", text="\n".join(norm), page_number=page_no))
        else:
            blocks.append(StructuredBlock(kind="paragraph", text=text, page_number=page_no))

    return blocks


def _plain_to_blocks(text: str, page_no: int) -> list[StructuredBlock]:
    """Для OCR-текста структуры нет — режем по пустым строкам."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paras and text.strip():
        paras = [text.strip()]
    return [StructuredBlock(kind="paragraph", text=p, page_number=page_no) for p in paras]


# ---------------------------------------------------------------------------
# Дедупликация колонтитулов (Этап 3)
# ---------------------------------------------------------------------------

def _dedup_repeated_headers(pages: list[PageExtraction]) -> None:
    """Блоки, повторяющиеся (нормализованно) на >=60% страниц, удаляем везде."""
    from collections import Counter
    counter: Counter[str] = Counter()
    total = max(len(pages), 1)
    for p in pages:
        seen_on_page = set()
        for b in p.blocks:
            key = re.sub(r"\W+", "", b.text.lower())[:80]
            if key and key not in seen_on_page:
                counter[key] += 1
                seen_on_page.add(key)
    repeated = {k for k, c in counter.items() if c >= max(2, int(total * 0.6))}
    if not repeated:
        return
    for p in pages:
        p.blocks = [
            b for b in p.blocks
            if re.sub(r"\W+", "", b.text.lower())[:80] not in repeated
        ]


# ---------------------------------------------------------------------------
# Семантический чанкинг (Этап 3) + обратные ссылки на страницы (Этап 1)
# ---------------------------------------------------------------------------

def build_heading_paths(pages: list[PageExtraction]) -> None:
    """Проставляем каждому блоку heading_path вида 'Раздел > Подраздел'."""
    stack: list[tuple[int, str]] = []  # (level, title)
    for p in pages:
        for b in p.blocks:
            if b.kind == "heading":
                level = 1 if b.text.isupper() or len(b.text) < 40 else 2
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, b.text))
                b.heading_path = " > ".join(t for _, t in stack[:-1])
            else:
                b.heading_path = " > ".join(t for _, t in stack)


def chunk_pages(
    pages: list[PageExtraction],
    chunk_size: int = 1200,
    chunk_overlap: int = 150,
) -> list[dict]:
    """Чанки по семантическим границам. Таблицы не разрываются.
    Каждый чанк несёт page_numbers и methods для цитирования в RAG."""
    build_heading_paths(pages)
    chunks: list[dict] = []
    current_parts: list[str] = []
    current_len = 0
    current_pages: set[int] = set()
    current_methods: set[str] = set()
    current_headings: set[str] = set()

    def flush():
        nonlocal current_parts, current_len, current_pages, current_methods, current_headings
        if current_len > 0:
            text = "\n\n".join(current_parts).strip()
            if text:
                chunks.append({
                    "content": text,
                    "page_numbers": sorted(current_pages),
                    "extraction_method": ",".join(sorted(current_methods)) or "text_layer",
                    "headings": sorted(current_headings)[:5],
                })
        current_parts, current_len, current_pages, current_methods, current_headings = [], 0, set(), set(), set()

    for p in pages:
        for b in p.blocks:
            piece = b.text
            if b.heading_path:
                piece = f"[{b.heading_path}]\n{piece}"
            # таблица целиком, если влезает хотя бы в один чанк — иначе отдельным чанком
            if b.kind == "table" and current_len + len(piece) > chunk_size:
                flush()
            if current_len + len(piece) > chunk_size and current_len > 0:
                flush()
            current_parts.append(piece)
            current_len += len(piece)
            current_pages.add(p.page_number)
            current_methods.add(p.extraction_method)
            if b.kind == "heading":
                current_headings.add(b.text)
        # конец страницы — не обязательная граница, но подчищаем хвост перекоса
    flush()

    # overlap: добавляем хвост предыдущего чанка к началу следующего (для связности)
    if chunk_overlap > 0:
        for i in range(1, len(chunks)):
            tail = chunks[i - 1]["content"][-chunk_overlap:]
            head = chunks[i]["content"][:40]
            if tail.strip() and not head.startswith(tail[-20:].strip()):
                chunks[i]["content"] = "...(продолжение)\n" + tail + "\n\n" + chunks[i]["content"]
                chunks[i]["page_numbers"] = sorted(set(chunks[i]["page_numbers"]) | set(chunks[i - 1]["page_numbers"]))
    return chunks
