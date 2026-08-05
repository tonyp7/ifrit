"""time_entries

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-05

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "time_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "service_line_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("service_lines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("time_entry", postgresql.INTERVAL(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "last_updated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint(
            "user_id",
            "service_line_id",
            "date",
            name="uq_time_entries_user_service_line_date",
        ),
        sa.CheckConstraint(
            "time_entry >= interval '0' AND time_entry <= interval '24:00:00'",
            name="ck_time_entries_time_entry_range",
        ),
    )
    op.create_index("ix_time_entries_user_id_date", "time_entries", ["user_id", "date"])


def downgrade() -> None:
    op.drop_table("time_entries")
