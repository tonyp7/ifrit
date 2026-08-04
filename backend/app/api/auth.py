import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import UNAUTHORIZED, get_current_user
from app.auth.security import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.config import settings
from app.core.db import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest
from app.schemas.user import UserOut
from app.services.user_service import (
    authenticate_local_user,
    get_user_by_id,
    to_user_out,
)

router = APIRouter(prefix="/auth", tags=["auth"])

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"


def _set_auth_cookies(response: Response, user: User) -> None:
    roles = [role.name for role in user.roles]
    access_token = create_access_token(user.id, roles)
    refresh_token = create_refresh_token(user.id)

    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.refresh_token_expire_minutes * 60,
        path="/",
    )


@router.post("/login", response_model=UserOut)
async def login(
    credentials: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> UserOut:
    user = await authenticate_local_user(db, credentials.email, credentials.password)
    if user is None:
        # Generic error: don't reveal whether the email exists.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    _set_auth_cookies(response, user)
    return to_user_out(user)


@router.post("/refresh", response_model=UserOut)
async def refresh(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> UserOut:
    token = request.cookies.get(REFRESH_COOKIE)
    if token is None:
        raise UNAUTHORIZED

    try:
        payload = decode_token(token, expected_type="refresh")
    except InvalidTokenError as err:
        raise UNAUTHORIZED from err

    user = await get_user_by_id(db, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise UNAUTHORIZED

    _set_auth_cookies(response, user)
    return to_user_out(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return to_user_out(user)
