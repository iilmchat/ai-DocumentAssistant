"""Этап 4 / S1: хеширование паролей, access/refresh JWT и чёрный список."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _create_token(subject: str, token_type: str, expires_delta: timedelta) -> tuple[str, str, int]:
    now = datetime.now(UTC)
    expire = now + expires_delta
    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return (
        jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM),
        jti,
        int(expire.timestamp()),
    )


def create_access_token(subject: str) -> str:
    token, _, _ = _create_token(subject, "access", timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    return token


def create_refresh_token(subject: str) -> str:
    token, _, _ = _create_token(subject, "refresh", timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    return token


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any] | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload


def decode_access_token(token: str) -> str | None:
    """Обратная совместимость: возвращает subject из access-токена."""
    payload = decode_token(token, "access")
    subject: str | None = payload.get("sub") if payload else None
    return subject
