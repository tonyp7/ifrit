from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select

from app.models.file import StoredFile
from app.models.invoice import Invoice, InvoiceLine
from app.pdf.errors import PdfEngineError, TemplateError
from app.pdf.odt import TemplateData
from tests.invoice_helpers import ensure_currency, login, make_project

URL = "/api/invoices/preview-pdf"
FAKE_PDF = b"%PDF-1.7 fake"


@pytest.fixture
def rendered(monkeypatch: pytest.MonkeyPatch) -> list[TemplateData]:
    """Stands in for the converter and keeps what the template was filled with."""
    calls: list[TemplateData] = []

    async def fake(data: TemplateData, template: bytes | None = None) -> bytes:
        calls.append(data)
        return FAKE_PDF

    monkeypatch.setattr("app.api.invoices.render_invoice_pdf", fake)
    return calls


def _body(project, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "project_id": str(project.id),
        "bill_from": {"name": "Ifrit Consulting"},
        "bill_to": {"name": "ACME"},
        "lines": [
            {"description": "Work", "quantity": "3", "uom": "hours", "unit_price": "10"}
        ],
        "taxes": [{"label": "GST", "base_mode": "subtotal", "rate": "7"}],
    }
    body.update(overrides)
    return body


async def _counts(db_session) -> tuple[int, int, int]:
    return (
        (
            await db_session.execute(select(func.count()).select_from(Invoice))
        ).scalar_one(),
        (
            await db_session.execute(select(func.count()).select_from(InvoiceLine))
        ).scalar_one(),
        (
            await db_session.execute(select(func.count()).select_from(StoredFile))
        ).scalar_one(),
    )


async def test_preview_returns_the_pdf_with_safe_headers(
    client, db_session, rendered
) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    response = await client.post(URL, json=_body(project))
    assert response.status_code == 200, response.text
    assert response.content == FAKE_PDF
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-security-policy"] == "sandbox; default-src 'none'"
    assert response.headers["cache-control"] == "no-store"


async def test_preview_stores_nothing(client, db_session, rendered) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    before = await _counts(db_session)
    assert (await client.post(URL, json=_body(project))).status_code == 200
    assert await _counts(db_session) == before == (0, 0, 0)


async def test_preview_fills_a_draft_with_the_amounts_a_save_computes(
    client, db_session, rendered
) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    body = _body(project)
    await client.post(URL, json=body)
    (data,) = rendered
    assert data.values["subtotal"] == "30.00"
    assert data.values["tax_total"] == "2.10"
    assert data.values["total"] == "32.10"
    assert data.values["total_with_currency"] == "EUR 32.10"
    assert data.values["invoice_number"] == "Assigned when issued"
    assert data.values["draft_watermark"] == "DRAFT"
    assert data.lines.taxes[0].label == "GST (7 %)"
    # The same body saved gives the same figures.
    saved = (await client.post("/api/invoices", json=body)).json()
    assert (Decimal(saved["subtotal"]), Decimal(saved["total"])) == (
        Decimal(30),
        Decimal("32.1"),
    )


async def test_preview_shows_unsaved_edits_and_leaves_the_saved_draft_alone(
    client, db_session, rendered
) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    saved = (await client.post("/api/invoices", json=_body(project))).json()
    edited = _body(
        project,
        lines=[
            {"description": "Edited", "quantity": "1", "uom": "ea", "unit_price": "5"}
        ],
    )
    assert (await client.post(URL, json=edited)).status_code == 200
    assert rendered[-1].lines.rows[0].description == "Edited"
    again = (await client.get(f"/api/invoices/{saved['id']}")).json()
    assert again["lines"][0]["description"] == "Work"


async def test_preview_uses_the_document_name_setting(
    client, db_session, rendered
) -> None:
    from app.services.app_settings import update_group

    user = await login(client, db_session)
    project = await make_project(db_session)
    await update_group(
        db_session, "invoicing", {"document_name": "Tax Invoice"}, user.id
    )
    await client.post(URL, json=_body(project))
    assert rendered[0].values["document_name"] == "Tax Invoice"


async def test_preview_of_an_invalid_payee_currency_is_422(
    client, db_session, rendered
) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    payee = {
        "payment_means_code": "42",
        "account_scheme": "other",
        "account_identifier": "123",
        "currency_code": "ZZZ",
    }
    response = await client.post(URL, json=_body(project, payee=payee))
    assert response.status_code == 422
    assert rendered == []


async def test_preview_of_a_malformed_body_is_422(client, db_session, rendered) -> None:
    await login(client, db_session)
    assert (await client.post(URL, json={"project_id": "nope"})).status_code == 422


async def test_preview_of_a_project_that_cannot_be_invoiced_is_409(
    client, db_session, rendered
) -> None:
    await login(client, db_session)
    project = await make_project(db_session, status="closed")
    response = await client.post(URL, json=_body(project))
    assert response.status_code == 409
    assert rendered == []


async def test_preview_needs_a_session_and_the_billing_role(
    client, db_session, rendered
) -> None:
    assert (await client.post(URL, json={})).status_code == 401
    await login(client, db_session, "manager")
    assert (await client.post(URL, json={})).status_code == 403


@pytest.mark.parametrize("error", [PdfEngineError("down"), TemplateError("broken")])
async def test_an_unavailable_engine_is_503_without_leaking_why(
    client, db_session, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    async def failing(data: TemplateData, template: bytes | None = None) -> bytes:
        raise error

    monkeypatch.setattr("app.api.invoices.render_invoice_pdf", failing)
    await login(client, db_session)
    await ensure_currency(db_session, "EUR")
    project = await make_project(db_session)
    response = await client.post(URL, json=_body(project))
    assert response.status_code == 503
    assert response.json()["detail"] == "The PDF engine is not available"
    assert str(error) not in response.text
    assert await _counts(db_session) == (0, 0, 0)


async def test_the_application_starts_without_the_converter(
    client, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from app.main import app
    from app.pdf import runner

    monkeypatch.setattr(runner, "soffice_path", lambda: None)
    async with app.router.lifespan_context(app):
        response = await client.get("/api/health")
    assert response.status_code == 200 and response.json() == {"status": "ok"}
    assert "not installed" in caplog.text
