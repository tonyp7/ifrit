import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

# Only invoices are numbered today. The series is a key of its own so another document type
# (a credit note, say) can get its own format and counters later without a schema change.
INVOICE_SERIES = "invoice"


class InvoiceNumberingFormat(Base):
    """How issued invoices are numbered: an ordered list of tokens (text, year, month, day
    and one sequence). A series with no row uses the application's default format."""

    __tablename__ = "invoice_numbering_formats"

    series: Mapped[str] = mapped_column(String(20), primary_key=True)
    # Always read and replaced whole, so it is one value rather than child rows.
    tokens: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    # Who last changed the format, not whose it is.
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(
            f"series = '{INVOICE_SERIES}'", name="ck_invoice_numbering_formats_series"
        ),
        CheckConstraint(
            "jsonb_typeof(tokens) = 'array'", name="ck_invoice_numbering_formats_tokens"
        ),
    )


class InvoiceNumberCounter(Base):
    """The last sequence value handed out in one restart period of a series: `all` for a
    sequence that never restarts, else the year, month or day (`2026`, `2026-10`,
    `2026-10-14`)."""

    __tablename__ = "invoice_number_counters"

    series: Mapped[str] = mapped_column(String(20), primary_key=True)
    period_key: Mapped[str] = mapped_column(String(10), primary_key=True)
    # -1 lets "the next number is 0" be stored as a last value.
    last_value: Mapped[int] = mapped_column(BigInteger, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "last_value >= -1", name="ck_invoice_number_counters_last_value"
        ),
    )
