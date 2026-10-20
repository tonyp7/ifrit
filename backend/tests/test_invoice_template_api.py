import io
import json
import shutil
from typing import Any

import pytest
from pypdf import PdfReader
from sqlalchemy import func, select

from app.models.file import File
from app.pdf.render import bundled_template
from app.pdf.tokens import TOKENS
from app.pdf.validate import Finding
from app.services import invoice_service
from app.services.invoice_template_service import resolve_template
from tests.invoice_helpers import login, make_project
from tests.pdf_helpers import fake_invoice_pdf
from tests.test_pdf_validate import _replace, _rewrite

URL = "/api/invoice-template"
ODT = "application/vnd.oasis.opendocument.text"
SAMPLE_PDF = fake_invoice_pdf("SAMPLE")


@pytest.fixture(autouse=True)
def _trial(monkeypatch: pytest.MonkeyPatch) -> list[bytes]:
    """The trial render needs LibreOffice: tests stand a fake in unless marked
    `libreoffice`. It records the templates it was asked about."""
    seen: list[bytes] = []

    async def fake(template: bytes) -> tuple[bytes | None, list[Finding]]:
        seen.append(template)
        return SAMPLE_PDF, []

    monkeypatch.setattr("app.api.invoice_template.trial_render", fake)
    return seen


def _custom(sentence: str = "Pay promptly") -> bytes:
    """The bundled template with one more sentence in the body."""
    return _rewrite(
        _replace(
            "content.xml",
            "{{invoice_lines}}",
            "{{invoice_lines}}</text:p><text:p>" + sentence,
        )
    )


def _upload(data: bytes, name: str = "acme.odt") -> dict[str, Any]:
    return {"files": {"file": (name, data, ODT)}}


async def _admin(client, db_session):
    return await login(client, db_session, "administrator")


async def _sign_in(client, role: str) -> None:
    """Back to a user that `login` already created."""
    response = await client.post(
        "/api/auth/login", json={"email": f"{role}@example.com", "password": "pw"}
    )
    assert response.status_code == 200


async def _put(client, data: bytes, name: str = "acme.odt"):
    return await client.put(URL, **_upload(data, name))


async def _file_count(db_session) -> int:
    return (
        await db_session.execute(select(func.count()).select_from(File))
    ).scalar_one()


# --- who may call it --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", ""),
        ("get", "/file"),
        ("get", "/tokens"),
        ("post", "/preview"),
        ("put", ""),
        ("delete", ""),
    ],
)
async def test_only_administrators_may_use_it(
    client, db_session, method: str, path: str
) -> None:
    assert (await getattr(client, method)(URL + path)).status_code == 401
    for role in ("billing", "manager", "consultant"):
        await login(client, db_session, role)
        assert (await getattr(client, method)(URL + path)).status_code == 403, role
        await client.post("/api/auth/logout")


# --- reading ----------------------------------------------------------------------------------


async def test_the_default_template_is_in_use_until_one_is_uploaded(
    client, db_session
) -> None:
    await _admin(client, db_session)

    info = (await client.get(URL)).json()

    assert info["source"] == "default" and info["filename"] == "invoice-template.odt"
    assert info["size_bytes"] == len(bundled_template())
    assert info["uploaded_by_name"] is None and info["uploaded_at"] is None
    assert "invoice_lines" in info["placeholders"]


async def test_the_default_template_downloads_as_an_odt(client, db_session) -> None:
    await _admin(client, db_session)

    response = await client.get(f"{URL}/file")

    assert response.status_code == 200 and response.content == bundled_template()
    assert response.headers["content-type"] == ODT
    assert response.headers["x-content-type-options"] == "nosniff"
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="invoice-template.odt"'
    )


async def test_the_token_catalogue_lists_every_placeholder(client, db_session) -> None:
    await _admin(client, db_session)

    tokens = (await client.get(f"{URL}/tokens")).json()

    assert {t["name"] for t in tokens} == set(TOKENS)
    lines = next(t for t in tokens if t["name"] == "invoice_lines")
    assert lines["kind"] == "lines" and lines["optional_capable"] is False
    assert all(t["description"] for t in tokens)


# --- uploading ---------------------------------------------------------------------------------


async def test_an_uploaded_template_becomes_the_one_in_use(client, db_session) -> None:
    user = await _admin(client, db_session)
    data = _custom()

    response = await _put(client, data)

    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["source"] == "custom" and saved["filename"] == "acme.odt"
    assert saved["size_bytes"] == len(data) and saved["warnings"] == []
    assert saved["uploaded_by_name"] == user.full_name and saved["uploaded_at"]
    info = (await client.get(URL)).json()
    assert info["source"] == "custom" and info["filename"] == "acme.odt"
    assert (await client.get(f"{URL}/file")).content == data
    assert (await client.get(f"{URL}/file")).headers["content-disposition"] == (
        'attachment; filename="acme.odt"'
    )


