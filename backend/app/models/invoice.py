import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Literal, get_args

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.company import AccountScheme, PaymentMeansCode
from app.models.project import ReferenceKind, Uom

if TYPE_CHECKING:
    from app.models.project import Project

InvoiceStatus = Literal["draft", "issued", "void"]
# A due date is either picked by hand or worked out from one of these at issue, from the
# invoice date: `net_<n>` adds n calendar days, `eom` is the last day of the invoice date's
# month and `eom_<n>` adds n days to that.
PaymentTerms = Literal[
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
]

# The postal fields of a party and of the payee's bank, in the same widths as `addresses`
# and `payee_accounts.bank_*`, so a company's address always fits when copied in.
_ADDRESS_FIELDS: tuple[tuple[str, int], ...] = (
    ("line1", 255),
    ("line2", 255),
    ("line3", 255),
    ("city", 255),
    ("postal_zone", 20),
    ("country_subdivision", 100),
    ("country_code", 2),
)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN (" + ", ".join(f"'{value}'" for value in values) + ")"


def _address_check(prefix: str) -> str:
    """Either a usable address (first line, city and country) or no address at all, so a
    half-filled one can never be stored."""
    columns = [f"{prefix}_{name}" for name, _ in _ADDRESS_FIELDS]
    return (
        f"({prefix}_line1 IS NOT NULL AND {prefix}_city IS NOT NULL"
        f" AND {prefix}_country_code IS NOT NULL)"
        " OR (" + " AND ".join(f"{column} IS NULL" for column in columns) + ")"
    )


# Every payee column other than the bank address, which has its own all-or-nothing check.
PAYEE_COLUMNS = (
    "payee_payment_means_code",
    "payee_account_scheme",
    "payee_account_identifier",
    "payee_account_name",
    "payee_currency_code",
    "payee_bic",
    "payee_bank_name",
)
PAYEE_BANK_ADDRESS_COLUMNS = tuple(f"payee_bank_{name}" for name, _ in _ADDRESS_FIELDS)
_PAYEE_REQUIRED = (
    "payee_payment_means_code",
    "payee_account_scheme",
    "payee_account_identifier",
    "payee_currency_code",
)
PAYEE_CHECK = (
    "("
    + " AND ".join(f"{c} IS NOT NULL" for c in _PAYEE_REQUIRED)
    + ") OR ("
    + " AND ".join(f"{c} IS NULL" for c in PAYEE_COLUMNS + PAYEE_BANK_ADDRESS_COLUMNS)
    + ")"
)


