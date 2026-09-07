import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import (
    Project,
    ServiceLine,
    project_manager_assignments,
    service_line_consultants,
)
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.schemas.time_entry import (
    EligibleServiceLineOut,
    ManagedConsultantOut,
    TimeEntryLockRequest,
    TimeEntryOut,
    TimeEntryUpsert,
    TimeEntryUpsertResult,
)


class NotAuthorizedError(Exception):
    """Raised by `set_service_line_lock` when the caller isn't a project_manager
    assigned to the target service line's project, or the target consultant isn't
    assigned to it — see specs/requirements/timesheet.md's Validation § API contract
    for PUT /time-entries/lock. Unlike a bulk PUT /time-entries item's per-item
    {ok: false}, this is a single-action endpoint — any failing check rejects the
    whole request, not a partial success."""


def _hours_to_timedelta(hours: Decimal) -> timedelta:
    return timedelta(minutes=int(hours * 60))


def _timedelta_to_hours(delta: timedelta) -> Decimal:
    total_minutes = delta.days * 24 * 60 + delta.seconds // 60
    return (Decimal(total_minutes) / Decimal(60)).quantize(Decimal("0.01"))


def _eligibility_filters() -> tuple:
    return (
        ServiceLine.is_active.is_(True),
        Project.is_active.is_(True),
        Project.status == "active",
    )


def _is_project_manager(user: User) -> bool:
    return any(role.name == "project_manager" for role in user.roles)


async def _pm_project_ids(db: AsyncSession, project_manager_id: uuid.UUID) -> set[uuid.UUID]:
    result = await db.execute(
        select(project_manager_assignments.c.project_id).where(
            project_manager_assignments.c.user_id == project_manager_id
        )
    )
    return {row[0] for row in result.all()}


async def _is_eligible(
    db: AsyncSession, user_id: uuid.UUID, service_line_id: uuid.UUID
) -> bool:
    stmt = (
        select(ServiceLine.id)
        .join(Project, ServiceLine.project_id == Project.id)
        .join(
            service_line_consultants,
            service_line_consultants.c.service_line_id == ServiceLine.id,
        )
        .where(
            ServiceLine.id == service_line_id,
            service_line_consultants.c.user_id == user_id,
            *_eligibility_filters(),
        )
    )
    result = await db.execute(stmt)
    return result.first() is not None


async def list_eligible_service_lines(
    db: AsyncSession, user_id: uuid.UUID
) -> list[tuple[ServiceLine, Project]]:
    stmt = (
        select(ServiceLine, Project)
        .join(Project, ServiceLine.project_id == Project.id)
        .join(
            service_line_consultants,
            service_line_consultants.c.service_line_id == ServiceLine.id,
        )
        .where(
            service_line_consultants.c.user_id == user_id,
            *_eligibility_filters(),
        )
        .order_by(Project.name, ServiceLine.name)
    )
    rows = (await db.execute(stmt)).all()
    return [(row[0], row[1]) for row in rows]


async def list_time_entries(
    db: AsyncSession, user_id: uuid.UUID, start_date: date, end_date: date
) -> list[tuple[TimeEntry, ServiceLine, Project]]:
    # Deliberately no is_active/status filtering here, unlike the eligibility query
    # above: historical entries must stay visible even after the user is later
    # unassigned or the line/project is deactivated (see
    # specs/requirements/timesheet.md#state's population rule).
    stmt = (
        select(TimeEntry, ServiceLine, Project)
        .join(ServiceLine, TimeEntry.service_line_id == ServiceLine.id)
        .join(Project, ServiceLine.project_id == Project.id)
        .where(
            TimeEntry.user_id == user_id,
            TimeEntry.date >= start_date,
            TimeEntry.date <= end_date,
        )
        .order_by(TimeEntry.date)
    )
    rows = (await db.execute(stmt)).all()
    return [(row[0], row[1], row[2]) for row in rows]


async def _fetch_entry_with_context(
    db: AsyncSession,
    user_id: uuid.UUID,
    service_line_id: uuid.UUID,
    entry_date: date,
) -> tuple[TimeEntry, ServiceLine, Project] | None:
    stmt = (
        select(TimeEntry, ServiceLine, Project)
        .join(ServiceLine, TimeEntry.service_line_id == ServiceLine.id)
        .join(Project, ServiceLine.project_id == Project.id)
        .where(
            TimeEntry.user_id == user_id,
            TimeEntry.service_line_id == service_line_id,
            TimeEntry.date == entry_date,
        )
    )
    row = (await db.execute(stmt)).first()
    return (row[0], row[1], row[2]) if row is not None else None


