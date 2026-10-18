import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import server_today
from app.models.invoice import Invoice
from app.models.invoice_numbering import (
    INVOICE_SERIES,
    InvoiceNumberCounter,
    InvoiceNumberingFormat,
)
from app.schemas.invoice_numbering import (
    NumberingFormat,
    NumberingState,
    Restart,
    SequenceToken,
    TextToken,
)

PREVIEW_SIZE = 3

# What a new installation numbers invoices with: INV-2026-0001, restarting every year.
DEFAULT_FORMAT = NumberingFormat.model_validate(
    {
        "tokens": [
            {"type": "text", "value": "INV-"},
            {"type": "year"},
            {"type": "text", "value": "-"},
            {"type": "sequence", "digits": 4, "start_at": 1, "restart": "yearly"},
        ]
    }
)


class NumberCollisionError(Exception):
    """The number a value would render to already belongs to an invoice."""

    def __init__(self, number: str) -> None:
        super().__init__(number)
        self.number = number


class UnconfirmedFormatChangeError(Exception):
    """The format was replaced after invoices were issued, without confirming it."""


def period_key(restart: Restart, day: date) -> str:
    """Which counter a value is taken from: one for good, or one per year, month or day."""
    match restart:
        case "never":
            return "all"
        case "yearly":
            return f"{day:%Y}"
        case "monthly":
            return f"{day:%Y-%m}"
        case "daily":
            return f"{day:%Y-%m-%d}"


def render(fmt: NumberingFormat, value: int, day: date) -> str:
    """The number for sequence `value` on `day`. A value wider than its digits is written
    in full, never truncated: a cut number would collide with an earlier one."""
    parts: list[str] = []
    for token in fmt.tokens:
        match token:
            case TextToken(value=text):
                parts.append(text)
            case SequenceToken(digits=digits):
                parts.append(str(value).zfill(digits))
            case _ if token.type == "year":
                parts.append(f"{day:%Y}")
            case _ if token.type == "month":
                parts.append(f"{day:%m}")
            case _:
                parts.append(f"{day:%d}")
    return "".join(parts)


async def get_format(db: AsyncSession) -> NumberingFormat:
    row = await db.get(InvoiceNumberingFormat, INVOICE_SERIES)
    return (
        DEFAULT_FORMAT
        if row is None
        else NumberingFormat.model_validate({"tokens": row.tokens})
    )


async def peek_next(db: AsyncSession, fmt: NumberingFormat, day: date) -> int:
    """The value the next take would return on `day`, without taking it."""
    sequence = fmt.sequence
    counter = await db.get(
        InvoiceNumberCounter, (INVOICE_SERIES, period_key(sequence.restart, day))
    )
    return sequence.start_at if counter is None else counter.last_value + 1


async def take_next_number(db: AsyncSession, day: date) -> tuple[int, str]:
    """Takes the next value for `day` and renders it. One atomic upsert: two concurrent
    calls never get the same value, and a rolled-back transaction gives its value back.
    Meant to run inside the transaction that stores the number."""
    fmt = await get_format(db)
    sequence = fmt.sequence
    statement = insert(InvoiceNumberCounter).values(
        series=INVOICE_SERIES,
        period_key=period_key(sequence.restart, day),
        last_value=sequence.start_at,
    )
    statement = statement.on_conflict_do_update(
        index_elements=["series", "period_key"],
        set_={"last_value": InvoiceNumberCounter.last_value + 1},
    ).returning(InvoiceNumberCounter.last_value)
    value = (await db.execute(statement)).scalar_one()
    return value, render(fmt, value, day)


async def _number_exists(db: AsyncSession, number: str) -> bool:
    found = await db.execute(
        select(Invoice.id).where(Invoice.number == number).limit(1)
    )
    return found.first() is not None


async def has_issued(db: AsyncSession) -> bool:
    found = await db.execute(
        select(Invoice.id).where(Invoice.status.in_(("issued", "void"))).limit(1)
    )
    return found.first() is not None


async def get_state(db: AsyncSession, day: date | None = None) -> NumberingState:
    today = day or server_today()
    fmt = await get_format(db)
    next_value = await peek_next(db, fmt, today)
    return NumberingState(
        tokens=fmt.tokens,
        next_value=next_value,
        preview=[render(fmt, next_value + i, today) for i in range(PREVIEW_SIZE)],
        has_issued=await has_issued(db),
    )


async def replace_format(
    db: AsyncSession, fmt: NumberingFormat, confirm: bool, user_id: uuid.UUID
) -> None:
    """Changing how numbers look once invoices have gone out has to be confirmed; numbers
    already given are never changed either way."""
    if not confirm and await has_issued(db):
        raise UnconfirmedFormatChangeError()
    tokens = [token.model_dump() for token in fmt.tokens]
    statement = insert(InvoiceNumberingFormat).values(
        series=INVOICE_SERIES, tokens=tokens, updated_by=user_id
    )
    statement = statement.on_conflict_do_update(
        index_elements=["series"],
        set_={
            "tokens": tokens,
            "updated_by": user_id,
            "updated_at": statement.excluded.updated_at,
        },
    )
    await db.execute(statement)
    await db.commit()


async def set_next(db: AsyncSession, value: int, day: date | None = None) -> None:
    """Makes `value` the next one taken in the current period, e.g. to continue from a
    previous system. Refused when that number already exists."""
    today = day or server_today()
    fmt = await get_format(db)
    number = render(fmt, value, today)
    if await _number_exists(db, number):
        raise NumberCollisionError(number)
    statement = insert(InvoiceNumberCounter).values(
        series=INVOICE_SERIES,
        period_key=period_key(fmt.sequence.restart, today),
        last_value=value - 1,
    )
    statement = statement.on_conflict_do_update(
        index_elements=["series", "period_key"], set_={"last_value": value - 1}
    )
    await db.execute(statement)
    await db.commit()
