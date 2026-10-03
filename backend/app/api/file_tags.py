from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.core.db import get_db
from app.schemas.file import FileTagOut
from app.services import project_file_service

router = APIRouter(
    prefix="/file-tags",
    tags=["file-tags"],
    dependencies=[Depends(require_roles("project_admin"))],
)


@router.get("", response_model=list[FileTagOut])
async def list_file_tags(db: AsyncSession = Depends(get_db)) -> list[FileTagOut]:
    """The fixed vocabulary a project file can be tagged with, ordered by name."""
    return [
        FileTagOut(id=tag.id, name=tag.name)
        for tag in await project_file_service.list_tags(db)
    ]