async def _fetch_existing(
    db: AsyncSession, user_id: uuid.UUID, service_line_id: uuid.UUID, entry_date: date
) -> TimeEntry | None:
    result = await db.execute(
        select(TimeEntry).where(
            TimeEntry.user_id == user_id,
            TimeEntry.service_line_id == service_line_id,
            TimeEntry.date == entry_date,
        )
    )
    return result.scalar_one_or_none()


async def _upsert_one(
    db: AsyncSession, user: User, item: TimeEntryUpsert
) -> TimeEntryUpsertResult:
    """One item of the bulk `PUT /time-entries` request (see
    specs/requirements/timesheet.md's "API contract: PUT /time-entries is bulk, not
    single-entry"). hours == 0 deletes any existing row instead of saving a zero;
    hours > 0 upserts, always unlocked, only if the entry's owner is currently
    assigned to the service line. **Every path here checks `is_locked` first,
    unconditionally** — locked rows are immutable through this endpoint regardless
    of direction (delete or overwrite) or who's calling; unlocking is exclusively a
    `project_manager`'s action via PUT /time-entries/lock, never this one. This is
    enforced here, server-side, independent of whatever the frontend believes the
    lock state is — see the same section's note on why relying on the frontend
    disabling a locked input alone isn't sufficient.

    `item.user_id` is the entry's *owner* — `None` (the only value My Timesheet's
    own calls ever send) means the caller's own entry; a different id is a
    `project_manager`'s override of a consultant's entry (see
    specs/requirements/timesheet.md's Validation § Scope, "Editing (override)"). An
    override is authorized per item, not once for the whole request — matching the
    "each item is processed and persisted independently" rule this endpoint already
    follows for everything else."""
    owner_id = item.user_id if item.user_id is not None else user.id

    if owner_id != user.id:
        if not _is_project_manager(user):
            return TimeEntryUpsertResult(
                service_line_id=item.service_line_id,
                date=item.date,
                ok=False,
                error="not_authorized",
            )
        pm_project_ids = await _pm_project_ids(db, user.id)
        service_line_project = (
            await db.execute(
                select(ServiceLine.project_id).where(ServiceLine.id == item.service_line_id)
            )
        ).scalar_one_or_none()
        if service_line_project is None or service_line_project not in pm_project_ids:
            return TimeEntryUpsertResult(
                service_line_id=item.service_line_id,
                date=item.date,
                ok=False,
                error="not_authorized",
            )

    existing = await _fetch_existing(db, owner_id, item.service_line_id, item.date)

    if existing is not None and existing.is_locked:
        return TimeEntryUpsertResult(
            service_line_id=item.service_line_id, date=item.date, ok=False, error="locked"
        )

    if item.hours == 0:
        if existing is not None:
            await db.delete(existing)
            await db.commit()
        return TimeEntryUpsertResult(
            service_line_id=item.service_line_id, date=item.date, ok=True
        )

    if not await _is_eligible(db, owner_id, item.service_line_id):
        return TimeEntryUpsertResult(
            service_line_id=item.service_line_id,
            date=item.date,
            ok=False,
            error="not_eligible",
        )

    time_value = _hours_to_timedelta(item.hours)
    stmt = (
        pg_insert(TimeEntry)
        .values(
            id=uuid.uuid4(),
            user_id=owner_id,
            service_line_id=item.service_line_id,
            date=item.date,
            time_entry=time_value,
            last_updated_by=user.id,
            is_locked=False,
        )
        .on_conflict_do_update(
            constraint="uq_time_entries_user_service_line_date",
            set_={
                "time_entry": time_value,
                "is_locked": False,
                "last_updated_by": user.id,
                "updated_at": datetime.now(UTC),
            },
        )
    )
    await db.execute(stmt)
    await db.commit()
    context = await _fetch_entry_with_context(db, owner_id, item.service_line_id, item.date)
    assert context is not None
    entry, line, project = context
    return TimeEntryUpsertResult(
        service_line_id=item.service_line_id,
        date=item.date,
        ok=True,
        entry=to_time_entry_out(entry, line, project),
    )


async def upsert_time_entries(
    db: AsyncSession, user: User, items: list[TimeEntryUpsert]
) -> list[TimeEntryUpsertResult]:
    """Bulk blur-triggered save — a single cell edit sends a one-element list; the
    clear-on-remove-service-line flow sends one list covering every day being
    cleared in the current period, in one call (see
    specs/requirements/timesheet.md#interactions--input-rules, "Removing a service
    line"). Each item is processed and persisted **independently** — one item's
    rejection (see _upsert_one above) never blocks or rolls back any other item in
    this same list; that's the API layer's job to report (207 vs 200), not this
    function's."""
    return [await _upsert_one(db, user, item) for item in items]


