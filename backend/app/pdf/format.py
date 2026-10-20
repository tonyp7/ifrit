"""How an invoice PDF writes dates, amounts and quantities. English only: the application's
own values are not translated."""

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal

_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


def month_name(month: int) -> str:
    return _MONTHS[month - 1]


def date_text(day: date) -> str:
    """`3 September 2026`, independent of the server's locale."""
    return f"{day.day} {month_name(day.month)} {day.year}"


def datetime_text(moment: datetime) -> str:
    """`3 September 2026 14:05` in the server's time zone."""
    local = moment.astimezone()
    return f"{date_text(local.date())} {local:%H:%M}"


def period_text(start: date, end: date) -> str:
    """`1-31 August 2026` within a month, written out in full otherwise."""
    if (start.year, start.month) == (end.year, end.month):
        if start == end:
            return date_text(start)
        return f"{start.day}-{end.day} {month_name(end.month)} {end.year}"
    if start.year == end.year:
        return f"{start.day} {month_name(start.month)} - {date_text(end)}"
    return f"{date_text(start)} - {date_text(end)}"


def money(value: Decimal, places: int) -> str:
    """`6,000.00`: comma thousands, a point, and the currency's number of decimals."""
    quantum = Decimal(1).scaleb(-places)
    return f"{value.quantize(quantum, rounding=ROUND_HALF_UP):,f}"


def unit_price(value: Decimal, places: int) -> str:
    """A unit price keeps the currency's decimals and shows more only when it has them
    (12.3456), so a price is never printed rounded."""
    shown = money(value, places)
    exact = f"{value.normalize():f}"
    decimals = len(exact.partition(".")[2])
    if decimals > places:
        return money(value, min(decimals, 4))
    return shown


def quantity(value: Decimal) -> str:
    """Up to five decimals with trailing zeros removed: `20`, `2.5`."""
    return f"{value.normalize():,f}"


def rate(value: Decimal) -> str:
    return f"{value.normalize():f}"


def iban_groups(value: str) -> str:
    stripped = value.replace(" ", "")
    return " ".join(stripped[i : i + 4] for i in range(0, len(stripped), 4))