async def test_a_second_upload_replaces_the_first(client, db_session) -> None:
    await _admin(client, db_session)
    await _put(client, _custom("first"), "one.odt")
    second = _custom("second")

    assert (await _put(client, second, "two.odt")).status_code == 200

    assert (await client.get(f"{URL}/file")).content == second
    assert await _file_count(db_session) == 1


async def test_an_invalid_upload_changes_nothing(client, db_session) -> None:
    await _admin(client, db_session)
    good = _custom()
    await _put(client, good)
    bad = _rewrite(_replace("content.xml", "{{invoice_number}}", "{{nope}}"))

    response = await _put(client, bad, "bad.odt")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["message"] == "The template cannot be used"
    assert detail["problems"] == [
        {"part": "content.xml", "message": "Unknown placeholder", "snippet": "{{nope}}"}
    ]
    assert (await client.get(f"{URL}/file")).content == good
    assert await _file_count(db_session) == 1


async def test_every_problem_is_listed(client, db_session) -> None:
    await _admin(client, db_session)

    def two(parts: dict[str, bytes]) -> None:
        parts["content.xml"] = (
            parts["content.xml"]
            .replace(b"{{invoice_number}}", b"{{a}}")
            .replace(b"{{due_date}}", b"{{b}}")
        )

    response = await _put(client, _rewrite(two))

    snippets = [p["snippet"] for p in response.json()["detail"]["problems"]]
    assert "{{a}}" in snippets and "{{b}}" in snippets


async def test_a_macro_is_refused(client, db_session) -> None:
    await _admin(client, db_session)

    def add(parts: dict[str, bytes]) -> None:
        parts["Scripts/m.xml"] = b"<x/>"

    response = await _put(client, _rewrite(add))

    assert response.status_code == 422
    assert "macro" in response.json()["detail"]["problems"][0]["message"]


async def test_a_file_that_is_not_an_odt_is_refused(client, db_session) -> None:
    await _admin(client, db_session)

    assert (await _put(client, b"%PDF-1.7 not a template", "x.odt")).status_code == 422
    assert (await _put(client, bundled_template(), "template.pdf")).status_code == 415
    assert await _file_count(db_session) == 0


async def test_warnings_do_not_block_an_upload(client, db_session) -> None:
    await _admin(client, db_session)

    def no_mark(parts: dict[str, bytes]) -> None:
        parts["styles.xml"] = parts["styles.xml"].replace(b"{{draft_watermark}}", b"")

    response = await _put(client, _rewrite(no_mark))

    assert response.status_code == 200
    assert [w["message"] for w in response.json()["warnings"]] == [
        "The template has no {{draft_watermark}}, so previews carry no DRAFT mark"
    ]


