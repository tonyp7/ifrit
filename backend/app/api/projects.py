import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.core.db import get_db
from app.models.file import ProjectFile
from app.models.project import Project, ServiceLine
from app.models.user import User
from app.schemas.file import ProjectFileOut
from app.schemas.project import (
    ProjectDetail,
    ProjectListItem,
    ProjectListResponse,
    ProjectWrite,
    ServiceLineOut,
    ServiceLineWrite,
)
from app.services import file_storage_service, project_file_service, project_service
from app.services.project_service import (
    InvalidReferenceError,
    ProjectReadOnlyError,
    ServiceLineHasLoggedTimeError,
)

_project_admin = Depends(require_roles("project_admin"))

router = APIRouter(
    prefix="/projects",
    tags=["projects"],
    dependencies=[_project_admin],
)


async def _get_project_or_404(db: AsyncSession, project_id: uuid.UUID) -> Project:
    project = await project_service.get_project(db, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return project


async def _get_service_line_or_404(
    db: AsyncSession, project_id: uuid.UUID, line_id: uuid.UUID
) -> ServiceLine:
    line = await project_service.get_service_line(db, project_id, line_id)
    if line is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Service line not found"
        )
    return line


async def _validate_references_or_422(db: AsyncSession, payload: ProjectWrite) -> None:
    try:
        await project_service.validate_references(db, payload)
    except InvalidReferenceError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(err)
        ) from err


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    sort_by: str | None = None,
    sort_dir: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> ProjectListResponse:
    rows, total = await project_service.list_projects(
        db, search, page, sort_by=sort_by, sort_dir=sort_dir
    )
    return ProjectListResponse(
        items=[
            ProjectListItem(
                id=project.id,
                name=project.name,
                status=project.status,
                project_type=project.project_type,
                client_company_id=project.client_company_id,
                client_company_name=client_name,
                vendor_company_id=project.vendor_company_id,
                vendor_company_name=vendor_name,
                created_at=project.created_at,
            )
            for project, vendor_name, client_name in rows
        ],
        total=total,
        page=page,
        page_size=project_service.PAGE_SIZE,
    )


@router.post("", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectWrite, db: AsyncSession = Depends(get_db)
) -> ProjectDetail:
    await _validate_references_or_422(db, payload)
    try:
        project = await project_service.create_project(db, payload)
    except InvalidReferenceError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(err)
        ) from err
    return project_service.to_project_detail(project)


@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> ProjectDetail:
    project = await _get_project_or_404(db, project_id)
    return project_service.to_project_detail(project)


@router.patch("/{project_id}", response_model=ProjectDetail)
async def update_project(
    project_id: uuid.UUID, payload: ProjectWrite, db: AsyncSession = Depends(get_db)
) -> ProjectDetail:
    project = await _get_project_or_404(db, project_id)
    # A closed project only accepts a status change (update_project rejects anything
    # else), so its references can't change here: skipping validation lets it be
    # reopened even if its company was soft-deleted since.
    if project.status != "closed":
        await _validate_references_or_422(db, payload)
    try:
        project = await project_service.update_project(db, project, payload)
    except ProjectReadOnlyError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(err)
        ) from err
    except InvalidReferenceError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(err)
        ) from err
    return project_service.to_project_detail(project)


