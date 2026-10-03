"""Stores uploaded files on disk and records them in the database.

The whole upload path lives here, in this order, rejecting at the first failure:
the file's size, then its extension, then the type sniffed from its bytes (which
must be one the extension may contain), then, for JPEG, PNG and WebP images, a decode
and fresh re-encode. Re-encoded images are persisted only as the re-encoded bytes, never
the original, which drops metadata and anything hidden in the file; every other
accepted format cannot be re-rendered and is stored exactly as received. The result is
written to a temporary file and moved into a hash-sharded path, so a partially written
file is never readable at its final location.

What an upload accepts is decided per upload context (see `UploadContext`), so the
organization logo stays images-only while project documents take many more formats.

Pillow, libmagic and disk I/O are blocking, so they run in a worker thread.
"""

import asyncio
import hashlib
import logging
import os
import shutil
import unicodedata
import uuid
import zipfile
from dataclasses import dataclass
from io import BufferedIOBase
from pathlib import Path
from typing import IO, Literal, cast

import magic
from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.file import File, ProjectFile, SettingFile, SettingKey, StoredFile
from app.models.user import User

logger = logging.getLogger(__name__)

# Folder below STORAGE_ROOT where uploads are staged before being moved into place.
# Same filesystem as the final location, which is what makes the move atomic.
TMP_DIR_NAME = ".tmp"

# A safety limit, not something to tune per deployment: a tiny file can declare a huge
# canvas, and decoding it would exhaust memory. Checked from the image header before
# any pixels are decoded.
MAX_IMAGE_PIXELS = 25_000_000

DISPLAY_NAME_MAX_LENGTH = 255
_HASH_CHUNK_BYTES = 1024 * 1024
# libmagic needs only the start of a file to identify an image.
_SNIFF_BYTES = 4096
# Legacy Office files only reveal which application made them deeper in the file; with
# less than this libmagic can only say "an OLE container".
_DOCUMENT_SNIFF_BYTES = 1024 * 1024


@dataclass(frozen=True)
class AllowedType:
    """What one extension may contain and how it is stored."""

    # Detected types the extension may legitimately hold. Formats with no signature
    # libmagic knows list a generic type, which leaves only the extension allowlist
    # standing guard for them.
    content_types: frozenset[str]
    # Extension used on disk: ours, never the client's spelling of it.
    disk_extension: str
    # Only JPEG, PNG and WebP can be decoded and written out again.
    reencode: bool = False
    # For zip-based formats libmagic can fail to recognize (the members it looks at may
    # lie beyond what it was shown): a file sniffed as a plain zip is accepted when it
    # has a member starting with this name. Read from the zip's central directory, so
    # nothing is decompressed.
    zip_marker: str | None = None


@dataclass(frozen=True)
class UploadContext:
    """What one kind of upload accepts, by extension."""

    allowed: dict[str, AllowedType]
    sniff_bytes: int = _SNIFF_BYTES


def _types(*content_types: str) -> frozenset[str]:
    return frozenset(content_types)


_JPEG = AllowedType(_types("image/jpeg"), ".jpg", reencode=True)
_PNG = AllowedType(_types("image/png"), ".png", reencode=True)
_WEBP = AllowedType(_types("image/webp"), ".webp", reencode=True)

IMAGE_CONTEXT = UploadContext(
    allowed={".jpg": _JPEG, ".jpeg": _JPEG, ".png": _PNG, ".webp": _WEBP}
)

_OLE = ("application/x-ole-storage", "application/CDFV2")
_OOXML = "application/vnd.openxmlformats-officedocument."
_ODF = "application/vnd.oasis.opendocument."
_TEXT = ("text/plain",)

