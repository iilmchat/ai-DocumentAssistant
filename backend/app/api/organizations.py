"""T9: organization API и tenant-квоты."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.rbac import require_admin
from app.models.models import Document, Organization, User

router = APIRouter(prefix="/api/v1/organizations", tags=["Organizations"])


class OrganizationCreate(BaseModel):
    name: str
    slug: str | None = None


class OrganizationResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str | None
    documents: int = 0
    storage_bytes: int = 0


@router.post("", response_model=OrganizationResponse, status_code=201)
async def create_organization(
    payload: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not settings.MULTITENANT_ENABLED:
        raise HTTPException(status_code=404, detail="Мультитенантность отключена")
    exists = await db.execute(select(Organization).where(Organization.slug == payload.slug))
    if payload.slug and exists.scalars().first():
        raise HTTPException(status_code=409, detail="slug уже занят")
    org = Organization(name=payload.name, slug=payload.slug)
    db.add(org)
    await db.flush()
    current_user.org_id = org.id
    await db.commit()
    return OrganizationResponse(id=org.id, name=org.name, slug=org.slug)


@router.get("/me", response_model=OrganizationResponse | None)
async def my_organization(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.org_id:
        return None
    org = await db.get(Organization, current_user.org_id)
    if not org:
        return None
    users = (await db.execute(select(User.id).where(User.org_id == org.id))).scalars().all()
    count = await db.scalar(
        select(func.count()).select_from(Document).where(Document.user_id.in_(users))
    )
    size = await db.scalar(
        select(func.coalesce(func.sum(Document.size_bytes), 0)).where(Document.user_id.in_(users))
    )
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        documents=count or 0,
        storage_bytes=size or 0,
    )


@router.post("/{org_id}/members/{user_id}", status_code=204)
async def add_member(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    user.org_id = org_id
    await db.commit()
