import pytest

from app.pdf import trial
from app.pdf.errors import PdfEngineError, PdfEngineNotInstalledError, TemplateError
from app.pdf.odt import placeholders_in
from app.pdf.render import bundled_template
from app.pdf.sample import sample_template_data
from tests.odt_helpers import make_odt
from tests.test_pdf_render import _pages, needs_libreoffice
from tests.test_pdf_validate import _rewrite


def test_the_sample_invoice_fills_every_placeholder_of_the_bundled_template() -> None:
    data = sample_template_data()
    for name in placeholders_in(bundled_template()):
        assert (
            data.values.get(name) or data.blocks.get(name) or name == "invoice_lines"
        ), name
    assert data.values["draft_watermark"] == "DRAFT"
    assert data.values["invoice_number"] == "INV-2026-0001"
    assert len(data.lines.rows) == 1 and len(data.lines.taxes) == 1


async def test_a_template_that_cannot_be_filled_is_a_finding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def failing(data, template=None) -> bytes:
        raise TemplateError("No placeholder like that")

    monkeypatch.setattr(trial, "render_invoice_pdf", failing)
    pdf, findings = await trial.trial_render(b"x")
    assert pdf is None and [f.message for f in findings] == ["No placeholder like that"]


async def test_a_template_the_converter_cannot_open_is_a_finding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def failing(data, template=None) -> bytes:
        raise PdfEngineError("exit 1")

    monkeypatch.setattr(trial, "render_invoice_pdf", failing)
    _, findings = await trial.trial_render(b"x")
    assert findings and "could not convert" in findings[0].message


async def test_a_missing_converter_is_not_the_templates_fault(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def missing(data, template=None) -> bytes:
        raise PdfEngineNotInstalledError("none")

    monkeypatch.setattr(trial, "render_invoice_pdf", missing)
    with pytest.raises(PdfEngineNotInstalledError):
        await trial.trial_render(b"x")


@pytest.mark.libreoffice
@needs_libreoffice
async def test_the_bundled_template_renders_the_sample_on_one_page() -> None:
    pdf, findings = await trial.trial_render(bundled_template())
    assert findings == [] and pdf is not None and _pages(pdf) == 1


@pytest.mark.libreoffice
@needs_libreoffice
async def test_a_template_that_forces_a_page_break_fails_the_page_check() -> None:
    # A hard break: a paragraph with a page-break-before style.
    def add_break(parts: dict[str, bytes]) -> None:
        text = parts["content.xml"].decode()
        text = text.replace(
            "<office:automatic-styles>",
            '<office:automatic-styles><style:style style:name="Brk" style:family="paragraph">'
            '<style:paragraph-properties fo:break-before="page"/></style:style>',
            1,
        )
        text = text.replace(
            "</office:text>",
            '<text:p text:style-name="Brk">second page</text:p></office:text>',
        )
        parts["content.xml"] = text.encode()

    pdf, findings = await trial.trial_render(_rewrite(add_break))
    assert pdf is not None and _pages(pdf) == 2
    assert "takes 2 pages" in findings[0].message


@pytest.mark.libreoffice
@needs_libreoffice
async def test_an_unusable_file_is_a_finding_not_a_crash() -> None:
    _, findings = await trial.trial_render(make_odt("<text:p>no table</text:p>"))
    assert findings
