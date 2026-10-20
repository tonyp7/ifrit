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
