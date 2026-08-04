import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.models.company import Company
from app.models.currency import Currency
from app.models.project import Project, ServiceLine
from app.models.user import User
from app.schemas.project import (
    ProjectDetail,
    ProjectWrite,
    ServiceLineConsultantOut,
    ServiceLineOut,
    ServiceLineWrite,
)

PAGE_SIZE = 50


class ProjectReadOnlyError(Exception):
    """Raised when an action is attempted on a `closed` project (see
    docs/requirements/project.md#status-enum) — the project itself, or its service
    lines, are fully read-only in that state."""


class InvalidReferenceError(Exception):
    """Raised when a write references a vendor/client/currency/consultant that
    doesn't satisfy the app-level rule for that reference (see
    docs/requirements/project.md#1-entity-project)."""


# Quantized to unit_price's column scale (NUMERIC(14, 4) — see app/models/project.py) so
# `value`/`total_value` have a fixed, predictable decimal precision regardless of how many
# decimal places `quantity`/`unit_price` happened to be given with (plain Decimal
# multiplication otherwise sums the two operands' scales, e.g. 10 x 100.00 -> 2 decimals but
# 10.5 x 100.00 -> 3, an inconsistent shape for API consumers to render).
_VALUE_QUANTUM = Decimal("0.0001")


def _service_line_value(line: ServiceLine) -> Decimal:
    return (line.quantity * line.unit_price).quantize(
        _VALUE_QUANTUM, rounding=ROUND_HALF_UP
    )


def project_total_value(project: Project) -> Decimal:
    total = sum(
        (_service_line_value(line) for line in project.service_lines if line.is_active),
        Decimal(0),
    )
    return total.quantize(_VALUE_QUANTUM, rounding=ROUND_HALF_UP)


async def list_projects(
    db: AsyncSession, search: str | None, page: int
) -> tuple[list[tuple[Project, str, str]], int]:
    """Returns (project, vendor_company_name, client_company_name) tuples — the list
    screen shows company names, not raw ids (see
    docs/requirements/project.md#projects-list-screen)."""
    vendor = aliased(Company)
    client = aliased(Company)

    base = select(Project).where(Project.is_active.is_(True))
    if search:
        base = base.where(Project.name.ilike(f"%{search}%"))

    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    stmt = (
        select(Project, vendor.legal_name, client.legal_name)
        .join(vendor, Project.vendor_company_id == vendor.id)
        .join(client, Project.client_company_id == client.id)
        .where(Project.is_active.is_(True))
    )
    if search:
        stmt = stmt.where(Project.name.ilike(f"%{search}%"))
    stmt = (
        stmt.order_by(Project.created_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    )
    rows = (await db.execute(stmt)).all()
    return [(row[0], row[1], row[2]) for row in rows], total


async def get_project(db: AsyncSession, project_id: uuid.UUID) -> Project | None:
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.service_lines).selectinload(ServiceLine.users))
        .where(Project.id == project_id, Project.is_active.is_(True))
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def _check_vendor(db: AsyncSession, company_id: uuid.UUID) -> None:
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if company is None or not company.is_vendor:
        raise InvalidReferenceError("vendor_company_id must reference a vendor company")


async def _check_client(db: AsyncSession, company_id: uuid.UUID) -> None:
    result = await db.execute(select(Company).where(Company.id == company_id))
    if result.scalar_one_or_none() is None:
        raise InvalidReferenceError(
            "client_company_id does not reference an existing company"
        )


async def _check_currency(db: AsyncSession, alpha_code: str) -> None:
    result = await db.execute(select(Currency).where(Currency.alpha_code == alpha_code))
    currency = result.scalar_one_or_none()
    if currency is None or not currency.is_enabled:
        raise InvalidReferenceError(
            "invoicing_currency must reference an enabled currency"
        )


async def validate_references(db: AsyncSession, data: ProjectWrite) -> None:
    await _check_vendor(db, data.vendor_company_id)
    await _check_client(db, data.client_company_id)
    await _check_currency(db, data.invoicing_currency)


async def create_project(db: AsyncSession, data: ProjectWrite) -> Project:
    project = Project(**data.model_dump())
    db.add(project)
    await db.commit()
    persisted = await get_project(db, project.id)
    assert persisted is not None
    return persisted


async def update_project(
    db: AsyncSession, project: Project, data: ProjectWrite
) -> Project:
    # `status` is the one field exempted from a `closed` project's read-only state
    # (see docs/requirements/project.md#status-enum) — everything else must be
    # unchanged while closed.
    if project.status == "closed":
        other_fields = data.model_dump(exclude={"status"})
        current = {field: getattr(project, field) for field in other_fields}
        if other_fields != current:
            raise ProjectReadOnlyError("Only status can change on a closed project")

    for field, value in data.model_dump().items():
        setattr(project, field, value)
    await db.commit()
    return project


