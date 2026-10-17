from datetime import UTC, date, datetime


def server_today(now: datetime | None = None) -> date:
    """Today's date in the server's time zone, which the deployment sets with the `TZ`
    environment variable (UTC when unset).

    Invoice numbers and invoice dates are calendar dates, and an organization reads them in
    its own time zone, not UTC: an invoice issued at 00:30 local time on 1 January belongs to
    the new year even though it is still 31 December in UTC. Every such date goes through
    here so they all agree. `now` is for tests; it must be timezone-aware.
    """
    return (now or datetime.now(UTC)).astimezone().date()
