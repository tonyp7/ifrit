import io
import zipfile
from xml.etree import ElementTree as ET

import pytest

from app.pdf.errors import TemplateError
from app.pdf.lines import LineRow, LinesData, TaxRow
from app.pdf.odt import TemplateData, fill_template, placeholders_in
from app.pdf.render import bundled_template
from app.pdf.tokens import TOKENS
from tests.odt_helpers import LINES_PARAGRAPH, make_odt, read_part

TEXT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"
TABLE = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"


def _data(
    values: dict[str, str] | None = None,
    blocks: dict[str, list[str]] | None = None,
    lines: LinesData | None = None,
) -> TemplateData:
    return TemplateData(
        values=values or {},
        blocks=blocks or {},
        lines=lines or LinesData(currency="USD"),
    )


def _fill(body: str, data: TemplateData | None = None, **kwargs: str) -> str:
    odt = make_odt(body + LINES_PARAGRAPH, **kwargs)
    return read_part(fill_template(odt, data or _data()))


def _texts(xml: str) -> list[str]:
    root = ET.fromstring(xml.encode())
    return ["".join(p.itertext()) for p in root.iter(f"{TEXT}p")]


def test_replaces_a_placeholder_in_the_body() -> None:
    xml = _fill(
        "<text:p>No. {{invoice_number}}</text:p>", _data({"invoice_number": "INV-1"})
    )
    assert "No. INV-1" in _texts(xml)


def test_replaces_a_placeholder_in_a_page_header() -> None:
    odt = make_odt(
        LINES_PARAGRAPH,
        master="<style:header><text:p>{{invoice_number}} - {{bill_to_name}}</text:p></style:header>",
    )
    out = fill_template(odt, _data({"invoice_number": "INV-1", "bill_to_name": "ACME"}))
    assert "INV-1 - ACME" in _texts(read_part(out, "styles.xml"))


def test_replaces_a_placeholder_inside_a_text_box() -> None:
    body = "<text:p><draw:frame><draw:text-box><text:p>{{status}}</text:p></draw:text-box></draw:frame></text:p>"
    assert "Draft" in _texts(_fill(body, _data({"status": "Draft"})))


def test_a_value_is_text_never_markup() -> None:
    xml = _fill(
        "<text:p>{{bill_to_name}}</text:p>",
        _data({"bill_to_name": "Smith & Sons <b>Ltd</b>"}),
    )
    assert "Smith &amp; Sons &lt;b&gt;Ltd&lt;/b&gt;" in xml
    assert "Smith & Sons <b>Ltd</b>" in _texts(xml)


def test_a_placeholder_split_over_formatting_runs_is_joined() -> None:
    body = (
        '<text:p><text:span text:style-name="B">{{inv</text:span>'
        '<text:span text:style-name="C">oice_nu</text:span>mber}} end</text:p>'
    )
    xml = _fill(body, _data({"invoice_number": "INV-9"}))
    assert "INV-9 end" in _texts(xml)
    # The value sits in the run of the placeholder's first character.
    assert '<text:span text:style-name="B">INV-9</text:span>' in xml


def test_line_breaks_in_a_value_are_kept() -> None:
    xml = _fill(
        "<text:p>{{bill_to_name}}</text:p>", _data({"bill_to_name": "One\nTwo"})
    )
    root = ET.fromstring(xml.encode())
    paragraph = next(p for p in root.iter(f"{TEXT}p") if p.text == "One")
    breaks = list(paragraph.iter(f"{TEXT}line-break"))
    assert len(breaks) == 1 and breaks[0].tail == "Two"


def test_an_empty_optional_placeholder_removes_its_paragraph() -> None:
    body = "<text:p>Bank: {{payee_bank_name?}}</text:p><text:p>Keep</text:p>"
    texts = _texts(_fill(body, _data({"payee_bank_name": ""})))
    assert "Keep" in texts
    assert not any(t.startswith("Bank") for t in texts)


def test_an_optional_placeholder_with_a_value_prints() -> None:
    texts = _texts(
        _fill(
            "<text:p>Bank: {{payee_bank_name?}}</text:p>",
            _data({"payee_bank_name": "DBS"}),
        )
    )
    assert "Bank: DBS" in texts


