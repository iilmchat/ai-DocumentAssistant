"""Этап S0: единый формат ошибок API.

Все собственные ошибки сериализуются как {"detail": ..., "code": ...}.
Стандартные HTTPException FastAPI остаются совместимыми (поле detail на месте).
"""


class AppError(Exception):
    status_code = 400
    code = "app_error"

    def __init__(self, detail: str, *, status_code: int | None = None):
        self.detail = detail
        if status_code is not None:
            self.status_code = status_code
        super().__init__(detail)


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ValidationAppError(AppError):
    status_code = 422
    code = "validation_error"
