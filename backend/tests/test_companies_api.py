import importlib.util
from pathlib import Path
from typing import get_args

from sqlalchemy import CheckConstraint, Table

from app.models.company import (
    BANK_ADDRESS_CHECK,
    AccountScheme,
    PayeeAccount,
    PaymentMeansCode,
)
from tests.factories import create_company, create_currency, create_user

BACKEND_DIR = Path(__file__).resolve().parent.parent


async def _login_admin(client, db_session) -> None:
    await create_user(
        db_session,
        name_id="admin@example.com",
        password="admin-pass",
        role_name="administrator",
    )
    response = await client.post(
        "/api/auth/login", json={"email": "admin@example.com", "password": "admin-pass"}
    )
    assert response.status_code == 200


async def test_list_companies_requires_auth(client, db_session) -> None:
    response = await client.get("/api/companies")
    assert response.status_code == 401


async def _login_manager(client, db_session) -> None:
    await create_user(
        db_session,
        name_id="project_admin@example.com",
        password="project_admin-pass",
        role_name="manager",
    )
    response = await client.post(
        "/api/auth/login",
        json={"email": "project_admin@example.com", "password": "project_admin-pass"},
    )
    assert response.status_code == 200


async def test_list_companies_rejects_consultant(client, db_session) -> None:
    await create_user(
        db_session,
        name_id="consultant@example.com",
        password="pw",
        role_name="consultant",
    )
    await client.post(
        "/api/auth/login", json={"email": "consultant@example.com", "password": "pw"}
    )
    response = await client.get("/api/companies")
    assert response.status_code == 403


async def test_list_and_get_company_allow_manager(client, db_session) -> None:
    # Read-only lookups are also needed by the `projects` screen (project_admin-accessible)
    # to populate its vendor/client pickers. Only company-configuration *writes* stay
    # administrator-only (see test_company_writes_reject_manager below).
    company = await create_company(db_session, legal_name="Acme Vendor", is_vendor=True)
    await _login_manager(client, db_session)

    listing = await client.get("/api/companies")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    detail = await client.get(f"/api/companies/{company.id}")
    assert detail.status_code == 200
    assert detail.json()["legal_name"] == "Acme Vendor"


async def test_company_writes_reject_manager(client, db_session) -> None:
    company = await create_company(db_session, legal_name="Acme Vendor", is_vendor=True)
    await _login_manager(client, db_session)

    create = await client.post(
        "/api/companies",
        json={
            "legal_name": "New Co",
            "is_vendor": False,
            "country_of_registration": "US",
        },
    )
    assert create.status_code == 403

    update = await client.patch(
        f"/api/companies/{company.id}",
        json={
            "legal_name": "Renamed",
            "is_vendor": True,
            "country_of_registration": "US",
        },
    )
    assert update.status_code == 403

    deactivate = await client.post(f"/api/companies/{company.id}/deactivate")
    assert deactivate.status_code == 403


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
    assert "trading_name" in payload["items"][0]


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


async def test_list_companies_sort_composes_with_pagination(client, db_session) -> None:
    # Sorting must be applied before pagination splits the rows into pages: a
    # client-side-only sort (as originally implemented) only reorders whatever page
    # is already in memory, which silently breaks once there's more than one page.
    await _login_admin(client, db_session)
    for i in range(55):
        await create_company(db_session, legal_name=f"Company {i:03d}")

    page1 = await client.get(
        "/api/companies",
        params={"page": 1, "sort_by": "legal_name", "sort_dir": "desc"},
    )
    page2 = await client.get(
        "/api/companies",
        params={"page": 2, "sort_by": "legal_name", "sort_dir": "desc"},
    )
    assert page1.status_code == 200
    page1_names = [item["legal_name"] for item in page1.json()["items"]]
    page2_names = [item["legal_name"] for item in page2.json()["items"]]

    assert page1_names[0] == "Company 054"
    assert page1_names[-1] == "Company 005"
    assert page2_names == [f"Company {i:03d}" for i in range(4, -1, -1)]
    # The two pages must be contiguous under the requested sort: no gap, no overlap.
    assert page1_names == sorted(page1_names, reverse=True)
    assert page2_names == sorted(page2_names, reverse=True)


