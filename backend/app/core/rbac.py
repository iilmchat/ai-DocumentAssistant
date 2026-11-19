"""T8: RBAC — роли и иерархия прав."""

from fastapi import Depends, HTTPException, status

from app.api.auth import get_current_user
from app.models.models import User

ROLE_LEVELS = {"viewer": 0, "editor": 1, "admin": 2}


def require_role(minimum: str):
    """Зависимость: требует роль не ниже указанной."""
    required = ROLE_LEVELS.get(minimum, 1)

    async def checker(
        current_user: User = Depends(get_current_user),  # noqa: B008
    ) -> User:
        level = ROLE_LEVELS.get(str(current_user.role), 0)
        if level < required:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Требуется роль '{minimum}' или выше",
            )
        return current_user

    return checker


require_editor = require_role("editor")
require_admin = require_role("admin")
