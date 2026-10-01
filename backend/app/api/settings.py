from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.core.db import get_db
from app.models.file import File
from app.models.user import User
from app.schemas.file import FileOut
from app.services import file_storage_service

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
