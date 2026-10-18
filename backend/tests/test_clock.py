import os
import time
from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest

from app.core.clock import server_today


@pytest.fixture
def server_tz() -> Iterator[None]:
    """Lets a test set the process time zone, and puts the original back afterwards."""
    original = os.environ.get("TZ")
    yield
    if original is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = original
    time.tzset()


def test_today_follows_the_server_time_zone(server_tz) -> None:
    late_new_years_eve_utc = datetime(2026, 12, 31, 23, 30, tzinfo=UTC)

    os.environ["TZ"] = "Pacific/Auckland"
    time.tzset()
    assert server_today(late_new_years_eve_utc) == date(2027, 1, 1)

    os.environ["TZ"] = "UTC"
    time.tzset()
    assert server_today(late_new_years_eve_utc) == date(2026, 12, 31)


def test_today_without_an_explicit_time() -> None:
    assert server_today() == datetime.now().astimezone().date()