async def test_the_trial_render_decides_too(
    client, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _admin(client, db_session)

    async def failing(template: bytes) -> tuple[bytes | None, list[Finding]]:
        return None, [Finding("template", "The sample invoice takes 2 pages")]

    monkeypatch.setattr("app.api.invoice_template.trial_render", failing)

    response = await _put(client, _custom())

    assert response.status_code == 422
    assert (
        response.json()["detail"]["problems"][0]["message"]
        == "The sample invoice takes 2 pages"
    )
    assert await _file_count(db_session) == 0


async def test_an_unavailable_engine_is_503_for_the_preview_and_the_upload(
    client, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.pdf.errors import PdfEngineNotInstalledError

    await _admin(client, db_session)

    async def missing(template: bytes) -> tuple[bytes | None, list[Finding]]:
        raise PdfEngineNotInstalledError("none")

    monkeypatch.setattr("app.api.invoice_template.trial_render", missing)

    for call in (client.put, client.post):
        url = URL if call == client.put else f"{URL}/preview"
        response = await call(url, **_upload(_custom()))
        assert response.status_code == 503
        assert response.json()["detail"] == "The PDF engine is not available"
    assert await _file_count(db_session) == 0


# --- previewing --------------------------------------------------------------------------------


async def test_a_preview_returns_the_sample_pdf_and_stores_nothing(
    client, db_session, _trial
) -> None:
    await _admin(client, db_session)
    data = _custom()

    response = await client.post(f"{URL}/preview", **_upload(data))

    assert response.status_code == 200 and response.content == SAMPLE_PDF
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert json.loads(response.headers["x-template-warnings"]) == []
    assert _trial == [data]
    assert await _file_count(db_session) == 0
    assert (await client.get(URL)).json()["source"] == "default"


async def test_a_preview_carries_the_warnings_in_a_header(client, db_session) -> None:
    await _admin(client, db_session)

    def no_mark(parts: dict[str, bytes]) -> None:
        parts["styles.xml"] = parts["styles.xml"].replace(b"{{draft_watermark}}", b"")

    response = await client.post(f"{URL}/preview", **_upload(_rewrite(no_mark)))

    warnings = json.loads(response.headers["x-template-warnings"])
    assert [w["part"] for w in warnings] == ["template"]


async def test_a_preview_of_an_invalid_file_is_422(client, db_session) -> None:
    await _admin(client, db_session)
    bad = _rewrite(_replace("content.xml", "{{invoice_number}}", "{{nope}}"))

    response = await client.post(f"{URL}/preview", **_upload(bad))

    assert response.status_code == 422 and response.json()["detail"]["problems"]


# --- resetting ---------------------------------------------------------------------------------


async def test_reset_discards_the_upload_and_is_idempotent(client, db_session) -> None:
    await _admin(client, db_session)
    await _put(client, _custom())

    assert (await client.delete(URL)).status_code == 204
    assert (await client.delete(URL)).status_code == 204

    assert (await client.get(URL)).json()["source"] == "default"
    assert (await client.get(f"{URL}/file")).content == bundled_template()
    assert await _file_count(db_session) == 0


# --- which template is used ---------------------------------------------------------------------


async def test_the_template_in_use_follows_the_upload_and_the_reset(
    client, db_session
) -> None:
    await _admin(client, db_session)
    assert (await resolve_template(db_session)).source == "default"

    data = _custom()
    await _put(client, data)
    db_session.expire_all()
    resolved = await resolve_template(db_session)
    assert resolved.source == "custom" and resolved.content == data

    await client.delete(URL)
    db_session.expire_all()
    assert (await resolve_template(db_session)).content == bundled_template()


async def test_an_unreadable_uploaded_template_is_an_error_not_a_silent_default(
    client, db_session, _storage_settings
) -> None:
    from app.pdf.errors import TemplateError

    await _admin(client, db_session)
    await _put(client, _custom())
    for path in _storage_settings.rglob("*.odt"):
        path.unlink()
    db_session.expire_all()

    with pytest.raises(TemplateError):
        await resolve_template(db_session)
    assert (await client.get(URL)).status_code == 404


async def test_issuing_uses_the_uploaded_template_and_leaves_earlier_invoices_alone(
    client, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[bytes | None] = []

    async def spy(data, template=None) -> bytes:
        seen.append(template)
        return fake_invoice_pdf(data.values["invoice_number"])

    monkeypatch.setattr(invoice_service, "render_invoice_pdf", spy)
    await _admin(client, db_session)
    await login(client, db_session, "billing")
    project = await make_project(db_session)
    body = {
        "project_id": str(project.id),
        "bill_from": {"name": "Ifrit"},
        "bill_to": {"name": "ACME"},
        "lines": [
            {"description": "Work", "quantity": "1", "uom": "hours", "unit_price": "10"}
        ],
    }

    async def issue() -> dict[str, Any]:
        created = await client.post("/api/invoices", json=body)
        return (await client.post(f"/api/invoices/{created.json()['id']}/issue")).json()

    first = await issue()
    first_pdf = (await client.get(f"/api/invoices/{first['id']}/pdf")).content
    await _sign_in(client, "administrator")
    custom = _custom()
    await _put(client, custom)
    await _sign_in(client, "billing")
    second = await issue()

    assert seen == [bundled_template(), custom]
    assert (await client.get(f"/api/invoices/{first['id']}/pdf")).content == first_pdf
    assert second["has_pdf"] is True


# --- with the real engine -----------------------------------------------------------------------


@pytest.mark.libreoffice
@pytest.mark.skipif(
    shutil.which("soffice") is None and shutil.which("libreoffice") is None,
    reason="LibreOffice is not installed",
)
async def test_an_uploaded_template_is_what_a_preview_and_an_issued_pdf_look_like(
    client, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The real trial render, not the fake.
    from app.pdf import trial

    monkeypatch.setattr("app.api.invoice_template.trial_render", trial.trial_render)
    await _admin(client, db_session)
    sentence = "ZZ-CUSTOM-SENTENCE-4711"
    data = _custom(sentence)

    preview = await client.post(f"{URL}/preview", **_upload(data))
    assert preview.status_code == 200
    assert sentence in PdfReader(io.BytesIO(preview.content)).pages[0].extract_text()

    assert (await _put(client, data)).status_code == 200
    await client.post("/api/auth/logout")
    await login(client, db_session, "billing")
    project = await make_project(db_session)
    created = await client.post(
        "/api/invoices",
        json={
            "project_id": str(project.id),
            "bill_from": {"name": "Ifrit"},
            "bill_to": {"name": "ACME"},
            "lines": [
                {
                    "description": "Work",
                    "quantity": "1",
                    "uom": "hours",
                    "unit_price": "10",
                }
            ],
        },
    )
    issued = await client.post(f"/api/invoices/{created.json()['id']}/issue")
    assert issued.status_code == 200
    pdf = (await client.get(f"/api/invoices/{created.json()['id']}/pdf")).content
    assert sentence in PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
