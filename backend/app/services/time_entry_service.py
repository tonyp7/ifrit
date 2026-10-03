import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import ColumnElement, select
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
    ReportFilterConsultantOut,
    ReportFilterProjectOut,
    ReportFilterServiceLineOut,
    TimeEntryLockRequest,
    TimeEntryOut,
    TimeEntryUpsert,
    TimeEntryUpsertResult,
    TimesheetReportFiltersOut,
    TimesheetReportRowOut,
)

REPORT_PROJECT_STATUSES = {"draft", "active", "closed"}


class NotAuthorizedError(Exception):
    """Raised by `set_service_line_lock` when the caller isn't a project_manager
    assigned to the target service line's project, or the target consultant isn't
    assigned to it. Unlike a bulk PUT /time-entries item's per-item {ok: false}, this
    is a single-action endpoint: any failing check rejects the whole request, not a
    partial success."""


def _hours_to_timedelta(hours: Decimal) -> timedelta:
    return timedelta(minutes=int(hours * 60))


def _timedelta_to_hours(delta: timedelta) -> Decimal:
    total_minutes = delta.days * 24 * 60 + delta.seconds // 60
    return (Decimal(total_minutes) / Decimal(60)).quantize(Decimal("0.01"))


def _eligibility_filters() -> tuple[ColumnElement[bool], ...]:
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
        .join(User, User.id == service_line_consultants.c.user_id)
        .where(
            ServiceLine.id == service_line_id,
            service_line_consultants.c.user_id == user_id,
            # A deleted user can't accrue new/edited time, even while they remain on
            # the line (history): see _is_eligible_ignoring_active_status for the
            # lock/unlock path, which deliberately still works for them.
            User.is_active.is_(True),
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
    # unassigned or the line/project is deactivated.
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
    # populate_existing=True: writes here go through a core upsert
    # (pg_insert ... on_conflict_do_update), which changes the row without telling
    # the ORM. If _fetch_existing already loaded this row into the session's identity
    # map, SQLAlchemy would hand that object back on this re-read with its old
    # attribute values (and the session is expire_on_commit=False, so the commit
    # doesn't expire it either): the response would then describe the value that was
    # just replaced instead of the one that was saved.
    stmt = (
        select(TimeEntry, ServiceLine, Project)
        .join(ServiceLine, TimeEntry.service_line_id == ServiceLine.id)
        .join(Project, ServiceLine.project_id == Project.id)
        .where(
            TimeEntry.user_id == user_id,
            TimeEntry.service_line_id == service_line_id,
            TimeEntry.date == entry_date,
        )
        .execution_options(populate_existing=True)
    )
    row = (await db.execute(stmt)).first()
    return (row[0], row[1], row[2]) if row is not None else None


async def _fetch_existing(
    db: AsyncSession, user_id: uuid.UUID, service_line_id: uuid.UUID, entry_date: date
) -> TimeEntry | None:
    # populate_existing=True: see _fetch_entry_with_context. Today the re-read after
    # each write already refreshes the cached row, so this is belt and braces, but the
    # unchanged-hours skip in _upsert_one compares against this row (and a bulk request
    # can repeat the same cell), so it shouldn't depend on that side effect.
    result = await db.execute(
        select(TimeEntry)
        .where(
            TimeEntry.user_id == user_id,
            TimeEntry.service_line_id == service_line_id,
            TimeEntry.date == entry_date,
        )
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def _upsert_one(
    db: AsyncSession, user: User, item: TimeEntryUpsert
) -> TimeEntryUpsertResult:
    """One item of the bulk `PUT /time-entries` request: this endpoint is always
    bulk, never a single-entry shape, even for a one-cell edit. hours == 0 deletes
    any existing row instead of saving a zero; hours > 0 upserts, always unlocked,
    only if the entry's owner is currently assigned to the service line, and only
    if the value actually differs from the stored one (an identical re-save writes
    nothing and leaves `last_updated_by`/`updated_at` untouched). **Every path
    here checks `is_locked` first, unconditionally**: locked rows are immutable
    through this endpoint regardless of direction (delete or overwrite) or who's
    calling; unlocking is exclusively a `project_manager`'s action via
    PUT /time-entries/lock, never this one. This is enforced here, server-side,
    independent of whatever the frontend believes the lock state is: a disabled
    input is a UI courtesy, not a security boundary; nothing stops a direct API call
    from attempting the same write.

    `item.user_id` is the entry's *owner*: `None` (the only value My Timesheet's
    own calls ever send) means the caller's own entry; a different id is a
    `project_manager`'s override of a consultant's entry. An override is authorized
    per item, not once for the whole request: matching the "each item is processed
    and persisted independently" rule this endpoint already follows for everything
    else."""
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

    if existing is not None and existing.time_entry == time_value:
        # Nothing changed: skip the write so `last_updated_by`/`updated_at` keep
        # recording who last actually changed the hours. Otherwise a project_manager
        # who merely re-saves (or tabs through) a consultant's cell would take over
        # the audit trail. Lock and eligibility were already checked above, so
        # rejections behave exactly as before; only the no-op write is dropped.
        context = await _fetch_entry_with_context(db, owner_id, item.service_line_id, item.date)
        assert context is not None
        entry, line, project = context
        return TimeEntryUpsertResult(
            service_line_id=item.service_line_id,
            date=item.date,
            ok=True,
            entry=to_time_entry_out(entry, line, project),
        )

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
    """Bulk blur-triggered save, a single cell edit sends a one-element list; the
    clear-on-remove-service-line flow sends one list covering every day being
    cleared in the current period, in one call. Each item is processed and persisted
    **independently**, one item's rejection (see _upsert_one above) never blocks or
    rolls back any other item in this same list; that's the API layer's job to report
    (207 vs 200), not this function's."""
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


async def set_service_line_lock(
    db: AsyncSession, caller: User, request: TimeEntryLockRequest
) -> list[TimeEntryOut]:
    """PUT /time-entries/lock. Locks or unlocks every day in
    [start_date, end_date] for one (consultant, service line) pair: never per
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

    # TimeEntryLockRequest already rejected an inverted or over-long range (422).
    day_count = (request.end_date - request.start_date).days
    days = [request.start_date + timedelta(days=i) for i in range(day_count + 1)]

    if request.locked:
        for day in days:
            # Single atomic upsert per day: the conflict branch touches is_locked
            # ONLY, never hours, so a consultant's value that lands moments before
            # this statement runs is locked as entered, never zeroed out by it.
            # Postgres's own row-level serialization on the unique key makes this
            # safe under concurrency, not application-level read-then-decide logic.
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
                # A genuine consultant save of 0 hours is always translated to a
                # delete instead (see _upsert_one above), so any row with
                # time_entry == 0 that reaches this point must be one of lock's own
                # gap-fill rows: safe to remove entirely, restoring the true gap,
                # rather than leaving a 0 row unlocked.
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
        # populate_existing=True: same reason as _fetch_entry_with_context (the lock
        # branch above writes with a core upsert).
        .execution_options(populate_existing=True)
    )
    return [to_time_entry_out(entry, line, project) for entry, line, project in result.all()]


async def _is_eligible_ignoring_active_status(
    db: AsyncSession, user_id: uuid.UUID, service_line_id: uuid.UUID
) -> bool:
    """Same consultant-assignment check `_is_eligible` makes, minus the active
    project/service-line filters: locking/unlocking a *historical* assignment
    must keep working even after the project's since closed or the line
    deactivated: history stays visible and, by extension, lockable, regardless of
    current status."""
    result = await db.execute(
        select(service_line_consultants.c.user_id).where(
            service_line_consultants.c.service_line_id == service_line_id,
            service_line_consultants.c.user_id == user_id,
        )
    )
    return result.first() is not None


async def list_report_filters(
    db: AsyncSession, project_manager: User
) -> TimesheetReportFiltersOut:
    """GET /time-entries/report/filters. Not period-scoped: one fetch on mount,
    covering every project status (unlike list_eligible_service_lines, which is
    restricted to active projects/lines via _eligibility_filters())."""
    pm_project_ids = await _pm_project_ids(db, project_manager.id)
    if not pm_project_ids:
        return TimesheetReportFiltersOut(projects=[], service_lines=[], consultants=[])

    projects = (
        (
            await db.execute(
                select(Project).where(Project.id.in_(pm_project_ids)).order_by(Project.name)
            )
        )
        .scalars()
        .all()
    )

    service_line_rows = (
        await db.execute(
            select(ServiceLine, Project)
            .join(Project, ServiceLine.project_id == Project.id)
            .where(Project.id.in_(pm_project_ids))
            .order_by(Project.name, ServiceLine.name)
        )
    ).all()

    # Two-part consultant roster: anyone currently assigned to a line under one of
    # these projects (regardless of active status), unioned with anyone holding
    # historical entries on such a line.
    eligible_ids_stmt = (
        select(service_line_consultants.c.user_id)
        .join(ServiceLine, ServiceLine.id == service_line_consultants.c.service_line_id)
        .where(ServiceLine.project_id.in_(pm_project_ids))
        .distinct()
    )
    eligible_ids = {row[0] for row in (await db.execute(eligible_ids_stmt)).all()}

    historical_ids_stmt = (
        select(TimeEntry.user_id)
        .join(ServiceLine, ServiceLine.id == TimeEntry.service_line_id)
        .where(ServiceLine.project_id.in_(pm_project_ids))
        .distinct()
    )
    historical_ids = {row[0] for row in (await db.execute(historical_ids_stmt)).all()}

    consultant_ids = eligible_ids | historical_ids
    consultants: list[User] = []
    if consultant_ids:
        consultants = list(
            (
                await db.execute(
                    select(User).where(User.id.in_(consultant_ids)).order_by(User.full_name)
                )
            )
            .scalars()
            .all()
        )

    return TimesheetReportFiltersOut(
        projects=[
            ReportFilterProjectOut(project_id=p.id, name=p.name, status=p.status)
            for p in projects
        ],
        service_lines=[
            ReportFilterServiceLineOut(
                service_line_id=line.id,
                service_line_name=line.name,
                project_id=project.id,
                project_name=project.name,
            )
            for line, project in service_line_rows
        ],
        consultants=[
            ReportFilterConsultantOut(user_id=c.id, full_name=c.full_name) for c in consultants
        ],
    )


async def list_time_entries_report(
    db: AsyncSession,
    project_manager: User,
    start_date: date,
    end_date: date,
    project_ids: list[uuid.UUID] | None,
    service_line_ids: list[uuid.UUID] | None,
    consultant_ids: list[uuid.UUID] | None,
    statuses: list[str] | None,
) -> list[TimesheetReportRowOut]:
    """GET /time-entries/report. Row membership: a (consultant, service_line) pair
    shows if the consultant is currently assigned to the line (regardless of active
    status: the same relationship _is_eligible_ignoring_active_status checks) or
    has a time_entries row on it in the requested period, even if no longer
    assigned at all: the same union list_report_filters' consultant roster already
    computes, applied one level down to the pair, so a currently-assigned-but-
    zero-data-this-period pairing still gets a row. Every filter param narrows this
    set further; an id outside the caller's own pm_project_ids scope contributes
    nothing: never a 403, a GET shouldn't hard-fail on a stale/tampered filter id."""
    pm_project_ids = await _pm_project_ids(db, project_manager.id)
    if project_ids:
        pm_project_ids &= set(project_ids)
    if not pm_project_ids:
        return []

    effective_statuses = set(statuses) if statuses else REPORT_PROJECT_STATUSES

    project_rows = (
        (
            await db.execute(
                select(Project).where(
                    Project.id.in_(pm_project_ids), Project.status.in_(effective_statuses)
                )
            )
        )
        .scalars()
        .all()
    )
    projects_by_id = {p.id: p for p in project_rows}
    if not projects_by_id:
        return []

    service_line_stmt = select(ServiceLine).where(
        ServiceLine.project_id.in_(projects_by_id.keys())
    )
    if service_line_ids:
        service_line_stmt = service_line_stmt.where(ServiceLine.id.in_(service_line_ids))
    service_lines = (await db.execute(service_line_stmt)).scalars().all()
    service_lines_by_id = {line.id: line for line in service_lines}
    if not service_lines_by_id:
        return []

    # Pair membership part 1: current assignment, regardless of active status,
    # scoped to the candidate service lines above.
    assignment_stmt = select(
        service_line_consultants.c.user_id, service_line_consultants.c.service_line_id
    ).where(service_line_consultants.c.service_line_id.in_(service_lines_by_id.keys()))
    if consultant_ids:
        assignment_stmt = assignment_stmt.where(
            service_line_consultants.c.user_id.in_(consultant_ids)
        )
    assigned_pairs = {(row[0], row[1]) for row in (await db.execute(assignment_stmt)).all()}

    # Pair membership part 2: historical entries in the requested period, whether or
    # not currently assigned: same "history stays visible" principle applied one
    # level down from list_report_filters' consultant roster.
    historical_stmt = (
        select(TimeEntry.user_id, TimeEntry.service_line_id)
        .where(
            TimeEntry.service_line_id.in_(service_lines_by_id.keys()),
            TimeEntry.date >= start_date,
            TimeEntry.date <= end_date,
        )
        .distinct()
    )
    if consultant_ids:
        historical_stmt = historical_stmt.where(TimeEntry.user_id.in_(consultant_ids))
    historical_pairs = {(row[0], row[1]) for row in (await db.execute(historical_stmt)).all()}

    pairs = assigned_pairs | historical_pairs
    if not pairs:
        return []

    pair_user_ids = {p[0] for p in pairs}
    consultants_by_id = {
        c.id: c
        for c in (
            await db.execute(select(User).where(User.id.in_(pair_user_ids)))
        )
        .scalars()
        .all()
    }

    # All in-scope entries for the whole pair set, in one query: one indexed query
    # beats N round trips.
    entries_stmt = (
        select(TimeEntry, ServiceLine, Project)
        .join(ServiceLine, TimeEntry.service_line_id == ServiceLine.id)
        .join(Project, ServiceLine.project_id == Project.id)
        .where(
            TimeEntry.service_line_id.in_(service_lines_by_id.keys()),
            TimeEntry.user_id.in_(pair_user_ids),
            TimeEntry.date >= start_date,
            TimeEntry.date <= end_date,
        )
        .order_by(TimeEntry.date)
    )
    entries_by_pair: dict[tuple[uuid.UUID, uuid.UUID], list[TimeEntryOut]] = defaultdict(list)
    for entry, line, project in (await db.execute(entries_stmt)).all():
        entries_by_pair[(entry.user_id, entry.service_line_id)].append(
            to_time_entry_out(entry, line, project)
        )

    # is_assigned: the narrower, existing eligibility rule, see TimesheetReportRowOut's
    # own docstring for why this is deliberately _eligibility_filters()-restricted,
    # unlike the broader membership rule above.
    assigned_eligible_stmt = (
        select(service_line_consultants.c.user_id, service_line_consultants.c.service_line_id)
        .join(ServiceLine, ServiceLine.id == service_line_consultants.c.service_line_id)
        .join(Project, Project.id == ServiceLine.project_id)
        .where(
            ServiceLine.id.in_(service_lines_by_id.keys()),
            *_eligibility_filters(),
        )
    )
    eligible_pairs = {
        (row[0], row[1]) for row in (await db.execute(assigned_eligible_stmt)).all()
    }

    rows = []
    for user_id, service_line_id in pairs:
        consultant = consultants_by_id.get(user_id)
        line = service_lines_by_id.get(service_line_id)
        project = projects_by_id.get(line.project_id) if line else None
        if consultant is None or line is None or project is None:
            continue
        rows.append(
            TimesheetReportRowOut(
                user_id=consultant.id,
                full_name=consultant.full_name,
                project_id=project.id,
                project_name=project.name,
                project_status=project.status,
                service_line_id=line.id,
                service_line_name=line.name,
                entries=entries_by_pair.get((user_id, service_line_id), []),
                is_assigned=(user_id, service_line_id) in eligible_pairs,
            )
        )

    rows.sort(
        key=lambda r: (r.full_name, r.project_name, r.service_line_name or "", str(r.service_line_id))
    )
    return rows
