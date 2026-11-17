import os
from typing import List
from pypdf import PdfReader
from docx import Document as DocxDocument

def extract_text_from_file(file_path: str, file_extension: str) -> str:
    text = ""
    if file_extension.lower() == ".pdf":
        reader = PdfReader(file_path)
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
    elif file_extension.lower() in [".docx", ".doc"]:
        doc = DocxDocument(file_path)
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
    else:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    return text

def split_text_into_chunks(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
    if not text:
        return []
    
    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk.strip())
        start += chunk_size - chunk_overlap

    return [c for c in chunks if c]