# Detected types were taken from real sample files of each format on libmagic 5.48,
# the version of the container image.
PROJECT_DOCUMENT_CONTEXT = UploadContext(
    allowed={
        ".pdf": AllowedType(_types("application/pdf"), ".pdf"),
        ".doc": AllowedType(_types("application/msword", *_OLE), ".doc"),
        ".docx": AllowedType(
            _types(_OOXML + "wordprocessingml.document"),
            ".docx",
            zip_marker="word/document.xml",
        ),
        ".rtf": AllowedType(_types("text/rtf", "application/rtf"), ".rtf"),
        ".odt": AllowedType(_types(_ODF + "text"), ".odt"),
        ".txt": AllowedType(_types(*_TEXT), ".txt"),
        ".md": AllowedType(
            _types(*_TEXT, "text/markdown", "text/x-markdown"), ".md"
        ),
        ".xls": AllowedType(_types("application/vnd.ms-excel", *_OLE), ".xls"),
        ".xlsx": AllowedType(
            _types(_OOXML + "spreadsheetml.sheet"),
            ".xlsx",
            zip_marker="xl/workbook.xml",
        ),
        ".csv": AllowedType(_types("text/csv", *_TEXT), ".csv"),
        ".ods": AllowedType(_types(_ODF + "spreadsheet"), ".ods"),
        ".ppt": AllowedType(_types("application/vnd.ms-powerpoint", *_OLE), ".ppt"),
        ".pptx": AllowedType(
            _types(_OOXML + "presentationml.presentation"),
            ".pptx",
            zip_marker="ppt/presentation.xml",
        ),
        ".key": AllowedType(
            _types("application/vnd.apple.keynote"), ".key", zip_marker="Index"
        ),
        ".png": _PNG,
        ".jpg": _JPEG,
        ".jpeg": _JPEG,
        ".webp": _WEBP,
        ".gif": AllowedType(_types("image/gif"), ".gif"),
        ".svg": AllowedType(_types("image/svg+xml", "text/xml"), ".svg"),
        ".heic": AllowedType(_types("image/heic", "image/heif"), ".heic"),
        ".mp4": AllowedType(_types("video/mp4"), ".mp4"),
        ".mov": AllowedType(_types("video/quicktime"), ".mov"),
        ".webm": AllowedType(_types("video/webm"), ".webm"),
        ".mp3": AllowedType(_types("audio/mpeg"), ".mp3"),
        ".wav": AllowedType(_types("audio/x-wav", "audio/vnd.wave"), ".wav"),
        ".m4a": AllowedType(_types("audio/x-m4a", "audio/mp4", "video/mp4"), ".m4a"),
        ".zip": AllowedType(_types("application/zip"), ".zip"),
        ".rar": AllowedType(_types("application/vnd.rar", "application/x-rar"), ".rar"),
        ".7z": AllowedType(_types("application/x-7z-compressed"), ".7z"),
        ".gz": AllowedType(_types("application/gzip", "application/x-gzip"), ".gz"),
        ".json": AllowedType(_types("application/json", *_TEXT), ".json"),
        ".xml": AllowedType(_types("text/xml", "application/xml"), ".xml"),
        ".html": AllowedType(_types("text/html"), ".html"),
        ".eml": AllowedType(_types("message/rfc822", *_TEXT), ".eml"),
        ".msg": AllowedType(
            _types("application/vnd.ms-outlook", *_OLE), ".msg"
        ),
        # Both are DER binaries libmagic has no signature for (the .cer may also be PEM
        # text), so for these the extension allowlist is the only real check.
        ".p12": AllowedType(
            _types("application/x-pkcs12", "application/octet-stream"), ".p12"
        ),
        ".pem": AllowedType(_types("application/x-pem-file", *_TEXT), ".pem"),
        ".cer": AllowedType(
            _types(
                "application/x-x509-ca-cert",
                "application/pkix-cert",
                "application/x-pem-file",
                "application/octet-stream",
            ),
            ".cer",
        ),
    },
    sniff_bytes=_DOCUMENT_SNIFF_BYTES,
)

_PILLOW_FORMAT_FOR_TYPE = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}


class FileUploadError(Exception):
    """An upload that was rejected. `status_code` is the HTTP status to answer with and
    `reason` a short stable code for logs; the message is safe to show the user."""

    status_code = 400
    reason = "rejected"


class FileTooLargeError(FileUploadError):
    status_code = 413
    reason = "too_large"


class UnsupportedFileTypeError(FileUploadError):
    status_code = 415
    reason = "unsupported_type"


class InvalidImageError(FileUploadError):
    status_code = 422
    reason = "invalid_image"


class StoragePathError(Exception):
    """A stored file's recorded location resolves outside the storage root."""


@dataclass(frozen=True)
class PreparedUpload:
    """A validated, re-encoded upload staged in the temporary folder, not yet stored."""

    tmp_path: Path
    checksum: str
    size_bytes: int
    content_type: str
    extension: str
    display_name: str


def sanitize_display_name(name: str | None) -> str:
    """Makes a client-supplied file name safe to keep and show: path parts dropped,
    control characters removed and the length capped. Display only, never a path."""
    base = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = "".join(
        ch for ch in base if unicodedata.category(ch) not in {"Cc", "Cf", "Zl", "Zp"}
    ).strip()
    return cleaned[:DISPLAY_NAME_MAX_LENGTH] or "file"


