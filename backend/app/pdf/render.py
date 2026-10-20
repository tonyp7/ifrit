import asyncio
from pathlib import Path

from app.pdf.odt import TemplateData, fill_template
from app.pdf.runner import convert_to_pdf

_BUNDLED = Path(__file__).with_name("invoice-template.odt")


def bundled_template() -> bytes:
    """The template that ships with the application."""
    return _BUNDLED.read_bytes()


async def render_invoice_pdf(
    data: TemplateData, template: bytes | None = None
) -> bytes:
    """The PDF of an invoice: `template` (the bundled one by default) filled with `data`, then
    converted. Raises TemplateError for a template that cannot be filled and PdfEngineError
    when the converter cannot produce a PDF."""
    source = (
        template if template is not None else await asyncio.to_thread(bundled_template)
    )
    odt = await asyncio.to_thread(fill_template, source, data)
    return await convert_to_pdf(odt)
