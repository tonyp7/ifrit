import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, ServiceLine, service_line_consultants
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.schemas.time_entry import (
    EligibleServiceLineOut,
    TimeEntryOut,
    TimeEntryUpsert,
    TimeEntryUpsertResult,
)


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
    # docs/requirements/timesheet.md#state's population rule).
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
    docs/requirements/timesheet.md's "API contract: PUT /time-entries is bulk, not
    single-entry"). hours == 0 deletes any existing row instead of saving a zero;
    hours > 0 upserts, always unlocked, only if the user is currently assigned to the
    service line. **Every path here checks `is_locked` first, unconditionally** —
    locked rows are immutable through this endpoint regardless of direction
    (delete or overwrite) or who's calling; unlocking is exclusively a
    `project_manager`'s action via the (not yet built) Validation screen, never this
    one. This is enforced here, server-side, independent of whatever the frontend
    believes the lock state is — see the same section's note on why relying on the
    frontend disabling a locked input alone isn't sufficient."""
    existing = await _fetch_existing(db, user.id, item.service_line_id, item.date)

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

    if not await _is_eligible(db, user.id, item.service_line_id):
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
            user_id=user.id,
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
    context = await _fetch_entry_with_context(db, user.id, item.service_line_id, item.date)
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
    docs/requirements/timesheet.md#interactions--input-rules, "Removing a service
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