def _storage_root() -> Path:
    return settings.storage_root


def resolve_storage_path(bucket_key: str) -> Path:
    """The absolute path of a stored file, verified to stay inside the storage root
    even though keys are generated by the system (defense in depth)."""
    root = _storage_root().resolve()
    path = (root / bucket_key).resolve()
    if not path.is_relative_to(root):
        raise StoragePathError("Stored file path escapes the storage root")
    return path


def _reject(error: FileUploadError, filename: str | None) -> FileUploadError:
    # %r-escaped and capped: the name is untrusted input that could otherwise forge log
    # lines. File content is never logged.
    logger.warning(
        "Upload rejected: reason=%s filename=%r", error.reason, (filename or "")[:255]
    )
    return error


def _measure(file: IO[bytes]) -> int:
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    return size


def _sniff(file: IO[bytes], sniff_bytes: int) -> str:
    head = file.read(sniff_bytes)
    file.seek(0)
    return magic.from_buffer(head, mime=True)


def _has_zip_member(file: IO[bytes], prefix: str) -> bool:
    """Whether the zip has a member whose name starts with `prefix`. Reads only the
    zip's directory, never a member's content, so a zip bomb costs nothing here."""
    try:
        with zipfile.ZipFile(file) as archive:
            return any(name.startswith(prefix) for name in archive.namelist())
    except (zipfile.BadZipFile, OSError, ValueError):
        return False
    finally:
        file.seek(0)


def _matches(file: IO[bytes], detected: str, entry: AllowedType) -> bool:
    if detected in entry.content_types:
        return True
    return (
        entry.zip_marker is not None
        and detected == "application/zip"
        and _has_zip_member(file, entry.zip_marker)
    )


def _encode_image(file: IO[bytes], content_type: str, tmp_path: Path) -> None:
    """Decodes the upload and writes a freshly encoded image of the same format.

    Pillow writes no metadata unless asked to, so EXIF, text chunks and ICC profiles
    are all dropped. The EXIF orientation is applied to the pixels first, otherwise a
    rotated phone photo would come out sideways once the tag is gone.
    """
    expected_format = _PILLOW_FORMAT_FOR_TYPE[content_type]
    try:
        with Image.open(file) as image:
            if image.format != expected_format:
                raise InvalidImageError("The file is not a valid image")
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise InvalidImageError("The image is too large to process")
            image.load()
            pixels = ImageOps.exif_transpose(image)
            if expected_format == "JPEG" and pixels.mode not in ("RGB", "L"):
                pixels = pixels.convert("RGB")
            elif expected_format == "WEBP" and pixels.mode not in ("RGB", "RGBA"):
                has_alpha = "A" in pixels.mode or "transparency" in pixels.info
                pixels = pixels.convert("RGBA" if has_alpha else "RGB")
            options: dict[str, int | bool] = {}
            if expected_format in ("JPEG", "WEBP"):
                options["quality"] = 90
            if expected_format in ("JPEG", "PNG"):
                options["optimize"] = True
            pixels.save(tmp_path, format=expected_format, **options)
    except FileUploadError:
        raise
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        OSError,
        ValueError,
        SyntaxError,
    ) as err:
        raise InvalidImageError("The file is not a valid image") from err


def _stage_as_received(file: IO[bytes], tmp_path: Path) -> None:
    """Writes the upload to the staging file unchanged, for formats that cannot be
    decoded and written out again."""
    with tmp_path.open("wb") as out:
        shutil.copyfileobj(file, out, _HASH_CHUNK_BYTES)


