import io
import uuid

from PIL import Image
from sqlalchemy import func, select

from app.models.file import File
from tests.conftest import TEST_MAX_UPLOAD_BYTES
from tests.factories import create_user
from tests.image_helpers import jpeg_bytes, png_bytes, webp_bytes

LOGO_URL = "/api/settings/org-logo"


async def _login(client, db_session, role: str) -> None:
    await create_user(
        db_session, name_id=f"{role}@example.com", password="pw", role_name=role
    )
    response = await client.post(
        "/api/auth/login", json={"email": f"{role}@example.com", "password": "pw"}
    )
    assert response.status_code == 200


def _logo(data: bytes, name: str, content_type: str = "image/png") -> dict:
    return {"file": (name, data, content_type)}


async def _file_count(db_session) -> int:
    return (
        await db_session.execute(select(func.count()).select_from(File))
    ).scalar_one()


# --- access ----------------------------------------------------------------------


async def test_signed_out_clients_get_401(client) -> None:
    assert (await client.get(LOGO_URL)).status_code == 401
    assert (
        await client.put(LOGO_URL, files=_logo(png_bytes(), "a.png"))
    ).status_code == 401
    assert (await client.delete(LOGO_URL)).status_code == 401
    assert (await client.get(f"/api/files/{uuid.uuid4()}/content")).status_code == 401


async def test_non_administrators_get_403(client, db_session) -> None:
    await _login(client, db_session, "project_admin")

    assert (await client.get(LOGO_URL)).status_code == 403
    assert (
        await client.put(LOGO_URL, files=_logo(png_bytes(), "a.png"))
    ).status_code == 403
    assert (await client.delete(LOGO_URL)).status_code == 403


async def test_a_non_administrator_cannot_download_a_setting_file(
    client, db_session
) -> None:
    await _login(client, db_session, "administrator")
    file_id = (await client.put(LOGO_URL, files=_logo(png_bytes(), "a.png"))).json()[
        "file_id"
    ]
    await client.post("/api/auth/logout")

    await _login(client, db_session, "project_admin")
    response = await client.get(f"/api/files/{file_id}/content")

    assert response.status_code == 403


# --- upload, details, download ---------------------------------------------------


async def test_no_logo_returns_404(client, db_session) -> None:
    await _login(client, db_session, "administrator")

    assert (await client.get(LOGO_URL)).status_code == 404


async def test_upload_then_details_then_download(client, db_session) -> None:
    await _login(client, db_session, "administrator")

    put = await client.put(LOGO_URL, files=_logo(png_bytes((40, 20)), "My Logo.png"))
    assert put.status_code == 200
    body = put.json()
    assert body["original_filename"] == "My Logo.png"
    assert body["content_type"] == "image/png"

    details = await client.get(LOGO_URL)
    assert details.status_code == 200
    assert details.json()["file_id"] == body["file_id"]

    content = await client.get(f"/api/files/{body['file_id']}/content")
    assert content.status_code == 200
    assert content.headers["content-type"] == "image/png"
    assert content.headers["x-content-type-options"] == "nosniff"
    assert content.headers["cache-control"] == "private, no-cache"
    assert Image.open(io.BytesIO(content.content)).size == (40, 20)


async def test_jpeg_and_webp_are_accepted(client, db_session) -> None:
    await _login(client, db_session, "administrator")

    jpeg = await client.put(LOGO_URL, files=_logo(jpeg_bytes(), "a.jpg", "image/jpeg"))
    assert jpeg.status_code == 200
    assert jpeg.json()["content_type"] == "image/jpeg"
    webp = await client.put(LOGO_URL, files=_logo(webp_bytes(), "a.webp", "image/webp"))
    assert webp.status_code == 200
    assert webp.json()["content_type"] == "image/webp"


