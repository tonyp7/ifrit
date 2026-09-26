from tests.factories import create_currency, create_user


async def test_list_currencies_requires_auth(client, db_session) -> None:
    response = await client.get("/api/currencies")
    assert response.status_code == 401


async def test_list_currencies_returns_only_enabled(client, db_session) -> None:
    await create_user(
        db_session,
        name_id="admin@example.com",
        password="admin-pass",
        role_name="administrator",
    )
    await client.post(
        "/api/auth/login", json={"email": "admin@example.com", "password": "admin-pass"}
    )
    await create_currency(
        db_session, alpha_code="USD", numeric_code="840", is_enabled=True
    )
    await create_currency(
        db_session,
        alpha_code="XYZ",
        numeric_code="999",
        name="Disabled Currency",
        is_enabled=False,
    )

    response = await client.get("/api/currencies")
    assert response.status_code == 200
    codes = [c["alpha_code"] for c in response.json()]
    assert codes == ["USD"]
