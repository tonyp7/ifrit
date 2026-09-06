import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_roles
from app.core.db import get_db
from app.models.user import User
from app.schemas.user import (
    PasswordResetRequest,
    ThemePreferenceUpdate,
    UserCreate,
    UserListResponse,
    UserOut,
    UserUpdate,
)
from app.services import user_service
from app.services.user_service import (
    SelfLockoutError,
    create_user,
    deactivate_user,
    get_user_by_id,
    list_users,
    reset_password,
    to_user_out,
    update_theme_preference,
    update_user,
)

router = APIRouter(prefix="/users", tags=["users"])


async def _get_user_or_404(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


@router.get("", response_model=UserListResponse)
async def list_users_endpoint(
    role: str | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    is_active: bool | None = None,
    sort_by: str | None = None,
    sort_dir: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("project_admin", "administrator")),  # noqa: B008
) -> UserListResponse:
    """Users, optionally filtered by role and/or a `full_name`/`name_id` substring
    (`search`) — used by both the Service Line consultant picker (see
    docs/requirements/project.md#service-lines, `is_active=true`, page 1 is always
    enough since `search` already narrows it) and the Users List Screen (see
    docs/requirements/user.md#users-list-screen, no `is_active` filter so both active
    and inactive users show)."""
    users, total = await list_users(
        db, role, search, page, is_active, sort_by=sort_by, sort_dir=sort_dir
    )
    return UserListResponse(
        items=[to_user_out(u) for u in users],
        total=total,
        page=page,
        page_size=user_service.PAGE_SIZE,
    )


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("administrator"))],
)
async def create_user_endpoint(
    payload: UserCreate, db: AsyncSession = Depends(get_db)
) -> UserOut:
    try:
        user = await create_user(db, payload)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(err)
        ) from err
    except IntegrityError as err:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this login identity already exists",
        ) from err
    return to_user_out(user)


@router.get(
    "/{user_id}",
    response_model=UserOut,
    dependencies=[Depends(require_roles("administrator"))],
)
async def get_user_endpoint(
    user_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> UserOut:
    user = await _get_user_or_404(db, user_id)
    return to_user_out(user)


@router.patch(
    "/{user_id}",
    response_model=UserOut,
    dependencies=[Depends(require_roles("administrator"))],
)
async def update_user_endpoint(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserOut:
    user = await _get_user_or_404(db, user_id)
    try:
        user = await update_user(db, user, payload, current_user)
    except SelfLockoutError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)
        ) from err
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(err)
        ) from err
    except IntegrityError as err:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this login identity already exists",
        ) from err
    return to_user_out(user)


@router.post(
    "/{user_id}/deactivate",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles("administrator"))],
)
async def deactivate_user_endpoint(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    user = await _get_user_or_404(db, user_id)
    try:
        await deactivate_user(db, user, current_user)
    except SelfLockoutError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)
        ) from err


@router.patch("/me/theme-preference", response_model=UserOut)
async def update_my_theme_preference(
    payload: ThemePreferenceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserOut:
    await update_theme_preference(db, current_user, payload.theme_preference)
    return to_user_out(current_user)


@router.post(
    "/{user_id}/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles("administrator"))],
)
async def admin_reset_password(
    user_id: uuid.UUID,
    payload: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    target = await get_user_by_id(db, user_id)
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if target.is_sso:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SSO users have no local password to reset",
        )

    await reset_password(db, target, payload.new_password)
