import hashlib
import io
import logging
import stat
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models.file import File, SettingFile, StoredFile
from app.models.user import User
from app.services import file_storage_service as storage
from tests.conftest import TEST_MAX_UPLOAD_BYTES
from tests.factories import create_user
from tests.image_helpers import jpeg_bytes, make_upload, png_bytes, webp_bytes


async def _admin(db: AsyncSession) -> User:
    existing = (
        await db.execute(select(User).where(User.name_id == "admin@example.com"))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    return await create_user(
        db, name_id="admin@example.com", password="pw", role_name="administrator"
    )


async def _attach(db: AsyncSession, data: bytes, filename: str, user=None) -> File:
    user = user or await _admin(db)
    return await storage.attach_setting_file(
        db,
        upload=make_upload(data, filename),
        setting_key="org_logo",
        uploaded_by=user,
    )


def _stored_files_on_disk(root: Path) -> list[Path]:
    return [
        p
        for p in root.rglob("*")
        if p.is_file() and storage.TMP_DIR_NAME not in p.parts
    ]


def _staged_files(root: Path) -> list[Path]:
    tmp = root / storage.TMP_DIR_NAME
    return [p for p in tmp.rglob("*") if p.is_file()] if tmp.exists() else []


async def _count(db: AsyncSession, model: type) -> int:
    return (await db.execute(select(func.count()).select_from(model))).scalar_one()


async def _assert_nothing_persisted(db: AsyncSession, root: Path) -> None:
    assert await _count(db, File) == 0
    assert await _count(db, StoredFile) == 0
    assert _stored_files_on_disk(root) == []
    assert _staged_files(root) == []


# --- storage layout --------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "name", "content_type", "extension"),
    [
        (png_bytes(), "logo.png", "image/png", ".png"),
        (jpeg_bytes(), "logo.JPEG", "image/jpeg", ".jpg"),
        (webp_bytes(), "logo.webp", "image/webp", ".webp"),
    ],
)
async def test_stores_images_in_a_hash_sharded_path(
    db_session, _storage_settings, data, name, content_type, extension
):
    file = await _attach(db_session, data, name)

    stored = file.stored_file
    assert stored.detected_content_type == content_type
    assert stored.status == "ready"
    path = storage.resolve_storage_path(stored.bucket_key)
    assert path.suffix == extension
    assert path.parent.parts[-2:] == (
        stored.checksum_sha256[0:2],
        stored.checksum_sha256[2:4],
    )
    content = path.read_bytes()
    assert hashlib.sha256(content).hexdigest() == stored.checksum_sha256
    assert stored.size_bytes == len(content)
    # Owner read/write and group read only.
    assert stat.S_IMODE(path.stat().st_mode) == 0o640
    assert _staged_files(_storage_settings) == []


async def test_client_file_name_is_never_used_on_disk(db_session, _storage_settings):
    file = await _attach(db_session, png_bytes(), "../../evil.php.png")

    on_disk = _stored_files_on_disk(_storage_settings)
    assert len(on_disk) == 1
    assert on_disk[0].resolve().is_relative_to(_storage_settings.resolve())
    assert "evil" not in str(on_disk[0])
    assert on_disk[0].suffix == ".png"
    assert file.original_filename == "evil.php.png"


def test_a_path_escaping_the_root_is_refused():
    with pytest.raises(storage.StoragePathError):
        storage.resolve_storage_path("../../etc/passwd")
    with pytest.raises(storage.StoragePathError):
        storage.resolve_storage_path("/etc/passwd")


# --- validation ------------------------------------------------------------------


async def test_disallowed_extension_is_rejected(db_session, _storage_settings):
    gif = io.BytesIO()
    Image.new("RGB", (4, 4)).save(gif, format="GIF")

    with pytest.raises(storage.UnsupportedFileTypeError):
        await _attach(db_session, gif.getvalue(), "logo.gif")
    await _assert_nothing_persisted(db_session, _storage_settings)


async def test_script_disguised_as_png_is_rejected(db_session, _storage_settings):
    with pytest.raises(storage.UnsupportedFileTypeError):
        await _attach(db_session, b"<?php system($_GET['c']); ?>", "logo.png")
    await _assert_nothing_persisted(db_session, _storage_settings)


