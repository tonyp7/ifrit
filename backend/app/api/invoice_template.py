import asyncio
import json
import logging
import shutil
import subprocess

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_roles
from app.core.db import get_db
from app.models.user import User
from app.pdf.errors import PdfEngineNotInstalledError, PdfError, TemplateError
from app.pdf.http import pdf_response
from app.pdf.odt import placeholders_in
from app.pdf.trial import trial_render
from app.pdf.validate import (
    MAX_BYTES,
    Finding,
    ValidationResult,
    parse_fc_list,
    validate_template,
)
from app.schemas.invoice_template import (
    TemplateFinding,
    TemplateInfo,
    TemplateSaved,
)
from app.services import file_storage_service, invoice_template_service
from app.services.invoice_template_service import ResolvedTemplate

logger = logging.getLogger(__name__)

# The template puts text on every invoice, so only administrators manage it, like the rest
# of the Configuration screen.
_admin_only = Depends(require_roles("administrator"))
router = APIRouter(
    prefix="/invoice-template", tags=["invoice-template"], dependencies=[_admin_only]
)

_ODT = "application/vnd.oasis.opendocument.text"
_UNAVAILABLE = "The PDF engine is not available"
DEFAULT_FILENAME = "invoice-template.odt"
# A header cannot carry much: the card shows the first few warnings of a template.
_MAX_HEADER_WARNINGS = 20

_fonts: set[str] | None = None
_fonts_read = False


def _read_fonts() -> set[str] | None:
    binary = shutil.which("fc-list")
    if binary is None:
        return None
    try:
        output = subprocess.run(
            [binary, ":", "family"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout
    except OSError, subprocess.SubprocessError:
        return None
    return parse_fc_list(output)


async def _installed_fonts() -> set[str] | None:
    """The font families the converter can use, read once; None when they cannot be listed,
    which skips the font warning."""
    global _fonts, _fonts_read
    if not _fonts_read:
        _fonts = await asyncio.to_thread(_read_fonts)
        _fonts_read = True
    return _fonts


def _finding(finding: Finding) -> TemplateFinding:
    return TemplateFinding(
        part=finding.part, message=finding.message, snippet=finding.snippet
    )


def _rejection(problems: list[Finding], warnings: list[Finding]) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={
            "message": "The template cannot be used",
            "problems": [_finding(f).model_dump() for f in problems],
            "warnings": [_finding(f).model_dump() for f in warnings],
        },
    )


async def _info(db: AsyncSession, resolved: ResolvedTemplate) -> TemplateInfo:
    placeholders: list[str] = []
    try:
        placeholders = list(placeholders_in(resolved.content))
    except TemplateError:
        pass
    if resolved.file is None:
        return TemplateInfo(
            source="default",
            filename=DEFAULT_FILENAME,
            size_bytes=len(resolved.content),
            uploaded_by_name=None,
            uploaded_at=None,
            placeholders=placeholders,
        )
    uploader = (
        await db.get(User, resolved.file.uploaded_by)
        if resolved.file.uploaded_by
        else None
    )
    return TemplateInfo(
        source="custom",
        filename=resolved.file.original_filename,
        size_bytes=resolved.file.stored_file.size_bytes,
        uploaded_by_name=uploader.full_name if uploader else None,
        uploaded_at=resolved.file.created_at,
        placeholders=placeholders,
    )


async def _checked(file: UploadFile) -> tuple[bytes, ValidationResult, bytes | None]:
    """The upload's bytes after every check: the static ones, then the trial render with the
    sample invoice. Raises the 422 listing the problems, or the 503 when the converter is
    not there to try."""
    # One byte more than allowed, so a file over the limit is seen as such.
    data = await file.read(MAX_BYTES + 1)
    result = validate_template(data, await _installed_fonts())
    if result.problems:
        raise _rejection(result.problems, [])
    try:
        pdf, findings = await trial_render(data)
    except PdfEngineNotInstalledError as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_UNAVAILABLE
        ) from err
    except PdfError as err:
        logger.exception("The trial render of an invoice template failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_UNAVAILABLE
        ) from err
    if findings:
        raise _rejection(findings, result.warnings)
    return data, result, pdf


@router.get("", response_model=TemplateInfo)
async def get_template(db: AsyncSession = Depends(get_db)) -> TemplateInfo:
    return await _info(db, await _resolve(db))


async def _resolve(db: AsyncSession) -> ResolvedTemplate:
    try:
        return await invoice_template_service.resolve_template(db)
    except TemplateError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The template file cannot be read",
        ) from err


@router.get("/file")
async def download_template(db: AsyncSession = Depends(get_db)) -> Response:
    resolved = await _resolve(db)
    name = (
        DEFAULT_FILENAME if resolved.file is None else resolved.file.original_filename
    )
    safe = "".join(ch for ch in name if ch.isprintable() and ch not in '"\\/')
    return Response(
        content=resolved.content,
        media_type=_ODT,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'attachment; filename="{safe or DEFAULT_FILENAME}"',
        },
    )


@router.post("/preview")
async def preview_template(file: UploadFile) -> Response:
    """The sample invoice made with an uploaded template, to try it before it is used.
    Stores nothing."""
    _, result, pdf = await _checked(file)
    assert pdf is not None
    warnings = [
        _finding(f).model_dump() for f in result.warnings[:_MAX_HEADER_WARNINGS]
    ]
    response = pdf_response(pdf)
    # ASCII-escaped JSON, so any characters of a font name or snippet fit in a header.
    response.headers["X-Template-Warnings"] = json.dumps(warnings)
    return response


@router.put("", response_model=TemplateSaved)
async def put_template(
    file: UploadFile,
    user: User = _admin_only,
    db: AsyncSession = Depends(get_db),
) -> TemplateSaved:
    _, result, _ = await _checked(file)
    await file.seek(0)
    try:
        await file_storage_service.attach_setting_file(
            db,
            upload=file,
            setting_key="invoice_template",
            uploaded_by=user,
            context=file_storage_service.TEMPLATE_CONTEXT,
        )
    except file_storage_service.FileUploadError as err:
        raise HTTPException(status_code=err.status_code, detail=str(err)) from err
    info = await _info(db, await _resolve(db))
    return TemplateSaved(
        **info.model_dump(), warnings=[_finding(f) for f in result.warnings]
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def reset_template(db: AsyncSession = Depends(get_db)) -> None:
    """Reset to default: discards an uploaded template, if any."""
    await file_storage_service.delete_setting_file(db, "invoice_template")
