from tests.factories import create_company, create_user


async def _login_admin(client, db_session) -> None:
    await create_user(
        db_session, name_id="admin@example.com", password="admin-pass", role_name="administrator"
    )
    response = await client.post(
        "/api/auth/login", json={"email": "admin@example.com", "password": "admin-pass"}
    )
    assert response.status_code == 200


async def test_list_companies_requires_auth(client, db_session) -> None:
    response = await client.get("/api/companies")
    assert response.status_code == 401


async def test_list_companies_requires_administrator(client, db_session) -> None:
    await create_user(
        db_session, name_id="manager@example.com", password="manager-pass", role_name="manager"
    )
    await client.post(
        "/api/auth/login", json={"email": "manager@example.com", "password": "manager-pass"}
    )
    response = await client.get("/api/companies")
    assert response.status_code == 403


async def test_create_and_list_company(client, db_session) -> None:
    await _login_admin(client, db_session)

    create = await client.post(
        "/api/companies",
        json={
            "legal_name": "Acme Manufacturing SA",
            "country_of_registration": "BE",
            "is_vendor": True,
        },
    )
    assert create.status_code == 201
    body = create.json()
    assert body["legal_name"] == "Acme Manufacturing SA"
    assert body["is_vendor"] is True
    assert body["is_active"] is True
    assert body["identifiers"] == []
    assert body["addresses"] == []

    listing = await client.get("/api/companies")
    assert listing.status_code == 200
    payload = listing.json()
    assert payload["page"] == 1
    assert payload["page_size"] == 50
    assert payload["total"] == 1
    assert payload["items"][0]["legal_name"] == "Acme Manufacturing SA"
    assert payload["items"][0]["country_of_registration"] == "BE"
    assert payload["items"][0]["is_active"] is True


async def test_create_company_rejects_empty_legal_name(client, db_session) -> None:
    await _login_admin(client, db_session)

    response = await client.post(
        "/api/companies", json={"legal_name": "   ", "country_of_registration": "BE"}
    )
    assert response.status_code == 422


async def test_list_companies_search_filters_by_legal_name(client, db_session) -> None:
    await _login_admin(client, db_session)
    await create_company(db_session, legal_name="Acme Manufacturing SA")
    await create_company(db_session, legal_name="Beta Logistics NV")

    response = await client.get("/api/companies", params={"search": "acme"})
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["legal_name"] == "Acme Manufacturing SA"


async def test_list_companies_pagination(client, db_session) -> None:
    await _login_admin(client, db_session)
    for i in range(55):
        await create_company(db_session, legal_name=f"Company {i:03d}")

    page1 = await client.get("/api/companies", params={"page": 1})
    page2 = await client.get("/api/companies", params={"page": 2})

    assert page1.json()["total"] == 55
    assert len(page1.json()["items"]) == 50
    assert len(page2.json()["items"]) == 5