def test_an_empty_plain_placeholder_prints_nothing() -> None:
    assert "Period: " in _texts(_fill("<text:p>Period: {{period}}</text:p>"))


def test_removing_the_only_paragraph_of_a_cell_leaves_an_empty_one() -> None:
    body = (
        "<table:table><table:table-row><table:table-cell>"
        '<text:p text:style-name="S">{{payee_bic?}}</text:p>'
        "</table:table-cell></table:table-row></table:table>"
    )
    xml = _fill(body)
    root = ET.fromstring(xml.encode())
    cell = next(root.iter(f"{TABLE}table-cell"))
    paragraphs = list(cell)
    assert len(paragraphs) == 1 and not "".join(paragraphs[0].itertext())


def test_a_block_placeholder_becomes_one_paragraph_per_item() -> None:
    body = '<text:p text:style-name="Ref">{{references}}</text:p>'
    xml = _fill(body, _data(blocks={"references": ["PO: 1", "Contract: 2"]}))
    root = ET.fromstring(xml.encode())
    refs = [p for p in root.iter(f"{TEXT}p") if p.get(f"{TEXT}style-name") == "Ref"]
    assert ["".join(p.itertext()) for p in refs] == ["PO: 1", "Contract: 2"]


def test_a_block_placeholder_without_items_removes_its_paragraph() -> None:
    body = '<text:p text:style-name="Addr">{{bill_to_address_lines}}</text:p><text:p>after</text:p>'
    xml = _fill(body)
    assert 'text:style-name="Addr"' not in xml
    assert "after" in _texts(xml)


def test_a_block_placeholder_must_be_alone_in_its_paragraph() -> None:
    with pytest.raises(TemplateError, match="alone"):
        _fill("<text:p>Refs: {{references}}</text:p>")


def test_an_unknown_placeholder_fails() -> None:
    with pytest.raises(TemplateError, match="invoice_numbr"):
        _fill("<text:p>{{invoice_numbr}}</text:p>")


@pytest.mark.parametrize("text", ["{{Invoice_Number}}", "{{ invoice_number }}", "{{}}"])
def test_a_misspelt_placeholder_fails(text: str) -> None:
    with pytest.raises(TemplateError):
        _fill(f"<text:p>{text}</text:p>")


def test_a_doctype_is_refused() -> None:
    odt = make_odt(LINES_PARAGRAPH, content_prefix='<!DOCTYPE x [<!ENTITY a "b">]>')
    with pytest.raises(TemplateError, match="document type"):
        fill_template(odt, _data())


def test_not_a_zip_fails() -> None:
    with pytest.raises(TemplateError):
        fill_template(b"not a zip", _data())


def test_the_lines_placeholder_is_required_exactly_once() -> None:
    with pytest.raises(TemplateError, match="exactly once"):
        fill_template(make_odt("<text:p>none</text:p>"), _data())
    with pytest.raises(TemplateError, match="exactly once"):
        fill_template(make_odt(LINES_PARAGRAPH * 2), _data())


def test_the_lines_placeholder_must_be_alone_in_its_paragraph() -> None:
    with pytest.raises(TemplateError, match="alone"):
        fill_template(make_odt("<text:p>x {{invoice_lines}}</text:p>"), _data())


def test_the_lines_placeholder_is_not_allowed_in_a_header() -> None:
    odt = make_odt(
        LINES_PARAGRAPH,
        master="<style:header><text:p>{{invoice_lines}}</text:p></style:header>",
    )
    with pytest.raises(TemplateError):
        fill_template(odt, _data())


def test_the_output_is_an_odt_with_the_mimetype_first_and_stored() -> None:
    out = fill_template(make_odt(), _data())
    with zipfile.ZipFile(io.BytesIO(out)) as archive:
        first = archive.infolist()[0]
        assert first.filename == "mimetype"
        assert first.compress_type == zipfile.ZIP_STORED
        assert archive.read("mimetype") == b"application/vnd.oasis.opendocument.text"