class Invoice(Base):
    """An invoice for one project.

    The parties, the payee account details, the references and the lines are all copies
    stored on the invoice, never links to the companies, accounts, service lines or
    milestones they came from: those keep changing after an invoice is sent, and an invoice
    has to keep showing what it said. Only the project is linked, so a draft can be picked
    up later and its lines generated again.
    """

    __tablename__ = "invoices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    status: Mapped[InvoiceStatus] = mapped_column(
        String(10), nullable=False, default="draft", server_default="draft"
    )
    # RESTRICT: projects are only ever deactivated by the app, so this never fires there,
    # but it stops a manual delete from taking an invoice's project out from under it.
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Always the project's invoicing currency while the invoice is a draft.
    currency_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.alpha_code"), nullable=False
    )

    bill_from_name: Mapped[str] = mapped_column(String(255), nullable=False)
    bill_from_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bill_from_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bill_from_line3: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bill_from_city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bill_from_postal_zone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bill_from_country_subdivision: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    bill_from_country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)

    bill_to_name: Mapped[str] = mapped_column(String(255), nullable=False)
    bill_to_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bill_to_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bill_to_line3: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bill_to_city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bill_to_postal_zone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bill_to_country_subdivision: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    bill_to_country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)

    # Time & Material only: the days whose hours the lines were generated from.
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_terms: Mapped[PaymentTerms | None] = mapped_column(
        String(20), nullable=True
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # The account the invoice asks to be paid into, copied from one of the vendor's payee
    # accounts (or typed in) with no link back to it, so editing or deleting the company's
    # account never changes an invoice. The currency has no foreign key either, so the copy
    # depends on nothing.
    payee_payment_means_code: Mapped[PaymentMeansCode | None] = mapped_column(
        String(3), nullable=True
    )
    payee_account_scheme: Mapped[AccountScheme | None] = mapped_column(
        String(10), nullable=True
    )
    payee_account_identifier: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    payee_account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payee_currency_code: Mapped[str | None] = mapped_column(String(3), nullable=True)
    payee_bic: Mapped[str | None] = mapped_column(String(11), nullable=True)
    payee_bank_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payee_bank_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payee_bank_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payee_bank_line3: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payee_bank_city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payee_bank_postal_zone: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    payee_bank_country_subdivision: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    payee_bank_country_code: Mapped[str | None] = mapped_column(
        String(2), nullable=True
    )

    # Derived from the lines, but stored: the list sorts by total in the database. The
    # service recomputes both on every write, in the same transaction as the lines.
    subtotal: Mapped[Decimal] = mapped_column(Numeric(22, 4), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(22, 4), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    # Who created it, not whose it is: deleting that user never deletes an invoice.
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    project: Mapped[Project] = relationship()
    lines: Mapped[list[InvoiceLine]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoiceLine.position",
        passive_deletes=True,
    )
    references: Mapped[list[InvoiceReference]] = relationship(
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by="InvoiceReference.position",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint(
            _in_list("status", get_args(InvoiceStatus)), name="ck_invoices_status"
        ),
        CheckConstraint(
            _address_check("bill_from"), name="ck_invoices_bill_from_address"
        ),
        CheckConstraint(_address_check("bill_to"), name="ck_invoices_bill_to_address"),
        CheckConstraint(
            "(period_start IS NULL AND period_end IS NULL)"
            " OR (period_start IS NOT NULL AND period_end IS NOT NULL"
            " AND period_start <= period_end)",
            name="ck_invoices_period",
        ),
        CheckConstraint(
            "payment_terms IS NULL OR "
            + _in_list("payment_terms", get_args(PaymentTerms)),
            name="ck_invoices_payment_terms",
        ),
        # A draft has a preset or a fixed date, never both. An issued invoice keeps the
        # preset next to the date worked out from it.
        CheckConstraint(
            "status <> 'draft' OR payment_terms IS NULL OR due_date IS NULL",
            name="ck_invoices_due",
        ),
        CheckConstraint(
            "payee_payment_means_code IS NULL OR "
            + _in_list("payee_payment_means_code", get_args(PaymentMeansCode)),
            name="ck_invoices_payee_payment_means_code",
        ),
        CheckConstraint(
            "payee_account_scheme IS NULL OR "
            + _in_list("payee_account_scheme", get_args(AccountScheme)),
            name="ck_invoices_payee_account_scheme",
        ),
        CheckConstraint(PAYEE_CHECK, name="ck_invoices_payee"),
        # A SEPA credit transfer is addressed by IBAN by definition.
        CheckConstraint(
            "payee_payment_means_code IS NULL OR payee_payment_means_code <> '58'"
            " OR payee_account_scheme = 'iban'",
            name="ck_invoices_payee_sepa_iban",
        ),
        CheckConstraint(
            _address_check("payee_bank"), name="ck_invoices_payee_bank_address"
        ),
        Index("ix_invoices_project_id_status", "project_id", "status"),
    )


class InvoiceLine(Base):
    """One line of an invoice: a plain description, quantity, unit and price, whether it
    was generated or typed in."""

    __tablename__ = "invoice_lines"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Display order. Rewritten 0..n-1 on every save, so not unique per invoice.
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    # Zero is allowed (a generated `Each` line waiting for its quantity); it is warned
    # about, not refused.
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 5), nullable=False)
    uom: Mapped[Uom] = mapped_column(String(10), nullable=False)
    # May be negative: that is how a discount or a correction is written.
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(22, 4), nullable=False)

    invoice: Mapped[Invoice] = relationship(back_populates="lines")

    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_invoice_lines_quantity"),
        CheckConstraint(_in_list("uom", get_args(Uom)), name="ck_invoice_lines_uom"),
        Index("ix_invoice_lines_invoice_id_position", "invoice_id", "position"),
    )


class InvoiceReference(Base):
    """A reference printed on an invoice (purchase order, contract...), copied from the
    project when the draft was started and editable on the invoice without touching the
    project."""

    __tablename__ = "invoice_references"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[ReferenceKind] = mapped_column(String(30), nullable=False)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)

    invoice: Mapped[Invoice] = relationship(back_populates="references")

    __table_args__ = (
        CheckConstraint(
            _in_list("kind", get_args(ReferenceKind)), name="ck_invoice_references_kind"
        ),
        CheckConstraint(
            "(kind = 'custom') = (label IS NOT NULL)",
            name="ck_invoice_references_label",
        ),
        Index("ix_invoice_references_invoice_id_position", "invoice_id", "position"),
    )