def to_time_entry_out(
    entry: TimeEntry, line: ServiceLine, project: Project
) -> TimeEntryOut:
    return TimeEntryOut(
        id=entry.id,
        service_line_id=entry.service_line_id,
        service_line_name=line.name,
        project_id=project.id,
        project_name=project.name,
        date=entry.date,
        hours=_timedelta_to_hours(entry.time_entry),
        is_locked=entry.is_locked,
    )


def to_eligible_service_line_out(
    line: ServiceLine, project: Project
) -> EligibleServiceLineOut:
    return EligibleServiceLineOut(
        service_line_id=line.id,
        service_line_name=line.name,
        project_id=project.id,
        project_name=project.name,
    )


async def list_managed_time_entries(
    db: AsyncSession, project_manager: User, start_date: date, end_date: date
) -> list[ManagedConsultantOut]:
    """GET /time-entries/managed — see specs/requirements/timesheet.md's Validation §
    API contract. One query for the roster, one for all entries across that whole
    roster, one for all eligible-service-line sets across that whole roster — never
    N round trips per consultant (see that section's rejection of the per-consultant
    loop alternative)."""
    pm_project_ids = await _pm_project_ids(db, project_manager.id)
    if not pm_project_ids:
        return []

    # Roster part 1: consultants currently eligible on an in-scope service line.
    eligible_ids_stmt = (
        select(service_line_consultants.c.user_id)
        .join(ServiceLine, ServiceLine.id == service_line_consultants.c.service_line_id)
        .join(Project, Project.id == ServiceLine.project_id)
        .where(Project.id.in_(pm_project_ids), *_eligibility_filters())
        .distinct()
    )
    eligible_ids = {row[0] for row in (await db.execute(eligible_ids_stmt)).all()}

    # Roster part 2: anyone with historical data on a line under one of these
    # projects, regardless of current assignment/active status — same "history
    # stays visible" principle as My Timesheet's own population rule, applied one
    # level up (see specs/requirements/timesheet.md#state).
    historical_ids_stmt = (
        select(TimeEntry.user_id)
        .join(ServiceLine, ServiceLine.id == TimeEntry.service_line_id)
        .where(ServiceLine.project_id.in_(pm_project_ids))
        .distinct()
    )
    historical_ids = {row[0] for row in (await db.execute(historical_ids_stmt)).all()}

    consultant_ids = eligible_ids | historical_ids
    if not consultant_ids:
        return []

    consultants = list(
        (
            await db.execute(
                select(User)
                .where(User.id.in_(consultant_ids))
                .order_by(User.full_name)
            )
        )
        .scalars()
        .all()
    )

    # All in-scope entries for the whole roster in one query — scoped to service
    # lines under *this* project_manager's projects only, never a consultant's
    # lines on projects this project_manager isn't assigned to (§Scope's hard
    # project-scoping rule).
    entries_stmt = (
        select(TimeEntry, ServiceLine, Project)
        .join(ServiceLine, TimeEntry.service_line_id == ServiceLine.id)
        .join(Project, ServiceLine.project_id == Project.id)
        .where(
            TimeEntry.user_id.in_(consultant_ids),
            Project.id.in_(pm_project_ids),
            TimeEntry.date >= start_date,
            TimeEntry.date <= end_date,
        )
        .order_by(TimeEntry.date)
    )
    entries_by_user: dict[uuid.UUID, list[TimeEntryOut]] = defaultdict(list)
    for entry, line, project in (await db.execute(entries_stmt)).all():
        entries_by_user[entry.user_id].append(to_time_entry_out(entry, line, project))

    # Every eligible-service-line row for the whole roster in one query too (see
    # ManagedConsultantOut's own docstring for why this is the unfiltered set, not
    # pre-filtered to "addable").
    eligible_lines_stmt = (
        select(ServiceLine, Project, service_line_consultants.c.user_id)
        .join(Project, ServiceLine.project_id == Project.id)
        .join(
            service_line_consultants,
            service_line_consultants.c.service_line_id == ServiceLine.id,
        )
        .where(
            Project.id.in_(pm_project_ids),
            service_line_consultants.c.user_id.in_(consultant_ids),
            *_eligibility_filters(),
        )
        .order_by(Project.name, ServiceLine.name)
    )
    eligible_by_user: dict[uuid.UUID, list[EligibleServiceLineOut]] = defaultdict(list)
    for line, project, consultant_id in (await db.execute(eligible_lines_stmt)).all():
        eligible_by_user[consultant_id].append(to_eligible_service_line_out(line, project))

    return [
        ManagedConsultantOut(
            user_id=consultant.id,
            full_name=consultant.full_name,
            entries=entries_by_user.get(consultant.id, []),
            eligible_service_lines=eligible_by_user.get(consultant.id, []),
        )
        for consultant in consultants
    ]


