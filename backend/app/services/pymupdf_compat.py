"""Единый импорт PyMuPDF: в новых версиях пакет называется pymupdf."""

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover — старые сборки PyMuPDF
    import fitz  # type: ignore[no-redef]

__all__ = ["fitz"]
