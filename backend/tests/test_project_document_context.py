"""The project document upload context: what it accepts, and what it must not.

`tests/fixtures/documents` holds one small, real sample per accepted extension (made with
LibreOffice, ffmpeg, openssl, 7z and heif-enc; `.msg`, `.key` and `.rar` are minimal
hand-built containers). Detected types depend on the libmagic version, so these samples are
what pins the context's allowed-type table.
"""

import os
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.core.config import settings
from app.services import file_storage_service as storage
from tests.conftest import TEST_MAX_UPLOAD_BYTES
from tests.image_helpers import jpeg_bytes, make_upload

SAMPLES = Path(__file__).parent / "fixtures" / "documents"
CONTEXT = storage.PROJECT_DOCUMENT_CONTEXT


async def _prepare(data: bytes, filename: str) -> storage.PreparedUpload:
    return await storage.prepare_upload(make_upload(data, filename), CONTEXT)


def _staged_files(root: Path) -> list[Path]:
    tmp = root / storage.TMP_DIR_NAME
    return list(tmp.iterdir()) if tmp.exists() else []


def _sample_extensions() -> list[str]:
    return sorted(path.suffix for path in SAMPLES.glob("sample.*"))


def test_every_accepted_extension_has_a_real_sample() -> None:
    # `.jpeg` shares the `.jpg` entry and sample.
    assert set(_sample_extensions()) | {".jpeg"} == set(CONTEXT.allowed)


