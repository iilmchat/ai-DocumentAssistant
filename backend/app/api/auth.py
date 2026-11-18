"""Этап 4 / S1: регистрация, логин, refresh-токены, logout и аудит."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.cache import (
    blacklist_jti,
    clear_failed_logins,
    is_jti_blacklisted,
    register_failed_login,
)
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.models import AuditLog, User
from app.services.audit import log_action

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

bearer_scheme = HTTPBearer(auto_error=False)


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    action: str
    resource_type: str | None
    resource_id: str | None
    ip_address: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Необходим действующий токен доступа",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not credentials:
        raise unauthorized

    payload = decode_token(credentials.credentials, "access")
    if not payload:
        raise unauthorized
    if await is_jti_blacklisted(payload["jti"]):
        raise unauthorized
    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError as exc:
        raise unauthorized from exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise unauthorized
    return user


def _validate_credentials(email: str, password: str) -> tuple[str, str]:
    email = email.strip().lower()
    if "@" not in email or len(email) < 5:
        raise HTTPException(status_code=400, detail="Некорректный email")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Пароль должен быть не короче 6 символов")
    return email, password


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _tokens_for(user_id: uuid.UUID) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(str(user_id)),
        refresh_token=create_refresh_token(str(user_id)),
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(settings.REGISTER_RATE_LIMIT)
async def register(request: Request, payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    email, password = _validate_credentials(payload.email, payload.password)
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="Пользователь с таким email уже существует")

    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    await db.flush()
    await log_action(db, user.id, "register", ip_address=_client_ip(request))
    await db.commit()
    return _tokens_for(user.id)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def login(request: Request, payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    email = payload.email.strip().lower()
    ip = _client_ip(request)
    lock_key = f"auth:failed:{email}:{ip or 'unknown'}"
    failures = await register_failed_login(lock_key)
    if failures > settings.MAX_FAILED_LOGINS:
        raise HTTPException(status_code=429, detail="Слишком много неудачных попыток входа")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")

    await clear_failed_logins(lock_key)
    await log_action(db, user.id, "login", ip_address=ip)
    await db.commit()
    return _tokens_for(user.id)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(settings.LOGIN_RATE_LIMIT)
async def refresh(request: Request, payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    token_payload = decode_token(payload.refresh_token, "refresh")
    if not token_payload:
        raise HTTPException(status_code=401, detail="Недействительный refresh-токен")
    try:
        user_id = uuid.UUID(token_payload["sub"])
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Недействительный refresh-токен") from exc

    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalars().first():
        raise HTTPException(status_code=401, detail="Недействительный refresh-токен")

    # ротация: старый refresh-токен больше не действует
    await blacklist_jti(token_payload["jti"], token_payload["exp"])
    await log_action(db, user_id, "refresh", ip_address=_client_ip(request))
    await db.commit()
    return _tokens_for(user_id)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    current_user: User = Depends(get_current_user),
):
    payload = decode_token(credentials.credentials, "access")  # type: ignore[union-attr]
    if payload:
        await blacklist_jti(payload["jti"], payload["exp"])


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/audit-log", response_model=list[AuditLogResponse])
async def audit_log(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.user_id == current_user.id)
        .order_by(AuditLog.created_at.desc())
        .limit(min(limit, 200))
    )
    return result.scalars().all()
