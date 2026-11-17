import os
import asyncio
from celery import Celery
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.future import select
from app.core.config import settings
from app.models.models import Document, DocumentChunk
from app.services.document_parser import extract_text_from_file, split_text_into_chunks
from app.services.ai_service import generate_embeddings, generate_document_summary

celery_app = Celery(
    "worker",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
)

engine = create_async_engine(settings.DATABASE_URL, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

async def async_process_document(document_id: str, file_path: str):
    async with AsyncSessionLocal() as session:
        doc = None
        try:
            result = await session.execute(select(Document).where(Document.id == document_id))
            doc = result.scalars().first()
            if not doc:
                return
            
            doc.status = "processing"
            await session.commit()

            ext = os.path.splitext(file_path)[1]
            text = extract_text_from_file(file_path, ext)
            
            summary = await generate_document_summary(text)
            doc.summary = summary

            chunks = split_text_into_chunks(text)
            
            batch_size = 100
            for i in range(0, len(chunks), batch_size):
                batch_texts = chunks[i:i+batch_size]
                embeddings = await generate_embeddings(batch_texts)

                for idx, (chunk_text, embedding) in enumerate(zip(batch_texts, embeddings)):
                    chunk_db = DocumentChunk(
                        document_id=doc.id,
                        chunk_index=i + idx,
                        content=chunk_text,
                        embedding=embedding
                    )
                    session.add(chunk_db)

            doc.status = "completed"
            await session.commit()
            print(f"Документ {document_id} успешно обработан и сохранен в БД.")
        except Exception as e:
            print(f"Ошибка обработки документа {document_id}: {e}")
            if doc:
                doc.status = "failed"
                await session.commit()

@celery_app.task(name="process_document_task")
def process_document_task(document_id: str, file_path: str):
    asyncio.run(async_process_document(document_id, file_path))
