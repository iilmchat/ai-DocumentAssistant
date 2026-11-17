import os
import uuid
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.core.config import settings
from app.core.database import get_db
from app.models.models import Document, User
from app.schemas.schemas import DocumentResponse
from app.worker import process_document_task

router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])

# Каталог для загруженных файлов. Внутри Docker-контейнера это /app/storage
# (именно этот путь монтируется в volume shared_storage). При локальном запуске
# из корня backend/ файлы попадают в ./storage.
UPLOAD_DIR = settings.UPLOAD_DIR or os.environ.get("STORAGE_PATH") or "storage"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = [".pdf", ".docx", ".txt"]


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).limit(1))
    user = result.scalars().first()
    if not user:
        user = User(email="test@example.com", password_hash="hashed_dummy")
        db.add(user)
        await db.commit()
        await db.refresh(user)

    file_ext = os.path.splitext(file.filename)[1]
    if file_ext.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Неподдерживаемый формат файла.")

    file_name = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, file_name)

    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    new_doc = Document(
        user_id=user.id,
        title=file.filename,
        file_path=file_path,
        status="pending"
    )
    db.add(new_doc)
    await db.commit()
    await db.refresh(new_doc)

    process_document_task.delay(str(new_doc.id), file_path)

    return new_doc

@router.get("/", response_model=list[DocumentResponse])
async def list_documents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).order_by(Document.created_at.desc()))
    documents = result.scalars().all()
    return documents

@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail="Документ не найден.")
    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)
    await db.delete(doc)
    await db.commit()
