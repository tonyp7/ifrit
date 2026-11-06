"""invoices: a Net 45 payment terms preset

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-06

Replaces `ck_invoices_payment_terms` with a check that also accepts `net_45`, the invoice date
plus 45 calendar days. Only a vocabulary is widened, so no data changes and the upgrade is safe on
any installation. `0003` created the check and stays as it was: a database that already ran it
reaches the new one only through this migration.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Spelled out here, not imported from the app, so this migration keeps meaning what it meant on
# the day it was written. tests/test_migrations.py compares `_PAYMENT_TERMS_CHECK` with the model's
# check, since `alembic check` does not compare CHECK constraints.
_BEFORE = (
    "due_on_receipt",
    "net_7",
    "net_15",
    "net_30",
    "net_60",
    "net_90",
    "eom",
    "eom_15",
    "eom_30",
    "eom_60",
    "eom_90",
)
_AFTER = (*_BEFORE[:4], "net_45", *_BEFORE[4:])


def _check(presets: Sequence[str]) -> str:
    quoted = ", ".join(f"'{preset}'" for preset in presets)
    return f"payment_terms IS NULL OR payment_terms IN ({quoted})"


_PAYMENT_TERMS_CHECK = _check(_AFTER)


def _replace_check(presets: Sequence[str]) -> None:
    op.drop_constraint("ck_invoices_payment_terms", "invoices", type_="check")
    op.create_check_constraint("ck_invoices_payment_terms", "invoices", _check(presets))


def upgrade() -> None:
    _replace_check(_AFTER)


def downgrade() -> None:
    # The older check would reject these rows, and giving them another preset would change what
    # an issued invoice's due date was worked out from. Refuse rather than rewrite them.
    net_45 = (
        op.get_bind()
        .execute(
            sa.text("SELECT count(*) FROM invoices WHERE payment_terms = 'net_45'")
        )
        .scalar_one()
    )
    if net_45:
        raise RuntimeError(
            f"{net_45} invoice(s) use the Net 45 payment terms: downgrading below 0005 "
            "would need them to use another preset"
        )
    _replace_check(_BEFORE)