def test_other_parts_are_carried_over() -> None:
    template = bundled_template()
    out = fill_template(template, _bundled_data())
    with (
        zipfile.ZipFile(io.BytesIO(template)) as before,
        zipfile.ZipFile(io.BytesIO(out)) as after,
    ):
        assert sorted(before.namelist()) == sorted(after.namelist())
        assert before.read("Pictures/logo.png") == after.read("Pictures/logo.png")


# --- the lines table -------------------------------------------------------------------------


def _lines() -> LinesData:
    return LinesData(
        currency="USD",
        rows=[LineRow("Consulting", "20", "Day(s)", "300.00", "6,000.00")],
        subtotal="6,000.00",
        taxes=[TaxRow("GST (7 %)", "420.00")],
        total="6,420.00",
    )


def _table(xml: str) -> ET.Element:
    root = ET.fromstring(xml.encode())
    return next(root.iter(f"{TABLE}table"))


def _row_texts(table: ET.Element) -> list[list[str]]:
    rows = []
    for row in table.iter(f"{TABLE}table-row"):
        rows.append(["".join(c.itertext()) for c in row.iter(f"{TABLE}table-cell")])
    return rows


def test_the_lines_table_has_header_line_subtotal_tax_and_total_rows() -> None:
    xml = read_part(fill_template(make_odt(), _data(lines=_lines())))
    rows = _row_texts(_table(xml))
    assert rows[0] == [
        "Description",
        "Quantity",
        "Unit",
        "Unit Price",
        "Currency",
        "Total Price",
    ]
    assert rows[1] == ["Consulting", "20", "Day(s)", "300.00", "USD", "6,000.00"]
    assert rows[2] == ["Subtotal", "USD", "6,000.00"]
    assert rows[3] == ["GST (7 %)", "USD", "420.00"]
    assert rows[4] == ["Total", "USD", "6,420.00"]


def test_the_header_row_repeats_and_rows_are_kept_whole() -> None:
    xml = read_part(fill_template(make_odt(), _data(lines=_lines())))
    table = _table(xml)
    assert table.find(f"{TABLE}table-header-rows") is not None
    assert 'fo:keep-together="always"' in xml
    assert 'style:rel-width="100%"' in xml


def test_the_label_cells_of_the_summary_rows_span_four_columns() -> None:
    xml = read_part(fill_template(make_odt(), _data(lines=_lines())))
    spans = [
        c.get(f"{TABLE}number-columns-spanned")
        for c in _table(xml).iter(f"{TABLE}table-cell")
    ]
    assert spans.count("4") == 3
    assert xml.count("<table:covered-table-cell") == 9


def test_an_invoice_without_lines_has_only_header_and_totals() -> None:
    data = _data(lines=LinesData(currency="USD", subtotal="0.00", total="0.00"))
    rows = _row_texts(_table(read_part(fill_template(make_odt(), data))))
    assert [r[0] for r in rows] == ["Description", "Subtotal", "Total"]


def test_template_paragraph_styles_are_used_when_defined_and_built_in_otherwise() -> (
    None
):
    defined = '<style:style style:name="InvoiceLinesCell" style:family="paragraph"/>'
    odt = make_odt(styles_extra=defined)
    xml = read_part(fill_template(odt, _data(lines=_lines())))
    # The defined style is not redefined; the five others get a built-in look.
    assert xml.count('style:name="InvoiceLinesCell"') == 0
    for name in ("InvoiceLinesHeader", "InvoiceLinesNumber", "InvoiceLinesTotal"):
        assert f'style:name="{name}"' in xml
    assert 'text:style-name="InvoiceLinesCell"' in xml


def test_line_text_with_breaks_and_spaces_is_written_as_elements() -> None:
    lines = _lines()
    lines.rows[0].description = "First\nSecond  gap"
    xml = read_part(fill_template(make_odt(), _data(lines=lines)))
    assert "<text:line-break" in xml
    assert '<text:s text:c="1"' in xml


# --- the bundled template --------------------------------------------------------------------


def _bundled_data() -> TemplateData:
    return _data(
        {name: f"<{name}>" for name, token in TOKENS.items() if token.kind == "value"},
        {
            name: [f"<{name}>"]
            for name, token in TOKENS.items()
            if token.kind == "block"
        },
        _lines(),
    )


