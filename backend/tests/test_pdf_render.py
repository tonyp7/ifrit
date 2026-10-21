import re
import shutil
import subprocess
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.models.invoice import InvoiceLine
from app.pdf import render
from app.pdf.odt import TemplateData
from app.pdf.render import render_invoice_pdf
from app.pdf.values import build_template_data
from tests.odt_helpers import read_part
from tests.test_pdf_values import _invoice

NOW = datetime(2026, 9, 3, 14, 5, tzinfo=UTC)


def _data(**overrides: object) -> TemplateData:
    invoice = _invoice(**overrides)
    return build_template_data(
        invoice,
        minor_unit=2,
        document_name="Invoice",
        vendor_identifiers=[],
        client_identifiers=[],
        now=NOW,
    )


async def test_the_bundled_template_is_filled_before_conversion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[bytes] = []

    async def fake_convert(odt: bytes) -> bytes:
        seen.append(odt)
        return b"%PDF"

    monkeypatch.setattr(render, "convert_to_pdf", fake_convert)
    assert await render_invoice_pdf(_data(bill_to_name="Acme & Co")) == b"%PDF"
    content = read_part(seen[0])
    assert "Acme &amp; Co" in content and "{{" not in content
    assert "Assigned when issued" in content


async def test_a_given_template_replaces_the_bundled_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.odt_helpers import make_odt

    seen: list[bytes] = []

    async def fake_convert(odt: bytes) -> bytes:
        seen.append(odt)
        return b"%PDF"

    monkeypatch.setattr(render, "convert_to_pdf", fake_convert)
    template = make_odt(
        "<text:p>Hello {{bill_to_name}}</text:p><text:p>{{invoice_lines}}</text:p>"
    )
    await render_invoice_pdf(_data(), template)
    assert "Hello ACME" in read_part(seen[0])


# --- with the real LibreOffice ---------------------------------------------------------------

needs_libreoffice = pytest.mark.skipif(
    shutil.which("soffice") is None and shutil.which("libreoffice") is None,
    reason="LibreOffice is not installed",
)


