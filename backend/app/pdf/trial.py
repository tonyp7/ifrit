"""Converts a template with the sample invoice, which is the last check an upload passes: a
file can be valid and still be one the converter cannot open."""

import io

from pypdf import PdfReader

from app.pdf.errors import PdfEngineError, PdfEngineNotInstalledError, TemplateError
from app.pdf.render import render_invoice_pdf
from app.pdf.sample import sample_template_data
from app.pdf.validate import Finding


async def trial_render(template: bytes) -> tuple[bytes | None, list[Finding]]:
    """The sample invoice rendered with `template`, and what is wrong with the result.
    A converter that is not installed is not the template's fault and propagates."""
    try:
        pdf = await render_invoice_pdf(sample_template_data(), template)
    except TemplateError as err:
        return None, [Finding("template", str(err))]
    except PdfEngineNotInstalledError:
        raise
    except PdfEngineError:
        # The converter is there and could not turn this file into a PDF.
        return None, [
            Finding("template", "The PDF engine could not convert the template")
        ]
    pages = len(PdfReader(io.BytesIO(pdf)).pages)
    if pages > 1:
        return pdf, [
            Finding(
                "template",
                f"The sample invoice, one line and one tax, takes {pages} pages: it should fit on one",
            )
        ]
    return pdf, []
