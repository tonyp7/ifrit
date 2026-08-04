"""projects, service_lines, service_line_consultants

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-02

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "vendor_company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column(
            "client_company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id"),
            nullable=False,
        ),
        sa.Column(
            "invoicing_currency",
            sa.String(length=3),
            sa.ForeignKey("currencies.alpha_code"),
            nullable=False,
        ),
        sa.Column("project_type", sa.String(length=20), nullable=False),
        sa.Column(
            "status", sa.String(length=10), nullable=False, server_default="draft"
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "project_type IN ('time_and_material', 'fixed_price', 'capped_tm')",
            name="ck_projects_project_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'closed')", name="ck_projects_status"
        ),
    )
    op.create_index("ix_projects_vendor_company_id", "projects", ["vendor_company_id"])
    op.create_index("ix_projects_client_company_id", "projects", ["client_company_id"])

    op.create_table(
        "service_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("quantity", sa.Numeric(precision=12, scale=5), nullable=False),
        sa.Column("uom", sa.String(length=10), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint(
            "uom IN ('hours', 'days', 'ea')", name="ck_service_lines_uom"
        ),
    )
    # Partial index: every query listing a project's service lines filters to
    # is_active = true (see docs/requirements/project.md#validation-rules-1).
    op.create_index(
        "ix_service_lines_project_id_active",
        "service_lines",
        ["project_id"],
        postgresql_where=sa.text("is_active"),
    )

    op.create_table(
        "service_line_consultants",
        sa.Column(
            "service_line_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("service_lines.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("service_line_consultants")
    op.drop_table("service_lines")
    op.drop_table("projects")
