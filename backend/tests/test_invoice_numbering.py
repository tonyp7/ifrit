import asyncio
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.invoice import Invoice
from app.models.invoice_numbering import InvoiceNumberCounter
from app.schemas.invoice_numbering import NumberingFormat, Restart
from app.services import invoice_numbering_service as numbering
from tests.factories import create_user
from tests.invoice_helpers import make_issued_invoice

OCT_14 = date(2026, 10, 14)


def _format(*tokens: dict[str, object]) -> NumberingFormat:
    return NumberingFormat.model_validate({"tokens": list(tokens)})


def _seq(
    digits: int = 4, restart: str = "yearly", start_at: int = 1
) -> dict[str, object]:
    return {
        "type": "sequence",
        "digits": digits,
        "start_at": start_at,
        "restart": restart,
    }


async def _issued_invoice(db_session, number: str, status: str = "issued") -> Invoice:
    return await make_issued_invoice(db_session, number, status=status)


# --- rendering -------------------------------------------------------------------


def test_render_monthly_format() -> None:
    fmt = _format(
        {"type": "year"},
        {"type": "month"},
        {"type": "text", "value": "-"},
        _seq(3, "monthly"),
    )
    assert numbering.render(fmt, 1, OCT_14) == "202610-001"


def test_render_writes_an_overflow_in_full() -> None:
    fmt = _format({"type": "text", "value": "INV-"}, _seq(5, "never"))
    assert numbering.render(fmt, 100000, OCT_14) == "INV-100000"


def test_render_day() -> None:
    fmt = _format({"type": "day"}, {"type": "text", "value": "/"}, _seq(2, "daily"))
    assert numbering.render(fmt, 7, OCT_14) == "14/07"


@pytest.mark.parametrize(
    ("restart", "key"),
    [
        ("never", "all"),
        ("yearly", "2026"),
        ("monthly", "2026-10"),
        ("daily", "2026-10-14"),
    ],
)
def test_period_keys(restart: Restart, key: str) -> None:
    assert numbering.period_key(restart, OCT_14) == key


# --- counters --------------------------------------------------------------------


async def test_default_format_starts_at_one(db_session) -> None:
    state = await numbering.get_state(db_session, OCT_14)
    assert state.preview == ["INV-2026-0001", "INV-2026-0002", "INV-2026-0003"]
    assert state.next_value == 1
    assert state.has_issued is False


async def test_take_counts_up_within_a_period(db_session) -> None:
    first = await numbering.take_next_number(db_session, OCT_14)
    second = await numbering.take_next_number(db_session, OCT_14)
    assert [first, second] == [(1, "INV-2026-0001"), (2, "INV-2026-0002")]


async def test_yearly_restart(db_session) -> None:
    db_session.add(
        InvoiceNumberCounter(series="invoice", period_key="2026", last_value=43)
    )
    await db_session.commit()

    assert (await numbering.take_next_number(db_session, date(2026, 12, 31)))[0] == 44
    assert await numbering.take_next_number(db_session, date(2027, 1, 2)) == (
        1,
        "INV-2027-0001",
    )


async def test_a_new_restart_period_starts_at_the_start_value(db_session) -> None:
    user = await create_user(
        db_session, name_id="a@example.com", password="pw", role_name="administrator"
    )
    await numbering.take_next_number(db_session, OCT_14)
    await numbering.replace_format(
        db_session,
        _format({"type": "text", "value": "M"}, _seq(3, "monthly", start_at=100)),
        False,
        user.id,
    )
    assert await numbering.take_next_number(db_session, OCT_14) == (100, "M100")


async def test_concurrent_takes_never_collide(db_session) -> None:
    factory = async_sessionmaker(db_session.bind, expire_on_commit=False)

    async def take() -> int:
        async with factory() as session, session.begin():
            value, _ = await numbering.take_next_number(session, OCT_14)
            # Hold the transaction open a moment so the two genuinely overlap.
            await asyncio.sleep(0.05)
            return value

    values = await asyncio.gather(take(), take())
    assert sorted(values) == [1, 2]


async def test_a_rolled_back_take_gives_its_value_back(db_session) -> None:
    factory = async_sessionmaker(db_session.bind, expire_on_commit=False)
    async with factory() as session:
        await numbering.take_next_number(session, OCT_14)
        await session.rollback()
    assert (await numbering.take_next_number(db_session, OCT_14))[0] == 1


# --- next number -----------------------------------------------------------------


async def test_set_next_continues_from_another_system(db_session) -> None:
    await numbering.set_next(db_session, 512, OCT_14)

    state = await numbering.get_state(db_session, OCT_14)
    assert state.preview[0] == "INV-2026-0512"
    assert state.next_value == 512


async def test_set_next_to_zero(db_session) -> None:
    await numbering.set_next(db_session, 0, OCT_14)
    assert (await numbering.take_next_number(db_session, OCT_14))[0] == 0


async def test_set_next_refuses_an_existing_number(db_session) -> None:
    await _issued_invoice(db_session, "INV-2026-0007")

    with pytest.raises(numbering.NumberCollisionError):
        await numbering.set_next(db_session, 7, OCT_14)

    assert await db_session.get(InvoiceNumberCounter, ("invoice", "2026")) is None


# --- replacing the format --------------------------------------------------------


async def test_format_change_needs_confirming_once_invoices_are_issued(
    db_session,
) -> None:
    user = await create_user(
        db_session, name_id="a@example.com", password="pw", role_name="administrator"
    )
    fmt = _format({"type": "text", "value": "X"}, _seq())
    await numbering.replace_format(db_session, fmt, False, user.id)
    invoice = await _issued_invoice(db_session, "INV-2026-0007", status="void")

    with pytest.raises(numbering.UnconfirmedFormatChangeError):
        await numbering.replace_format(db_session, _format(_seq()), False, user.id)
    assert (await numbering.get_format(db_session)) == fmt

    await numbering.replace_format(db_session, _format(_seq()), True, user.id)
    assert len((await numbering.get_format(db_session)).tokens) == 1
    await db_session.refresh(invoice)
    assert invoice.number == "INV-2026-0007"
