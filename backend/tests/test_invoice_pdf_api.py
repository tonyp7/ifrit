import io
import shutil
from typing import Any

import pytest
from pypdf import PdfReader
from sqlalchemy import select

from app.core.clock import server_today
from app.models.file import File, StoredFile
from app.pdf import format as fmt
from app.pdf.errors import PdfEngineError
from app.pdf.odt import TemplateData
from app.services import invoice_numbering_service
from tests.invoice_helpers import login, make_issued_invoice, make_project
from tests.pdf_helpers import fake_invoice_pdf
from tests.test_pdf_render import _text as pdf_text

URL = "/api/invoices"
FAKE = b"%PDF-1.7 draft"


def _body(project, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "project_id": str(project.id),
        "bill_from": {"name": "Ifrit"},
        "bill_to": {"name": "ACME"},
        "lines": [
            {"description": "Work", "quantity": "3", "uom": "hours", "unit_price": "10"}
        ],
    }
    body.update(overrides)
    return body


async def _draft_id(client, project) -> str:
    response = await client.post(URL, json=_body(project))
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def _issued(client, project) -> dict[str, Any]:
    invoice_id = await _draft_id(client, project)
    response = await client.post(f"{URL}/{invoice_id}/issue")
    assert response.status_code == 200, response.text
    return response.json()


