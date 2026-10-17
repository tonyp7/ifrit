"""invoices, their lines and their references

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-17

Three new tables, no existing data to migrate. Parties, payee account details, references and
lines are copies stored on the invoice, so the only links out are the project, the currency
and the creating user.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Kept as data, not inline in create_table, so tests/test_migrations.py can compare them with
# the models': `alembic check` does not compare CHECK constraints.
_INVOICE_CHECKS = {
    "ck_invoices_payee_account_scheme": (
        "payee_account_scheme IS NULL OR payee_account_scheme IN ('iban', 'other')"
    ),
    "ck_invoices_payee_sepa_iban": (
        "payee_payment_means_code IS NULL OR payee_payment_means_code <> '58' OR payee_account_scheme = 'iban'"
    ),
    "ck_invoices_payee_payment_means_code": (
        "payee_payment_means_code IS NULL OR payee_payment_means_code IN ('30', '42', '58')"
    ),
    "ck_invoices_payment_terms": (
        "payment_terms IS NULL OR payment_terms IN ('due_on_receipt', 'net_7', 'net_15', 'net_30', 'net_60', 'net_90', 'eom', 'eom_15', 'eom_30', 'eom_60', 'eom_90')"
    ),
    "ck_invoices_due": (
        "status <> 'draft' OR payment_terms IS NULL OR due_date IS NULL"
    ),
    "ck_invoices_status": ("status IN ('draft', 'issued', 'void')"),
    "ck_invoices_bill_from_address": (
        "(bill_from_line1 IS NOT NULL AND bill_from_city IS NOT NULL AND bill_from_country_code IS NOT NULL) OR (bill_from_line1 IS NULL AND bill_from_line2 IS NULL AND bill_from_line3 IS NULL AND bill_from_city IS NULL AND bill_from_postal_zone IS NULL AND bill_from_country_subdivision IS NULL AND bill_from_country_code IS NULL)"
    ),
    "ck_invoices_bill_to_address": (
        "(bill_to_line1 IS NOT NULL AND bill_to_city IS NOT NULL AND bill_to_country_code IS NOT NULL) OR (bill_to_line1 IS NULL AND bill_to_line2 IS NULL AND bill_to_line3 IS NULL AND bill_to_city IS NULL AND bill_to_postal_zone IS NULL AND bill_to_country_subdivision IS NULL AND bill_to_country_code IS NULL)"
    ),
    "ck_invoices_payee_bank_address": (
        "(payee_bank_line1 IS NOT NULL AND payee_bank_city IS NOT NULL AND payee_bank_country_code IS NOT NULL) OR (payee_bank_line1 IS NULL AND payee_bank_line2 IS NULL AND payee_bank_line3 IS NULL AND payee_bank_city IS NULL AND payee_bank_postal_zone IS NULL AND payee_bank_country_subdivision IS NULL AND payee_bank_country_code IS NULL)"
    ),
    "ck_invoices_payee": (
        "(payee_payment_means_code IS NOT NULL AND payee_account_scheme IS NOT NULL AND payee_account_identifier IS NOT NULL AND payee_currency_code IS NOT NULL) OR (payee_payment_means_code IS NULL AND payee_account_scheme IS NULL AND payee_account_identifier IS NULL AND payee_account_name IS NULL AND payee_currency_code IS NULL AND payee_bic IS NULL AND payee_bank_name IS NULL AND payee_bank_line1 IS NULL AND payee_bank_line2 IS NULL AND payee_bank_line3 IS NULL AND payee_bank_city IS NULL AND payee_bank_postal_zone IS NULL AND payee_bank_country_subdivision IS NULL AND payee_bank_country_code IS NULL)"
    ),
    "ck_invoices_period": (
        "(period_start IS NULL AND period_end IS NULL) OR (period_start IS NOT NULL AND period_end IS NOT NULL AND period_start <= period_end)"
    ),
}

_LINE_CHECKS = {
    "ck_invoice_lines_uom": ("uom IN ('hours', 'days', 'ea')"),
    "ck_invoice_lines_quantity": ("quantity >= 0"),
}

_REFERENCE_CHECKS = {
    "ck_invoice_references_label": ("(kind = 'custom') = (label IS NOT NULL)"),
    "ck_invoice_references_kind": (
        "kind IN ('purchase_order', 'sales_order', 'contract', 'buyer_reference', 'accounting_reference', 'project_reference', 'document_reference', 'custom')"
    ),
}


def _checks(checks: dict[str, str]) -> list[sa.CheckConstraint]:
    return [sa.CheckConstraint(sql, name=name) for name, sql in checks.items()]


def upgrade() -> None:
    op.create_table(
        "invoices",
        *_checks(_INVOICE_CHECKS),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "status", sa.String(length=10), server_default="draft", nullable=False
        ),
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("bill_from_name", sa.String(length=255), nullable=False),
        sa.Column("bill_from_line1", sa.String(length=255), nullable=True),
        sa.Column("bill_from_line2", sa.String(length=255), nullable=True),
        sa.Column("bill_from_line3", sa.String(length=255), nullable=True),
        sa.Column("bill_from_city", sa.String(length=255), nullable=True),
        sa.Column("bill_from_postal_zone", sa.String(length=20), nullable=True),
        sa.Column(
            "bill_from_country_subdivision", sa.String(length=100), nullable=True
        ),
        sa.Column("bill_from_country_code", sa.String(length=2), nullable=True),
        sa.Column("bill_to_name", sa.String(length=255), nullable=False),
        sa.Column("bill_to_line1", sa.String(length=255), nullable=True),
        sa.Column("bill_to_line2", sa.String(length=255), nullable=True),
        sa.Column("bill_to_line3", sa.String(length=255), nullable=True),
        sa.Column("bill_to_city", sa.String(length=255), nullable=True),
        sa.Column("bill_to_postal_zone", sa.String(length=20), nullable=True),
        sa.Column("bill_to_country_subdivision", sa.String(length=100), nullable=True),
        sa.Column("bill_to_country_code", sa.String(length=2), nullable=True),
        sa.Column("period_start", sa.Date(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=True),
        sa.Column("payment_terms", sa.String(length=20), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("payee_payment_means_code", sa.String(length=3), nullable=True),
        sa.Column("payee_account_scheme", sa.String(length=10), nullable=True),
        sa.Column("payee_account_identifier", sa.String(length=64), nullable=True),
        sa.Column("payee_account_name", sa.String(length=255), nullable=True),
        sa.Column("payee_currency_code", sa.String(length=3), nullable=True),
        sa.Column("payee_bic", sa.String(length=11), nullable=True),
        sa.Column("payee_bank_name", sa.String(length=255), nullable=True),
        sa.Column("payee_bank_line1", sa.String(length=255), nullable=True),
        sa.Column("payee_bank_line2", sa.String(length=255), nullable=True),
        sa.Column("payee_bank_line3", sa.String(length=255), nullable=True),
        sa.Column("payee_bank_city", sa.String(length=255), nullable=True),
        sa.Column("payee_bank_postal_zone", sa.String(length=20), nullable=True),
        sa.Column(
            "payee_bank_country_subdivision", sa.String(length=100), nullable=True
        ),
        sa.Column("payee_bank_country_code", sa.String(length=2), nullable=True),
        sa.Column("subtotal", sa.Numeric(precision=22, scale=4), nullable=False),
        sa.Column("total", sa.Numeric(precision=22, scale=4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["currency_code"],
            ["currencies.alpha_code"],
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_invoices_project_id_status",
        "invoices",
        ["project_id", "status"],
        unique=False,
    )
    op.create_table(
        "invoice_lines",
        *_checks(_LINE_CHECKS),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("invoice_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=12, scale=5), nullable=False),
        sa.Column("uom", sa.String(length=10), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=14, scale=4), nullable=False),
        sa.Column("amount", sa.Numeric(precision=22, scale=4), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_invoice_lines_invoice_id_position",
        "invoice_lines",
        ["invoice_id", "position"],
        unique=False,
    )
    op.create_table(
        "invoice_references",
        *_checks(_REFERENCE_CHECKS),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("invoice_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=True),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_invoice_references_invoice_id_position",
        "invoice_references",
        ["invoice_id", "position"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_invoice_references_invoice_id_position", table_name="invoice_references"
    )
    op.drop_table("invoice_references")
    op.drop_index("ix_invoice_lines_invoice_id_position", table_name="invoice_lines")
    op.drop_table("invoice_lines")
    op.drop_index("ix_invoices_project_id_status", table_name="invoices")
    op.drop_table("invoices")
