"""Which template invoice PDFs are made from: the one an administrator uploaded, or the one
that ships with the application."""

import asyncio
import logging
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import File
from app.pdf.errors import TemplateError
from app.pdf.render import bundled_template
from app.services import file_storage_service

logger = logging.getLogger(__name__)

SETTING_KEY = "invoice_template"


@dataclass(frozen=True)
class ResolvedTemplate:
    content: bytes
    source: Literal["default", "custom"]
    # The uploaded file's record; None for the bundled template.
    file: File | None


async def resolve_template(db: AsyncSession) -> ResolvedTemplate:
    """The template in use: the uploaded one when there is one, otherwise the bundled file.
    The bundled file is never copied into storage, so an installation that never uploaded a
    template follows the shipped one across releases."""
    file = await file_storage_service.get_setting_file(db, SETTING_KEY)
    if file is None or file.stored_file.status != "ready":
        return ResolvedTemplate(
            content=await asyncio.to_thread(bundled_template),
            source="default",
            file=None,
        )
    try:
        path = file_storage_service.resolve_storage_path(file.stored_file.bucket_key)
        content = await asyncio.to_thread(path.read_bytes)
    except (OSError, file_storage_service.StoragePathError) as err:
        logger.exception("The uploaded invoice template cannot be read")
        raise TemplateError("The uploaded invoice template cannot be read") from err
    return ResolvedTemplate(content=content, source="custom", file=file)
