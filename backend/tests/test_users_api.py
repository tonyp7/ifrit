from tests.factories import create_user, ensure_role


async def _login(client, name_id: str, password: str) -> None:
    response = await client.post(
        "/api/auth/login", json={"email": name_id, "password": password}
    )
    assert response.status_code == 200


async def test_admin_can_reset_local_user_password(client, db_session) -> None:
    await create_user(
        db_session, name_id="admin@example.com", password="admin-pass", role_name="administrator"
    )
    target = await create_user(
        db_session, name_id="jane@example.com", password="old-pass", role_name="consultant"
    )

    await _login(client, "admin@example.com", "admin-pass")
    response = await client.post(
        f"/api/users/{target.id}/reset-password", json={"new_password": "new-secret-pass"}
    )
    assert response.status_code == 204

    # Old password no longer works, new one does.
    old = await client.post(
        "/api/auth/login", json={"email": "jane@example.com", "password": "old-pass"}
    )
    assert old.status_code == 401

    new = await client.post(
        "/api/auth/login", json={"email": "jane@example.com", "password": "new-secret-pass"}
    )
    assert new.status_code == 200


async def test_non_admin_cannot_reset_password(client, db_session) -> None:
    await create_user(
        db_session, name_id="project_admin@example.com", password="project_admin-pass", role_name="project_admin"
    )
    target = await create_user(
        db_session, name_id="jane@example.com", password="old-pass", role_name="consultant"
    )

    await _login(client, "project_admin@example.com", "project_admin-pass")
    response = await client.post(
        f"/api/users/{target.id}/reset-password", json={"new_password": "new-secret-pass"}
    )
    assert response.status_code == 403


async def test_reset_password_requires_auth(client, db_session) -> None:
    target = await create_user(
        db_session, name_id="jane@example.com", password="old-pass", role_name="consultant"
    )

    response = await client.post(
        f"/api/users/{target.id}/reset-password", json={"new_password": "new-secret-pass"}
    )
    assert response.status_code == 401


async def test_cannot_reset_password_for_sso_user(client, db_session) -> None:
    await create_user(
        db_session, name_id="admin@example.com", password="admin-pass", role_name="administrator"
    )
    target = await create_user(
        db_session,
        name_id="jane@example.com",
        password=None,
        role_name="consultant",
        is_sso=True,
    )

    await _login(client, "admin@example.com", "admin-pass")
    response = await client.post(
        f"/api/users/{target.id}/reset-password", json={"new_password": "new-secret-pass"}
    )
    assert response.status_code == 400


async def test_new_user_defaults_to_system_theme(client, db_session) -> None:
    await create_user(
        db_session, name_id="jane@example.com", password="s3cret-pass", role_name="consultant"
    )

    await _login(client, "jane@example.com", "s3cret-pass")
    response = await client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["theme_preference"] == "system"


async def test_user_can_update_own_theme_preference(client, db_session) -> None:
    await create_user(
        db_session, name_id="jane@example.com", password="s3cret-pass", role_name="consultant"
    )

    await _login(client, "jane@example.com", "s3cret-pass")
    response = await client.patch(
        "/api/users/me/theme-preference", json={"theme_preference": "dark"}
    )

    assert response.status_code == 200
    assert response.json()["theme_preference"] == "dark"

    # Persisted, not just returned in the response.
    me = await client.get("/api/auth/me")
    assert me.json()["theme_preference"] == "dark"


async def test_update_theme_preference_requires_auth(client, db_session) -> None:
    response = await client.patch(
        "/api/users/me/theme-preference", json={"theme_preference": "dark"}
    )
    assert response.status_code == 401


async def test_list_users_filters_by_search(client, db_session) -> None:
    await create_user(
        db_session,
        name_id="admin@example.com",
        password="admin-pass",
        role_name="administrator",
        full_name="Admin User",
    )
    await create_user(
        db_session,
        name_id="jane@example.com",
        password="pw",
        role_name="consultant",
        full_name="Jane Doe",
    )
    await create_user(
        db_session,
        name_id="john@example.com",
        password="pw",
        role_name="consultant",
        full_name="John Smith",
    )

    await _login(client, "admin@example.com", "admin-pass")
    response = await client.get("/api/users", params={"search": "jane"})

    assert response.status_code == 200
    names = [u["full_name"] for u in response.json()["items"]]
    assert names == ["Jane Doe"]


async def test_list_users_search_is_case_insensitive_substring(client, db_session) -> None:
    await create_user(
        db_session,
        name_id="admin@example.com",
        password="admin-pass",
        role_name="administrator",
        full_name="Admin User",
    )
    await create_user(
        db_session,
        name_id="jane@example.com",
        password="pw",
        role_name="consultant",
        full_name="Jane Doe",
    )

    await _login(client, "admin@example.com", "admin-pass")
    response = await client.get("/api/users", params={"search": "DOE"})

    assert response.status_code == 200
    assert [u["full_name"] for u in response.json()["items"]] == ["Jane Doe"]