def test_the_bundled_template_uses_only_catalogue_placeholders() -> None:
    names = list(placeholders_in(bundled_template()))
    assert "invoice_lines" in names and "draft_watermark" in names
    assert len(names) == 19
    assert set(names) <= set(TOKENS)


def test_the_bundled_template_fills_without_leftover_placeholders() -> None:
    out = fill_template(bundled_template(), _bundled_data())
    assert "{{" not in read_part(out) and "{{" not in read_part(out, "styles.xml")


STYLE = "{urn:oasis:names:tc:opendocument:xmlns:style:1.0}"
FO = "{urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0}"


def _paragraph_style_of_cells(row: ET.Element) -> list[str]:
    return [
        cell.find(f"{TEXT}p").get(f"{TEXT}style-name")  # type: ignore[union-attr]
        for cell in row.findall(f"{TABLE}table-cell")
    ]


def _style_element(xml: str, name: str) -> ET.Element:
    root = ET.fromstring(xml.encode())
    return next(s for s in root.iter(f"{STYLE}style") if s.get(f"{STYLE}name") == name)


def _total_row_currency_style(xml: str) -> tuple[str, list[str]]:
    rows = list(_table(xml).iter(f"{TABLE}table-row"))
    names = _paragraph_style_of_cells(rows[-1])
    return names[1], names


def test_the_total_rows_currency_is_aligned_like_the_rest_of_the_column() -> None:
    xml = read_part(fill_template(make_odt(), _data(lines=_lines())))
    rows = list(_table(xml).iter(f"{TABLE}table-row"))
    currency, names = _total_row_currency_style(xml)
    # The Total label and amount keep the Total style; the line, Subtotal and tax rows are as before.
    assert names[0] == names[2] == "InvoiceLinesTotal"
    assert _paragraph_style_of_cells(rows[1])[4] == "InvoiceLinesCell"
    assert _paragraph_style_of_cells(rows[2])[1] == "InvoiceLinesCell"
    assert _paragraph_style_of_cells(rows[3])[1] == "InvoiceLinesCell"
    # The built-in look: the currency cell is bold like the Total row but starts at the cell's edge.
    assert currency != "InvoiceLinesTotal"
    style = _style_element(xml, currency)
    assert style.find(f"{STYLE}paragraph-properties").get(f"{FO}text-align") == "start"  # type: ignore[union-attr]
    assert style.find(f"{STYLE}text-properties").get(f"{FO}font-weight") == "bold"  # type: ignore[union-attr]


def test_the_total_rows_currency_inherits_a_template_defined_total_style() -> None:
    defined = (
        '<style:style style:name="InvoiceLinesTotal" style:family="paragraph">'
        '<style:paragraph-properties fo:text-align="end"/>'
        '<style:text-properties fo:font-weight="bold" fo:font-size="12pt"/>'
        "</style:style>"
    )
    xml = read_part(
        fill_template(make_odt(styles_extra=defined), _data(lines=_lines()))
    )
    currency, _ = _total_row_currency_style(xml)
    style = _style_element(xml, currency)
    assert style.get(f"{STYLE}parent-style-name") == "InvoiceLinesTotal"
    assert style.find(f"{STYLE}paragraph-properties").get(f"{FO}text-align") == "start"  # type: ignore[union-attr]
    # Only the alignment is overridden: the weight and size come from the parent.
    assert style.find(f"{STYLE}text-properties") is None


def test_the_bundled_footer_names_the_issuer_centred_above_the_page_number() -> None:
    styles = read_part(fill_template(bundled_template(), _bundled_data()), "styles.xml")
    root = ET.fromstring(styles.encode())
    footers = list(root.iter(f"{STYLE}footer"))
    assert footers
    for footer in footers:
        paragraphs = footer.findall(f"{TEXT}p")
        assert (
            "".join(paragraphs[0].itertext()) == "<bill_from_name>, <bill_from_address>"
        )
        assert paragraphs[0].get(f"{TEXT}style-name") == "InvFooterText"
        assert "/" in "".join(paragraphs[-1].itertext())
    style = _style_element(styles, "InvFooterText")
    assert style.find(f"{STYLE}paragraph-properties").get(f"{FO}text-align") == "center"  # type: ignore[union-attr]