def _hash_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK_BYTES):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _prepare(
    file: IO[bytes] | BufferedIOBase, filename: str | None, context: UploadContext
) -> PreparedUpload:
    source: IO[bytes] = file  # type: ignore[assignment]
    max_bytes = settings.max_upload_bytes
    if _measure(source) > max_bytes:
        raise FileTooLargeError(f"The file is larger than {max_bytes} bytes")

    extension = Path(filename or "").suffix.lower()
    entry = context.allowed.get(extension)
    if entry is None:
        raise UnsupportedFileTypeError("This file type is not allowed")

    detected = _sniff(source, context.sniff_bytes)
    if not _matches(source, detected, entry):
        raise UnsupportedFileTypeError("The file content does not match its extension")

    tmp_dir = _storage_root() / TMP_DIR_NAME
    tmp_dir.mkdir(mode=0o750, parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"{uuid.uuid4()}.tmp"
    try:
        if entry.reencode:
            _encode_image(source, detected, tmp_path)
        else:
            _stage_as_received(source, tmp_path)
        os.chmod(tmp_path, 0o640)
        checksum, size = _hash_file(tmp_path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    return PreparedUpload(
        tmp_path=tmp_path,
        checksum=checksum,
        size_bytes=size,
        content_type=detected,
        extension=entry.disk_extension,
        display_name=sanitize_display_name(filename),
    )


async def prepare_upload(upload: UploadFile, context: UploadContext) -> PreparedUpload:
    """Validates and re-encodes an upload into the staging folder. Raises a
    FileUploadError (already logged) if it is rejected, leaving nothing behind."""
    try:
        return await asyncio.to_thread(_prepare, upload.file, upload.filename, context)
    except FileUploadError as err:
        raise _reject(err, upload.filename) from err


def _bucket_key(checksum: str, extension: str) -> str:
    return f"{checksum[0:2]}/{checksum[2:4]}/{uuid.uuid4()}{extension}"


def _move_into_place(tmp_path: Path, bucket_key: str) -> Path:
    destination = resolve_storage_path(bucket_key)
    destination.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    os.replace(tmp_path, destination)
    return destination


async def _discard(path: Path) -> None:
    await asyncio.to_thread(path.unlink, True)


async def _store_content(
    db: AsyncSession, prepared: PreparedUpload
) -> tuple[StoredFile, Path | None]:
    """Inserts the stored-content row, or finds the existing one for identical content.
    Returns the row and the path of a newly written disk file (None if the content
    was already stored and nothing was written). The staged file is moved into place
    only when new; otherwise it is left for the caller to discard."""
    bucket_key = _bucket_key(prepared.checksum, prepared.extension)
    inserted_id = (
        await db.execute(
            pg_insert(StoredFile)
            .values(
                id=uuid.uuid4(),
                checksum_sha256=prepared.checksum,
                size_bytes=prepared.size_bytes,
                detected_content_type=prepared.content_type,
                bucket_key=bucket_key,
                status="ready",
            )
            .on_conflict_do_nothing(index_elements=[StoredFile.checksum_sha256])
            .returning(StoredFile.id)
        )
    ).scalar_one_or_none()

    if inserted_id is None:
        # Identical content is already stored: refer to it instead of writing again.
        existing = (
            await db.execute(
                select(StoredFile).where(
                    StoredFile.checksum_sha256 == prepared.checksum
                )
            )
        ).scalar_one()
        return existing, None

    written = await asyncio.to_thread(_move_into_place, prepared.tmp_path, bucket_key)
    stored = (
        await db.execute(select(StoredFile).where(StoredFile.id == inserted_id))
    ).scalar_one()
    return stored, written


async def attach_setting_file(
    db: AsyncSession,
    *,
    upload: UploadFile,
    setting_key: SettingKey,
    uploaded_by: User,
    context: UploadContext = IMAGE_CONTEXT,
) -> File:
    """Stores an upload as the file of a single-slot setting, replacing any current
    one in the same transaction so a failure leaves the current file untouched."""
    prepared = await prepare_upload(upload, context)
    # Two simultaneous replacements can both miss each other's uncommitted row and
    # collide on the single-slot index; the loser retries once and then replaces the
    # winner's file.
    for attempt in (1, 2):
        written: Path | None = None
        try:
            stored, written = await _store_content(db, prepared)
            await db.execute(
                delete(File).where(
                    File.id.in_(
                        select(SettingFile.file_id).where(
                            SettingFile.setting_key == setting_key
                        )
                    )
                )
            )
            file = File(
                stored_file_id=stored.id,
                kind="setting",
                uploaded_by=uploaded_by.id,
                original_filename=prepared.display_name,
            )
            db.add(file)
            await db.flush()
            db.add(
                SettingFile(file_id=file.id, kind="setting", setting_key=setting_key)
            )
            await db.commit()
        except IntegrityError:
            await db.rollback()
            if attempt == 2:
                await _cleanup_failed(prepared, written)
                raise
            if written is not None:
                # The row was rolled back, so put the staged file back for the retry.
                await asyncio.to_thread(os.replace, written, prepared.tmp_path)
        except BaseException:
            await db.rollback()
            await _cleanup_failed(prepared, written)
            raise
        else:
            # Only still present when the content was already stored.
            await _discard(prepared.tmp_path)
            return await _load_file(db, file.id)
    raise AssertionError("unreachable")  # pragma: no cover


async def attach_project_file(
    db: AsyncSession,
    *,
    upload: UploadFile,
    project_id: uuid.UUID,
    uploaded_by: User,
    context: UploadContext = PROJECT_DOCUMENT_CONTEXT,
) -> File:
    """Stores an upload as a new file of a project. Unlike a setting slot nothing is
    replaced: every upload adds an attachment, even one with the same name or content."""
    prepared = await prepare_upload(upload, context)
    written: Path | None = None
    try:
        stored, written = await _store_content(db, prepared)
        file = File(
            stored_file_id=stored.id,
            kind="project",
            uploaded_by=uploaded_by.id,
            original_filename=prepared.display_name,
        )
        db.add(file)
        await db.flush()
        db.add(ProjectFile(file_id=file.id, kind="project", project_id=project_id))
        await db.commit()
    except BaseException:
        await db.rollback()
        await _cleanup_failed(prepared, written)
        raise
    # Only still present when the content was already stored.
    await _discard(prepared.tmp_path)
    return await _load_file(db, file.id)


async def _cleanup_failed(prepared: PreparedUpload, written: Path | None) -> None:
    """A failed upload must leave nothing behind on disk."""
    if written is not None:
        await _discard(written)
    await _discard(prepared.tmp_path)


async def _load_file(db: AsyncSession, file_id: uuid.UUID) -> File:
    return (
        await db.execute(
            select(File)
            .options(selectinload(File.stored_file))
            .where(File.id == file_id)
        )
    ).scalar_one()


async def get_setting_file(db: AsyncSession, setting_key: SettingKey) -> File | None:
    return (
        await db.execute(
            select(File)
            .options(selectinload(File.stored_file))
            .join(SettingFile, SettingFile.file_id == File.id)
            .where(SettingFile.setting_key == setting_key)
        )
    ).scalar_one_or_none()


async def read_setting_file_bytes(
    db: AsyncSession, setting_key: SettingKey
) -> bytes | None:
    """The stored bytes of a single-slot setting's file, for backend code acting on behalf
    of the system (e.g. putting the organization logo in a generated report).

    Deliberately has no access check: it is not a download. The caller is trusted backend
    code, never a route, and the bytes only leave the server inside whatever that code
    produces for a user who was already allowed to request it, which is why the logo reaches
    a project manager who has no access to setting files. It does require the file to be
    `ready`.

    Returns None when the setting has no file or the file is not ready. A missing disk
    file (OSError) or a recorded path outside the storage root (StoragePathError) is raised,
    so the caller decides what a broken file means for it.
    """
    file = await get_setting_file(db, setting_key)
    if file is None or file.stored_file.status != "ready":
        return None
    path = resolve_storage_path(file.stored_file.bucket_key)
    return await asyncio.to_thread(path.read_bytes)


async def delete_setting_file(db: AsyncSession, setting_key: SettingKey) -> bool:
    """Removes a single-slot setting's file. Setting files keep no history, so the
    record is deleted outright; the stored content stays until the cleanup job."""
    result = await db.execute(
        delete(File).where(
            File.id.in_(
                select(SettingFile.file_id).where(
                    SettingFile.setting_key == setting_key
                )
            )
        )
    )
    await db.commit()
    return cast(CursorResult[tuple[()]], result).rowcount > 0


async def get_file(db: AsyncSession, file_id: uuid.UUID) -> File | None:
    return (
        await db.execute(
            select(File)
            .options(selectinload(File.stored_file))
            .where(File.id == file_id, File.deleted_at.is_(None))
        )
    ).scalar_one_or_none()


async def user_can_access_file(db: AsyncSession, user: User, file: File) -> bool:
    """Access is decided by the object the file is attached to, never by the file or
    its uploader, so it cannot drift from that object's own role rules. Each new
    attachable kind adds one branch."""
    kind: Literal["setting", "project"] = file.kind  # type: ignore[assignment]
    role_names = {role.name for role in user.roles}
    if kind == "setting":
        return "administrator" in role_names
    if kind == "project":
        # The literal role: holding `administrator` alone grants nothing here.
        return "project_admin" in role_names
    return False  # pragma: no cover - unknown kinds get no access