async def set_service_line_lock(
    db: AsyncSession, caller: User, request: TimeEntryLockRequest
) -> list[TimeEntryOut]:
    """PUT /time-entries/lock — see specs/requirements/timesheet.md's Validation §
    Lock / Unlock and its API contract. Locks or unlocks every day in
    [start_date, end_date] for one (consultant, service line) pair — never per
    cell, never per day as separate actions from the caller's perspective."""
    if not _is_project_manager(caller):
        raise NotAuthorizedError("Only a project_manager can lock or unlock a service line")

    pm_project_ids = await _pm_project_ids(db, caller.id)
    service_line_project = (
        await db.execute(
            select(ServiceLine.project_id).where(ServiceLine.id == request.service_line_id)
        )
    ).scalar_one_or_none()
    if service_line_project is None or service_line_project not in pm_project_ids:
        raise NotAuthorizedError(
            "You are not assigned as project manager on this service line's project"
        )

    if not await _is_eligible_ignoring_active_status(db, request.user_id, request.service_line_id):
        raise NotAuthorizedError(
            "This consultant is not assigned to this service line"
        )

    # An inverted range (end before start) just produces no days to act on — a
    # harmless no-op, not an authorization failure, so no error is raised for it.
    day_count = (request.end_date - request.start_date).days
    days = [request.start_date + timedelta(days=i) for i in range(day_count + 1)]

    if request.locked:
        for day in days:
            # Single atomic upsert per day — see specs/requirements/timesheet.md's
            # "must be written as a single atomic upsert per day" resolution: the
            # conflict branch touches is_locked ONLY, never hours, so a
            # consultant's value that lands moments before this statement runs is
            # locked as entered, never zeroed out by it. Postgres's own row-level
            # serialization on the unique key makes this safe under concurrency,
            # not application-level read-then-decide logic.
            stmt = (
                pg_insert(TimeEntry)
                .values(
                    id=uuid.uuid4(),
                    user_id=request.user_id,
                    service_line_id=request.service_line_id,
                    date=day,
                    time_entry=timedelta(0),
                    last_updated_by=caller.id,
                    is_locked=True,
                )
                .on_conflict_do_update(
                    constraint="uq_time_entries_user_service_line_date",
                    set_={
                        "is_locked": True,
                        "last_updated_by": caller.id,
                        "updated_at": datetime.now(UTC),
                    },
                )
            )
            await db.execute(stmt)
        await db.commit()
    else:
        existing_rows = (
            await db.execute(
                select(TimeEntry).where(
                    TimeEntry.user_id == request.user_id,
                    TimeEntry.service_line_id == request.service_line_id,
                    TimeEntry.date >= request.start_date,
                    TimeEntry.date <= request.end_date,
                )
            )
        ).scalars().all()
        for row in existing_rows:
            if row.time_entry == timedelta(0):
                # One of lock's own gap-fill rows — a genuine consultant-entered 0
                # can never exist (see §Persistence) — so unlocking removes it
                # entirely, restoring the true gap, rather than leaving a 0 row
                # unlocked.
                await db.delete(row)
            else:
                row.is_locked = False
                row.last_updated_by = caller.id
        await db.commit()

    result = await db.execute(
        select(TimeEntry, ServiceLine, Project)
        .join(ServiceLine, TimeEntry.service_line_id == ServiceLine.id)
        .join(Project, ServiceLine.project_id == Project.id)
        .where(
            TimeEntry.user_id == request.user_id,
            TimeEntry.service_line_id == request.service_line_id,
            TimeEntry.date >= request.start_date,
            TimeEntry.date <= request.end_date,
        )
        .order_by(TimeEntry.date)
    )
    return [to_time_entry_out(entry, line, project) for entry, line, project in result.all()]


async def _is_eligible_ignoring_active_status(
    db: AsyncSession, user_id: uuid.UUID, service_line_id: uuid.UUID
) -> bool:
    """Same consultant-assignment check `_is_eligible` makes, minus the active
    project/service-line filters — locking/unlocking a *historical* assignment
    must keep working even after the project's since closed or the line
    deactivated (see specs/requirements/timesheet.md's Validation § Scope: history
    stays visible and, by extension, lockable, regardless of current status)."""
    result = await db.execute(
        select(service_line_consultants.c.user_id).where(
            service_line_consultants.c.service_line_id == service_line_id,
            service_line_consultants.c.user_id == user_id,
        )
    )
    return result.first() is not None