@router.post("/{project_id}/duplicate", response_model=ProjectDetail)
async def duplicate_project(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> ProjectDetail:
    project = await _get_project_or_404(db, project_id)
    new_project = await project_service.duplicate_project(db, project)
    return project_service.to_project_detail(new_project)


@router.post("/{project_id}/deactivate", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_project(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    project = await _get_project_or_404(db, project_id)
    await project_service.deactivate_project(db, project)


@router.post(
    "/{project_id}/service-lines",
    response_model=ServiceLineOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_service_line(
    project_id: uuid.UUID, payload: ServiceLineWrite, db: AsyncSession = Depends(get_db)
) -> ServiceLineOut:
    project = await _get_project_or_404(db, project_id)
    try:
        line = await project_service.add_service_line(db, project, payload)
    except ProjectReadOnlyError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(err)
        ) from err
    except InvalidReferenceError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(err)
        ) from err
    return project_service.to_service_line_out(line)


@router.patch("/{project_id}/service-lines/{line_id}", response_model=ServiceLineOut)
async def update_service_line(
    project_id: uuid.UUID,
    line_id: uuid.UUID,
    payload: ServiceLineWrite,
    db: AsyncSession = Depends(get_db),
) -> ServiceLineOut:
    project = await _get_project_or_404(db, project_id)
    line = await _get_service_line_or_404(db, project_id, line_id)
    try:
        line = await project_service.update_service_line(db, project, line, payload)
    except ProjectReadOnlyError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(err)
        ) from err
    except InvalidReferenceError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(err)
        ) from err
    return project_service.to_service_line_out(line)


@router.delete(
    "/{project_id}/service-lines/{line_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_service_line(
    project_id: uuid.UUID, line_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    project = await _get_project_or_404(db, project_id)
    line = await _get_service_line_or_404(db, project_id, line_id)
    try:
        await project_service.delete_service_line(db, project, line)
    except (ProjectReadOnlyError, ServiceLineHasLoggedTimeError) as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(err)
        ) from err


async def _get_editable_project_or_404(
    db: AsyncSession, project_id: uuid.UUID
) -> Project:
    project = await project_file_service.get_active_project(db, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return project


async def _get_project_file_or_404(
    db: AsyncSession, project_id: uuid.UUID, file_id: uuid.UUID
) -> ProjectFile:
    # Looked up through the project, so another project's file id is a plain 404.
    link = await project_file_service.get_file(db, project_id, file_id)
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )
    return link


@router.get("/{project_id}/files", response_model=list[ProjectFileOut])
async def list_project_files(
    project_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[ProjectFileOut]:
    await _get_editable_project_or_404(db, project_id)
    links = await project_file_service.list_files(db, project_id)
    return [project_file_service.to_project_file_out(link) for link in links]


@router.post(
    "/{project_id}/files",
    response_model=ProjectFileOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_project_file(
    project_id: uuid.UUID,
    file: UploadFile,
    user: User = _project_admin,
    db: AsyncSession = Depends(get_db),
) -> ProjectFileOut:
    project = await _get_editable_project_or_404(db, project_id)
    try:
        link = await project_file_service.upload_file(db, project, file, user)
    except ProjectReadOnlyError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(err)
        ) from err
    except file_storage_service.FileUploadError as err:
        raise HTTPException(status_code=err.status_code, detail=str(err)) from err
    return project_file_service.to_project_file_out(link)


@router.delete(
    "/{project_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_project_file(
    project_id: uuid.UUID, file_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    project = await _get_editable_project_or_404(db, project_id)
    link = await _get_project_file_or_404(db, project_id, file_id)
    try:
        await project_file_service.delete_file(db, project, link)
    except ProjectReadOnlyError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(err)
        ) from err


@router.put(
    "/{project_id}/files/{file_id}/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def add_project_file_tag(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    tag_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    project = await _get_editable_project_or_404(db, project_id)
    link = await _get_project_file_or_404(db, project_id, file_id)
    try:
        await project_file_service.add_tag(db, project, link, tag_id)
    except ProjectReadOnlyError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(err)
        ) from err
    except project_file_service.UnknownTagError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found"
        ) from err


@router.delete(
    "/{project_id}/files/{file_id}/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_project_file_tag(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    tag_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    project = await _get_editable_project_or_404(db, project_id)
    link = await _get_project_file_or_404(db, project_id, file_id)
    try:
        await project_file_service.remove_tag(db, project, link, tag_id)
    except ProjectReadOnlyError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(err)
        ) from err
    except project_file_service.UnknownTagError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found"
        ) from err
