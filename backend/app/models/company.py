import uuid
from datetime import UTC, date, datetime
from typing import Literal, get_args

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

IdentifierType = Literal[
    "legal_registration", "vat", "peppol_participant", "duns", "gln", "internal"
]
AddressType = Literal["registered", "bill_to", "ship_to", "postal"]
# UNCL4461 payment means that pay into a bank account: 30 Credit transfer, 42 Payment to
# bank account, 58 SEPA credit transfer. Direct debit and card codes carry the buyer's
# account or card instead, so they have no place on the payee's side.
PaymentMeansCode = Literal["30", "42", "58"]
AccountScheme = Literal["iban", "other"]


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Every company is implicitly usable as a project's client; is_vendor additionally
    # marks it as selectable as a project's vendor.
    is_vendor: Mapped[bool] = mapped_column(default=False)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trading_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    legal_form: Mapped[str | None] = mapped_column(String(50), nullable=True)
    country_of_registration: Mapped[str] = mapped_column(String(2), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    identifiers: Mapped[list[PartyIdentifier]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    addresses: Mapped[list[Address]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    payee_accounts: Mapped[list[PayeeAccount]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class PartyIdentifier(Base):
    __tablename__ = "party_identifiers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Indexed: a company's identifiers/addresses are always read by its id, and the cascade
    # delete needs the index to find them.
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    id_type: Mapped[IdentifierType] = mapped_column(String(20), nullable=False)
    # Required (app-level) for legal_registration/peppol_participant: ISO 6523 ICD/EAS code.
    scheme_id: Mapped[str | None] = mapped_column(String(10), nullable=True)
    id_value: Mapped[str] = mapped_column(String(255), nullable=False)
    is_primary: Mapped[bool] = mapped_column(default=False)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    company: Mapped[Company] = relationship(back_populates="identifiers")

    __table_args__ = (
        CheckConstraint(
            "id_type IN ('legal_registration', 'vat', 'peppol_participant', 'duns', 'gln', "
            "'internal')",
            name="ck_party_identifiers_id_type",
        ),
        # A plain UniqueConstraint wouldn't catch this: SQL treats NULL as distinct from
        # NULL, and scheme_id is NULL for most id_types (e.g. `vat`), which would let
        # duplicate VAT numbers through. COALESCE to '' makes NULL comparable.
        Index(
            "uq_party_identifiers",
            "company_id",
            "id_type",
            func.coalesce(scheme_id, ""),
            "id_value",
            unique=True,
        ),
    )


class Address(Base):
    __tablename__ = "addresses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Indexed: a company's identifiers/addresses are always read by its id, and the cascade
    # delete needs the index to find them.
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    address_type: Mapped[AddressType] = mapped_column(String(15), nullable=False)
    line1: Mapped[str] = mapped_column(String(255), nullable=False)
    line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    line3: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str] = mapped_column(String(255), nullable=False)
    postal_zone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country_subdivision: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    is_primary: Mapped[bool] = mapped_column(default=False)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    company: Mapped[Company] = relationship(back_populates="addresses")

    __table_args__ = (
        CheckConstraint(
            "address_type IN ('registered', 'bill_to', 'ship_to', 'postal')",
            name="ck_addresses_address_type",
        ),
        # At most one primary address per (company_id, address_type). Defense in depth:
        # the API layer checks this proactively for a clean error message, this index is
        # the DB-level backstop (also closes the race between two concurrent requests).
        Index(
            "uq_addresses_primary_per_type",
            "company_id",
            "address_type",
            unique=True,
            postgresql_where=is_primary.is_(True),
        ),
    )


# Every bank address column: either line 1, city and country are all set, or none of
# these is. The migration spells the same check out on its own (a migration must not
# import the models it predates); a test compares the two.
BANK_ADDRESS_COLUMNS = (
    "bank_line1",
    "bank_line2",
    "bank_line3",
    "bank_city",
    "bank_postal_zone",
    "bank_country_subdivision",
    "bank_country_code",
)
BANK_ADDRESS_CHECK = (
    "(bank_line1 IS NOT NULL AND bank_city IS NOT NULL AND bank_country_code IS NOT NULL)"
    " OR (" + " AND ".join(f"{column} IS NULL" for column in BANK_ADDRESS_COLUMNS) + ")"
)


class PayeeAccount(Base):
    """A bank account a company is paid into, as an invoice would print it.

    The bank's address is stored inline rather than as an `addresses` row: it belongs to
    the bank, not to the company, so it must not show up among the company's own
    addresses or take part in their one-primary-per-type rule.
    """

    __tablename__ = "payee_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    payment_means_code: Mapped[PaymentMeansCode] = mapped_column(
        String(3), nullable=False
    )
    account_scheme: Mapped[AccountScheme] = mapped_column(String(10), nullable=False)
    # Stored normalized (an IBAN compact and upper case) so the unique index below compares
    # what the user meant, not how it was typed. 64 leaves room for national formats; an
    # IBAN is at most 34.
    account_identifier: Mapped[str] = mapped_column(String(64), nullable=False)
    account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("currencies.alpha_code"), nullable=False
    )
    bic: Mapped[str | None] = mapped_column(String(11), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bank_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bank_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bank_line3: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bank_city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bank_postal_zone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bank_country_subdivision: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    bank_country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    is_primary: Mapped[bool] = mapped_column(default=False)

    company: Mapped[Company] = relationship(back_populates="payee_accounts")

    __table_args__ = (
        CheckConstraint(
            "payment_means_code IN ("
            + ", ".join(f"'{code}'" for code in get_args(PaymentMeansCode))
            + ")",
            name="ck_payee_accounts_payment_means_code",
        ),
        CheckConstraint(
            "account_scheme IN ("
            + ", ".join(f"'{scheme}'" for scheme in get_args(AccountScheme))
            + ")",
            name="ck_payee_accounts_account_scheme",
        ),
        # A SEPA credit transfer is addressed by IBAN by definition.
        CheckConstraint(
            "payment_means_code <> '58' OR account_scheme = 'iban'",
            name="ck_payee_accounts_sepa_iban",
        ),
        CheckConstraint(BANK_ADDRESS_CHECK, name="ck_payee_accounts_bank_address"),
        Index(
            "uq_payee_accounts_identifier",
            "company_id",
            "account_identifier",
            unique=True,
        ),
        # At most one primary account per currency: it is the one an invoice in that
        # currency would default to. The API checks first for a clear message; this is the
        # backstop for two concurrent requests.
        Index(
            "uq_payee_accounts_primary_per_currency",
            "company_id",
            "currency_code",
            unique=True,
            postgresql_where=is_primary.is_(True),
        ),
    )
