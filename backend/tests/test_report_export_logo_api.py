import csv
import io
import logging
import re
import zipfile

import pytest

from app.models.app_setting import AppSetting
from app.services import file_storage_service as storage
from app.services import report_export_service as svc
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


# --- the saved pdf-export settings -----------------------------------------------


async def _save_settings(db_session, **values) -> None:
    """Stores values in the pdf-export group directly, as an administrator's save would."""
    for key, value in values.items():
        db_session.add(AppSetting(group_name="pdf-export", key=key, value=value))
    await db_session.commit()


def _capture_pdf_logo(monkeypatch) -> list:
    """Records the logo handed to the PDF builder on each export (None when there is none)."""
    seen: list = []
    real = svc._build_pdf

    def build(rows, days, label, logo=None):
        seen.append(logo)
        return real(rows, days, label, logo)

    monkeypatch.setattr(svc, "_build_pdf", build)
    return seen


async def test_with_no_saved_settings_the_logo_is_drawn_at_the_default_height(
    client, db_session, monkeypatch
) -> None:
    await _setup(client, db_session)
    seen = _capture_pdf_logo(monkeypatch)

    response = await _export(client, "pdf")

    assert response.status_code == 200
    assert _images(response.content) >= 1
    (logo,) = seen
    assert logo.height_mm == pytest.approx(20)
    assert logo.width_mm == pytest.approx(60)  # the test logo is 3:1


async def test_the_saved_height_is_used_for_a_project_manager_without_administrator(
    client, db_session, monkeypatch
) -> None:
    file_id = await _setup(client, db_session)  # leaves the project manager signed in
    await _save_settings(db_session, logo_height_mm=35)
    seen = _capture_pdf_logo(monkeypatch)

    response = await _export(client, "pdf")

    assert response.status_code == 200
    (logo,) = seen
    assert (logo.width_mm, logo.height_mm) == (pytest.approx(105), pytest.approx(35))
    # They get it without being able to read the setting or download the logo.
    assert (await client.get("/api/settings/pdf-export")).status_code == 403
    assert (await client.get(f"/api/files/{file_id}/content")).status_code == 403


async def test_a_very_wide_logo_is_capped_at_the_width_limit(
    client, db_session, monkeypatch
) -> None:
    await _create(db_session, "admin@example.com", "administrator")
    await _create(db_session, "pm@example.com", "project_manager")
    await _login_as(client, "admin@example.com")
    wide = png_bytes((500, 100))
    assert (
        await client.put(LOGO_URL, files={"file": ("logo.png", wide, "image/png")})
    ).status_code == 200
    await _login_as(client, "pm@example.com")
    await _save_settings(db_session, logo_height_mm=60)
    seen = _capture_pdf_logo(monkeypatch)

    assert (await _export(client, "pdf")).status_code == 200

    (logo,) = seen
    assert (logo.width_mm, logo.height_mm) == (pytest.approx(180), pytest.approx(36))


async def test_with_the_logo_switched_off_the_pdf_has_no_image(
    client, db_session, monkeypatch
) -> None:
    await _setup(client, db_session)
    await _save_settings(db_session, export_logo=False, logo_height_mm=40)
    seen = _capture_pdf_logo(monkeypatch)

    response = await _export(client, "pdf")

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert _images(response.content) == 0
    assert seen == [None]


async def test_with_the_logo_switched_off_the_logo_file_is_not_read(
    client, db_session, monkeypatch
) -> None:
    await _setup(client, db_session)
    await _save_settings(db_session, export_logo=False)

    async def must_not_be_called(*args, **kwargs):
        raise AssertionError("the logo file was read although the logo is switched off")

    monkeypatch.setattr(storage, "read_setting_file_bytes", must_not_be_called)

    response = await _export(client, "pdf")

    assert response.status_code == 200
    assert _images(response.content) == 0


async def test_an_invalid_saved_height_falls_back_to_the_default(
    client, db_session, monkeypatch
) -> None:
    await _setup(client, db_session)
    await _save_settings(db_session, logo_height_mm=500)
    seen = _capture_pdf_logo(monkeypatch)

    response = await _export(client, "pdf")

    assert response.status_code == 200
    (logo,) = seen
    assert logo.height_mm == pytest.approx(20)


async def test_a_missing_logo_file_still_exports_when_the_logo_is_switched_on(
    client, db_session, caplog
) -> None:
    await _setup(client, db_session)
    await _save_settings(db_session, export_logo=True, logo_height_mm=45)
    logo = await storage.get_setting_file(db_session, "org_logo")
    storage.resolve_storage_path(logo.stored_file.bucket_key).unlink()

    with caplog.at_level(logging.WARNING):
        response = await _export(client, "pdf")

    assert response.status_code == 200
    assert _images(response.content) == 0
    assert "Organization logo left out of the PDF export" in caplog.text


async def test_excel_and_csv_do_not_read_the_pdf_settings_or_the_logo(
    client, db_session, monkeypatch
) -> None:
    await _setup(client, db_session)
    csv_default = (await _export(client, "csv")).content
    await _save_settings(db_session, export_logo=False, logo_height_mm=60)

    async def must_not_be_called(*args, **kwargs):
        raise AssertionError("a non-PDF export touched the PDF logo settings")

    monkeypatch.setattr(svc, "_load_pdf_logo", must_not_be_called)

    xlsx = await _export(client, "xlsx")
    csv_after = await _export(client, "csv")

    assert xlsx.status_code == 200
    assert csv_after.content == csv_default
