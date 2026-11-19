"""T8: CSRF-защита (double-submit cookie) для cookie-аутентификации.

Сервер выставляет не-httpOnly cookie `csrf_token`; state-changing запросы обязаны
повторить его значение в заголовке `X-CSRF-Token`. Bearer-клиенты освобождаются —
у них нет cookie, и CSRF им не угрожает.
"""

import secrets
from typing import Literal, cast

from fastapi import HTTPException, Request, Response

from app.core.config import settings


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=token,
        httponly=False,  # JS должен прочитать и отправить его значение в заголовке
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=cast(Literal["lax", "strict", "none"], settings.SESSION_COOKIE_SAMESITE),
        path="/",
    )


async def enforce_csrf(request: Request) -> None:
    if not settings.CSRF_ENFORCE:
        return
    if request.method in {"GET", "HEAD", "OPTIONS", "TRACE"}:
        return
    # Логин/регистрация/refresh не подвержены классическому CSRF: до них нет сессии,
    # а доступ подтверждён паролем или refresh-токеном. CSRF-cookie ещё может отсутствовать.
    if request.url.path.startswith("/api/v1/auth/"):
        return
    bearer = request.headers.get("authorization", "")
    if bearer.lower().startswith("bearer "):
        return  # Bearer-клиент не подвержен CSRF
    cookie_token = request.cookies.get(settings.CSRF_COOKIE_NAME)
    header_token = request.headers.get(settings.CSRF_HEADER_NAME)
    if not cookie_token or not header_token or cookie_token != header_token:
        raise HTTPException(status_code=403, detail="CSRF token missing or invalid")
