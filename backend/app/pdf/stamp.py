"""Marks a finished PDF as voided by drawing VOIDED over every page.

The issued PDF is the document that was sent, so a void changes nothing in it except adding
the mark: the pages are kept as they are and a one-page overlay is merged on top of each, with
no template and no LibreOffice involved."""

import io
from dataclasses import dataclass

from fpdf import FPDF
from pypdf import PageObject, PdfReader, PdfWriter

from app.pdf.errors import PdfStampError

WORD = "VOIDED"
# Large enough to be unmistakable, light enough to read the text under it.
_SIZE_OF_SHORT_SIDE = 0.24
_GRAY = 128
_OPACITY = 0.18
_DEGREES = 45
# The baseline sits this far below the centre of a capital letter, in em, so the word is
# centred and not just its baseline.
_HALF_CAP_HEIGHT = 0.36


@dataclass(frozen=True)
class _Geometry:
    width: float
    height: float
    rotation: int


def _overlay(geometry: _Geometry) -> PageObject:
    """A page of the same size as the one it marks, holding only the word."""
    pdf = FPDF(unit="pt", format=(geometry.width, geometry.height))
    pdf.set_auto_page_break(False)
    pdf.add_page()
    size = min(geometry.width, geometry.height) * _SIZE_OF_SHORT_SIDE
    pdf.set_font("Helvetica", "B")
    pdf.set_font_size(size)
    pdf.set_text_color(_GRAY)
    centre_x, centre_y = geometry.width / 2, geometry.height / 2
    word_width = pdf.get_string_width(WORD)
    # A page stored with /Rotate is turned by the viewer after drawing, so the word is
    # drawn that much further the other way to still read upward at 45 degrees.
    angle = _DEGREES + geometry.rotation
    with (
        pdf.local_context(fill_opacity=_OPACITY),
        pdf.rotation(angle, centre_x, centre_y),
    ):
        pdf.text(centre_x - word_width / 2, centre_y + size * _HALF_CAP_HEIGHT, WORD)
    return PdfReader(io.BytesIO(bytes(pdf.output()))).pages[0]


def stamp_voided(pdf: bytes) -> bytes:
    """The same PDF with VOIDED on top of every page. Raises PdfStampError when `pdf` cannot
    be read or marked."""
    try:
        reader = PdfReader(io.BytesIO(pdf))
        if reader.is_encrypted:
            raise PdfStampError("The PDF is encrypted")
        # Cloning keeps the document information and everything else as it was.
        writer = PdfWriter(clone_from=reader)
        if not writer.pages:
            raise PdfStampError("The PDF has no pages")
        for page in writer.pages:
            # The visible area: the crop box when there is one, else the media box.
            box = page.cropbox
            geometry = _Geometry(
                width=float(box.width),
                height=float(box.height),
                rotation=page.rotation % 360,
            )
            page.merge_translated_page(
                _overlay(geometry), float(box.left), float(box.bottom), over=True
            )
        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()
    except PdfStampError:
        raise
    except Exception as err:
        raise PdfStampError("The PDF could not be marked") from err
