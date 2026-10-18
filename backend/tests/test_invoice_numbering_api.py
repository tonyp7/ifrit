from typing import Any

import pytest

from app.core.clock import server_today
from app.models.invoice_numbering import InvoiceNumberCounter
from app.services.invoice_numbering_service import period_key
from tests.invoice_helpers import login, make_issued_invoice

URL = "/api/invoice-numbering"
SEQ: dict[str, Any] = {
    "type": "sequence",
    "digits": 4,
    "start_at": 1,
    "restart": "yearly",
}
YEAR = f"{server_today():%Y}"


async def _issued(db_session, number: str) -> None:
    await make_issued_invoice(db_session, number)


async def test_no_session_is_401(client) -> None:
    assert (await client.get(URL)).status_code == 401


@pytest.mark.parametrize("role", ["billing", "manager"])
async def test_other_roles_are_403(client, db_session, role) -> None:
    await login(client, db_session, role)
    for response in (
        await client.get(URL),
        await client.put(URL, json={"tokens": [SEQ]}),
        await client.put(f"{URL}/next", json={"next_value": 5}),
    ):
        assert response.status_code == 403


async def test_default_format_and_preview(client, db_session) -> None:
    await login(client, db_session, "administrator")

    body = (await client.get(URL)).json()

    assert [t["type"] for t in body["tokens"]] == ["text", "year", "text", "sequence"]
    assert body["preview"][0] == f"INV-{YEAR}-0001"
    assert body["next_value"] == 1
    assert body["has_issued"] is False


async def test_preview_follows_the_counter(client, db_session) -> None:
    await login(client, db_session, "administrator")
    db_session.add(
        InvoiceNumberCounter(
            series="invoice",
            period_key=period_key("yearly", server_today()),
            last_value=42,
        )
    )
    await db_session.commit()

    body = (await client.get(URL)).json()

    assert body["preview"] == [
        f"INV-{YEAR}-0043",
        f"INV-{YEAR}-0044",
        f"INV-{YEAR}-0045",
    ]


async def test_replace_before_any_issue(client, db_session) -> None:
    await login(client, db_session, "administrator")

    response = await client.put(
        URL, json={"tokens": [{"type": "text", "value": "F-"}, SEQ]}
    )

    assert response.status_code == 200
    assert response.json()["preview"][0] == "F-0001"


async def test_invalid_format_is_422_with_the_reason(client, db_session) -> None:
    await login(client, db_session, "administrator")

    response = await client.put(
        URL, json={"tokens": [{"type": "text", "value": "INV-"}]}
    )

    assert response.status_code == 422
    assert "Add a sequence" in response.text


async def test_unconfirmed_change_after_issuing_is_409(client, db_session) -> None:
    await login(client, db_session, "administrator")
    await _issued(db_session, f"INV-{YEAR}-0007")

    refused = await client.put(
        URL, json={"tokens": [{"type": "text", "value": "F-"}, SEQ]}
    )
    confirmed = await client.put(
        URL, json={"tokens": [{"type": "text", "value": "F-"}, SEQ], "confirm": True}
    )

    assert refused.status_code == 409
    assert confirmed.status_code == 200
    assert confirmed.json()["preview"][0] == "F-0001"
    assert confirmed.json()["has_issued"] is True


async def test_next_number(client, db_session) -> None:
    await login(client, db_session, "administrator")

    response = await client.put(f"{URL}/next", json={"next_value": 512})

    assert response.status_code == 200
    assert response.json()["preview"][0] == f"INV-{YEAR}-0512"


async def test_next_number_collision_is_409(client, db_session) -> None:
    await login(client, db_session, "administrator")
    await _issued(db_session, f"INV-{YEAR}-0007")

    response = await client.put(f"{URL}/next", json={"next_value": 7})

    assert response.status_code == 409
    assert f"INV-{YEAR}-0007" in response.json()["detail"]
    assert (await client.get(URL)).json()["next_value"] == 1


@pytest.mark.parametrize("value", [-1, 10_000_000_000, "5"])
async def test_next_number_out_of_range_is_422(client, db_session, value) -> None:
    await login(client, db_session, "administrator")
    assert (
        await client.put(f"{URL}/next", json={"next_value": value})
    ).status_code == 422