async def test_update_theme_preference_rejects_invalid_value(client, db_session) -> None:
    await create_user(
        db_session, name_id="jane@example.com", password="s3cret-pass", role_name="consultant"
    )

    await _login(client, "jane@example.com", "s3cret-pass")
    response = await client.patch(
        "/api/users/me/theme-preference", json={"theme_preference": "solarized"}
    )
    assert response.status_code == 422


async def _login_admin(client, db_session, name_id: str = "admin@example.com") -> None:
    await create_user(
        db_session,
        name_id=name_id,
        password="admin-password-12",
        role_name="administrator",
        full_name="Admin User",
    )
    await _login(client, name_id, "admin-password-12")


async def test_create_local_user(client, db_session) -> None:
    await _login_admin(client, db_session)
    await ensure_role(db_session, "consultant")

    response = await client.post(
        "/api/users",
        json={
            "full_name": "New Consultant",
            "name_id": "new-consultant@example.com",
            "is_sso": False,
            "roles": ["consultant"],
            "password": "a-strong-password-123",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["full_name"] == "New Consultant"
    assert body["roles"] == ["consultant"]
    assert body["is_sso"] is False
    assert body["is_active"] is True

    # The password actually works.
    new_login = await client.post(
        "/api/auth/login",
        json={"email": "new-consultant@example.com", "password": "a-strong-password-123"},
    )
    assert new_login.status_code == 200


async def test_create_local_user_requires_password(client, db_session) -> None:
    await _login_admin(client, db_session)

    response = await client.post(
        "/api/users",
        json={
            "full_name": "New Consultant",
            "name_id": "new-consultant@example.com",
            "is_sso": False,
            "roles": ["consultant"],
        },
    )
    assert response.status_code == 422


async def test_create_local_user_rejects_short_password(client, db_session) -> None:
    await _login_admin(client, db_session)

    response = await client.post(
        "/api/users",
        json={
            "full_name": "New Consultant",
            "name_id": "new-consultant@example.com",
            "is_sso": False,
            "roles": ["consultant"],
            "password": "short1",
        },
    )
    assert response.status_code == 422


async def test_create_local_user_rejects_non_printable_password(client, db_session) -> None:
    await _login_admin(client, db_session)

    response = await client.post(
        "/api/users",
        json={
            "full_name": "New Consultant",
            "name_id": "new-consultant@example.com",
            "is_sso": False,
            "roles": ["consultant"],
            "password": "has-a-tab\tcharacter-in-it",
        },
    )
    assert response.status_code == 422


async def test_create_local_user_allows_spaces_and_unicode_password(client, db_session) -> None:
    await _login_admin(client, db_session)
    await ensure_role(db_session, "consultant")

    password = "correct 马 horse 🐴 battery staple"
    response = await client.post(
        "/api/users",
        json={
            "full_name": "New Consultant",
            "name_id": "new-consultant@example.com",
            "is_sso": False,
            "roles": ["consultant"],
            "password": password,
        },
    )
    assert response.status_code == 201

    login = await client.post(
        "/api/auth/login",
        json={"email": "new-consultant@example.com", "password": password},
    )
    assert login.status_code == 200


async def test_create_sso_user_rejects_password(client, db_session) -> None:
    await _login_admin(client, db_session)

    response = await client.post(
        "/api/users",
        json={
            "full_name": "New Consultant",
            "name_id": "new-consultant@example.com",
            "is_sso": True,
            "roles": ["consultant"],
            "password": "a-strong-password-123",
        },
    )
    assert response.status_code == 422


async def test_create_sso_user_without_password(client, db_session) -> None:
    await _login_admin(client, db_session)
    await ensure_role(db_session, "consultant")

    response = await client.post(
        "/api/users",
        json={
            "full_name": "New SSO Consultant",
            "name_id": "sso-consultant@example.com",
            "is_sso": True,
            "roles": ["consultant"],
        },
    )
    assert response.status_code == 201
    assert response.json()["is_sso"] is True


async def test_create_user_requires_at_least_one_role(client, db_session) -> None:
    await _login_admin(client, db_session)

    response = await client.post(
        "/api/users",
        json={
            "full_name": "New Consultant",
            "name_id": "new-consultant@example.com",
            "is_sso": False,
            "roles": [],
            "password": "a-strong-password-123",
        },
    )
    assert response.status_code == 422


async def test_create_user_rejects_duplicate_name_id(client, db_session) -> None:
    await _login_admin(client, db_session)
    await create_user(
        db_session, name_id="jane@example.com", password="pw", role_name="consultant"
    )

    response = await client.post(
        "/api/users",
        json={
            "full_name": "Another Jane",
            "name_id": "jane@example.com",
            "is_sso": False,
            "roles": ["consultant"],
            "password": "a-strong-password-123",
        },
    )
    assert response.status_code == 409


async def test_create_user_requires_administrator(client, db_session) -> None:
    await create_user(
        db_session, name_id="project_admin@example.com", password="project_admin-pass", role_name="project_admin"
    )
    await _login(client, "project_admin@example.com", "project_admin-pass")

    response = await client.post(
        "/api/users",
        json={
            "full_name": "New Consultant",
            "name_id": "new-consultant@example.com",
            "is_sso": False,
            "roles": ["consultant"],
            "password": "a-strong-password-123",
        },
    )
    assert response.status_code == 403


async def test_admin_cannot_remove_own_administrator_role(client, db_session) -> None:
    await create_user(
        db_session,
        name_id="admin@example.com",
        password="admin-password-12",
        role_name="administrator",
        full_name="Admin User",
    )
    await _login(client, "admin@example.com", "admin-password-12")

    me = await client.get("/api/auth/me")
    admin_id = me.json()["id"]

    response = await client.patch(
        f"/api/users/{admin_id}",
        json={
            "full_name": "Admin User",
            "name_id": "admin@example.com",
            "is_sso": False,
            "roles": ["project_admin"],
        },
    )
    assert response.status_code == 400


async def test_admin_can_edit_own_non_role_fields(client, db_session) -> None:
    await create_user(
        db_session,
        name_id="admin@example.com",
        password="admin-password-12",
        role_name="administrator",
        full_name="Admin User",
    )
    await _login(client, "admin@example.com", "admin-password-12")

    me = await client.get("/api/auth/me")
    admin_id = me.json()["id"]

    response = await client.patch(
        f"/api/users/{admin_id}",
        json={
            "full_name": "Renamed Admin",
            "name_id": "admin@example.com",
            "is_sso": False,
            "roles": ["administrator"],
        },
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Renamed Admin"


async def test_admin_cannot_deactivate_own_account(client, db_session) -> None:
    await create_user(
        db_session,
        name_id="admin@example.com",
        password="admin-password-12",
        role_name="administrator",
        full_name="Admin User",
    )
    await _login(client, "admin@example.com", "admin-password-12")

    me = await client.get("/api/auth/me")
    admin_id = me.json()["id"]

    response = await client.post(f"/api/users/{admin_id}/deactivate")
    assert response.status_code == 400


async def test_admin_can_deactivate_another_user(client, db_session) -> None:
    await _login_admin(client, db_session)
    target = await create_user(
        db_session, name_id="jane@example.com", password="pw", role_name="consultant"
    )

    response = await client.post(f"/api/users/{target.id}/deactivate")
    assert response.status_code == 204

    listing = await client.get("/api/users", params={"is_active": "false"})
    assert [u["id"] for u in listing.json()["items"]] == [str(target.id)]


async def test_switching_local_user_to_sso_clears_password(client, db_session) -> None:
    await _login_admin(client, db_session)
    target = await create_user(
        db_session, name_id="jane@example.com", password="old-password-123", role_name="consultant"
    )

    response = await client.patch(
        f"/api/users/{target.id}",
        json={
            "full_name": "Jane Doe",
            "name_id": "jane@example.com",
            "is_sso": True,
            "roles": ["consultant"],
        },
    )
    assert response.status_code == 200
    assert response.json()["is_sso"] is True

    # Old local password no longer works.
    login = await client.post(
        "/api/auth/login",
        json={"email": "jane@example.com", "password": "old-password-123"},
    )
    assert login.status_code == 401

    # Reset-password now correctly rejects it as an SSO account.
    reset = await client.post(
        f"/api/users/{target.id}/reset-password", json={"new_password": "another-password-1"}
    )
    assert reset.status_code == 400


async def test_switching_sso_user_to_local_requires_password(client, db_session) -> None:
    await _login_admin(client, db_session)
    target = await create_user(
        db_session,
        name_id="jane@example.com",
        password=None,
        role_name="consultant",
        is_sso=True,
    )

    response = await client.patch(
        f"/api/users/{target.id}",
        json={
            "full_name": "Jane Doe",
            "name_id": "jane@example.com",
            "is_sso": False,
            "roles": ["consultant"],
        },
    )
    assert response.status_code == 422


async def test_switching_sso_user_to_local_with_password(client, db_session) -> None:
    await _login_admin(client, db_session)
    target = await create_user(
        db_session,
        name_id="jane@example.com",
        password=None,
        role_name="consultant",
        is_sso=True,
    )

    response = await client.patch(
        f"/api/users/{target.id}",
        json={
            "full_name": "Jane Doe",
            "name_id": "jane@example.com",
            "is_sso": False,
            "roles": ["consultant"],
            "password": "brand-new-password-1",
        },
    )
    assert response.status_code == 200
    assert response.json()["is_sso"] is False

    login = await client.post(
        "/api/auth/login",
        json={"email": "jane@example.com", "password": "brand-new-password-1"},
    )
    assert login.status_code == 200


async def test_list_users_paginated_response_shape(client, db_session) -> None:
    await _login_admin(client, db_session)

    response = await client.get("/api/users")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"items", "total", "page", "page_size"}
    assert body["page"] == 1
    assert body["page_size"] == 50
