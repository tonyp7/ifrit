import csv
import io
import logging
import re
import zipfile

from app.services import file_storage_service as storage
from tests.factories import create_user
from tests.image_helpers import png_bytes

EXPORT_URL = "/api/time-entries/report/export"
LOGO_URL = "/api/settings/org-logo"
PARAMS = {"period_type": "month", "start_date": "2026-08-01", "end_date": "2026-08-31"}


async def _create(db_session, name_id: str, role: str) -> None:
    await create_user(db_session, name_id=name_id, password="pw", role_name=role)


async def _login_as(client, name_id: str) -> None:
    response = await client.post(
        "/api/auth/login", json={"email": name_id, "password": "pw"}
    )
    assert response.status_code == 200


async def _setup(client, db_session) -> str:
    """An administrator who uploads a logo, and a project manager who is not an
    administrator. Returns the logo's file id; leaves the project manager signed in."""
    await _create(db_session, "admin@example.com", "administrator")
    await _create(db_session, "pm@example.com", "project_manager")
    await _login_as(client, "admin@example.com")
    upload = await client.put(
        LOGO_URL, files={"file": ("logo.png", png_bytes((120, 40)), "image/png")}
    )
    assert upload.status_code == 200
    file_id = upload.json()["file_id"]
    await _login_as(client, "pm@example.com")
    return file_id


def _images(pdf: bytes) -> int:
    return len(re.findall(rb"/Subtype\s*/Image", pdf))


async def _export(client, export_format: str):
    return await client.get(EXPORT_URL, params={**PARAMS, "format": export_format})


async def test_a_project_manager_without_the_administrator_role_gets_the_logo(
    client, db_session
) -> None:
    file_id = await _setup(client, db_session)

    response = await _export(client, "pdf")

    assert response.status_code == 200
    assert _images(response.content) >= 1
    # They get the logo inside the PDF without being able to download the logo itself.
    assert (await client.get(f"/api/files/{file_id}/content")).status_code == 403
    assert (await client.get(LOGO_URL)).status_code == 403


async def test_a_pdf_without_an_uploaded_logo_has_no_image(client, db_session) -> None:
    await _create(db_session, "pm@example.com", "project_manager")
    await _login_as(client, "pm@example.com")

    response = await _export(client, "pdf")

    assert response.status_code == 200
    assert _images(response.content) == 0


async def test_a_deleted_logo_file_still_exports_with_a_warning(
    client, db_session, caplog
) -> None:
    await _setup(client, db_session)
    logo = await storage.get_setting_file(db_session, "org_logo")
    storage.resolve_storage_path(logo.stored_file.bucket_key).unlink()

    with caplog.at_level(logging.WARNING):
        response = await _export(client, "pdf")

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert _images(response.content) == 0
    # The warning names the error type only, never a storage path.
    assert [m for m in caplog.messages if "Organization logo" in m] == [
        "Organization logo left out of the PDF export: FileNotFoundError"
    ]


async def test_an_undecodable_logo_still_exports_with_a_warning(
    client, db_session, caplog
) -> None:
    await _setup(client, db_session)
    logo = await storage.get_setting_file(db_session, "org_logo")
    storage.resolve_storage_path(logo.stored_file.bucket_key).write_bytes(
        b"not an image"
    )

    with caplog.at_level(logging.WARNING):
        response = await _export(client, "pdf")

    assert response.status_code == 200
    assert _images(response.content) == 0
    assert "Organization logo left out of the PDF export" in caplog.text


async def test_excel_and_csv_exports_ignore_the_logo(client, db_session) -> None:
    await _create(db_session, "pm@example.com", "project_manager")
    await _login_as(client, "pm@example.com")
    csv_before = (await _export(client, "csv")).content

    await _create(db_session, "admin@example.com", "administrator")
    await _login_as(client, "admin@example.com")
    assert (
        await client.put(
            LOGO_URL, files={"file": ("logo.png", png_bytes((120, 40)), "image/png")}
        )
    ).status_code == 200
    await _login_as(client, "pm@example.com")

    xlsx = await _export(client, "xlsx")
    csv_after = await _export(client, "csv")

    assert xlsx.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(xlsx.content)).namelist()
    assert not [n for n in names if n.startswith("xl/media") or "drawing" in n]
    assert csv_after.content == csv_before
    assert next(csv.reader(io.StringIO(csv_after.text)))[0] == "Project Name"
