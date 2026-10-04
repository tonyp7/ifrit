import pytest
from httpx import Response
from sqlalchemy import select

from app.models.app_setting import AppSetting
from tests.factories import create_user

URL = "/api/settings"
GROUP_URL = "/api/settings/pdf-export"
DEFAULTS = {"export_logo": True, "logo_height_mm": 20}


async def _login(client, db_session, role: str) -> None:
    await create_user(
        db_session, name_id=f"{role}@example.com", password="pw", role_name=role
    )
    response = await client.post(
        "/api/auth/login", json={"email": f"{role}@example.com", "password": "pw"}
    )
    assert response.status_code == 200


async def _rows(db_session) -> dict[str, object]:
    result = await db_session.execute(select(AppSetting.key, AppSetting.value))
    return {key: value for key, value in result}


# --- access ----------------------------------------------------------------------


async def _every_endpoint(client) -> list[Response]:
    return [
        await client.get(URL),
        await client.get(GROUP_URL),
        await client.patch(GROUP_URL, json={"logo_height_mm": 25}),
        await client.delete(f"{GROUP_URL}/logo_height_mm"),
    ]


async def test_signed_out_clients_get_401(client) -> None:
    for response in await _every_endpoint(client):
        assert response.status_code == 401


@pytest.mark.parametrize("role", ["project_admin", "project_manager", "consultant"])
async def test_other_roles_get_403(client, db_session, role) -> None:
    await _login(client, db_session, role)
    for response in await _every_endpoint(client):
        assert response.status_code == 403
    assert await _rows(db_session) == {}


async def test_an_administrator_is_allowed(client, db_session) -> None:
    await _login(client, db_session, "administrator")
    for response in await _every_endpoint(client):
        assert response.status_code == 200


# --- reading ---------------------------------------------------------------------


async def test_reading_returns_defaults_when_nothing_is_stored(
    client, db_session
) -> None:
    await _login(client, db_session, "administrator")

    assert (await client.get(GROUP_URL)).json() == DEFAULTS
    assert (await client.get(URL)).json() == {"pdf-export": DEFAULTS}


async def test_reading_an_unknown_group_is_404(client, db_session) -> None:
    await _login(client, db_session, "administrator")
    assert (await client.get("/api/settings/nope")).status_code == 404


# --- updating --------------------------------------------------------------------


async def test_a_partial_update_returns_the_full_group(client, db_session) -> None:
    await _login(client, db_session, "administrator")

    response = await client.patch(GROUP_URL, json={"logo_height_mm": 25})

    assert response.status_code == 200
    assert response.json() == {"export_logo": True, "logo_height_mm": 25}
    assert (await client.get(GROUP_URL)).json() == response.json()
    assert await _rows(db_session) == {"logo_height_mm": 25}


async def test_the_response_never_exposes_audit_data(client, db_session) -> None:
    await _login(client, db_session, "administrator")

    patched = await client.patch(GROUP_URL, json={"export_logo": False})

    for body in (patched.json(), (await client.get(GROUP_URL)).json()):
        assert set(body) == {"export_logo", "logo_height_mm"}
    assert set((await client.get(URL)).json()["pdf-export"]) == set(DEFAULTS)


@pytest.mark.parametrize("height", [0, 61, -1, "25", 25.5, True, None])
async def test_invalid_heights_are_422_and_write_nothing(
    client, db_session, height
) -> None:
    await _login(client, db_session, "administrator")

    response = await client.patch(GROUP_URL, json={"logo_height_mm": height})

    assert response.status_code == 422
    assert await _rows(db_session) == {}


async def test_an_unknown_setting_is_422(client, db_session) -> None:
    await _login(client, db_session, "administrator")
    response = await client.patch(GROUP_URL, json={"nope": 1})
    assert response.status_code == 422
    assert await _rows(db_session) == {}


async def test_one_invalid_value_rejects_the_whole_update(client, db_session) -> None:
    await _login(client, db_session, "administrator")

    response = await client.patch(
        GROUP_URL, json={"export_logo": False, "logo_height_mm": 500}
    )

    assert response.status_code == 422
    assert (await client.get(GROUP_URL)).json() == DEFAULTS
    assert await _rows(db_session) == {}


async def test_the_422_carries_a_readable_reason(client, db_session) -> None:
    await _login(client, db_session, "administrator")
    response = await client.patch(GROUP_URL, json={"logo_height_mm": 500})
    detail = response.json()["detail"]
    assert detail[0]["loc"] == ["logo_height_mm"]
    assert "60" in detail[0]["msg"]
    assert "500" not in str(detail)


async def test_a_body_that_is_not_an_object_is_422(client, db_session) -> None:
    await _login(client, db_session, "administrator")
    assert (await client.patch(GROUP_URL, json=[1, 2])).status_code == 422


async def test_an_empty_update_changes_nothing(client, db_session) -> None:
    await _login(client, db_session, "administrator")
    response = await client.patch(GROUP_URL, json={})
    assert response.status_code == 200
    assert response.json() == DEFAULTS
    assert await _rows(db_session) == {}


async def test_updating_an_unknown_group_is_404(client, db_session) -> None:
    await _login(client, db_session, "administrator")
    assert (await client.patch("/api/settings/nope", json={})).status_code == 404


async def test_the_height_survives_switching_the_logo_off(client, db_session) -> None:
    await _login(client, db_session, "administrator")
    await client.patch(GROUP_URL, json={"logo_height_mm": 35})

    response = await client.patch(GROUP_URL, json={"export_logo": False})

    assert response.json() == {"export_logo": False, "logo_height_mm": 35}


# --- reset -----------------------------------------------------------------------


async def test_reset_restores_the_default(client, db_session) -> None:
    await _login(client, db_session, "administrator")
    await client.patch(GROUP_URL, json={"logo_height_mm": 35, "export_logo": False})

    response = await client.delete(f"{GROUP_URL}/logo_height_mm")

    assert response.status_code == 200
    assert response.json() == {"export_logo": False, "logo_height_mm": 20}
    assert await _rows(db_session) == {"export_logo": False}


async def test_reset_of_a_key_with_no_row_succeeds(client, db_session) -> None:
    await _login(client, db_session, "administrator")
    response = await client.delete(f"{GROUP_URL}/logo_height_mm")
    assert response.status_code == 200
    assert response.json() == DEFAULTS


async def test_reset_of_an_unknown_key_is_422(client, db_session) -> None:
    await _login(client, db_session, "administrator")
    assert (await client.delete(f"{GROUP_URL}/nope")).status_code == 422


async def test_reset_in_an_unknown_group_is_404(client, db_session) -> None:
    await _login(client, db_session, "administrator")
    assert (await client.delete("/api/settings/nope/x")).status_code == 404


# --- the logo endpoint is unaffected ---------------------------------------------


async def test_org_logo_is_not_treated_as_a_group(client, db_session) -> None:
    await _login(client, db_session, "administrator")

    # No logo uploaded: the logo endpoint's own 404 message, not "Unknown settings group".
    response = await client.get("/api/settings/org-logo")

    assert response.status_code == 404
    assert response.json()["detail"] == "No logo uploaded"
    assert "org-logo" not in (await client.get(URL)).json()
