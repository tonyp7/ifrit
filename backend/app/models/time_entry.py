import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Interval,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class TimeEntry(Base):
    __tablename__ = "time_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # A time entry's primary subject is the person who logged it; deleting that user
    # deletes their entries (see specs/requirements/timesheet.md#data-model).
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # A time entry can't outlive the service line it was logged against.
    service_line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("service_lines.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    # Deliberately INTERVAL, not TIME: TIME's natural 24:00:00 ceiling looked like it
    # enforced the domain constraint for free, but asyncpg binds/decodes TIME exclusively
    # via datetime.time (hour capped at 23) and can neither write nor read back 24:00:00 —
    # confirmed against a live connection. The CHECK constraint below does that job
    # explicitly instead (see specs/requirements/timesheet.md#data-model).
    time_entry: Mapped[timedelta] = mapped_column(Interval, nullable=False)
    # Unused in the current UI — deliberate scope-fencing for a later iteration.
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Deliberately not CASCADE, unlike user_id/service_line_id above: this just records
    # who last touched the row (e.g. a project_manager's lock/unlock), not whose data it is.
    last_updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    is_locked: Mapped[bool] = mapped_column(default=False)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "service_line_id",
            "date",
            name="uq_time_entries_user_service_line_date",
        ),
        Index("ix_time_entries_user_id_date", "user_id", "date"),
        CheckConstraint(
            "time_entry >= interval '0' AND time_entry <= interval '24:00:00'",
            name="ck_time_entries_time_entry_range",
        ),
    )
