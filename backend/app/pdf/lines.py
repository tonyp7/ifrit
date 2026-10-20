"""Builds the line-items table that stands in for `{{invoice_lines}}`.

A template author cannot write "one row per line" in a template, so the table is generated:
the engine writes its structure, widths and borders, and the template controls how the text
looks through six paragraph styles it may define by name."""

import re
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
TABLE_NS = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
STYLE_NS = "urn:oasis:names:tc:opendocument:xmlns:style:1.0"
OFFICE_NS = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
FO_NS = "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"

for _prefix, _uri in (
    ("text", TEXT_NS),
    ("table", TABLE_NS),
    ("style", STYLE_NS),
    ("office", OFFICE_NS),
    ("fo", FO_NS),
):
    ET.register_namespace(_prefix, _uri)


def _q(namespace: str, name: str) -> str:
    return f"{{{namespace}}}{name}"


# The six paragraph styles a template may define to restyle the table.
HEADER = "InvoiceLinesHeader"
HEADER_NUMBER = "InvoiceLinesHeaderNumber"
CELL = "InvoiceLinesCell"
NUMBER = "InvoiceLinesNumber"
LABEL = "InvoiceLinesLabel"
TOTAL = "InvoiceLinesTotal"

COLUMNS = ("Description", "Quantity", "Unit", "Unit Price", "Currency", "Total Price")
# Relative widths of the six columns, in the same order.
_WEIGHTS = (36, 12, 10, 14, 11, 17)
# The width of the text area of the default template (A4, 20 mm margins). Only a starting
# point: the table is set to 100 % of the text width, which Writer applies whatever the page.
_NOMINAL_WIDTH_MM = 170

_INK = "#1f2933"
_RULE = "#52606d"
_LIGHT = "#cbd2d9"

_PREFIX = "IvLn"
_SPACES = re.compile(r" {2,}")


@dataclass
class LineRow:
    description: str
    quantity: str
    unit: str
    unit_price: str
    amount: str


@dataclass
class TaxRow:
    label: str
    amount: str


@dataclass
class LinesData:
    currency: str = ""
    rows: list[LineRow] = field(default_factory=list)
    subtotal: str = ""
    taxes: list[TaxRow] = field(default_factory=list)
    total: str = ""


def _style(name: str, family: str, **props: dict[str, str]) -> ET.Element:
    style = ET.Element(
        _q(STYLE_NS, "style"),
        {_q(STYLE_NS, "name"): name, _q(STYLE_NS, "family"): family},
    )
    for tag, attributes in props.items():
        ET.SubElement(style, _q(STYLE_NS, tag.replace("_", "-")), attributes)
    return style


def _fo(**attributes: str) -> dict[str, str]:
    return {
        _q(FO_NS, key.replace("_", "-")): value for key, value in attributes.items()
    }


def _cell_style(name: str, *, top: str = "none", bottom: str = "none") -> ET.Element:
    return _style(
        name,
        "table-cell",
        table_cell_properties=_fo(
            padding_top="1.2mm",
            padding_bottom="1.2mm",
            padding_left="1.5mm",
            padding_right="1.5mm",
            border_top=top,
            border_bottom=bottom,
            border_left="none",
            border_right="none",
        ),
    )


def _fallback_paragraph(name: str, *, bold: bool, align: str) -> ET.Element:
    return _style(
        name,
        "paragraph",
        paragraph_properties=_fo(
            text_align=align, margin_top="0mm", margin_bottom="0mm"
        ),
        text_properties={
            **_fo(
                font_size="9.5pt", font_weight="bold" if bold else "normal", color=_INK
            ),
            _q(FO_NS, "font-family"): "'Liberation Sans'",
        },
    )


_FALLBACKS: dict[str, tuple[bool, str]] = {
    HEADER: (True, "start"),
    HEADER_NUMBER: (True, "end"),
    CELL: (False, "start"),
    NUMBER: (False, "end"),
    LABEL: (False, "end"),
    TOTAL: (True, "end"),
}


def _paragraph(style: str, text: str) -> ET.Element:
    paragraph = ET.Element(_q(TEXT_NS, "p"), {_q(TEXT_NS, "style-name"): style})
    _write_text(paragraph, text)
    return paragraph


def _write_text(paragraph: ET.Element, text: str) -> None:
    """Text as ODF wants it: line breaks and runs of spaces are elements, since plain
    whitespace in a text node collapses to one space."""
    last: ET.Element | None = None

    def add(chunk: str) -> None:
        nonlocal last
        # Runs of spaces become one space plus a counted `text:s`.
        position = 0
        for match in _SPACES.finditer(chunk):
            _append(chunk[position : match.start() + 1])
            space = ET.SubElement(
                paragraph,
                _q(TEXT_NS, "s"),
                {_q(TEXT_NS, "c"): str(len(match.group()) - 1)},
            )
            last = space
            position = match.end()
        _append(chunk[position:])

    def _append(chunk: str) -> None:
        nonlocal last
        if last is None:
            paragraph.text = (paragraph.text or "") + chunk
        else:
            last.tail = (last.tail or "") + chunk

    for index, part in enumerate(text.split("\n")):
        if index:
            last = ET.SubElement(paragraph, _q(TEXT_NS, "line-break"))
        add(part)


