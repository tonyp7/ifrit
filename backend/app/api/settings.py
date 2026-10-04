from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.core.db import get_db
from app.models.file import File
from app.models.user import User
from app.schemas.file import FileOut
from app.services import app_settings, file_storage_service

# Instance-wide settings are managed by administrators only.
_admin_only = Depends(require_roles("administrator"))

router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    dependencies=[_admin_only],
)


def _to_out(file: File) -> FileOut:
    return FileOut(
        file_id=file.id,
        original_filename=file.original_filename,
        content_type=file.stored_file.detected_content_type,
        size_bytes=file.stored_file.size_bytes,
        uploaded_at=file.created_at,
    )


@router.get("/org-logo", response_model=FileOut)
async def get_org_logo(db: AsyncSession = Depends(get_db)) -> FileOut:
    file = await file_storage_service.get_setting_file(db, "org_logo")
    if file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No logo uploaded"
        )
    return _to_out(file)


@router.put("/org-logo", response_model=FileOut)
async def put_org_logo(
    file: UploadFile,
    user: User = _admin_only,
    db: AsyncSession = Depends(get_db),
) -> FileOut:
    try:
        stored = await file_storage_service.attach_setting_file(
            db, upload=file, setting_key="org_logo", uploaded_by=user
        )
    except file_storage_service.FileUploadError as err:
        raise HTTPException(status_code=err.status_code, detail=str(err)) from err
    return _to_out(stored)


@router.delete("/org-logo", status_code=status.HTTP_204_NO_CONTENT)
async def delete_org_logo(db: AsyncSession = Depends(get_db)) -> None:
    removed = await file_storage_service.delete_setting_file(db, "org_logo")
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No logo uploaded"
        )


# Scalar settings. These routes come after the fixed `/org-logo` ones, which must keep
# winning over the `{group}` path parameter.


def _unknown_group() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Unknown settings group"
    )


def _invalid(err: ValidationError) -> HTTPException:
    # The same {loc, msg, type} shape FastAPI uses for its own 422s, which is what the
    # frontend turns into a message. Pydantic's `input` is left out: it echoes the value.
    detail = [
        {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
        for e in err.errors()
    ]
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail
    )


@router.get("")
async def get_all_settings(
    db: AsyncSession = Depends(get_db),
) -> dict[str, dict[str, Any]]:
    groups = await app_settings.get_all_groups(db)
    return {name: group.model_dump() for name, group in groups.items()}


@router.get("/{group}")
async def get_settings_group(
    group: str, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    try:
        current = await app_settings.get_group(db, group)
    except app_settings.UnknownSettingGroupError as err:
        raise _unknown_group() from err
    return current.model_dump()


@router.patch("/{group}")
async def patch_settings_group(
    group: str,
    patch: dict[str, Any],
    user: User = _admin_only,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    try:
        updated: BaseModel = await app_settings.update_group(db, group, patch, user.id)
    except app_settings.UnknownSettingGroupError as err:
        raise _unknown_group() from err
    except ValidationError as err:
        raise _invalid(err) from err
    return updated.model_dump()


@router.delete("/{group}/{key}")
async def reset_setting(
    group: str, key: str, db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    try:
        current = await app_settings.reset_key(db, group, key)
    except app_settings.UnknownSettingGroupError as err:
        raise _unknown_group() from err
    except app_settings.UnknownSettingKeyError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Unknown setting",
        ) from err
    return current.model_dump()
