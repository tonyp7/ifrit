import pytest

from tests.factories import create_user

URL = "/api/information-banner"
SETTINGS_URL = "/api/settings/information-banner"


async def _login_admin(client, db_session) -> None:
    await create_user(
        db_session,
        name_id="administrator@example.com",
        password="pw",
        role_name="administrator",
    )
    response = await client.post(
        "/api/auth/login",
        json={"email": "administrator@example.com", "password": "pw"},
    )
    assert response.status_code == 200


async def _save(client, **values) -> None:
    response = await client.patch(SETTINGS_URL, json=values)
    assert response.status_code == 200


async def _signed_out(client):
    # The same client keeps the session cookie, so sign out to read as a visitor.
    await client.post("/api/auth/logout")
    client.cookies.clear()
    return await client.get(URL)


async def test_signed_out_clients_can_read_it(client) -> None:
    response = await client.get(URL)
    assert response.status_code == 200


async def test_a_fresh_installation_shows_nothing(client) -> None:
    assert (await client.get(URL)).json() == {"login": None, "site_wide": None}


async def test_login_placement_only(client, db_session) -> None:
    await _login_admin(client, db_session)
    await _save(
        client,
        show_on_login=True,
        message="Maintenance on Saturday",
        icon="warning",
        color="red",
    )
    shown = {"message": "Maintenance on Saturday", "icon": "warning", "color": "red"}
    assert (await _signed_out(client)).json() == {"login": shown, "site_wide": None}


async def test_site_wide_placement_only(client, db_session) -> None:
    await _login_admin(client, db_session)
    await _save(client, show_site_wide=True, message="Maintenance on Saturday")
    shown = {"message": "Maintenance on Saturday", "icon": "info", "color": "neutral"}
    assert (await client.get(URL)).json() == {"login": None, "site_wide": shown}


async def test_both_placements_share_one_message(client, db_session) -> None:
    await _login_admin(client, db_session)
    await _save(client, show_on_login=True, show_site_wide=True, message="Hello")
    body = (await client.get(URL)).json()
    assert body["login"] == body["site_wide"]
    assert body["login"]["message"] == "Hello"


async def test_a_draft_is_not_exposed_while_both_switches_are_off(
    client, db_session
) -> None:
    await _login_admin(client, db_session)
    await _save(client, message="Draft text")
    response = await _signed_out(client)
    assert response.json() == {"login": None, "site_wide": None}
    assert "Draft text" not in response.text


@pytest.mark.parametrize("message", ["", "   ", "\n \t"])
async def test_a_switch_on_with_no_message_shows_nothing(
    client, db_session, message
) -> None:
    await _login_admin(client, db_session)
    await _save(client, show_on_login=True, show_site_wide=True, message=message)
    assert (await client.get(URL)).json() == {"login": None, "site_wide": None}


async def test_a_change_is_visible_at_once(client, db_session) -> None:
    await _login_admin(client, db_session)
    await _save(client, show_on_login=True, message="First")
    assert (await client.get(URL)).json()["login"]["message"] == "First"
    await _save(client, message="Second")
    assert (await client.get(URL)).json()["login"]["message"] == "Second"


async def test_the_answer_is_not_cacheable(client) -> None:
    assert (await client.get(URL)).headers["cache-control"] == "no-store"


async def test_the_answer_carries_no_settings_beyond_the_banner(
    client, db_session
) -> None:
    await _login_admin(client, db_session)
    await _save(client, show_on_login=True, message="Hello")
    body = (await client.get(URL)).json()
    assert set(body) == {"login", "site_wide"}
    assert set(body["login"]) == {"message", "icon", "color"}


async def test_the_settings_endpoint_stays_protected(client) -> None:
    assert (await client.get(SETTINGS_URL)).status_code == 401