async def test_extension_disagreeing_with_content_is_rejected(
    db_session, _storage_settings
):
    with pytest.raises(storage.UnsupportedFileTypeError):
        await _attach(db_session, png_bytes(), "logo.jpg")
    await _assert_nothing_persisted(db_session, _storage_settings)


async def test_oversized_upload_is_rejected(db_session, _storage_settings):
    data = png_bytes() + b"\0" * TEST_MAX_UPLOAD_BYTES

    with pytest.raises(storage.FileTooLargeError):
        await _attach(db_session, data, "logo.png")
    await _assert_nothing_persisted(db_session, _storage_settings)


async def test_upload_at_the_limit_is_accepted(db_session):
    image = png_bytes()
    # Trailing bytes after the PNG's end chunk are ignored by the decoder, which is what
    # lets this valid image be exactly as large as the limit.
    data = image + b"\0" * (TEST_MAX_UPLOAD_BYTES - len(image))
    assert len(data) == settings.max_upload_bytes

    file = await _attach(db_session, data, "logo.png")

    assert file.stored_file.size_bytes < len(data)


async def test_corrupt_image_is_rejected(db_session, _storage_settings):
    truncated = png_bytes((200, 200))[:200]

    with pytest.raises(storage.InvalidImageError):
        await _attach(db_session, truncated, "logo.png")
    await _assert_nothing_persisted(db_session, _storage_settings)


async def test_decompression_bomb_is_rejected(db_session, _storage_settings):
    # A flat 6000x6000 canvas compresses to a few KB but is 36 megapixels once decoded.
    buffer = io.BytesIO()
    Image.new("L", (6000, 6000)).save(buffer, format="PNG", optimize=True)
    assert len(buffer.getvalue()) < TEST_MAX_UPLOAD_BYTES

    with pytest.raises(storage.InvalidImageError):
        await _attach(db_session, buffer.getvalue(), "logo.png")
    await _assert_nothing_persisted(db_session, _storage_settings)


async def test_rejection_is_logged_with_its_reason(db_session, caplog):
    with (
        caplog.at_level(logging.WARNING, logger=storage.logger.name),
        pytest.raises(storage.UnsupportedFileTypeError),
    ):
        await _attach(db_session, b"nope", "logo.gif")

    assert "reason=unsupported_type" in caplog.text
    assert "logo.gif" in caplog.text


# --- re-encoding -----------------------------------------------------------------


def _stored_image(file: File) -> Image.Image:
    path = storage.resolve_storage_path(file.stored_file.bucket_key)
    return Image.open(io.BytesIO(path.read_bytes()))


async def test_exif_metadata_is_removed(db_session):
    original = jpeg_bytes(gps=True)
    assert len(Image.open(io.BytesIO(original)).getexif()) > 0

    file = await _attach(db_session, original, "photo.jpg")

    assert len(_stored_image(file).getexif()) == 0


async def test_exif_orientation_is_applied_to_the_pixels(db_session):
    # Orientation 6 means "rotate 90 degrees clockwise to display upright".
    file = await _attach(db_session, jpeg_bytes((40, 20), orientation=6), "photo.jpg")

    image = _stored_image(file)
    assert image.size == (20, 40)
    assert image.getexif().get(0x0112) is None


async def test_png_transparency_is_kept(db_session):
    original = png_bytes((8, 8), "RGBA", (255, 0, 0, 0))

    file = await _attach(db_session, original, "logo.png")

    image = _stored_image(file)
    assert image.mode == "RGBA"
    assert image.getpixel((0, 0))[3] == 0


async def test_stored_bytes_are_not_the_original_bytes(db_session):
    original = png_bytes() + b"<script>alert(1)</script>"

    file = await _attach(db_session, original, "logo.png")

    content = storage.resolve_storage_path(file.stored_file.bucket_key).read_bytes()
    assert b"<script>" not in content


# --- display name ----------------------------------------------------------------


def test_display_name_loses_control_characters_and_path_parts():
    assert storage.sanitize_display_name("a\nb\x00c.png") == "abc.png"
    assert storage.sanitize_display_name("C:\\dir\\logo.png") == "logo.png"
    assert storage.sanitize_display_name("") == "file"
    assert storage.sanitize_display_name(None) == "file"


