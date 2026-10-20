import io
from typing import Any

import pytest
from fpdf import FPDF
from pypdf import PageObject, PdfReader, PdfWriter

from app.pdf.errors import PdfStampError
from app.pdf.stamp import stamp_voided


def _pdf(pages: list[tuple[float, float, str]], title: str = "INV-1") -> bytes:
    doc = FPDF(unit="pt")
    doc.set_title(title)
    doc.set_author("Ifrit")
    doc.set_font("Helvetica", size=14)
    for width, height, text in pages:
        doc.add_page(format=(width, height))
        doc.text(60, 80, text)
    return bytes(doc.output())


def _rewrite(pdf: bytes, edit) -> bytes:
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf)))
    edit(writer)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _rotate_90(writer: PdfWriter) -> None:
    writer.pages[0].rotate(90)


def _encrypt(writer: PdfWriter) -> None:
    writer.encrypt("secret")


def _remove_first_page(writer: PdfWriter) -> None:
    writer.remove_page(0)


def _without_mark(text: str) -> str:
    return text.replace("VOIDED", "").strip()


def _drawn(page: PageObject) -> bytes:
    contents = page.get_contents()
    assert contents is not None
    return contents.get_data()


A4 = (595.0, 842.0)
LETTER = (612.0, 792.0)


def test_every_page_keeps_its_text_and_gains_the_mark() -> None:
    original = _pdf([(*A4, "Page one"), (*A4, "Page two"), (*A4, "Page three")])

    stamped = PdfReader(io.BytesIO(stamp_voided(original)))
    before = PdfReader(io.BytesIO(original))

    assert len(stamped.pages) == 3
    for index, (after, source) in enumerate(
        zip(stamped.pages, before.pages, strict=True)
    ):
        assert _without_mark(after.extract_text()) == source.extract_text().strip()
        assert "VOIDED" in after.extract_text()
        assert b"VOIDED" in _drawn(after), f"page {index + 1}"
        assert b"VOIDED" not in _drawn(source)


def test_the_mark_is_translucent_and_drawn_after_the_content() -> None:
    stamped = PdfReader(io.BytesIO(stamp_voided(_pdf([(*A4, "Body")]))))
    data = _drawn(stamped.pages[0])
    assert data.index(b"Body") < data.index(b"VOIDED")
    resources: Any = stamped.pages[0]["/Resources"]
    states = resources["/ExtGState"]
    assert any(abs(float(states[name].get("/ca", 1)) - 0.18) < 0.001 for name in states)


def test_pages_of_different_sizes_keep_their_size() -> None:
    stamped = PdfReader(io.BytesIO(stamp_voided(_pdf([(*A4, "a"), (*LETTER, "b")]))))
    sizes = [(float(p.mediabox.width), float(p.mediabox.height)) for p in stamped.pages]
    assert sizes == [A4, LETTER]
    assert all(b"VOIDED" in _drawn(p) for p in stamped.pages)


def test_a_rotated_page_is_marked_and_stays_rotated() -> None:
    source = _rewrite(_pdf([(*A4, "turned")]), _rotate_90)

    stamped = PdfReader(io.BytesIO(stamp_voided(source)))

    assert stamped.pages[0].rotation == 90
    assert b"VOIDED" in _drawn(stamped.pages[0])
    assert _without_mark(stamped.pages[0].extract_text()) == "turned"


def test_the_mark_is_drawn_at_the_page_rotation_plus_45_degrees() -> None:
    # Content rotated by r degrees counter-clockwise shows its matrix as cos/sin of r.
    def angle_of(pdf: bytes) -> float:
        import math
        import re

        data = _drawn(PdfReader(io.BytesIO(pdf)).pages[0]).decode("latin-1")
        a, b = (
            float(x)
            for x in re.findall(
                r"([-\d.]+) ([-\d.]+) [-\d.]+ [-\d.]+ [-\d.]+ [-\d.]+ cm", data
            )[-1][:2]
        )
        return round(math.degrees(math.atan2(b, a))) % 360

    upright = stamp_voided(_pdf([(*A4, "x")]))
    turned = stamp_voided(_rewrite(_pdf([(*A4, "x")]), _rotate_90))
    assert angle_of(upright) == 45
    assert angle_of(turned) == 135


def test_a_page_with_a_crop_box_is_marked_inside_it() -> None:
    def crop(writer: PdfWriter) -> None:
        from pypdf.generic import RectangleObject

        writer.pages[0].cropbox = RectangleObject((100, 200, 500, 700))

    stamped = PdfReader(
        io.BytesIO(stamp_voided(_rewrite(_pdf([(*A4, "cropped")]), crop)))
    )

    page = stamped.pages[0]
    assert [float(v) for v in page.cropbox] == [100, 200, 500, 700]
    assert b"VOIDED" in _drawn(page)


def test_the_document_information_is_unchanged() -> None:
    original = _pdf([(*A4, "a")], title="INV-2026-0043")
    stamped = PdfReader(io.BytesIO(stamp_voided(original)))
    before = PdfReader(io.BytesIO(original))
    assert stamped.metadata is not None and before.metadata is not None
    assert stamped.metadata.title == "INV-2026-0043"
    assert stamped.metadata.author == "Ifrit"
    assert dict(stamped.metadata) == dict(before.metadata)


def test_the_input_is_not_modified() -> None:
    original = _pdf([(*A4, "a")])
    copy = bytes(original)
    stamp_voided(original)
    assert original == copy


@pytest.mark.parametrize("data", [b"", b"not a pdf at all", b"%PDF-1.7\n"])
def test_unreadable_input_is_refused(data: bytes) -> None:
    with pytest.raises(PdfStampError):
        stamp_voided(data)


def test_a_truncated_pdf_is_refused() -> None:
    original = _pdf([(*A4, "a"), (*A4, "b")])
    with pytest.raises(PdfStampError):
        stamp_voided(original[: len(original) // 3])


def test_an_encrypted_pdf_is_refused() -> None:
    encrypted = _rewrite(_pdf([(*A4, "a")]), _encrypt)
    with pytest.raises(PdfStampError, match="encrypted"):
        stamp_voided(encrypted)


def test_a_pdf_with_no_pages_is_refused() -> None:
    empty = _rewrite(_pdf([(*A4, "a")]), _remove_first_page)
    with pytest.raises(PdfStampError):
        stamp_voided(empty)