async def test_an_issued_invoice_downloads_the_stored_bytes(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    issued = await _issued(client, project)

    response = await client.get(f"{URL}/{issued['id']}/pdf")

    assert response.status_code == 200
    assert response.content == fake_invoice_pdf(issued["number"])
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-security-policy"] == "sandbox; default-src 'none'"
    assert (
        response.headers["content-disposition"]
        == f'inline; filename="{issued["number"]}.pdf"'
    )


async def test_the_download_is_the_same_bytes_every_time(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    issued = await _issued(client, project)
    first = await client.get(f"{URL}/{issued['id']}/pdf")
    second = await client.get(f"{URL}/{issued['id']}/pdf")
    assert first.content == second.content


async def test_a_number_with_a_slash_gives_a_single_file_name(
    client, db_session
) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    issued = await _issued(client, project)
    from app.models.invoice import Invoice

    invoice = await db_session.get(Invoice, issued["id"])
    assert invoice is not None
    invoice.number = "2026/0043"
    await db_session.commit()

    response = await client.get(f"{URL}/{issued['id']}/pdf")

    assert response.headers["content-disposition"] == 'inline; filename="2026-0043.pdf"'


async def test_a_saved_draft_is_rendered_with_nothing_stored(
    client, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[TemplateData] = []

    async def fake(data: TemplateData, template: bytes | None = None) -> bytes:
        seen.append(data)
        return FAKE

    monkeypatch.setattr("app.api.invoices.render_invoice_pdf", fake)
    await login(client, db_session)
    project = await make_project(db_session)
    invoice_id = await _draft_id(client, project)
    fmt_ = await invoice_numbering_service.get_format(db_session)
    value = await invoice_numbering_service.peek_next(db_session, fmt_, server_today())
    expected_number = invoice_numbering_service.render(fmt_, value, server_today())

    response = await client.get(f"{URL}/{invoice_id}/pdf")

    assert response.status_code == 200 and response.content == FAKE
    assert seen[0].values["draft_watermark"] == "DRAFT"
    # What issuing today would give, not the placeholder words.
    assert seen[0].values["invoice_number"] != "Assigned when issued"
    assert seen[0].values["invoice_date"] == fmt.date_text(server_today())
    assert seen[0].values["invoice_number"] == expected_number
    assert response.headers["content-disposition"] == (
        f'inline; filename="draft-{invoice_id[:8]}.pdf"'
    )
    assert (await db_session.execute(select(StoredFile))).scalars().all() == []


async def test_a_draft_pdf_is_503_when_the_engine_is_down(
    client, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken(data: TemplateData, template: bytes | None = None) -> bytes:
        raise PdfEngineError("down")

    monkeypatch.setattr("app.api.invoices.render_invoice_pdf", broken)
    await login(client, db_session)
    project = await make_project(db_session)
    invoice_id = await _draft_id(client, project)

    response = await client.get(f"{URL}/{invoice_id}/pdf")

    assert response.status_code == 503
    assert response.json()["detail"] == "The PDF engine is not available"


async def test_an_invoice_issued_before_pdfs_were_kept_has_none(
    client, db_session
) -> None:
    await login(client, db_session)
    legacy = await make_issued_invoice(db_session, "OLD-1")

    response = await client.get(f"{URL}/{legacy.id}/pdf")

    assert response.status_code == 404
    detail = (await client.get(f"{URL}/{legacy.id}")).json()
    assert detail["has_pdf"] is False


async def test_an_unknown_invoice_is_404(client, db_session) -> None:
    await login(client, db_session)
    response = await client.get(f"{URL}/00000000-0000-0000-0000-000000000000/pdf")
    assert response.status_code == 404


async def test_the_pdf_needs_a_session_and_the_billing_role(client, db_session) -> None:
    assert (await client.get(f"{URL}/x/pdf")).status_code == 401
    await login(client, db_session, "manager")
    response = await client.get(f"{URL}/00000000-0000-0000-0000-000000000000/pdf")
    assert response.status_code == 403


async def test_a_stored_path_outside_the_storage_root_is_refused(
    client, db_session
) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    issued = await _issued(client, project)
    stored = (await db_session.execute(select(StoredFile))).scalar_one()
    stored.bucket_key = "../../etc/passwd"
    await db_session.commit()

    response = await client.get(f"{URL}/{issued['id']}/pdf")

    assert response.status_code == 404


async def test_a_missing_stored_file_is_404(
    client, db_session, _storage_settings
) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    issued = await _issued(client, project)
    for path in _storage_settings.rglob("*.pdf"):
        path.unlink()

    assert (await client.get(f"{URL}/{issued['id']}/pdf")).status_code == 404


async def test_has_pdf_in_the_detail_and_the_list(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    draft_id = await _draft_id(client, project)
    issued = await _issued(client, project)
    legacy = await make_issued_invoice(db_session, "OLD-1", project=project)

    assert (await client.get(f"{URL}/{draft_id}")).json()["has_pdf"] is False
    assert (await client.get(f"{URL}/{issued['id']}")).json()["has_pdf"] is True
    items = (await client.get(f"{URL}?status=draft&status=issued")).json()["items"]
    by_id = {item["id"]: item["has_pdf"] for item in items}
    assert by_id == {draft_id: False, issued["id"]: True, str(legacy.id): False}


async def test_issue_is_503_and_changes_nothing_when_the_pdf_cannot_be_made(
    client, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken(data: TemplateData, template: bytes | None = None) -> bytes:
        raise PdfEngineError("down")

    monkeypatch.setattr("app.services.invoice_service.render_invoice_pdf", broken)
    await login(client, db_session)
    project = await make_project(db_session)
    invoice_id = await _draft_id(client, project)

    response = await client.post(f"{URL}/{invoice_id}/issue")

    assert response.status_code == 503
    assert "not issued" in response.json()["detail"]
    detail = (await client.get(f"{URL}/{invoice_id}")).json()
    assert detail["status"] == "draft" and detail["number"] is None
    assert (await db_session.execute(select(StoredFile))).scalars().all() == []


async def test_the_generic_file_download_never_serves_an_invoice_pdf(
    client, db_session
) -> None:
    await login(client, db_session, "billing")
    project = await make_project(db_session)
    issued = await _issued(client, project)
    from app.models.invoice import Invoice

    invoice = await db_session.get(Invoice, issued["id"])
    assert invoice is not None and invoice.pdf_file_id is not None
    file_id = invoice.pdf_file_id

    assert (await client.get(f"/api/files/{file_id}/content")).status_code == 403
    await client.post("/api/auth/logout")
    await login(client, db_session, "administrator")
    assert (await client.get(f"/api/files/{file_id}/content")).status_code == 403


async def test_changing_the_document_name_later_does_not_change_the_pdf(
    client, db_session
) -> None:
    from app.services.app_settings import update_group

    user = await login(client, db_session)
    project = await make_project(db_session)
    issued = await _issued(client, project)
    before = (await client.get(f"{URL}/{issued['id']}/pdf")).content

    await update_group(
        db_session, "invoicing", {"document_name": "Tax Invoice"}, user.id
    )

    assert (await client.get(f"{URL}/{issued['id']}/pdf")).content == before
    assert (await client.get(f"{URL}/{issued['id']}")).json()[
        "document_name"
    ] == "Invoice"


@pytest.mark.libreoffice
@pytest.mark.skipif(
    shutil.which("soffice") is None and shutil.which("libreoffice") is None,
    reason="LibreOffice is not installed",
)
async def test_an_invoice_issued_with_the_real_engine_has_a_real_pdf(
    client, db_session
) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    issued = await _issued(client, project)

    pdf = (await client.get(f"{URL}/{issued['id']}/pdf")).content

    assert pdf.startswith(b"%PDF")
    if shutil.which("pdftotext"):
        text = pdf_text(pdf)
        assert issued["number"] in text
        assert "Assigned when issued" not in text


async def test_a_void_invoice_downloads_the_stamped_pdf(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    issued = await _issued(client, project)
    before = await client.get(f"{URL}/{issued['id']}/pdf")

    voided = await client.post(f"{URL}/{issued['id']}/void", json={"reason": "Wrong"})
    assert voided.status_code == 200 and voided.json()["has_pdf"] is True
    after = await client.get(f"{URL}/{issued['id']}/pdf")

    assert after.status_code == 200
    assert after.content != before.content
    pages = PdfReader(io.BytesIO(after.content)).pages
    assert all("VOIDED" in page.extract_text() for page in pages)
    assert (
        after.headers["content-disposition"]
        == f'inline; filename="{issued["number"]}.pdf"'
    )


async def test_voiding_twice_is_409_and_stamps_nothing_more(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    issued = await _issued(client, project)
    await client.post(f"{URL}/{issued['id']}/void", json={})
    files = len((await db_session.execute(select(File))).scalars().all())

    again = await client.post(f"{URL}/{issued['id']}/void", json={})

    assert again.status_code == 409
    assert len((await db_session.execute(select(File))).scalars().all()) == files == 2


async def test_a_pdf_that_cannot_be_marked_is_500_and_the_invoice_stays_issued(
    client, db_session, _storage_settings
) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    issued = await _issued(client, project)
    for path in _storage_settings.rglob("*.pdf"):
        path.write_bytes(b"damaged")

    response = await client.post(f"{URL}/{issued['id']}/void", json={})

    assert response.status_code == 500
    assert "not voided" in response.json()["detail"]
    detail = (await client.get(f"{URL}/{issued['id']}")).json()
    assert detail["status"] == "issued" and detail["voided_at"] is None
    assert len((await db_session.execute(select(File))).scalars().all()) == 1


@pytest.mark.libreoffice
@pytest.mark.skipif(
    shutil.which("soffice") is None and shutil.which("libreoffice") is None,
    reason="LibreOffice is not installed",
)
async def test_a_pdf_made_by_the_real_engine_can_be_stamped(client, db_session) -> None:
    await login(client, db_session)
    project = await make_project(db_session)
    issued = await _issued(client, project)
    original = (await client.get(f"{URL}/{issued['id']}/pdf")).content

    assert (await client.post(f"{URL}/{issued['id']}/void", json={})).status_code == 200
    stamped = (await client.get(f"{URL}/{issued['id']}/pdf")).content

    before = PdfReader(io.BytesIO(original)).pages
    after = PdfReader(io.BytesIO(stamped)).pages
    assert len(after) == len(before) >= 1
    assert all("VOIDED" in page.extract_text() for page in after)
    assert issued["number"] in after[0].extract_text()