def test_display_name_is_capped_at_255_characters():
    assert len(storage.sanitize_display_name("x" * 400 + ".png")) == 255


# --- atomicity and failure -------------------------------------------------------


async def test_a_failed_write_leaves_nothing_behind(
    db_session, _storage_settings, monkeypatch
):
    def fail(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(storage, "_move_into_place", fail)

    with pytest.raises(OSError, match="disk full"):
        await _attach(db_session, png_bytes(), "logo.png")
    await _assert_nothing_persisted(db_session, _storage_settings)


async def test_a_failure_after_the_write_removes_the_written_file(
    db_session, _storage_settings, monkeypatch
):
    user = await _admin(db_session)
    real_commit = db_session.commit

    async def failing_commit():
        raise RuntimeError("commit failed")

    monkeypatch.setattr(db_session, "commit", failing_commit)
    with pytest.raises(RuntimeError, match="commit failed"):
        await storage.attach_setting_file(
            db_session,
            upload=make_upload(png_bytes(), "logo.png"),
            setting_key="org_logo",
            uploaded_by=user,
        )
    monkeypatch.setattr(db_session, "commit", real_commit)

    assert _stored_files_on_disk(_storage_settings) == []
    assert _staged_files(_storage_settings) == []
    assert await _count(db_session, File) == 0


# --- persistence: dedup and replace ----------------------------------------------


async def test_same_content_uploaded_again_is_stored_once(
    db_session, _storage_settings
):
    data = png_bytes((16, 16))
    first = await _attach(db_session, data, "logo.png")
    assert await storage.delete_setting_file(db_session, "org_logo")

    second = await _attach(db_session, data, "again.png")

    assert second.id != first.id
    assert second.stored_file_id == first.stored_file_id
    assert await _count(db_session, StoredFile) == 1
    assert len(_stored_files_on_disk(_storage_settings)) == 1
    assert _staged_files(_storage_settings) == []


async def test_replace_leaves_exactly_one_logo(db_session):
    first = await _attach(db_session, png_bytes((10, 10)), "one.png")

    second = await _attach(db_session, jpeg_bytes((12, 12)), "two.jpg")

    assert second.id != first.id
    assert await _count(db_session, SettingFile) == 1
    assert await _count(db_session, File) == 1
    current = await storage.get_setting_file(db_session, "org_logo")
    assert current is not None
    assert current.id == second.id
    assert current.original_filename == "two.jpg"


async def test_failed_replace_keeps_the_current_logo(db_session, _storage_settings):
    first = await _attach(db_session, png_bytes(), "one.png")
    before = _stored_files_on_disk(_storage_settings)

    with pytest.raises(storage.UnsupportedFileTypeError):
        await _attach(db_session, b"not an image", "two.png")

    current = await storage.get_setting_file(db_session, "org_logo")
    assert current is not None
    assert current.id == first.id
    assert _stored_files_on_disk(_storage_settings) == before
    assert _staged_files(_storage_settings) == []


async def test_concurrent_replacements_leave_exactly_one_logo(db_session):
    import asyncio

    user = await _admin(db_session)
    factory = async_sessionmaker(db_session.bind, expire_on_commit=False)

    async def upload(data: bytes, name: str) -> File:
        async with factory() as session:
            return await storage.attach_setting_file(
                session,
                upload=make_upload(data, name),
                setting_key="org_logo",
                uploaded_by=user,
            )

    results = await asyncio.gather(
        upload(png_bytes((10, 10)), "a.png"), upload(png_bytes((11, 11)), "b.png")
    )

    assert len(results) == 2
    assert await _count(db_session, SettingFile) == 1
    assert await _count(db_session, File) == 1


async def test_delete_setting_file_reports_whether_anything_was_removed(db_session):
    assert await storage.delete_setting_file(db_session, "org_logo") is False
    await _attach(db_session, png_bytes(), "logo.png")
    assert await storage.delete_setting_file(db_session, "org_logo") is True
    assert await storage.get_setting_file(db_session, "org_logo") is None
