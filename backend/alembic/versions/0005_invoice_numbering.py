"""invoice numbering: the format, its counters and the invoice number

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-17

Two new tables and a nullable column, no existing data to migrate. With no format row the
application uses its default format, so nothing is seeded.
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
        "invoice_number_counters",
        sa.Column("series", sa.String(length=20), nullable=False),
        sa.Column("period_key", sa.String(length=10), nullable=False),
        sa.Column("last_value", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "last_value >= -1", name="ck_invoice_number_counters_last_value"
        ),
        sa.PrimaryKeyConstraint("series", "period_key"),
    )
    op.create_table(
        "invoice_numbering_formats",
        sa.Column("series", sa.String(length=20), nullable=False),
        sa.Column("tokens", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "jsonb_typeof(tokens) = 'array'", name="ck_invoice_numbering_formats_tokens"
        ),
        sa.CheckConstraint(
            "series = 'invoice'", name="ck_invoice_numbering_formats_series"
        ),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("series"),
    )
    op.add_column("invoices", sa.Column("number", sa.String(length=100), nullable=True))
    op.create_index(
        "uq_invoices_number",
        "invoices",
        ["number"],
        unique=True,
        postgresql_where=sa.text("number IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_invoices_number", table_name="invoices")
    op.drop_column("invoices", "number")
    op.drop_table("invoice_numbering_formats")
    op.drop_table("invoice_number_counters")
