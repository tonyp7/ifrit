import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.core.db import get_db
from app.models.project import Project, ServiceLine
from app.schemas.project import (
    ProjectDetail,
    ProjectListItem,
    ProjectListResponse,
    ProjectWrite,
    ServiceLineOut,
    ServiceLineWrite,
)
from app.services import project_service
from app.services.project_service import InvalidReferenceError, ProjectReadOnlyError

router = APIRouter(
    prefix="/projects",
    tags=["projects"],
    dependencies=[Depends(require_roles("project_admin"))],
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
    db: AsyncSession = Depends(get_db),
) -> ProjectListResponse:
    rows, total = await project_service.list_projects(db, search, page)
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
    project = await project_service.create_project(db, payload)
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
    await _validate_references_or_422(db, payload)
    try:
        project = await project_service.update_project(db, project, payload)
    except ProjectReadOnlyError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(err)
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
    except ProjectReadOnlyError as err:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(err)
        ) from err
