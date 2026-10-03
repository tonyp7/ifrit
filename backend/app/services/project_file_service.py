"""Files attached to a project: listing, uploading, deleting and tagging them.

The bytes and the upload rules live in `file_storage_service`; this module owns what is
specific to a project: the closed-project lock, scoping every file to its project, and the
tags on an attachment.
"""

import uuid

from fastapi import UploadFile
from sqlalchemy import Select, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.file import File, FileTag, ProjectFile, ProjectFileTag
from app.models.project import Project
from app.models.user import User
from app.schemas.file import FileTagOut, ProjectFileOut
from app.services import file_storage_service
from app.services.project_service import ProjectReadOnlyError


class UnknownTagError(Exception):
    """Raised when a tag id is not in the vocabulary."""


async def get_active_project(db: AsyncSession, project_id: uuid.UUID) -> Project | None:
    """The project itself, without the relations the project form needs: file calls are
    frequent (every tag click) and only need its status."""
    return (
        await db.execute(
            select(Project).where(Project.id == project_id, Project.is_active.is_(True))
        )
    ).scalar_one_or_none()


def _ensure_editable(project: Project) -> None:
    if project.status == "closed":
        raise ProjectReadOnlyError("A closed project's documents cannot be changed")


def to_project_file_out(link: ProjectFile) -> ProjectFileOut:
    file = link.file
    return ProjectFileOut(
        file_id=file.id,
        original_filename=file.original_filename,
        content_type=file.stored_file.detected_content_type,
        size_bytes=file.stored_file.size_bytes,
        uploaded_at=file.created_at,
        tags=[FileTagOut(id=tag.id, name=tag.name) for tag in link.tags],
    )


def _link_query(project_id: uuid.UUID) -> Select[tuple[ProjectFile]]:
    return (
        select(ProjectFile)
        .options(
            selectinload(ProjectFile.file).selectinload(File.stored_file),
            selectinload(ProjectFile.tags),
        )
        .join(File, File.id == ProjectFile.file_id)
        .where(ProjectFile.project_id == project_id)
        # populate_existing: tag changes are made with bulk statements, which would
        # otherwise leave an already-loaded instance showing its old tags.
        .execution_options(populate_existing=True)
    )


async def list_files(db: AsyncSession, project_id: uuid.UUID) -> list[ProjectFile]:
    result = await db.execute(
        _link_query(project_id).order_by(File.created_at, File.id)
    )
    return list(result.scalars().all())


async def is_file_of_active_project(db: AsyncSession, file_id: uuid.UUID) -> bool:
    return (
        await db.execute(
            select(ProjectFile.file_id)
            .join(Project, Project.id == ProjectFile.project_id)
            .where(ProjectFile.file_id == file_id, Project.is_active.is_(True))
        )
    ).scalar_one_or_none() is not None


async def get_file(
    db: AsyncSession, project_id: uuid.UUID, file_id: uuid.UUID
) -> ProjectFile | None:
    """A file of this project, or None, including for a file of another project."""
    result = await db.execute(_link_query(project_id).where(ProjectFile.file_id == file_id))
    return result.scalar_one_or_none()


async def upload_file(
    db: AsyncSession, project: Project, upload: UploadFile, uploaded_by: User
) -> ProjectFile:
    _ensure_editable(project)
    file = await file_storage_service.attach_project_file(
        db, upload=upload, project_id=project.id, uploaded_by=uploaded_by
    )
    link = await get_file(db, project.id, file.id)
    assert link is not None
    return link


async def delete_file(db: AsyncSession, project: Project, link: ProjectFile) -> None:
    """Removes the attachment for good. Deleting the `files` row cascades to the link and
    its tags; the stored content stays, since other attachments may share it."""
    _ensure_editable(project)
    await db.execute(delete(File).where(File.id == link.file_id))
    await db.commit()


async def list_tags(db: AsyncSession) -> list[FileTag]:
    return list((await db.execute(select(FileTag).order_by(FileTag.name))).scalars())


async def add_tag(
    db: AsyncSession, project: Project, link: ProjectFile, tag_id: uuid.UUID
) -> None:
    """Idempotent: adding a tag the file already has changes nothing."""
    _ensure_editable(project)
    if await db.get(FileTag, tag_id) is None:
        raise UnknownTagError(str(tag_id))
    await db.execute(
        pg_insert(ProjectFileTag)
        .values(file_id=link.file_id, tag_id=tag_id)
        .on_conflict_do_nothing()
    )
    await db.commit()


async def remove_tag(
    db: AsyncSession, project: Project, link: ProjectFile, tag_id: uuid.UUID
) -> None:
    """Idempotent: removing a tag the file does not have is not an error."""
    _ensure_editable(project)
    if await db.get(FileTag, tag_id) is None:
        raise UnknownTagError(str(tag_id))
    await db.execute(
        delete(ProjectFileTag).where(
            ProjectFileTag.file_id == link.file_id, ProjectFileTag.tag_id == tag_id
        )
    )
    await db.commit()
