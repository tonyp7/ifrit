import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.models.company import Company
from app.models.currency import Currency
from app.models.project import BillingMilestone, Project, ProjectReference, ServiceLine
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.schemas.project import (
    MAX_PROJECT_REFERENCES,
    BillingMilestoneOut,
    BillingMilestoneWrite,
    ProjectDetail,
    ProjectManagerOut,
    ProjectReferenceOut,
    ProjectReferenceWrite,
    ProjectWrite,
    ServiceLineConsultantOut,
    ServiceLineOut,
    ServiceLineWrite,
)
from app.services.sorting import resolve_sort

PAGE_SIZE = 50


class ProjectReadOnlyError(Exception):
    """Raised when an action is attempted on a `closed` project: the project itself,
    or its service lines, are fully read-only in that state."""


class InvalidReferenceError(Exception):
    """Raised when a write references a vendor/client/currency/consultant that
    doesn't satisfy the app-level rule for that reference."""


class MilestonesNotAllowedError(Exception):
    """Raised when a billing milestone write targets a project that is not Fixed Price:
    only Fixed Price contracts are billed in installments."""


class InvalidMilestoneValueError(Exception):
    """Raised when a billing milestone's value has more decimal places than the
    project's currency allows."""


class MilestoneOrderMismatchError(Exception):
    """Raised when a reorder does not list exactly the project's current milestones,
    typically because another session added or deleted one in the meantime."""


class DuplicateReferenceError(Exception):
    """Raised when a project reference equals another one on the same project (same kind,
    label and value, ignoring case)."""


class TooManyReferencesError(Exception):
    """Raised when adding a project reference to a project that already has the most a
    project may carry."""


class ReferenceOrderMismatchError(Exception):
    """Raised when a reorder does not list exactly the project's current references,
    typically because another session added or deleted one in the meantime."""


class ServiceLineHasLoggedTimeError(Exception):
    """Raised when deleting a service line on an `active` project is attempted
    while time has already been logged against it: editing remains allowed,
    only deletion is blocked."""


# Quantized to unit_price's column scale (NUMERIC(14, 4): see app/models/project.py) so
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
    db: AsyncSession,
    search: str | None,
    page: int,
    sort_by: str | None = None,
    sort_dir: str | None = None,
    mine_only_for: uuid.UUID | None = None,
) -> tuple[list[tuple[Project, str | None, str | None]], int]:
    """Returns (project, vendor_company_name, client_company_name) tuples: the list
    screen shows company names, not raw ids. Names are None for a project with no
    company link (see Project.vendor_company_id). `mine_only_for` narrows the list to
    projects listing that user as a project manager, applied to the count too so
    the page count matches."""
    vendor = aliased(Company)
    client = aliased(Company)

    # Built here (not at module scope) since client_company_name/vendor_company_name
    # sort by the aliased join columns above, not a plain Project attribute: those
    # aliases only exist inside this function.
    sortable_columns = {
        "name": Project.name,
        "status": Project.status,
        "client_company_name": client.legal_name,
        "vendor_company_name": vendor.legal_name,
        "project_type": Project.project_type,
        "created_at": Project.created_at,
    }

    filters: list[ColumnElement[bool]] = [Project.is_active.is_(True)]
    if search:
        filters.append(Project.name.ilike(f"%{search}%"))
    if mine_only_for is not None:
        filters.append(Project.project_managers.any(User.id == mine_only_for))
    base = select(Project).where(*filters)

    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    stmt = (
        select(Project, vendor.legal_name, client.legal_name)
        .outerjoin(vendor, Project.vendor_company_id == vendor.id)
        .outerjoin(client, Project.client_company_id == client.id)
        .where(*filters)
    )
    order = resolve_sort(
        sortable_columns, sort_by, sort_dir, default=Project.created_at.desc()
    )
    stmt = (
        # `Project.id` is a stable tie-breaker: see app/services/sorting.py.
        stmt.order_by(order, Project.id).offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    )
    rows = (await db.execute(stmt)).all()
    return [(row[0], row[1], row[2]) for row in rows], total


