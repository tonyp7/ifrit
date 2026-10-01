import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.services import file_storage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["files"])

_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
)


@router.get("/{file_id}/content")
async def download_file(
    file_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    file = await file_storage_service.get_file(db, file_id)
    if file is None:
        raise _NOT_FOUND
    # Checked on every request against the object the file is attached to, not inferred
    # from the path or from who uploaded it.
    if not await file_storage_service.user_can_access_file(db, user, file):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )

    try:
        path = file_storage_service.resolve_storage_path(file.stored_file.bucket_key)
    except file_storage_service.StoragePathError:
        logger.error("Stored file %s resolves outside the storage root", file_id)
        raise _NOT_FOUND from None
    if not await asyncio.to_thread(path.is_file):
        logger.error("Stored content for file %s is missing from disk", file_id)
        raise _NOT_FOUND

    return FileResponse(
        path,
        media_type=file.stored_file.detected_content_type,
        headers={
            # The bytes are re-encoded images, so inline display is safe, but the browser
            # must still never second-guess the type we declare.
            "X-Content-Type-Options": "nosniff",
            # A replaced logo gets a new file id, and so a new URL, but cached bytes
            # should still be revalidated rather than trusted blindly.
            "Cache-Control": "private, no-cache",
        },
    )
