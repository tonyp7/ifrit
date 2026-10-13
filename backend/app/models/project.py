import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.user import User

ProjectType = Literal["time_and_material", "fixed_price", "capped_tm"]
ProjectStatus = Literal["draft", "active", "closed"]
Uom = Literal["hours", "days", "ea"]

service_line_consultants = Table(
    "service_line_consultants",
    Base.metadata,
    Column(
        "service_line_id",
        UUID(as_uuid=True),
        ForeignKey("service_lines.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# Users (holding the manager role) listed as a project's managers. A label, not a
# permission: every manager may work on every project, and this only decides what their
# "Only see my projects" views show. Only reflects current assignment, not history. Named
# `project_manager_assignments`, distinct from `Project.project_managers` below (the
# relationship attribute): same distinct-names precaution as
# `service_line_consultants`/`ServiceLine.users` above, since `secondary=project_managers`
# would otherwise shadow this Table with the class attribute being defined on the same line.
project_manager_assignments = Table(
    "project_managers",
    Base.metadata,
    Column(
        "project_id",
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "user_id",
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Must reference an active company with is_vendor = true: a business rule on
    # Company, not enforceable via a plain FK, so this is checked at the app level on
    # write. Nullable only because duplicating a project whose company was since
    # soft-deleted clears the link (the user must pick a valid one before saving); the
    # write schema (ProjectWrite) still requires it.
    vendor_company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True, index=True
    )
    # Any active company, is_vendor or not. Can be the same company as vendor_company_id
    # (inter-company/self-billing): intentional. Nullable for the same reason as above.
    client_company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True, index=True
    )
    vendor_company: Mapped[Company | None] = relationship(
        foreign_keys=[vendor_company_id]
    )
    client_company: Mapped[Company | None] = relationship(
        foreign_keys=[client_company_id]
    )
    # Must reference a currency with is_enabled = true (app-level check).
    invoicing_currency: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.alpha_code"), nullable=False
    )
    project_type: Mapped[ProjectType] = mapped_column(String(20), nullable=False)
    # status transitions are unrestricted (any -> any); it's a filtering/edit-rule
    # switch (e.g. gating whether service lines can still be edited), not a workflow
    # gate with an enforced lifecycle.
    status: Mapped[ProjectStatus] = mapped_column(
        String(10), nullable=False, default="draft", server_default="draft"
    )
    # Soft-delete flag, independent of `status`: a project can be `closed` (a real
    # lifecycle state) and still `is_active = true`, or vice versa. Deleted projects are
    # filtered out of the list entirely, same as deactivated Companies.
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    service_lines: Mapped[list[ServiceLine]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    project_managers: Mapped[list[User]] = relationship(
        "User", secondary=project_manager_assignments
    )
    billing_milestones: Mapped[list[BillingMilestone]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="(BillingMilestone.position, BillingMilestone.created_at)",
    )

    __table_args__ = (
        CheckConstraint(
            "project_type IN ('time_and_material', 'fixed_price', 'capped_tm')",
            name="ck_projects_project_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'active', 'closed')", name="ck_projects_status"
        ),
    )


class ServiceLine(Base):
    __tablename__ = "service_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Free text, no uniqueness constraint, may be empty: exists purely so a consultant
    # assigned to more than one service line on the same project can tell them apart
    # when picking which one to log time against; not used in billing or calculations.
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Does not depend on uom: always the same decimal shape regardless of whether it's
    # counting hours, days, or a fixed quantity.
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 5), nullable=False)
    uom: Mapped[Uom] = mapped_column(String(10), nullable=False)
    # Denominated in the parent project's invoicing_currency: no separate per-line
    # currency field. Numeric(14, 4): more decimal places than any real-world minor
    # unit needs, headroom for currencies like BHD (3 decimals) without rounding loss.
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    # Soft-delete flag. Every query listing a project's service lines must filter to
    # is_active = true (see the partial index below); there is no UI to recover a
    # soft-deleted line.
    is_active: Mapped[bool] = mapped_column(default=True)

    project: Mapped[Project] = relationship(back_populates="service_lines")
    users: Mapped[list[User]] = relationship(
        "User", secondary=service_line_consultants
    )

    __table_args__ = (
        CheckConstraint("uom IN ('hours', 'days', 'ea')", name="ck_service_lines_uom"),
        Index(
            "ix_service_lines_project_id_active",
            "project_id",
            postgresql_where=is_active.is_(True),
        ),
    )


class BillingMilestone(Base):
    """An agreed billing installment of a Fixed Price project (e.g. "30% at kick-off").

    Hard-deleted, unlike service lines: nothing references a milestone (an invoice copies
    its description and value rather than linking to it), so there is no history that a
    soft-delete flag would protect.
    """

    __tablename__ = "billing_milestones"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    # A calendar date, no time: stored as DATE so it reads back as the same day in every
    # time zone.
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # The only stored amount; the percentage shown next to it is always derived from the
    # project's current contract value. Same Numeric(14, 4) as a service line's unit
    # price, so a value saved under a 3-decimal currency still fits after the project's
    # currency changes.
    value: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    # Ordering key only: gaps after a delete are harmless, and a reorder renumbers the
    # whole project 0..n-1. Deliberately not unique per project, or that renumbering
    # would collide with itself mid-update.
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    project: Mapped[Project] = relationship(back_populates="billing_milestones")

    __table_args__ = (
        CheckConstraint("value >= 0", name="ck_billing_milestones_value"),
        Index("ix_billing_milestones_project_id_position", "project_id", "position"),
    )