async def deactivate_project(db: AsyncSession, project: Project) -> None:
    project.is_active = False
    await db.commit()


async def duplicate_project(db: AsyncSession, source: Project) -> Project:
    new_project = Project(
        name=source.name,
        vendor_company_id=source.vendor_company_id,
        client_company_id=source.client_company_id,
        invoicing_currency=source.invoicing_currency,
        project_type=source.project_type,
        status="draft",
        is_active=True,
    )
    for line in source.service_lines:
        if not line.is_active:
            continue
        new_project.service_lines.append(
            ServiceLine(
                name=line.name,
                quantity=line.quantity,
                uom=line.uom,
                unit_price=line.unit_price,
                users=list(line.users),
            )
        )
    db.add(new_project)
    await db.commit()
    persisted = await get_project(db, new_project.id)
    assert persisted is not None
    return persisted


async def _resolve_consultants(
    db: AsyncSession, user_ids: list[uuid.UUID]
) -> list[User]:
    if not user_ids:
        return []
    result = await db.execute(
        select(User).options(selectinload(User.roles)).where(User.id.in_(user_ids))
    )
    users = list(result.scalars().all())
    found_ids = {u.id for u in users}
    missing = set(user_ids) - found_ids
    if missing:
        raise InvalidReferenceError(
            f"Unknown user id(s): {', '.join(str(m) for m in missing)}"
        )
    for user in users:
        role_names = {role.name for role in user.roles}
        if not user.is_active or "consultant" not in role_names:
            raise InvalidReferenceError(f"User {user.id} is not an active consultant")
    return users


async def add_service_line(
    db: AsyncSession, project: Project, data: ServiceLineWrite
) -> ServiceLine:
    if project.status == "closed":
        raise ProjectReadOnlyError("Cannot add a service line to a closed project")
    users = await _resolve_consultants(db, data.user_ids)
    line = ServiceLine(
        project_id=project.id,
        name=data.name,
        quantity=data.quantity,
        uom=data.uom,
        unit_price=data.unit_price,
        users=users,
    )
    db.add(line)
    await db.commit()
    await db.refresh(line, attribute_names=["users"])
    return line


async def get_service_line(
    db: AsyncSession, project_id: uuid.UUID, service_line_id: uuid.UUID
) -> ServiceLine | None:
    result = await db.execute(
        select(ServiceLine)
        .options(selectinload(ServiceLine.users))
        .where(
            ServiceLine.id == service_line_id,
            ServiceLine.project_id == project_id,
            ServiceLine.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def update_service_line(
    db: AsyncSession, project: Project, line: ServiceLine, data: ServiceLineWrite
) -> ServiceLine:
    if project.status == "closed":
        raise ProjectReadOnlyError("Cannot edit a service line on a closed project")
    users = await _resolve_consultants(db, data.user_ids)
    line.name = data.name
    line.quantity = data.quantity
    line.uom = data.uom
    line.unit_price = data.unit_price
    line.users = users
    await db.commit()
    await db.refresh(line, attribute_names=["users"])
    return line


async def delete_service_line(
    db: AsyncSession, project: Project, line: ServiceLine
) -> None:
    # Deletion should additionally be blocked on an `active` project once any time has
    # been logged against the line — not yet enforceable, no time-entry concept exists
    # yet (see docs/requirements/timesheet.md and
    # docs/requirements/project.md#validation-rules-1). Only the `closed`-project block
    # is implemented for now.
    if project.status == "closed":
        raise ProjectReadOnlyError("Cannot delete a service line on a closed project")
    line.is_active = False
    await db.commit()


def to_consultant_out(user: User) -> ServiceLineConsultantOut:
    return ServiceLineConsultantOut(id=user.id, full_name=user.full_name)


def to_service_line_out(line: ServiceLine) -> ServiceLineOut:
    return ServiceLineOut(
        id=line.id,
        project_id=line.project_id,
        name=line.name,
        quantity=line.quantity,
        uom=line.uom,
        unit_price=line.unit_price,
        value=_service_line_value(line),
        is_active=line.is_active,
        users=[to_consultant_out(u) for u in line.users],
    )


def to_project_detail(project: Project) -> ProjectDetail:
    active_lines = [line for line in project.service_lines if line.is_active]
    return ProjectDetail(
        id=project.id,
        name=project.name,
        vendor_company_id=project.vendor_company_id,
        client_company_id=project.client_company_id,
        invoicing_currency=project.invoicing_currency,
        project_type=project.project_type,
        status=project.status,
        is_active=project.is_active,
        created_at=project.created_at,
        updated_at=project.updated_at,
        service_lines=[to_service_line_out(line) for line in active_lines],
        total_value=project_total_value(project),
    )
