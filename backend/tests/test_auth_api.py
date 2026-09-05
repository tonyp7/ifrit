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