async def test_list_companies_unknown_sort_by_falls_back_to_default(
    client, db_session
) -> None:
    await _login_admin(client, db_session)
    await create_company(db_session, legal_name="Zeta Corp")
    await create_company(db_session, legal_name="Acme Corp")

    response = await client.get(
        "/api/companies", params={"sort_by": "not_a_real_column"}
    )
    assert response.status_code == 200
    names = [item["legal_name"] for item in response.json()["items"]]
    assert names == ["Acme Corp", "Zeta Corp"]


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

    # Deactivated companies drop out of the list and 404 on lookup.
    assert (await client.get(f"/api/companies/{company.id}")).status_code == 404
    assert (await client.get("/api/companies")).json()["total"] == 0


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

    await _create_eur(db_session)
    account = await client.post(
        f"/api/companies/{company.id}/payee-accounts",
        json=_payee_payload(
            account_name="Acme Manufacturing SA",
            bic="GEBABEBB",
            bank_name="BNP Paribas Fortis",
            bank_address=_BANK_ADDRESS,
            is_primary=True,
        ),
    )
    assert account.status_code == 201

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
    assert len(body["payee_accounts"]) == 1
    copied = body["payee_accounts"][0]
    original = account.json()
    assert copied["id"] != original["id"]
    assert copied["company_id"] == body["id"]
    for key in ("id", "company_id"):
        del copied[key], original[key]
    assert copied == original


async def test_list_companies_excludes_inactive(client, db_session) -> None:
    await _login_admin(client, db_session)
    await create_company(db_session, legal_name="Alive Co")
    await create_company(db_session, legal_name="Dead Co", is_active=False)

    payload = (await client.get("/api/companies")).json()
    assert [c["legal_name"] for c in payload["items"]] == ["Alive Co"]
    assert payload["total"] == 1
    assert "is_active" not in payload["items"][0]


async def test_list_companies_search_matches_trading_name(client, db_session) -> None:
    await _login_admin(client, db_session)
    await client.post(
        "/api/companies",
        json={
            "legal_name": "Acme Manufacturing SA",
            "trading_name": "Wile E.",
            "country_of_registration": "BE",
        },
    )
    await create_company(db_session, legal_name="Other Corp")

    payload = (await client.get("/api/companies", params={"search": "wile"})).json()
    assert [c["legal_name"] for c in payload["items"]] == ["Acme Manufacturing SA"]
    assert payload["items"][0]["trading_name"] == "Wile E."


async def test_list_companies_sort_by_trading_name(client, db_session) -> None:
    await _login_admin(client, db_session)
    for legal, trading in [("A Co", "Zeta"), ("B Co", "Alpha")]:
        await client.post(
            "/api/companies",
            json={
                "legal_name": legal,
                "trading_name": trading,
                "country_of_registration": "BE",
            },
        )

    payload = (
        await client.get("/api/companies", params={"sort_by": "trading_name"})
    ).json()
    assert [c["trading_name"] for c in payload["items"]] == ["Alpha", "Zeta"]


async def test_inactive_company_is_not_found_on_every_route(client, db_session) -> None:
    await _login_admin(client, db_session)
    company = await create_company(db_session)
    identifier = await client.post(
        f"/api/companies/{company.id}/identifiers",
        json={"id_type": "vat", "id_value": "BE0123456749"},
    )
    address = await client.post(
        f"/api/companies/{company.id}/addresses",
        json={
            "address_type": "registered",
            "line1": "Rue de la Loi 1",
            "city": "Brussels",
            "country_code": "BE",
        },
    )
    await _create_eur(db_session)
    account = await client.post(
        f"/api/companies/{company.id}/payee-accounts", json=_payee_payload()
    )
    identifier_id = identifier.json()["id"]
    address_id = address.json()["id"]
    account_id = account.json()["id"]
    assert (
        await client.post(f"/api/companies/{company.id}/deactivate")
    ).status_code == 204

    base = f"/api/companies/{company.id}"
    company_payload = {"legal_name": "X", "country_of_registration": "BE"}
    identifier_payload = {"id_type": "vat", "id_value": "BE9999999999"}
    address_payload = {
        "address_type": "postal",
        "line1": "L",
        "city": "C",
        "country_code": "BE",
    }
    responses = [
        await client.get(base),
        await client.patch(base, json=company_payload),
        await client.post(f"{base}/duplicate"),
        await client.post(f"{base}/deactivate"),
        await client.post(f"{base}/identifiers", json=identifier_payload),
        await client.patch(
            f"{base}/identifiers/{identifier_id}", json=identifier_payload
        ),
        await client.delete(f"{base}/identifiers/{identifier_id}"),
        await client.post(f"{base}/addresses", json=address_payload),
        await client.patch(f"{base}/addresses/{address_id}", json=address_payload),
        await client.delete(f"{base}/addresses/{address_id}"),
        await client.post(f"{base}/payee-accounts", json=_payee_payload()),
        await client.patch(
            f"{base}/payee-accounts/{account_id}", json=_payee_payload()
        ),
        await client.delete(f"{base}/payee-accounts/{account_id}"),
    ]
    assert [r.status_code for r in responses] == [404] * len(responses)


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


async def test_cannot_create_second_primary_address_of_same_type(
    client, db_session
) -> None:
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


# --- Payee accounts -------------------------------------------------------------------

_IBAN = "BE71096123456769"
_BANK_ADDRESS = {
    "line1": "Montagne du Parc 3",
    "city": "Brussels",
    "postal_zone": "1000",
    "country_code": "BE",
}


