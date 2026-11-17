import os
from celery import Celery
from app.services.document_parser import extract_text_from_file, split_text_into_chunks

celery_app = Celery(
    "worker",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
)

@celery_app.task(name="process_document_task")
def process_document_task(document_id: str, file_path: str):
    print(f"Начата обработка документа {document_id}, путь: {file_path}")
    ext = os.path.splitext(file_path)[1]
    text = extract_text_from_file(file_path, ext)
    chunks = split_text_into_chunks(text)
    print(f"Документ разбит на {len(chunks)} чанков.")
    return {"status": "success", "chunks_count": len(chunks)}
