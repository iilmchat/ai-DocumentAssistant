import os
import re
from typing import List
from pypdf import PdfReader
from docx import Document as DocxDocument

def extract_text_from_file(file_path: str, file_extension: str) -> str:
    """Извлекает сырой текст из файлов."""
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

def split_text_into_sentences(text: str) -> List[str]:
    """Разбивает текст на предложения с учетом базовых правил пунктуации."""
    # Регулярное выражение ищет точки, вопросительные и восклицательные знаки,
    # после которых идет пробел, игнорируя сокращения (например, "т.е." или "Mr.")
    pattern = r'(?<!\w\.\w.)(?<![А-ЯA-Z][а-яa-z]\.)(?<=\.|\?|!)\s'
    sentences = re.split(pattern, text.strip())
    return [s.strip() for s in sentences if s.strip()]

def split_text_into_chunks(
    text: str, 
    max_chunk_size: int = 1000, 
    chunk_overlap: int = 200
) -> List[str]:
    """
    Умный чанкинг: склеивает предложения в чанки заданного размера.
    Гарантирует, что предложения не будут разрезаны пополам.
    """
    if not text:
        return []
        
    sentences = split_text_into_sentences(text)
    if not sentences:
        return [text]

    chunks = []
    current_chunk = []
    current_length = 0
    
    for sentence in sentences:
        sentence_length = len(sentence)
        
        # Если добавление текущего предложения превышает лимит и у нас уже есть что-то в чанке
        if current_length + sentence_length > max_chunk_size and current_chunk:
            # Сохраняем собранный чанк
            chunks.append(" ".join(current_chunk))
            
            # Формируем overlap (перекрытие): берем последние предложения из предыдущего чанка
            # чтобы сохранить контекст на стыке
            overlap_chunk = []
            overlap_length = 0
            for s in reversed(current_chunk):
                if overlap_length + len(s) <= chunk_overlap:
                    overlap_chunk.insert(0, s)
                    overlap_length += len(s) + 1 # +1 за пробел
                else:
                    break
            
            current_chunk = overlap_chunk
            current_length = overlap_length
            
        current_chunk.append(sentence)
        current_length += sentence_length + 1
        
    # Не забываем добавить последний чанк
    if current_chunk:
        chunks.append(" ".join(current_chunk))
        
    return chunks