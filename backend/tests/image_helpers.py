"""Builds small in-memory images and uploads for the file-storage tests."""

import io

from fastapi import UploadFile
from PIL import Image


def png_bytes(
    size: tuple[int, int] = (30, 20), mode: str = "RGB", color: object = (200, 30, 30)
) -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, size, color).save(buffer, format="PNG")  # type: ignore[arg-type]
    return buffer.getvalue()


def jpeg_bytes(
    size: tuple[int, int] = (30, 20),
    *,
    orientation: int | None = None,
    gps: bool = False,
) -> bytes:
    exif = Image.Exif()
    if orientation is not None:
        exif[0x0112] = orientation
    exif[0x010F] = "TestCamera"  # Make
    if gps:
        exif[0x8825] = {1: "N", 2: (1.0, 2.0, 3.0), 3: "E", 4: (4.0, 5.0, 6.0)}
    buffer = io.BytesIO()
    Image.new("RGB", size, (20, 120, 220)).save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def webp_bytes(size: tuple[int, int] = (30, 20)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (10, 200, 10)).save(buffer, format="WEBP")
    return buffer.getvalue()


def make_upload(data: bytes, filename: str) -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename=filename)
