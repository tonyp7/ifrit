"""A real one-page PDF for tests that stand in for the converter, so code that reads the
file afterwards (the void stamp) has something valid to read."""

from datetime import UTC, datetime

from fpdf import FPDF


def fake_invoice_pdf(number: str) -> bytes:
    doc = FPDF(unit="pt", format="A4")
    doc.set_title(number)
    # Same number, same bytes: tests compare what was stored with what was rendered.
    doc.creation_date = datetime(2026, 1, 1, tzinfo=UTC)
    doc.add_page()
    doc.set_font("Helvetica", size=14)
    doc.text(60, 80, f"Invoice {number}")
    return bytes(doc.output())
