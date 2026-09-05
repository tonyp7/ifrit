import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Literal

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Table,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

if TYPE_CHECKING:
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

# Users (holding the project_manager role) assigned to review/lock a project's
# timesheets — see docs/requirements/project.md#1-entity-project. Only reflects
# current assignment, not history. Named `project_manager_assignments`, distinct
# from `Project.project_managers` below (the relationship attribute) — same
# distinct-names precaution as `service_line_consultants`/`ServiceLine.users`
# above, since `secondary=project_managers` would otherwise shadow this Table
# with the class attribute being defined on the same line.
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
    # Must reference a company with is_vendor = true (app-level check, see
    # docs/requirements/project.md#1-entity-project).
    vendor_company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    # Any company, is_vendor or not. Can be the same company as vendor_company_id
    # (inter-company/self-billing) — intentional.
    client_company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False
    )
    # Must reference a currency with is_enabled = true (app-level check).
    invoicing_currency: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.alpha_code"), nullable=False
    )
    project_type: Mapped[ProjectType] = mapped_column(String(20), nullable=False)
    # status transitions are unrestricted (any -> any); it's a filtering/edit-rule
    # switch, not a workflow gate — see docs/requirements/project.md#status-enum.
    status: Mapped[ProjectStatus] = mapped_column(
        String(10), nullable=False, default="draft", server_default="draft"
    )
    # Soft-delete flag, independent of `status` — see docs/requirements/project.md
    # #1-entity-project. Deleted projects are filtered out of the list entirely
    # (unlike Company, which keeps deactivated rows visible).
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    service_lines: Mapped[list["ServiceLine"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    project_managers: Mapped[list["User"]] = relationship(
        "User", secondary=project_manager_assignments
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
    # Free text, no uniqueness constraint, may be empty — lets a consultant assigned to
    # more than one line on the same project tell them apart when logging time (see
    # docs/requirements/project.md#2-entity-service-line, docs/requirements/timesheet.md).
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Does not depend on uom — always the same decimal shape (see
    # docs/requirements/project.md#2-entity-service-line).
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 5), nullable=False)
    uom: Mapped[Uom] = mapped_column(String(10), nullable=False)
    # Denominated in the parent project's invoicing_currency — no separate per-line
    # currency field. Numeric(14, 4): more decimal places than any real-world minor
    # unit needs, headroom for currencies like BHD (3 decimals) without rounding loss.
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    # Soft-delete flag — see docs/requirements/project.md#validation-rules-1. Every
    # query listing a project's service lines must filter to is_active = true (see the
    # partial index below); there is no UI to recover a soft-deleted line.
    is_active: Mapped[bool] = mapped_column(default=True)

    project: Mapped[Project] = relationship(back_populates="service_lines")
    users: Mapped[list["User"]] = relationship(
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