async def test_update_company(client, db_session) -> None:
    await _login_admin(client, db_session)
    company = await create_company(db_session, legal_name="Old Name")

    response = await client.patch(
        f"/api/companies/{company.id}",
        json={
            "legal_name": "New Name",
            "country_of_registration": "FR",
            "is_vendor": True,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["legal_name"] == "New Name"
    assert body["country_of_registration"] == "FR"
    assert body["is_vendor"] is True


async def test_deactivate_company(client, db_session) -> None:
    await _login_admin(client, db_session)
    company = await create_company(db_session)

    response = await client.post(f"/api/companies/{company.id}/deactivate")
    assert response.status_code == 204

    detail = await client.get(f"/api/companies/{company.id}")
    assert detail.json()["is_active"] is False


async def test_duplicate_company_copies_fields_and_children(client, db_session) -> None:
    await _login_admin(client, db_session)
    company = await create_company(
        db_session, legal_name="Acme Manufacturing SA", is_vendor=True
    )

    await client.post(
        f"/api/companies/{company.id}/identifiers",
        json={"id_type": "vat", "id_value": "BE0123456749"},
    )
    await client.post(
        f"/api/companies/{company.id}/addresses",
        json={
            "address_type": "registered",
            "line1": "Rue de la Loi 1",
            "city": "Brussels",
            "country_code": "BE",
        },
    )

    response = await client.post(f"/api/companies/{company.id}/duplicate")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] != str(company.id)
    assert body["legal_name"] == "Acme Manufacturing SA"
    assert body["is_vendor"] is True
    assert body["is_active"] is True
    assert len(body["identifiers"]) == 1
    assert body["identifiers"][0]["id_value"] == "BE0123456749"
    assert len(body["addresses"]) == 1
    assert body["addresses"][0]["city"] == "Brussels"


async def test_duplicate_of_deactivated_company_is_active(client, db_session) -> None:
    await _login_admin(client, db_session)
    company = await create_company(db_session, is_active=False)

    response = await client.post(f"/api/companies/{company.id}/duplicate")
    assert response.status_code == 200
    assert response.json()["is_active"] is True


async def test_add_identifier_requires_scheme_id_for_legal_registration(
    client, db_session
) -> None:
    await _login_admin(client, db_session)
    company = await create_company(db_session)

    response = await client.post(
        f"/api/companies/{company.id}/identifiers",
        json={"id_type": "legal_registration", "id_value": "0123456749"},
    )
    assert response.status_code == 422


async def test_add_duplicate_identifier_conflicts(client, db_session) -> None:
    await _login_admin(client, db_session)
    company = await create_company(db_session)

    payload = {"id_type": "vat", "id_value": "BE0123456749"}
    first = await client.post(f"/api/companies/{company.id}/identifiers", json=payload)
    assert first.status_code == 201

    second = await client.post(f"/api/companies/{company.id}/identifiers", json=payload)
    assert second.status_code == 409


async def test_identifier_update_and_delete(client, db_session) -> None:
    await _login_admin(client, db_session)
    company = await create_company(db_session)

    created = await client.post(
        f"/api/companies/{company.id}/identifiers",
        json={"id_type": "vat", "id_value": "BE0123456749"},
    )
    identifier_id = created.json()["id"]

    updated = await client.patch(
        f"/api/companies/{company.id}/identifiers/{identifier_id}",
        json={"id_type": "vat", "id_value": "BE0999999999"},
    )
    assert updated.status_code == 200
    assert updated.json()["id_value"] == "BE0999999999"

    deleted = await client.delete(
        f"/api/companies/{company.id}/identifiers/{identifier_id}"
    )
    assert deleted.status_code == 204

    detail = await client.get(f"/api/companies/{company.id}")
    assert detail.json()["identifiers"] == []


async def test_address_requires_valid_country_code(client, db_session) -> None:
    await _login_admin(client, db_session)
    company = await create_company(db_session)

    response = await client.post(
        f"/api/companies/{company.id}/addresses",
        json={
            "address_type": "registered",
            "line1": "Rue de la Loi 1",
            "city": "Brussels",
            "country_code": "BEL",
        },
    )
    assert response.status_code == 422


async def test_address_update_and_delete(client, db_session) -> None:
    await _login_admin(client, db_session)
    company = await create_company(db_session)

    created = await client.post(
        f"/api/companies/{company.id}/addresses",
        json={
            "address_type": "registered",
            "line1": "Rue de la Loi 1",
            "city": "Brussels",
            "country_code": "BE",
        },
    )
    address_id = created.json()["id"]

    updated = await client.patch(
        f"/api/companies/{company.id}/addresses/{address_id}",
        json={
            "address_type": "ship_to",
            "line1": "Zone Industrielle 12",
            "city": "Liège",
            "country_code": "BE",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["address_type"] == "ship_to"

    deleted = await client.delete(f"/api/companies/{company.id}/addresses/{address_id}")
    assert deleted.status_code == 204

    detail = await client.get(f"/api/companies/{company.id}")
    assert detail.json()["addresses"] == []


async def test_get_company_not_found(client, db_session) -> None:
    await _login_admin(client, db_session)
    response = await client.get("/api/companies/00000000-0000-0000-0000-000000000099")
    assert response.status_code == 404


async def test_cannot_create_second_primary_address_of_same_type(client, db_session) -> None:
    await _login_admin(client, db_session)
    company = await create_company(db_session)

    first = await client.post(
        f"/api/companies/{company.id}/addresses",
        json={
            "address_type": "registered",
            "line1": "Rue de la Loi 1",
            "city": "Brussels",
            "country_code": "BE",
            "is_primary": True,
        },
    )
    assert first.status_code == 201

    second = await client.post(
        f"/api/companies/{company.id}/addresses",
        json={
            "address_type": "registered",
            "line1": "Avenue Louise 2",
            "city": "Brussels",
            "country_code": "BE",
            "is_primary": True,
        },
    )
    assert second.status_code == 409

    # A non-primary of the same type, and a primary of a *different* type, are fine.
    third = await client.post(
        f"/api/companies/{company.id}/addresses",
        json={
            "address_type": "registered",
            "line1": "Avenue Louise 2",
            "city": "Brussels",
            "country_code": "BE",
            "is_primary": False,
        },
    )
    assert third.status_code == 201

    fourth = await client.post(
        f"/api/companies/{company.id}/addresses",
        json={
            "address_type": "ship_to",
            "line1": "Zone Industrielle 12",
            "city": "Liège",
            "country_code": "BE",
            "is_primary": True,
        },
    )
    assert fourth.status_code == 201


async def test_updating_own_primary_address_does_not_conflict_with_itself(
    client, db_session
) -> None:
    await _login_admin(client, db_session)
    company = await create_company(db_session)

    created = await client.post(
        f"/api/companies/{company.id}/addresses",
        json={
            "address_type": "registered",
            "line1": "Rue de la Loi 1",
            "city": "Brussels",
            "country_code": "BE",
            "is_primary": True,
        },
    )
    address_id = created.json()["id"]

    updated = await client.patch(
        f"/api/companies/{company.id}/addresses/{address_id}",
        json={
            "address_type": "registered",
            "line1": "Rue de la Loi 1 bis",
            "city": "Brussels",
            "country_code": "BE",
            "is_primary": True,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["line1"] == "Rue de la Loi 1 bis"


async def test_updating_address_to_primary_conflicts_with_existing_primary(
    client, db_session
) -> None:
    await _login_admin(client, db_session)
    company = await create_company(db_session)

    await client.post(
        f"/api/companies/{company.id}/addresses",
        json={
            "address_type": "registered",
            "line1": "Rue de la Loi 1",
            "city": "Brussels",
            "country_code": "BE",
            "is_primary": True,
        },
    )
    second = await client.post(
        f"/api/companies/{company.id}/addresses",
        json={
            "address_type": "registered",
            "line1": "Avenue Louise 2",
            "city": "Brussels",
            "country_code": "BE",
            "is_primary": False,
        },
    )
    second_id = second.json()["id"]

    response = await client.patch(
        f"/api/companies/{company.id}/addresses/{second_id}",
        json={
            "address_type": "registered",
            "line1": "Avenue Louise 2",
            "city": "Brussels",
            "country_code": "BE",
            "is_primary": True,
        },
    )
    assert response.status_code == 409