async def test_replacing_leaves_one_logo_and_a_new_file_id(client, db_session) -> None:
    await _login(client, db_session, "administrator")
    first = (await client.put(LOGO_URL, files=_logo(png_bytes(), "one.png"))).json()

    second = (
        await client.put(LOGO_URL, files=_logo(jpeg_bytes(), "two.jpg", "image/jpeg"))
    ).json()

    assert second["file_id"] != first["file_id"]
    assert (await client.get(LOGO_URL)).json()["file_id"] == second["file_id"]
    assert await _file_count(db_session) == 1
    assert (
        await client.get(f"/api/files/{first['file_id']}/content")
    ).status_code == 404


async def test_delete_removes_the_logo(client, db_session) -> None:
    await _login(client, db_session, "administrator")
    file_id = (await client.put(LOGO_URL, files=_logo(png_bytes(), "a.png"))).json()[
        "file_id"
    ]

    assert (await client.delete(LOGO_URL)).status_code == 204

    assert (await client.get(LOGO_URL)).status_code == 404
    assert (await client.get(f"/api/files/{file_id}/content")).status_code == 404
    assert (await client.delete(LOGO_URL)).status_code == 404


async def test_unknown_file_returns_404(client, db_session) -> None:
    await _login(client, db_session, "administrator")

    assert (await client.get(f"/api/files/{uuid.uuid4()}/content")).status_code == 404


# --- rejections leave the current logo unchanged ---------------------------------


async def _assert_rejected(client, db_session, files: dict, status: int) -> None:
    current = (await client.get(LOGO_URL)).json()
    response = await client.put(LOGO_URL, files=files)
    assert response.status_code == status, response.text
    assert (await client.get(LOGO_URL)).json()["file_id"] == current["file_id"]
    assert await _file_count(db_session) == 1


async def test_rejected_uploads_keep_the_current_logo(client, db_session) -> None:
    await _login(client, db_session, "administrator")
    await client.put(LOGO_URL, files=_logo(png_bytes(), "current.png"))

    gif = io.BytesIO()
    Image.new("RGB", (4, 4)).save(gif, format="GIF")
    await _assert_rejected(
        client, db_session, _logo(gif.getvalue(), "a.gif", "image/gif"), 415
    )
    # The client-declared content type is ignored: a script is a script.
    await _assert_rejected(
        client, db_session, _logo(b"<?php ?>", "a.png", "image/png"), 415
    )
    await _assert_rejected(
        client, db_session, _logo(png_bytes(), "a.jpg", "image/jpeg"), 415
    )
    await _assert_rejected(
        client, db_session, _logo(png_bytes((300, 300))[:100], "a.png"), 422
    )
    too_big = png_bytes() + b"\0" * TEST_MAX_UPLOAD_BYTES
    await _assert_rejected(client, db_session, _logo(too_big, "a.png"), 413)


async def test_a_rejection_carries_a_user_facing_reason(client, db_session) -> None:
    await _login(client, db_session, "administrator")

    response = await client.put(LOGO_URL, files=_logo(b"nope", "a.gif", "image/gif"))

    assert response.status_code == 415
    assert response.json()["detail"] == "This file type is not allowed"


# --- request body limit (in-app layer behind the proxy limit) --------------------


async def test_a_body_far_over_the_limit_is_cut_off(client, db_session) -> None:
    await _login(client, db_session, "administrator")
    huge = b"\0" * (TEST_MAX_UPLOAD_BYTES + 2 * 1024 * 1024)

    response = await client.put(LOGO_URL, files=_logo(huge, "a.png"))

    assert response.status_code == 413
    assert await _file_count(db_session) == 0


async def test_a_chunked_body_over_the_limit_is_cut_off(client, db_session) -> None:
    await _login(client, db_session, "administrator")

    # A well-formed multipart body sent without a declared length, so only the
    # streaming count can stop it.
    async def chunks():
        yield (
            b'--x\r\nContent-Disposition: form-data; name="file"; filename="a.png"\r\n'
            b"Content-Type: image/png\r\n\r\n"
        )
        for _ in range(40):
            yield b"\0" * 65536
        yield b"\r\n--x--\r\n"

    response = await client.put(
        LOGO_URL,
        content=chunks(),
        headers={"content-type": "multipart/form-data; boundary=x"},
    )

    assert response.status_code == 413
