"""issuing and voiding invoices: the issue snapshot and audit columns

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-17

Nullable columns and two CHECKs on `invoices`. Every existing row is a draft with these
columns NULL, so the CHECKs hold as soon as they are added.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Kept as data so tests/test_migrations.py can compare them with the model's: `alembic check`
# does not compare CHECK constraints.
_ISSUED_FIELDS_CHECK = (
    "(status = 'draft' AND number IS NULL AND invoice_date IS NULL AND issued_at IS NULL"
    " AND currency_minor_unit IS NULL) OR (status <> 'draft' AND number IS NOT NULL"
    " AND invoice_date IS NOT NULL AND issued_at IS NOT NULL"
    " AND currency_minor_unit IS NOT NULL)"
)
_VOID_FIELDS_CHECK = "(status = 'void') = (voided_at IS NOT NULL) AND (void_reason IS NULL OR status = 'void')"


def upgrade() -> None:
    op.add_column("invoices", sa.Column("invoice_date", sa.Date(), nullable=True))
    op.add_column(
        "invoices", sa.Column("currency_minor_unit", sa.SmallInteger(), nullable=True)
    )
    op.add_column(
        "invoices", sa.Column("document_name", sa.String(length=60), nullable=True)
    )
    op.add_column(
        "invoices",
        sa.Column(
            "vendor_identifiers", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    op.add_column(
        "invoices",
        sa.Column(
            "client_identifiers", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )
    op.add_column(
        "invoices", sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("invoices", sa.Column("issued_by", sa.UUID(), nullable=True))
    op.add_column(
        "invoices", sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("invoices", sa.Column("voided_by", sa.UUID(), nullable=True))
    op.add_column(
        "invoices", sa.Column("void_reason", sa.String(length=500), nullable=True)
    )
    op.create_foreign_key(
        "invoices_issued_by_fkey",
        "invoices",
        "users",
        ["issued_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "invoices_voided_by_fkey",
        "invoices",
        "users",
        ["voided_by"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_invoices_issued_fields", "invoices", _ISSUED_FIELDS_CHECK
    )
    op.create_check_constraint(
        "ck_invoices_void_fields", "invoices", _VOID_FIELDS_CHECK
    )


def downgrade() -> None:
    # Going back would drop the numbers, dates and snapshots of issued invoices, records that
    # must be kept. Refuse rather than lose them.
    issued = (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM invoices WHERE status <> 'draft'"))
        .scalar_one()
    )
    if issued:
        raise RuntimeError(
            f"{issued} issued or void invoice(s) exist: downgrading below 0006 would lose them"
        )
    op.drop_constraint("ck_invoices_void_fields", "invoices", type_="check")
    op.drop_constraint("ck_invoices_issued_fields", "invoices", type_="check")
    op.drop_constraint("invoices_voided_by_fkey", "invoices", type_="foreignkey")
    op.drop_constraint("invoices_issued_by_fkey", "invoices", type_="foreignkey")
    for column in (
        "void_reason",
        "voided_by",
        "voided_at",
        "issued_by",
        "issued_at",
        "client_identifiers",
        "vendor_identifiers",
        "document_name",
        "currency_minor_unit",
        "invoice_date",
    ):
        op.drop_column("invoices", column)
