"""payee accounts: an account identifier no longer has to be unique on a company

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-29

Drops `uq_payee_accounts_identifier`, the unique index on `(company_id, account_identifier)`.
Some banks give every currency of an account the same number, and one number in one currency
can be offered as a wire transfer and as a SEPA credit transfer with different BICs, so what
tells two accounts of a company apart is open ended and no narrower key would hold. The
one-primary-per-currency index is unchanged: it is what picks an invoice's default account.

Only a constraint is loosened, so no data changes and the upgrade is safe on any installation.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("uq_payee_accounts_identifier", table_name="payee_accounts")


def downgrade() -> None:
    # The old index cannot be rebuilt while a company holds one identifier on two accounts.
    # Refuse rather than delete or merge rows, which would lose accounts silently.
    shared = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT count(*) FROM ("
                "SELECT 1 FROM payee_accounts "
                "GROUP BY company_id, account_identifier HAVING count(*) > 1"
                ") AS shared"
            )
        )
        .scalar_one()
    )
    if shared:
        raise RuntimeError(
            f"{shared} company account identifier(s) are used on more than one payee "
            "account: downgrading below 0004 would need them to be unique"
        )
    op.create_index(
        "uq_payee_accounts_identifier",
        "payee_accounts",
        ["company_id", "account_identifier"],
        unique=True,
    )
