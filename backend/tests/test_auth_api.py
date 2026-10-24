import logging
import time

from app.api import auth as auth_api
from tests.factories import create_user


async def test_login_success(client, db_session) -> None:
    await create_user(
        db_session,
        name_id="jane@example.com",
        password="s3cret-pass",
        role_name="consultant",
    )

    response = await client.post(
        "/api/auth/login", json={"email": "jane@example.com", "password": "s3cret-pass"}
    )

    assert response.status_code == 200
    assert response.json()["name_id"] == "jane@example.com"
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies


async def test_login_wrong_password(client, db_session) -> None:
    await create_user(
        db_session,
        name_id="jane@example.com",
        password="s3cret-pass",
        role_name="consultant",
    )

    response = await client.post(
        "/api/auth/login", json={"email": "jane@example.com", "password": "wrong"}
    )

    assert response.status_code == 401


async def test_login_unknown_email(client, db_session) -> None:
    response = await client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": "whatever"}
    )

    assert response.status_code == 401


async def test_sso_user_cannot_login_locally(client, db_session) -> None:
    await create_user(
        db_session,
        name_id="jane@example.com",
        password=None,
        role_name="consultant",
        is_sso=True,
    )

    response = await client.post(
        "/api/auth/login", json={"email": "jane@example.com", "password": "anything"}
    )

    assert response.status_code == 401


async def test_me_requires_auth(client) -> None:
    response = await client.get("/api/auth/me")

    assert response.status_code == 401


async def test_me_with_valid_session(client, db_session) -> None:
    await create_user(
        db_session,
        name_id="jane@example.com",
        password="s3cret-pass",
        role_name="manager",
    )

    await client.post(
        "/api/auth/login", json={"email": "jane@example.com", "password": "s3cret-pass"}
    )
    response = await client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["roles"] == ["manager"]


async def _login(client, email="jane@example.com", password="s3cret-pass") -> None:
    response = await client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200


async def test_logout_revokes_previously_issued_tokens(client, db_session) -> None:
    await create_user(
        db_session,
        name_id="jane@example.com",
        password="s3cret-pass",
        role_name="consultant",
    )
    await _login(client)
    stolen = dict(client.cookies)

    assert (await client.post("/api/auth/logout")).status_code == 204

    # A copy of the cookies captured before logout must be dead, not just the client's own.
    client.cookies.clear()
    for name, value in stolen.items():
        client.cookies.set(name, value)
    assert (await client.get("/api/auth/me")).status_code == 401
    assert (await client.post("/api/auth/refresh")).status_code == 401


async def test_logout_without_session_still_succeeds(client) -> None:
    response = await client.post("/api/auth/logout")

    assert response.status_code == 204


async def test_password_reset_revokes_existing_sessions(client, db_session) -> None:
    await create_user(
        db_session,
        name_id="admin@example.com",
        password="admin-pass-123",
        role_name="administrator",
    )
    target = await create_user(
        db_session,
        name_id="jane@example.com",
        password="s3cret-pass",
        role_name="consultant",
    )
    await _login(client)
    victim_cookies = dict(client.cookies)

    client.cookies.clear()
    await _login(client, "admin@example.com", "admin-pass-123")
    reset = await client.post(
        f"/api/users/{target.id}/reset-password",
        json={"new_password": "brand-new-pass-1"},
    )
    assert reset.status_code == 204

    client.cookies.clear()
    for name, value in victim_cookies.items():
        client.cookies.set(name, value)
    assert (await client.get("/api/auth/me")).status_code == 401
    assert (await client.post("/api/auth/refresh")).status_code == 401
    # The admin's own session is unaffected, and the new password logs in normally.
    client.cookies.clear()
    await _login(client, "jane@example.com", "brand-new-pass-1")
    assert (await client.get("/api/auth/me")).status_code == 200


async def test_refresh_keeps_session_valid(client, db_session) -> None:
    await create_user(
        db_session,
        name_id="jane@example.com",
        password="s3cret-pass",
        role_name="consultant",
    )
    await _login(client)

    assert (await client.post("/api/auth/refresh")).status_code == 200
    assert (await client.get("/api/auth/me")).status_code == 200


