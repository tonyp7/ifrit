from tests.factories import create_user


async def test_login_success(client, db_session) -> None:
    await create_user(
        db_session, name_id="jane@example.com", password="s3cret-pass", role_name="consultant"
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
        db_session, name_id="jane@example.com", password="s3cret-pass", role_name="consultant"
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
        db_session, name_id="jane@example.com", password="s3cret-pass", role_name="project_admin"
    )

    await client.post(
        "/api/auth/login", json={"email": "jane@example.com", "password": "s3cret-pass"}
    )
    response = await client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["roles"] == ["project_admin"]


async def _login(client, email="jane@example.com", password="s3cret-pass") -> None:
    response = await client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200


async def test_logout_revokes_previously_issued_tokens(client, db_session) -> None:
    await create_user(
        db_session, name_id="jane@example.com", password="s3cret-pass", role_name="consultant"
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
        db_session, name_id="admin@example.com", password="admin-pass-123", role_name="administrator"
    )
    target = await create_user(
        db_session, name_id="jane@example.com", password="s3cret-pass", role_name="consultant"
    )
    await _login(client)
    victim_cookies = dict(client.cookies)

    client.cookies.clear()
    await _login(client, "admin@example.com", "admin-pass-123")
    reset = await client.post(
        f"/api/users/{target.id}/reset-password", json={"new_password": "brand-new-pass-1"}
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
        db_session, name_id="jane@example.com", password="s3cret-pass", role_name="consultant"
    )
    await _login(client)

    assert (await client.post("/api/auth/refresh")).status_code == 200
    assert (await client.get("/api/auth/me")).status_code == 200
