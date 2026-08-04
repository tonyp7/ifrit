import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import InvalidTokenError, decode_token
from app.core.db import get_db
from app.models.user import User
from app.services.user_service import get_user_by_id

UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
)


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User:
    token = request.cookies.get("access_token")
    if token is None:
        raise UNAUTHORIZED

    try:
        payload = decode_token(token, expected_type="access")
    except InvalidTokenError as err:
        raise UNAUTHORIZED from err

    user = await get_user_by_id(db, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise UNAUTHORIZED

    return user


def require_roles(*allowed_roles: str) -> Callable[[User], User]:
    """Dependency factory enforcing the current user holds at least one of the given
    roles (see the Role -> Screen Access matrix in docs/requirements/user.md)."""

    def check(user: User = Depends(get_current_user)) -> User:
        user_roles = {role.name for role in user.roles}
        if user_roles.isdisjoint(allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
            )
        return user

    return check