def _cell(
    style: str, paragraph_style: str, text: str, span: int = 1
) -> list[ET.Element]:
    attributes = {
        _q(TABLE_NS, "style-name"): style,
        _q(OFFICE_NS, "value-type"): "string",
    }
    if span > 1:
        attributes[_q(TABLE_NS, "number-columns-spanned")] = str(span)
    cell = ET.Element(_q(TABLE_NS, "table-cell"), attributes)
    cell.append(_paragraph(paragraph_style, text))
    covered = [ET.Element(_q(TABLE_NS, "covered-table-cell")) for _ in range(span - 1)]
    return [cell, *covered]


def _row(cells: list[list[ET.Element]]) -> ET.Element:
    row = ET.Element(
        _q(TABLE_NS, "table-row"), {_q(TABLE_NS, "style-name"): f"{_PREFIX}Row"}
    )
    for group in cells:
        row.extend(group)
    return row


def build_lines_table(
    data: LinesData, defined_styles: set[str]
) -> tuple[ET.Element, ET.Element, list[ET.Element]]:
    """The table, the small paragraph that follows it, and the automatic styles to add to the
    document. Paragraph styles the template defines are used by name; the others get a
    built-in look."""
    total_weight = sum(_WEIGHTS)
    styles: list[ET.Element] = [
        _style(
            f"{_PREFIX}Table",
            "table",
            table_properties={
                _q(STYLE_NS, "width"): f"{_NOMINAL_WIDTH_MM}mm",
                _q(STYLE_NS, "rel-width"): "100%",
                _q(TABLE_NS, "align"): "margins",
                **_fo(margin_top="2mm", margin_bottom="0mm"),
            },
        ),
        _style(
            f"{_PREFIX}Row",
            "table-row",
            table_row_properties=_fo(keep_together="always"),
        ),
        _cell_style(f"{_PREFIX}Head", bottom=f"0.75pt solid {_RULE}"),
        _cell_style(f"{_PREFIX}Body", bottom=f"0.25pt solid {_LIGHT}"),
        _cell_style(f"{_PREFIX}Sub", top=f"0.75pt solid {_RULE}"),
        _cell_style(f"{_PREFIX}Plain"),
        _cell_style(f"{_PREFIX}Total", top=f"1.25pt solid {_INK}"),
    ]
    for index, weight in enumerate(_WEIGHTS):
        styles.append(
            _style(
                f"{_PREFIX}Col{index}",
                "table-column",
                table_column_properties={
                    _q(
                        STYLE_NS, "column-width"
                    ): f"{_NOMINAL_WIDTH_MM * weight / total_weight:.2f}mm",
                    _q(STYLE_NS, "rel-column-width"): f"{weight * 100}*",
                },
            )
        )
    for name, options in _FALLBACKS.items():
        if name not in defined_styles:
            styles.append(_fallback_paragraph(name, bold=options[0], align=options[1]))
    styles.append(
        _style(
            f"{_PREFIX}After",
            "paragraph",
            paragraph_properties=_fo(margin_top="0mm", margin_bottom="0mm"),
            text_properties=_fo(font_size="6pt"),
        )
    )

    table = ET.Element(
        _q(TABLE_NS, "table"),
        {
            _q(TABLE_NS, "name"): "InvoiceLines",
            _q(TABLE_NS, "style-name"): f"{_PREFIX}Table",
        },
    )
    for index in range(len(COLUMNS)):
        ET.SubElement(
            table,
            _q(TABLE_NS, "table-column"),
            {_q(TABLE_NS, "style-name"): f"{_PREFIX}Col{index}"},
        )

    head = ET.SubElement(table, _q(TABLE_NS, "table-header-rows"))
    numeric = {1, 3, 5}
    head.append(
        _row(
            [
                _cell(
                    f"{_PREFIX}Head", HEADER_NUMBER if i in numeric else HEADER, label
                )
                for i, label in enumerate(COLUMNS)
            ]
        )
    )
    for line in data.rows:
        table.append(
            _row(
                [
                    _cell(f"{_PREFIX}Body", CELL, line.description),
                    _cell(f"{_PREFIX}Body", NUMBER, line.quantity),
                    _cell(f"{_PREFIX}Body", CELL, line.unit),
                    _cell(f"{_PREFIX}Body", NUMBER, line.unit_price),
                    _cell(f"{_PREFIX}Body", CELL, data.currency),
                    _cell(f"{_PREFIX}Body", NUMBER, line.amount),
                ]
            )
        )

    def summary(
        cell_style: str, label_style: str, label: str, amount: str, amount_style: str
    ) -> ET.Element:
        return _row(
            [
                _cell(cell_style, label_style, label, span=4),
                _cell(
                    cell_style, CELL if amount_style == NUMBER else TOTAL, data.currency
                ),
                _cell(cell_style, amount_style, amount),
            ]
        )

    table.append(summary(f"{_PREFIX}Sub", LABEL, "Subtotal", data.subtotal, NUMBER))
    for tax in data.taxes:
        table.append(summary(f"{_PREFIX}Plain", LABEL, tax.label, tax.amount, NUMBER))
    table.append(summary(f"{_PREFIX}Total", TOTAL, "Total", data.total, TOTAL))

    after = ET.Element(_q(TEXT_NS, "p"), {_q(TEXT_NS, "style-name"): f"{_PREFIX}After"})
    return table, after, styles