async def test_login_is_rate_limited(client, db_session) -> None:
    await create_user(
        db_session,
        name_id="jane@example.com",
        password="s3cret-pass",
        role_name="consultant",
    )
    bad_login = {"email": "jane@example.com", "password": "wrong"}

    for _ in range(10):
        assert (await client.post("/api/auth/login", json=bad_login)).status_code == 401

    blocked = await client.post("/api/auth/login", json=bad_login)
    assert blocked.status_code == 429
    # The SPA only reads `detail`, so a different body shape would show users a bare
    # "Request failed with status 429".
    assert "login attempts" in blocked.json()["detail"]
    assert 1 <= int(blocked.headers["Retry-After"]) <= 60

    # The limit applies to the client, not to the outcome: a correct password is refused
    # too, otherwise a guesser could keep trying and only "win" once it finds the password.
    correct = await client.post(
        "/api/auth/login", json={"email": "jane@example.com", "password": "s3cret-pass"}
    )
    assert correct.status_code == 429
    assert "access_token" not in correct.cookies


async def test_blocked_login_never_checks_the_password(
    client, db_session, monkeypatch
) -> None:
    checked = 0
    original = auth_api.authenticate_local_user

    async def counting(*args, **kwargs):
        nonlocal checked
        checked += 1
        return await original(*args, **kwargs)

    monkeypatch.setattr(auth_api, "authenticate_local_user", counting)
    bad_login = {"email": "nobody@example.com", "password": "wrong"}

    for _ in range(10):
        await client.post("/api/auth/login", json=bad_login)
    assert checked == 10

    assert (await client.post("/api/auth/login", json=bad_login)).status_code == 429
    assert checked == 10


async def test_login_is_allowed_again_after_the_window(
    client, db_session, monkeypatch
) -> None:
    await create_user(
        db_session,
        name_id="jane@example.com",
        password="s3cret-pass",
        role_name="consultant",
    )
    bad_login = {"email": "jane@example.com", "password": "wrong"}
    for _ in range(11):
        await client.post("/api/auth/login", json=bad_login)
    assert (await client.post("/api/auth/login", json=bad_login)).status_code == 429

    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + 61)

    ok = await client.post(
        "/api/auth/login", json={"email": "jane@example.com", "password": "s3cret-pass"}
    )
    assert ok.status_code == 200


async def test_failed_login_is_logged(client, db_session, caplog) -> None:
    await create_user(
        db_session,
        name_id="jane@example.com",
        password="s3cret-pass",
        role_name="consultant",
    )

    with caplog.at_level(logging.WARNING, logger="app.api.auth"):
        await client.post(
            "/api/auth/login",
            json={"email": "jane@example.com", "password": "wrong-pass"},
        )
        await client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com\nforged line", "password": "x"},
        )

    assert "Failed login attempt for 'jane@example.com'" in caplog.messages[0]
    # Never the submitted password, and control characters in the email stay escaped.
    assert "wrong-pass" not in caplog.text
    assert "\n" not in caplog.messages[1]


async def test_successful_login_is_not_logged_as_failure(
    client, db_session, caplog
) -> None:
    await create_user(
        db_session,
        name_id="jane@example.com",
        password="s3cret-pass",
        role_name="consultant",
    )

    with caplog.at_level(logging.WARNING, logger="app.api.auth"):
        await client.post(
            "/api/auth/login",
            json={"email": "jane@example.com", "password": "s3cret-pass"},
        )

    assert caplog.messages == []


async def test_billing_alone_grants_no_project_or_company_endpoint(
    client, db_session
) -> None:
    await create_user(
        db_session,
        name_id="biller@example.com",
        password="s3cret-pass",
        role_name="billing",
    )
    login = await client.post(
        "/api/auth/login",
        json={"email": "biller@example.com", "password": "s3cret-pass"},
    )
    assert login.status_code == 200

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["roles"] == ["billing"]

    for path in ("/api/projects", "/api/companies"):
        response = await client.get(path)
        assert response.status_code == 403, path
        assert response.json()["detail"] == "Insufficient permissions"