async def _create_eur(db_session) -> None:
    await create_currency(
        db_session, alpha_code="EUR", numeric_code="978", name="Euro", symbol="€"
    )


def _payee_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "payment_means_code": "58",
        "account_scheme": "iban",
        "account_identifier": _IBAN,
        "currency_code": "EUR",
    }
    payload.update(overrides)
    return payload


async def _admin_with_company(client, db_session, *, is_vendor: bool = True) -> str:
    await _login_admin(client, db_session)
    await _create_eur(db_session)
    company = await create_company(db_session, is_vendor=is_vendor)
    return f"/api/companies/{company.id}/payee-accounts"


def test_payee_account_checks_match_the_migration() -> None:
    # `alembic check` compares columns and indexes but not CHECK constraints, so the
    # vocabularies and the bank address rule are compared here instead.
    path = (
        BACKEND_DIR
        / "alembic"
        / "versions"
        / "0002_manager_role_billing_milestones_project_references_payee_accounts.py"
    )
    spec = importlib.util.spec_from_file_location("migration_0002", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert tuple(module._PAYMENT_MEANS_CODES) == get_args(PaymentMeansCode)
    assert tuple(module._ACCOUNT_SCHEMES) == get_args(AccountScheme)
    assert module._BANK_ADDRESS_CHECK == BANK_ADDRESS_CHECK
    table = PayeeAccount.__table__
    assert isinstance(table, Table)
    checks = {
        c.name: str(c.sqltext)
        for c in table.constraints
        if isinstance(c, CheckConstraint)
    }
    assert checks["ck_payee_accounts_bank_address"] == BANK_ADDRESS_CHECK
    for code in get_args(PaymentMeansCode):
        assert f"'{code}'" in checks["ck_payee_accounts_payment_means_code"]


async def test_add_sepa_payee_account_normalizes_the_iban(client, db_session) -> None:
    url = await _admin_with_company(client, db_session)

    response = await client.post(
        url,
        json=_payee_payload(account_identifier="be71 0961 2345 6769", bic="gebabebb"),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["account_identifier"] == _IBAN
    assert body["bic"] == "GEBABEBB"
    assert body["bank_address"] is None
    assert body["is_primary"] is False


async def test_payee_account_rejects_a_bad_iban_checksum(client, db_session) -> None:
    url = await _admin_with_company(client, db_session)

    response = await client.post(
        url, json=_payee_payload(account_identifier="BE71096123456768")
    )
    assert response.status_code == 422


async def test_sepa_payee_account_requires_an_iban(client, db_session) -> None:
    url = await _admin_with_company(client, db_session)

    response = await client.post(
        url,
        json=_payee_payload(account_scheme="other", account_identifier="123-456789-0"),
    )
    assert response.status_code == 422


async def test_other_scheme_identifier_is_kept_as_typed(client, db_session) -> None:
    url = await _admin_with_company(client, db_session)

    response = await client.post(
        url,
        json=_payee_payload(
            payment_means_code="30",
            account_scheme="other",
            account_identifier="  123-456789-0 ",
        ),
    )
    assert response.status_code == 201
    assert response.json()["account_identifier"] == "123-456789-0"


async def test_a_wire_transfer_account_needs_no_bic(client, db_session) -> None:
    url = await _admin_with_company(client, db_session)

    response = await client.post(url, json=_payee_payload(payment_means_code="30"))

    assert response.status_code == 201
    assert response.json()["payment_means_code"] == "30"
    assert response.json()["bic"] is None


async def test_payee_account_rejects_an_unsupported_payment_means_code(
    client, db_session
) -> None:
    url = await _admin_with_company(client, db_session)

    response = await client.post(url, json=_payee_payload(payment_means_code="49"))
    assert response.status_code == 422


async def test_payee_account_currency_must_be_enabled(client, db_session) -> None:
    url = await _admin_with_company(client, db_session)
    await create_currency(
        db_session,
        alpha_code="SEK",
        numeric_code="752",
        name="Swedish Krona",
        is_enabled=False,
    )

    disabled = await client.post(url, json=_payee_payload(currency_code="SEK"))
    unknown = await client.post(url, json=_payee_payload(currency_code="ZZZ"))
    assert disabled.status_code == 422
    assert unknown.status_code == 422


async def test_payee_account_rejects_a_malformed_bic(client, db_session) -> None:
    url = await _admin_with_company(client, db_session)

    response = await client.post(url, json=_payee_payload(bic="GEBABEBB0"))
    assert response.status_code == 422


async def test_payee_account_rejects_a_partial_bank_address(client, db_session) -> None:
    url = await _admin_with_company(client, db_session)

    response = await client.post(
        url,
        json=_payee_payload(
            bank_address={"line1": "", "city": "Brussels", "country_code": ""}
        ),
    )
    assert response.status_code == 422


async def test_payee_account_with_a_bank_address(client, db_session) -> None:
    url = await _admin_with_company(client, db_session)

    response = await client.post(
        url,
        json=_payee_payload(
            bank_name="BNP Paribas Fortis",
            bank_address={**_BANK_ADDRESS, "country_code": "be", "line2": " "},
        ),
    )
    assert response.status_code == 201
    assert response.json()["bank_address"] == {
        "line1": "Montagne du Parc 3",
        "line2": None,
        "line3": None,
        "city": "Brussels",
        "postal_zone": "1000",
        "country_subdivision": None,
        "country_code": "BE",
    }


async def test_duplicate_payee_account_identifier_conflicts(client, db_session) -> None:
    url = await _admin_with_company(client, db_session)
    assert (await client.post(url, json=_payee_payload())).status_code == 201

    response = await client.post(
        url, json=_payee_payload(account_identifier="be71 0961 2345 6769")
    )
    assert response.status_code == 409
    assert response.json()["detail"] == (
        "An account with this identifier already exists for this company"
    )


async def test_second_primary_payee_account_in_a_currency_conflicts(
    client, db_session
) -> None:
    url = await _admin_with_company(client, db_session)
    first = await client.post(url, json=_payee_payload(is_primary=True))
    assert first.status_code == 201

    response = await client.post(
        url,
        json=_payee_payload(account_identifier="NL91ABNA0417164300", is_primary=True),
    )
    assert response.status_code == 409
    assert (
        response.json()["detail"]
        == "A primary account in EUR already exists for this company"
    )
    company = (await client.get(url.removesuffix("/payee-accounts"))).json()
    assert [a["is_primary"] for a in company["payee_accounts"]] == [True]


async def test_primary_payee_accounts_in_different_currencies(
    client, db_session
) -> None:
    url = await _admin_with_company(client, db_session)
    await create_currency(db_session)  # USD
    assert (
        await client.post(url, json=_payee_payload(is_primary=True))
    ).status_code == 201

    response = await client.post(
        url,
        json=_payee_payload(
            payment_means_code="30",
            account_scheme="other",
            account_identifier="026009593 1234567890",
            currency_code="USD",
            is_primary=True,
        ),
    )
    assert response.status_code == 201


async def test_editing_the_primary_payee_account_does_not_conflict_with_itself(
    client, db_session
) -> None:
    url = await _admin_with_company(client, db_session)
    created = (await client.post(url, json=_payee_payload(is_primary=True))).json()

    response = await client.patch(
        f"{url}/{created['id']}",
        json=_payee_payload(account_name="Renamed", is_primary=True),
    )
    assert response.status_code == 200
    assert response.json()["account_name"] == "Renamed"


async def test_payee_account_update_and_delete(client, db_session) -> None:
    url = await _admin_with_company(client, db_session)
    created = (await client.post(url, json=_payee_payload())).json()

    updated = await client.patch(
        f"{url}/{created['id']}",
        json=_payee_payload(payment_means_code="42", bank_address=_BANK_ADDRESS),
    )
    assert updated.status_code == 200
    assert updated.json()["payment_means_code"] == "42"
    assert updated.json()["bank_address"]["city"] == "Brussels"

    assert (await client.delete(f"{url}/{created['id']}")).status_code == 204
    company = (await client.get(url.removesuffix("/payee-accounts"))).json()
    assert company["payee_accounts"] == []
    assert (await client.delete(f"{url}/{created['id']}")).status_code == 404


async def test_payee_account_of_another_company_is_not_found(
    client, db_session
) -> None:
    url = await _admin_with_company(client, db_session)
    created = (await client.post(url, json=_payee_payload())).json()
    other = await create_company(db_session, legal_name="Other Corp")

    response = await client.patch(
        f"/api/companies/{other.id}/payee-accounts/{created['id']}",
        json=_payee_payload(),
    )
    assert response.status_code == 404


async def test_payee_account_on_a_client_company(client, db_session) -> None:
    url = await _admin_with_company(client, db_session, is_vendor=False)

    response = await client.post(url, json=_payee_payload())
    assert response.status_code == 201


async def test_manager_reads_but_cannot_write_payee_accounts(
    client, db_session
) -> None:
    url = await _admin_with_company(client, db_session)
    assert (await client.post(url, json=_payee_payload())).status_code == 201
    await client.post("/api/auth/logout")
    await _login_manager(client, db_session)

    detail = await client.get(url.removesuffix("/payee-accounts"))
    assert detail.status_code == 200
    assert detail.json()["payee_accounts"][0]["account_identifier"] == _IBAN
    response = await client.post(
        url, json=_payee_payload(account_identifier="NL91ABNA0417164300")
    )
    assert response.status_code == 403