@pytest.mark.parametrize("extension", _sample_extensions())
async def test_a_real_sample_of_each_accepted_format_is_accepted(
    extension: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Some real samples (a LibreOffice .ppt) are larger than the suite's small limit.
    monkeypatch.setattr(settings, "max_upload_bytes", 5_000_000)
    data = (SAMPLES / f"sample{extension}").read_bytes()

    prepared = await _prepare(data, f"Some Name{extension.upper()}")

    # Stored under our own extension, whatever case the client spelled it in.
    assert prepared.extension == CONTEXT.allowed[extension].disk_extension
    # .key is the one real sample libmagic only calls a zip: the member check accepts it.
    expected = CONTEXT.allowed[extension].content_types | {"application/zip"}
    assert prepared.content_type in expected
    prepared.tmp_path.unlink()


async def test_jpeg_extension_is_accepted_like_jpg() -> None:
    prepared = await _prepare((SAMPLES / "sample.jpg").read_bytes(), "photo.jpeg")
    assert prepared.extension == ".jpg"
    prepared.tmp_path.unlink()


async def test_a_pdf_is_stored_exactly_as_received() -> None:
    data = (SAMPLES / "sample.pdf").read_bytes()

    prepared = await _prepare(data, "contract.pdf")

    assert prepared.tmp_path.read_bytes() == data
    assert prepared.size_bytes == len(data)
    prepared.tmp_path.unlink()


async def test_a_jpeg_in_the_document_context_is_still_re_encoded() -> None:
    data = jpeg_bytes(gps=True)

    prepared = await _prepare(data, "site.jpg")

    stored = prepared.tmp_path.read_bytes()
    assert stored != data
    assert b"TestCamera" not in stored
    prepared.tmp_path.unlink()


async def test_a_rejected_upload_leaves_nothing_staged(
    _storage_settings: Path,
) -> None:
    with pytest.raises(storage.UnsupportedFileTypeError):
        await _prepare(b"MZ\x90\x00 definitely not a pdf", "invoice.pdf")

    assert _staged_files(_storage_settings) == []


@pytest.mark.parametrize(
    ("data", "filename"),
    [
        (b"MZ\x90\x00\x03\x00\x00\x00 windows executable", "setup.exe"),
        (b"#!/bin/sh\necho owned\n", "report.pdf"),
        (b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff" + b"\x00" * 64, "invoice.pdf"),
        (b"<script>alert(1)</script>", "notes.pdf"),
        (os.urandom(2048), "notes.txt"),
        (b"#!/bin/sh\necho owned\n", "notes.txt"),
        (b"just text", "archive.zip"),
        (b"just text", "no-extension"),
    ],
)
async def test_content_that_disagrees_with_its_extension_is_rejected(
    data: bytes, filename: str
) -> None:
    with pytest.raises(storage.UnsupportedFileTypeError):
        await _prepare(data, filename)


async def test_a_plain_zip_renamed_to_an_office_extension_is_rejected() -> None:
    plain_zip = (SAMPLES / "sample.zip").read_bytes()

    for name in ("contract.docx", "budget.xlsx", "deck.pptx", "letter.odt"):
        with pytest.raises(storage.UnsupportedFileTypeError):
            await _prepare(plain_zip, name)


async def test_an_office_file_renamed_to_another_extension_is_rejected() -> None:
    docx = (SAMPLES / "sample.docx").read_bytes()

    with pytest.raises(storage.UnsupportedFileTypeError):
        await _prepare(docx, "contract.xlsx")
    with pytest.raises(storage.UnsupportedFileTypeError):
        await _prepare(docx, "contract.pdf")


async def test_a_plain_zip_named_key_is_rejected() -> None:
    with pytest.raises(storage.UnsupportedFileTypeError):
        await _prepare((SAMPLES / "sample.zip").read_bytes(), "talk.key")


async def test_an_office_zip_libmagic_cannot_see_into_is_judged_by_its_members() -> None:
    # With only the zip's first bytes shown, libmagic can say no more than "a zip", as
    # it would for a large document whose telling members lie further in.
    short_sight = storage.UploadContext(
        allowed={".docx": CONTEXT.allowed[".docx"]}, sniff_bytes=64
    )
    docx = (SAMPLES / "sample.docx").read_bytes()
    assert storage._sniff(BytesIO(docx), 64) == "application/zip"

    prepared = await storage.prepare_upload(make_upload(docx, "big.docx"), short_sight)
    prepared.tmp_path.unlink()

    plain_zip = (SAMPLES / "sample.zip").read_bytes()
    with pytest.raises(storage.UnsupportedFileTypeError):
        await storage.prepare_upload(make_upload(plain_zip, "big.docx"), short_sight)


async def test_a_corrupt_zip_named_docx_is_rejected() -> None:
    short_sight = storage.UploadContext(
        allowed={".docx": CONTEXT.allowed[".docx"]}, sniff_bytes=64
    )
    broken = b"PK\x03\x04" + b"\x00" * 200

    with pytest.raises(storage.UnsupportedFileTypeError):
        await storage.prepare_upload(make_upload(broken, "x.docx"), short_sight)


async def test_a_zip_member_named_like_a_marker_inside_a_bomb_is_not_decompressed() -> None:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"\x00" * 5_000_000)
    short_sight = storage.UploadContext(
        allowed={".docx": CONTEXT.allowed[".docx"]}, sniff_bytes=64
    )

    # 5 MB of zeros compress to a few KB: accepted by name, never inflated.
    prepared = await storage.prepare_upload(
        make_upload(buffer.getvalue(), "x.docx"), short_sight
    )
    assert prepared.size_bytes == len(buffer.getvalue())
    prepared.tmp_path.unlink()


async def test_the_client_content_type_is_ignored() -> None:
    upload = UploadFile(
        file=BytesIO(b"#!/bin/sh\necho owned\n"),
        filename="report.pdf",
        headers=Headers({"content-type": "application/pdf"}),
    )

    with pytest.raises(storage.UnsupportedFileTypeError):
        await storage.prepare_upload(upload, CONTEXT)


async def test_an_oversized_file_is_rejected_with_413_semantics() -> None:
    data = (SAMPLES / "sample.pdf").read_bytes()
    padded = data + b"\n" * (TEST_MAX_UPLOAD_BYTES + 1 - len(data))

    with pytest.raises(storage.FileTooLargeError) as caught:
        await _prepare(padded, "big.pdf")
    assert caught.value.status_code == 413


async def test_a_file_at_exactly_the_limit_is_accepted() -> None:
    data = (SAMPLES / "sample.pdf").read_bytes()
    padded = data + b"\n" * (TEST_MAX_UPLOAD_BYTES - len(data))
    assert len(padded) == TEST_MAX_UPLOAD_BYTES

    prepared = await _prepare(padded, "exact.pdf")

    assert prepared.size_bytes == TEST_MAX_UPLOAD_BYTES
    prepared.tmp_path.unlink()


async def test_a_disallowed_extension_is_rejected_with_415() -> None:
    with pytest.raises(storage.UnsupportedFileTypeError) as caught:
        await _prepare(b"MZ\x90\x00", "setup.exe")
    assert caught.value.status_code == 415
