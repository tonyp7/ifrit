import uuid
from datetime import UTC, date, datetime
from typing import Literal

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


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Every company is implicitly usable as a project's client; is_vendor additionally
    # marks it as selectable as a project's vendor (see specs/requirements/company.md).
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

    identifiers: Mapped[list["PartyIdentifier"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    addresses: Mapped[list["Address"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class PartyIdentifier(Base):
    __tablename__ = "party_identifiers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    id_type: Mapped[IdentifierType] = mapped_column(String(20), nullable=False)
    # Required (app-level) for legal_registration/peppol_participant — ISO 6523 ICD/EAS code.
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
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
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
        # At most one primary address per (company_id, address_type) — see
        # specs/requirements/company.md §3 Validation rules. Defense in depth: the API
        # layer checks this proactively for a clean error message, this index is the
        # DB-level backstop (also closes the race between two concurrent requests).
        Index(
            "uq_addresses_primary_per_type",
            "company_id",
            "address_type",
            unique=True,
            postgresql_where=is_primary.is_(True),
        ),
    )