def _pages(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page(?![a-z])", pdf))


def _many_lines(count: int) -> list[InvoiceLine]:
    return [
        InvoiceLine(
            position=i,
            description=f"Consulting line {i + 1}",
            quantity=Decimal(1),
            uom="days",
            unit_price=Decimal(100),
            amount=Decimal(100),
        )
        for i in range(count)
    ]


@pytest.mark.libreoffice
@needs_libreoffice
async def test_a_one_line_invoice_is_one_page() -> None:
    pdf = await render_invoice_pdf(_data())
    assert pdf.startswith(b"%PDF")
    assert _pages(pdf) == 1


@pytest.mark.libreoffice
@needs_libreoffice
async def test_a_forty_line_invoice_spans_several_pages() -> None:
    pdf = await render_invoice_pdf(_data(lines=_many_lines(40)))
    assert pdf.startswith(b"%PDF")
    assert _pages(pdf) >= 2


@pytest.mark.libreoffice
@needs_libreoffice
async def test_the_draft_mark_is_drawn_for_a_draft_only() -> None:
    draft = await render_invoice_pdf(_data())
    issued = await render_invoice_pdf(
        _data(status="issued", number="INV-1", invoice_date=NOW.date(), issued_at=NOW)
    )
    assert draft != issued
    if shutil.which("pdftotext"):
        assert "Assigned when issued" in _text(draft)
        assert "INV-1" in _text(issued)


def _currency_words(pdf: bytes) -> list[tuple[float, float, float]]:
    """(left edge, top, width) of every `USD` word the PDF prints, top to bottom."""
    out = subprocess.run(
        ["pdftotext", "-bbox", "-", "-"], input=pdf, capture_output=True, check=True
    ).stdout.decode()
    words = re.findall(
        r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="[\d.]+">USD</word>',
        out,
    )
    return sorted(
        ((float(x0), float(y0), float(x1) - float(x0)) for x0, y0, x1 in words),
        key=lambda w: w[1],
    )


@pytest.mark.libreoffice
@needs_libreoffice
@pytest.mark.skipif(
    shutil.which("pdftotext") is None, reason="pdftotext is not installed"
)
async def test_the_currency_code_lines_up_on_every_row_of_the_table() -> None:
    words = _currency_words(await render_invoice_pdf(_data()))
    # Line, Subtotal, tax and Total rows (the header row says "Currency", not the code).
    assert len(words) >= 4
    table = words[-4:]
    lefts = [left for left, _, _ in table]
    assert max(lefts) - min(lefts) < 0.5, lefts


def _text(pdf: bytes) -> str:
    return subprocess.run(
        ["pdftotext", "-", "-"], input=pdf, capture_output=True, check=True
    ).stdout.decode()


def test_a_pdf_file_name_is_one_name() -> None:
    from app.pdf.http import pdf_filename

    assert pdf_filename("INV-2026-0043") == "INV-2026-0043.pdf"
    assert pdf_filename("2026/0043") == "2026-0043.pdf"
    assert pdf_filename('a\\b:c"d') == "a-b-c-d.pdf"
    assert pdf_filename("  ") == "invoice.pdf"


# --- the payment block sits at the foot of the page that ends the table -----------------------

_WORD = re.compile(
    r'<word xMin="[\d.]+" yMin="([\d.]+)" xMax="[\d.]+" yMax="([\d.]+)">([^<]*)</word>'
)
# The payment block is anchored to the bottom of the page's text area: its heading starts
# well below the middle of an A4 page (842 pt high) whatever the invoice.
_LOWER_PART = 600.0
_FOOTER_TOP = 790.0


def _words_by_page(pdf: bytes) -> list[list[tuple[float, float, str]]]:
    """(top, bottom, text) of every word, for each page."""
    out = subprocess.run(
        ["pdftotext", "-bbox", "-", "-"], input=pdf, capture_output=True, check=True
    ).stdout.decode()
    return [
        [(float(y0), float(y1), text) for y0, y1, text in _WORD.findall(page)]
        for page in out.split("<page ")[1:]
    ]


def _heading_and_total(
    pages: list[list[tuple[float, float, str]]],
) -> tuple[tuple[int, float], tuple[int, float]]:
    """(page, top) of the "Payment" heading and of the last "Total" of the table."""
    heading = next(
        (n, top)
        for n, words in enumerate(pages)
        for top, _, text in words
        if text == "Payment"
    )
    total = max(
        (n, top)
        for n, words in enumerate(pages)
        for top, _, text in words
        if text == "Total"
    )
    return heading, total


needs_pdftotext = pytest.mark.skipif(
    shutil.which("pdftotext") is None, reason="pdftotext is not installed"
)


@pytest.mark.libreoffice
@needs_libreoffice
@needs_pdftotext
async def test_a_short_invoice_has_its_payment_block_at_the_foot_of_the_page() -> None:
    pages = _words_by_page(await render_invoice_pdf(_data()))
    assert len(pages) == 1
    (_, heading), (_, total) = _heading_and_total(pages)
    assert heading > _LOWER_PART
    assert heading > total + 12


@pytest.mark.libreoffice
@needs_libreoffice
@needs_pdftotext
async def test_a_long_invoice_has_its_payment_block_on_the_last_page_under_the_table() -> (
    None
):
    short = _words_by_page(await render_invoice_pdf(_data()))
    pages = _words_by_page(await render_invoice_pdf(_data(lines=_many_lines(40))))
    assert len(pages) == 2
    (heading_page, heading), (total_page, total) = _heading_and_total(pages)
    assert heading_page == total_page == 1
    assert heading > total + 12
    # The same place on the page as on a one-page invoice.
    assert abs(heading - _heading_and_total(short)[0][1]) < 1.0


@pytest.mark.libreoffice
@needs_libreoffice
@needs_pdftotext
async def test_a_table_ending_low_on_its_page_sends_the_block_to_the_next_page() -> (
    None
):
    # 24 lines leave no room under the Total row for the block.
    pages = _words_by_page(await render_invoice_pdf(_data(lines=_many_lines(24))))
    (heading_page, heading), (total_page, _) = _heading_and_total(pages)
    assert heading_page == total_page + 1
    assert heading > _LOWER_PART


@pytest.mark.libreoffice
@needs_libreoffice
@needs_pdftotext
async def test_a_longer_payment_block_grows_upwards_and_stays_on_the_page() -> None:
    async def render(bank_name: str) -> list[list[tuple[float, float, str]]]:
        return _words_by_page(
            await render_invoice_pdf(
                _data(
                    payee_payment_means_code="58",
                    payee_account_scheme="iban",
                    payee_account_identifier="SG1234567890123456",
                    payee_currency_code="USD",
                    payee_bic="EXMPSGSG",
                    payee_bank_name=bank_name,
                    payee_bank_line1="1 Sample Blvd",
                    payee_bank_city="Singapore",
                    payee_bank_country_code="SG",
                )
            )
        )

    short = await render("Example Bank")
    long = await render("An equally long bank name " * 10)
    assert len(short) == len(long) == 1
    (_, short_top), _ = _heading_and_total(short)
    (_, long_top), _ = _heading_and_total(long)
    # The block grew upwards, and its last line is still above the footer.
    assert long_top < short_top - 20
    assert any(text == "EXMPSGSG" and top < _FOOTER_TOP for top, _, text in long[0])
