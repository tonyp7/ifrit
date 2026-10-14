"""merge the project roles into manager; add billing milestones, project references and
payee accounts

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-12

Four unreleased changes, folded into one revision before they ship:

- project_admin and project_manager become one `manager` role. The two roles always went to
  the same people, and project_admin could list itself as manager of any project, so the
  per-project scope of project_manager protected nothing. Project manager assignments are
  left untouched: they still say who manages which project, they just no longer gate anything.
- The `billing_milestones` table: the agreed billing installments of a Fixed Price project.
  New table only, no existing data to migrate.
- The `project_references` table: the values a buyer expects on invoices for a project (a
  purchase order number, a contract ID). New table only, no existing data to migrate.
- The `payee_accounts` table: the bank accounts a company is paid into, as an invoice would
  print them. New table only, no existing data to migrate.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Ids seeded by 0001.
_PROJECT_ADMIN_ID = "00000000-0000-0000-0000-000000000002"
_PROJECT_MANAGER_ID = "00000000-0000-0000-0000-000000000004"


def upgrade() -> None:
    _merge_project_roles()
    _create_billing_milestones()
    _create_project_references()
    _create_payee_accounts()


def downgrade() -> None:
    _drop_payee_accounts()
    _drop_project_references()
    _drop_billing_milestones()
    _split_manager_role()


def _merge_project_roles() -> None:
    # Renaming (rather than inserting a new row) keeps every project_admin holder's
    # user_roles row as is.
    op.execute(f"UPDATE roles SET name = 'manager' WHERE id = '{_PROJECT_ADMIN_ID}'")
    op.execute(
        f"""
        INSERT INTO user_roles (user_id, role_id)
        SELECT user_id, '{_PROJECT_ADMIN_ID}' FROM user_roles
        WHERE role_id = '{_PROJECT_MANAGER_ID}'
        ON CONFLICT DO NOTHING
        """
    )
    # user_roles.role_id cascades, so the old project_manager rows go with it.
    op.execute(f"DELETE FROM roles WHERE id = '{_PROJECT_MANAGER_ID}'")


def _split_manager_role() -> None:
    # Who held which of the two roles is gone, so every manager gets both: the closest
    # pre-merge state to what they could actually do, so a rollback takes no access away.
    op.execute(
        f"UPDATE roles SET name = 'project_admin' WHERE id = '{_PROJECT_ADMIN_ID}'"
    )
    op.execute(
        f"INSERT INTO roles (id, name) VALUES ('{_PROJECT_MANAGER_ID}', 'project_manager')"
    )
    op.execute(
        f"""
        INSERT INTO user_roles (user_id, role_id)
        SELECT user_id, '{_PROJECT_MANAGER_ID}' FROM user_roles
        WHERE role_id = '{_PROJECT_ADMIN_ID}'
        """
    )


def _create_billing_milestones() -> None:
    op.create_table(
        "billing_milestones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("value", sa.Numeric(precision=14, scale=4), nullable=False),
        # Ordering key only, deliberately not unique per project: a reorder renumbers
        # every milestone of the project in one statement, which a unique constraint
        # would reject mid-update.
        sa.Column("position", sa.Integer(), nullable=False),
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
        sa.CheckConstraint("value >= 0", name="ck_billing_milestones_value"),
    )
    op.create_index(
        "ix_billing_milestones_project_id_position",
        "billing_milestones",
        ["project_id", "position"],
    )


def _drop_billing_milestones() -> None:
    op.drop_index(
        "ix_billing_milestones_project_id_position", table_name="billing_milestones"
    )
    op.drop_table("billing_milestones")


_REFERENCE_KINDS = (
    "purchase_order",
    "sales_order",
    "contract",
    "buyer_reference",
    "accounting_reference",
    "project_reference",
    "document_reference",
    "custom",
)


def _create_project_references() -> None:
    kinds = ", ".join(f"'{kind}'" for kind in _REFERENCE_KINDS)
    op.create_table(
        "project_references",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=True),
        sa.Column("value", sa.String(length=255), nullable=False),
        # Entry order, rewritten 0..n-1 on every save, so deliberately not unique.
        sa.Column("position", sa.Integer(), nullable=False),
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
        sa.CheckConstraint(f"kind IN ({kinds})", name="ck_project_references_kind"),
        sa.CheckConstraint(
            "(kind = 'custom') = (label IS NOT NULL)",
            name="ck_project_references_label",
        ),
    )
    op.create_index(
        "ix_project_references_project_id_position",
        "project_references",
        ["project_id", "position"],
    )
    # Case-insensitive on purpose: PO-17 and po-17 are one number typed twice.
    op.create_index(
        "uq_project_references_project_kind_label_value",
        "project_references",
        [
            "project_id",
            "kind",
            sa.text("lower(COALESCE(label, ''))"),
            sa.text("lower(value)"),
        ],
        unique=True,
    )


def _drop_project_references() -> None:
    op.drop_index(
        "uq_project_references_project_kind_label_value",
        table_name="project_references",
    )
    op.drop_index(
        "ix_project_references_project_id_position", table_name="project_references"
    )
    op.drop_table("project_references")


_PAYMENT_MEANS_CODES = ("30", "42", "58")
_ACCOUNT_SCHEMES = ("iban", "other")
_BANK_ADDRESS_COLUMNS = (
    "bank_line1",
    "bank_line2",
    "bank_line3",
    "bank_city",
    "bank_postal_zone",
    "bank_country_subdivision",
    "bank_country_code",
)
# Either the address is usable (line 1, city and country) or it is absent altogether.
_BANK_ADDRESS_CHECK = (
    "(bank_line1 IS NOT NULL AND bank_city IS NOT NULL AND bank_country_code IS NOT NULL)"
    " OR ("
    + " AND ".join(f"{column} IS NULL" for column in _BANK_ADDRESS_COLUMNS)
    + ")"
)


def _create_payee_accounts() -> None:
    codes = ", ".join(f"'{code}'" for code in _PAYMENT_MEANS_CODES)
    schemes = ", ".join(f"'{scheme}'" for scheme in _ACCOUNT_SCHEMES)
    op.create_table(
        "payee_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("payment_means_code", sa.String(length=3), nullable=False),
        sa.Column("account_scheme", sa.String(length=10), nullable=False),
        sa.Column("account_identifier", sa.String(length=64), nullable=False),
        sa.Column("account_name", sa.String(length=255), nullable=True),
        sa.Column(
            "currency_code",
            sa.String(length=3),
            sa.ForeignKey("currencies.alpha_code"),
            nullable=False,
        ),
        sa.Column("bic", sa.String(length=11), nullable=True),
        sa.Column("bank_name", sa.String(length=255), nullable=True),
        sa.Column("bank_line1", sa.String(length=255), nullable=True),
        sa.Column("bank_line2", sa.String(length=255), nullable=True),
        sa.Column("bank_line3", sa.String(length=255), nullable=True),
        sa.Column("bank_city", sa.String(length=255), nullable=True),
        sa.Column("bank_postal_zone", sa.String(length=20), nullable=True),
        sa.Column("bank_country_subdivision", sa.String(length=100), nullable=True),
        sa.Column("bank_country_code", sa.String(length=2), nullable=True),
        sa.Column(
            "is_primary", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.CheckConstraint(
            f"payment_means_code IN ({codes})",
            name="ck_payee_accounts_payment_means_code",
        ),
        sa.CheckConstraint(
            f"account_scheme IN ({schemes})", name="ck_payee_accounts_account_scheme"
        ),
        sa.CheckConstraint(
            "payment_means_code <> '58' OR account_scheme = 'iban'",
            name="ck_payee_accounts_sepa_iban",
        ),
        sa.CheckConstraint(_BANK_ADDRESS_CHECK, name="ck_payee_accounts_bank_address"),
    )
    op.create_index("ix_payee_accounts_company_id", "payee_accounts", ["company_id"])
    op.create_index(
        "uq_payee_accounts_identifier",
        "payee_accounts",
        ["company_id", "account_identifier"],
        unique=True,
    )
    op.create_index(
        "uq_payee_accounts_primary_per_currency",
        "payee_accounts",
        ["company_id", "currency_code"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )


def _drop_payee_accounts() -> None:
    op.drop_index("uq_payee_accounts_primary_per_currency", table_name="payee_accounts")
    op.drop_index("uq_payee_accounts_identifier", table_name="payee_accounts")
    op.drop_index("ix_payee_accounts_company_id", table_name="payee_accounts")
    op.drop_table("payee_accounts")
