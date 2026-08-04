"""service_lines: add optional name column

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-02

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "service_lines", sa.Column("name", sa.String(length=255), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("service_lines", "name")