async def get_project(db: AsyncSession, project_id: uuid.UUID) -> Project | None:
    result = await db.execute(
        select(Project)
        .options(
            selectinload(Project.service_lines).selectinload(ServiceLine.users),
            selectinload(Project.project_managers),
            selectinload(Project.billing_milestones),
            selectinload(Project.project_references),
            selectinload(Project.vendor_company),
            selectinload(Project.client_company),
        )
        .where(Project.id == project_id, Project.is_active.is_(True))
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def _check_vendor(db: AsyncSession, company_id: uuid.UUID) -> None:
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if company is None or not company.is_vendor or not company.is_active:
        raise InvalidReferenceError(
            "vendor_company_id must reference an active vendor company"
        )


async def _check_client(db: AsyncSession, company_id: uuid.UUID) -> None:
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if company is None or not company.is_active:
        raise InvalidReferenceError(
            "client_company_id does not reference an active company"
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
    fields = data.model_dump(exclude={"project_manager_ids"})
    managers = await _resolve_project_managers(db, data.project_manager_ids)
    project = Project(**fields, project_managers=managers)
    db.add(project)
    await db.commit()
    persisted = await get_project(db, project.id)
    assert persisted is not None
    return persisted


async def update_project(
    db: AsyncSession, project: Project, data: ProjectWrite
) -> Project:
    # `status` is the one field exempted from a `closed` project's read-only state:
    # everything else, including `project_managers` (which is NOT exempted the way
    # `status` is), must be unchanged while closed.
    if project.status == "closed":
        other_fields = data.model_dump(exclude={"status", "project_manager_ids"})
        current = {field: getattr(project, field) for field in other_fields}
        manager_ids_changed = {u.id for u in project.project_managers} != set(
            data.project_manager_ids
        )
        if other_fields != current or manager_ids_changed:
            raise ProjectReadOnlyError("Only status can change on a closed project")

    # Only Fixed Price contracts are billed in installments, so a project leaving that
    # type loses its milestones, in the same commit as the type change: a save that
    # fails keeps them, and no other project type is ever left carrying milestones it
    # couldn't edit or delete.
    if project.project_type == "fixed_price" and data.project_type != "fixed_price":
        project.billing_milestones.clear()

    for field, value in data.model_dump(exclude={"project_manager_ids"}).items():
        setattr(project, field, value)
    project.project_managers = await _resolve_project_managers(
        db, data.project_manager_ids
    )
    await db.commit()
    return project


async def deactivate_project(db: AsyncSession, project: Project) -> None:
    project.is_active = False
    await db.commit()


async def duplicate_project(db: AsyncSession, source: Project) -> Project:
    new_project = Project(
        name=source.name,
        # A soft-deleted company's link is dropped rather than copied: the duplicate
        # must not start out pointing at a company nobody can select any more, so the
        # user has to pick an active one before saving.
        vendor_company_id=(
            source.vendor_company_id
            if source.vendor_company is not None and source.vendor_company.is_active
            else None
        ),
        client_company_id=(
            source.client_company_id
            if source.client_company is not None and source.client_company.is_active
            else None
        ),
        invoicing_currency=source.invoicing_currency,
        project_type=source.project_type,
        status="draft",
        is_active=True,
        # Copied verbatim, same consistency reason service lines' consultant
        # assignments are: a duplicate should start as a faithful snapshot of the
        # source, not a blank slate.
        project_managers=list(source.project_managers),
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
                # A deleted user stays on the source line (history) but isn't carried
                # over: the copy is a fresh start, and only active users can be saved.
                users=[u for u in line.users if u.is_active],
            )
        )
    # Part of the contract, like the service lines: copied with their order.
    for milestone in source.billing_milestones:
        new_project.billing_milestones.append(
            BillingMilestone(
                description=milestone.description,
                due_date=milestone.due_date,
                value=milestone.value,
                position=milestone.position,
            )
        )
    for reference in source.project_references:
        new_project.project_references.append(
            ProjectReference(
                kind=reference.kind,
                label=reference.label,
                value=reference.value,
                position=reference.position,
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
        if not user.is_active:
            raise InvalidReferenceError(
                f"User {user.id} no longer exists; remove them from the service line"
            )
        if "consultant" not in role_names:
            raise InvalidReferenceError(f"User {user.id} is not an active consultant")
    return users


async def _resolve_project_managers(
    db: AsyncSession, user_ids: list[uuid.UUID]
) -> list[User]:
    """Same shape as _resolve_consultants above, checking `manager` instead of
    `consultant`. Holding the role is the only eligibility check; there is
    deliberately no minimum-one or empty-assignment guard: a project with zero
    project managers is valid, it simply shows up in nobody's "my projects" view."""
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
        if not user.is_active or "manager" not in role_names:
            raise InvalidReferenceError(f"User {user.id} is not an active manager")
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


async def _has_logged_time(db: AsyncSession, service_line_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(TimeEntry.id)
        .where(TimeEntry.service_line_id == service_line_id)
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def delete_service_line(
    db: AsyncSession, project: Project, line: ServiceLine
) -> None:
    if project.status == "closed":
        raise ProjectReadOnlyError("Cannot delete a service line on a closed project")
    # On an `active` project, a line with any time_entries row is edit-only, not
    # deletable, deleting it would silently orphan the time entries already logged
    # against it, with no cascade and no warning. `_has_logged_time` is an
    # existence check, not filtered by value: a locked 0-hour gap-fill row (see
    # set_service_line_lock) still counts, since it exists precisely because a
    # manager took a real, recorded action on it, not because anyone
    # actually logged zero hours.
    #
    # `draft` isn't exempt from this check the way it used to be, a draft project
    # can carry real historical time from an earlier active -> draft transition
    # (status transitions are unrestricted), so "no time can be logged against a
    # non-active project" is true only for entries created *while* draft, not for
    # everything the line has ever accumulated.
    has_history = await _has_logged_time(db, line.id)
    if project.status == "active" and has_history:
        raise ServiceLineHasLoggedTimeError(
            "Cannot delete a service line with logged time on an active project"
        )
    if has_history:
        # Preserve it: a draft project reaching this branch has real history from
        # before it was draft (active can never reach here with has_history=True,
        # it already raised above).
        line.is_active = False
        await db.commit()
    else:
        # Nothing to preserve. A hard delete here (rather than the is_active=False
        # used when there IS history) avoids leaving a permanent, invisible,
        # zero-purpose row behind forever: the DB's own ON DELETE CASCADE on
        # service_line_consultants.service_line_id takes any now-stale consultant
        # assignments with it, rather than leaving them orphaned on a line nothing
        # can ever reach again.
        await db.delete(line)
        await db.commit()


async def _lock_project(db: AsyncSession, project: Project) -> None:
    # Serializes milestone appends and reorders on one project: two concurrent appends
    # would otherwise read the same max(position), and two reorders could interleave.
    await db.execute(
        select(Project.id).where(Project.id == project.id).with_for_update()
    )


def _check_milestones_writable(project: Project) -> None:
    if project.status == "closed":
        raise ProjectReadOnlyError(
            "Cannot change billing milestones on a closed project"
        )
    if project.project_type != "fixed_price":
        raise MilestonesNotAllowedError(
            "Billing milestones exist only on Fixed Price projects"
        )


async def _check_milestone_value(
    db: AsyncSession, project: Project, value: Decimal
) -> None:
    result = await db.execute(
        select(Currency.minor_unit).where(
            Currency.alpha_code == project.invoicing_currency
        )
    )
    minor_unit = result.scalar_one_or_none()
    # A currency without a minor unit (e.g. gold) is still entered and shown with 2
    # decimals, the same fallback the amount display uses.
    allowed = 2 if minor_unit is None else minor_unit
    exponent = value.normalize().as_tuple().exponent
    decimals = -exponent if isinstance(exponent, int) and exponent < 0 else 0
    if decimals > allowed:
        raise InvalidMilestoneValueError(
            f"value must have at most {allowed} decimal places for "
            f"{project.invoicing_currency}"
        )


async def get_billing_milestone(
    db: AsyncSession, project_id: uuid.UUID, milestone_id: uuid.UUID
) -> BillingMilestone | None:
    result = await db.execute(
        select(BillingMilestone).where(
            BillingMilestone.id == milestone_id,
            BillingMilestone.project_id == project_id,
        )
    )
    return result.scalar_one_or_none()


async def add_billing_milestone(
    db: AsyncSession, project: Project, data: BillingMilestoneWrite
) -> BillingMilestone:
    _check_milestones_writable(project)
    await _check_milestone_value(db, project, data.value)
    await _lock_project(db, project)
    result = await db.execute(
        select(func.max(BillingMilestone.position)).where(
            BillingMilestone.project_id == project.id
        )
    )
    last = result.scalar_one_or_none()
    milestone = BillingMilestone(
        project_id=project.id,
        description=data.description.strip(),
        due_date=data.due_date,
        value=data.value,
        position=0 if last is None else last + 1,
    )
    db.add(milestone)
    await db.commit()
    return milestone


async def update_billing_milestone(
    db: AsyncSession,
    project: Project,
    milestone: BillingMilestone,
    data: BillingMilestoneWrite,
) -> BillingMilestone:
    _check_milestones_writable(project)
    await _check_milestone_value(db, project, data.value)
    milestone.description = data.description.strip()
    milestone.due_date = data.due_date
    milestone.value = data.value
    await db.commit()
    return milestone


async def delete_billing_milestone(
    db: AsyncSession, project: Project, milestone: BillingMilestone
) -> None:
    _check_milestones_writable(project)
    await db.delete(milestone)
    await db.commit()


async def reorder_billing_milestones(
    db: AsyncSession, project: Project, ids: list[uuid.UUID]
) -> list[BillingMilestone]:
    _check_milestones_writable(project)
    await _lock_project(db, project)
    result = await db.execute(
        select(BillingMilestone).where(BillingMilestone.project_id == project.id)
    )
    by_id = {m.id: m for m in result.scalars()}
    # The client sends the order it sees; if that no longer matches what is stored, a
    # milestone was added or removed elsewhere and applying a partial order would
    # silently misplace it.
    if len(ids) != len(by_id) or set(ids) != set(by_id):
        raise MilestoneOrderMismatchError(
            "The milestone list has changed; reload and try again"
        )
    for position, milestone_id in enumerate(ids):
        by_id[milestone_id].position = position
    await db.commit()
    return [by_id[milestone_id] for milestone_id in ids]


def to_billing_milestone_out(milestone: BillingMilestone) -> BillingMilestoneOut:
    return BillingMilestoneOut(
        id=milestone.id,
        project_id=milestone.project_id,
        description=milestone.description,
        due_date=milestone.due_date,
        value=milestone.value,
        position=milestone.position,
    )


def _check_references_writable(project: Project) -> None:
    if project.status == "closed":
        raise ProjectReadOnlyError("Cannot change references on a closed project")


def _reference_identity(
    kind: str, label: str | None, value: str
) -> tuple[str, str, str]:
    # Case is ignored: PO-17 and po-17 are one number typed twice. `lower` is also what the
    # unique index uses, so nothing accepted here is refused there.
    return (kind, (label or "").lower(), value.lower())


async def _check_reference_is_new(
    db: AsyncSession,
    project: Project,
    data: ProjectReferenceWrite,
    *,
    ignoring: uuid.UUID | None = None,
) -> None:
    result = await db.execute(
        select(ProjectReference).where(ProjectReference.project_id == project.id)
    )
    wanted = _reference_identity(data.kind, data.label, data.value)
    for other in result.scalars():
        if other.id != ignoring and wanted == _reference_identity(
            other.kind, other.label, other.value
        ):
            raise DuplicateReferenceError("This reference is already listed")


async def get_project_reference(
    db: AsyncSession, project_id: uuid.UUID, reference_id: uuid.UUID
) -> ProjectReference | None:
    result = await db.execute(
        select(ProjectReference).where(
            ProjectReference.id == reference_id,
            ProjectReference.project_id == project_id,
        )
    )
    return result.scalar_one_or_none()


async def add_project_reference(
    db: AsyncSession, project: Project, data: ProjectReferenceWrite
) -> ProjectReference:
    _check_references_writable(project)
    await _lock_project(db, project)
    result = await db.execute(
        select(func.count(), func.max(ProjectReference.position)).where(
            ProjectReference.project_id == project.id
        )
    )
    count, last = result.one()
    if count >= MAX_PROJECT_REFERENCES:
        raise TooManyReferencesError(
            f"A project has at most {MAX_PROJECT_REFERENCES} references"
        )
    await _check_reference_is_new(db, project, data)
    reference = ProjectReference(
        project_id=project.id,
        kind=data.kind,
        label=data.label,
        value=data.value,
        position=0 if last is None else last + 1,
    )
    db.add(reference)
    await db.commit()
    return reference


async def update_project_reference(
    db: AsyncSession,
    project: Project,
    reference: ProjectReference,
    data: ProjectReferenceWrite,
) -> ProjectReference:
    _check_references_writable(project)
    await _check_reference_is_new(db, project, data, ignoring=reference.id)
    reference.kind = data.kind
    reference.label = data.label
    reference.value = data.value
    await db.commit()
    return reference


async def delete_project_reference(
    db: AsyncSession, project: Project, reference: ProjectReference
) -> None:
    _check_references_writable(project)
    await db.delete(reference)
    await db.commit()


async def reorder_project_references(
    db: AsyncSession, project: Project, ids: list[uuid.UUID]
) -> list[ProjectReference]:
    _check_references_writable(project)
    await _lock_project(db, project)
    result = await db.execute(
        select(ProjectReference).where(ProjectReference.project_id == project.id)
    )
    by_id = {r.id: r for r in result.scalars()}
    # The client sends the order it sees; if that no longer matches what is stored, a
    # reference was added or removed elsewhere and applying a partial order would
    # silently misplace it.
    if len(ids) != len(by_id) or set(ids) != set(by_id):
        raise ReferenceOrderMismatchError(
            "The reference list has changed; reload and try again"
        )
    for position, reference_id in enumerate(ids):
        by_id[reference_id].position = position
    await db.commit()
    return [by_id[reference_id] for reference_id in ids]


def to_project_reference_out(reference: ProjectReference) -> ProjectReferenceOut:
    return ProjectReferenceOut(
        id=reference.id,
        project_id=reference.project_id,
        kind=reference.kind,
        label=reference.label,
        value=reference.value,
        position=reference.position,
    )


def to_consultant_out(user: User) -> ServiceLineConsultantOut:
    return ServiceLineConsultantOut(
        id=user.id, full_name=user.full_name, is_active=user.is_active
    )


def to_project_manager_out(user: User) -> ProjectManagerOut:
    return ProjectManagerOut(id=user.id, full_name=user.full_name)


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
    vendor = project.vendor_company
    client = project.client_company
    return ProjectDetail(
        id=project.id,
        name=project.name,
        vendor_company_id=project.vendor_company_id,
        vendor_company_name=vendor.legal_name if vendor else None,
        vendor_company_is_active=vendor.is_active if vendor else None,
        client_company_id=project.client_company_id,
        client_company_name=client.legal_name if client else None,
        client_company_is_active=client.is_active if client else None,
        invoicing_currency=project.invoicing_currency,
        project_type=project.project_type,
        status=project.status,
        is_active=project.is_active,
        created_at=project.created_at,
        updated_at=project.updated_at,
        service_lines=[to_service_line_out(line) for line in active_lines],
        project_managers=[to_project_manager_out(u) for u in project.project_managers],
        project_references=[
            to_project_reference_out(r)
            for r in sorted(
                project.project_references, key=lambda r: (r.position, r.created_at)
            )
        ],
        billing_milestones=[
            to_billing_milestone_out(m)
            for m in sorted(
                project.billing_milestones, key=lambda m: (m.position, m.created_at)
            )
        ],
        total_value=project_total_value(project),
    )
