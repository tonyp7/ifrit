"""Fills an ODT template: replaces `{{placeholders}}` with an invoice's values and builds the
line-items table, using only the standard library.

An ODT file is a zip of XML parts. The text of the document is in `content.xml`, and page
headers and footers are in `styles.xml`, so both are filled the same way."""

import io
import re
import zipfile
from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from app.pdf.errors import TemplateError
from app.pdf.lines import LinesData, build_lines_table
from app.pdf.tokens import TOKENS

TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
TABLE_NS = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
STYLE_NS = "urn:oasis:names:tc:opendocument:xmlns:style:1.0"
OFFICE_NS = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"

_P = f"{{{TEXT_NS}}}p"
_H = f"{{{TEXT_NS}}}h"
_SPAN = f"{{{TEXT_NS}}}span"
_LINE_BREAK = f"{{{TEXT_NS}}}line-break"
_CELL = f"{{{TABLE_NS}}}table-cell"
_STYLE_NAME = f"{{{STYLE_NS}}}name"
_TEXT_STYLE_NAME = f"{{{TEXT_NS}}}style-name"

# Anything between double braces is meant as a placeholder, so a misspelt one (capitals, a
# space) is reported instead of silently printed as text.
_ANY_BRACES = re.compile(r"\{\{(.*?)\}\}", re.DOTALL)
_STRICT = re.compile(r"([a-z0-9_]+)(\?)?")

_MIMETYPE = "mimetype"
_PARTS = ("content.xml", "styles.xml")


@dataclass
class TemplateData:
    """Everything a template can ask for: `values` for the value placeholders, `blocks` for
    the ones that expand to a paragraph per item, and the line-items table."""

    values: dict[str, str]
    blocks: dict[str, list[str]]
    lines: LinesData
    # Placeholders missing from `values` and `blocks` print as nothing.
    extra: dict[str, str] = field(default_factory=dict)


def _parse(data: bytes, part: str) -> ET.Element:
    # A document type declaration is how entity-expansion attacks are written. ODF never
    # needs one, so a part that has one is refused before it is parsed.
    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        raise TemplateError(f"{part} contains a document type declaration")
    for _, (prefix, uri) in ET.iterparse(io.BytesIO(data), events=("start-ns",)):
        # Keeps the template's own prefixes (text:, table:, style:...) when it is written back.
        if prefix and not re.fullmatch(r"ns\d+", prefix):
            ET.register_namespace(prefix, uri)
    try:
        return ET.fromstring(data)
    except ET.ParseError as err:
        raise TemplateError(f"{part} is not well-formed XML: {err}") from err


def _serialize(root: ET.Element) -> bytes:
    serialized: bytes = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    return serialized


def _parent_map(root: ET.Element) -> dict[ET.Element, ET.Element]:
    return {child: parent for parent in root.iter() for child in parent}


# --- text slots --------------------------------------------------------------------------


@dataclass
class _Slot:
    element: ET.Element
    is_tail: bool

    def get(self) -> str:
        return (self.element.tail if self.is_tail else self.element.text) or ""

    def set(self, value: str) -> None:
        if self.is_tail:
            self.element.tail = value
        else:
            self.element.text = value


def _slots(paragraph: ET.Element) -> list[_Slot]:
    """The pieces of text of a paragraph in reading order. It looks into formatting spans, so
    a placeholder the editor split over several of them is seen whole, and stops at anything
    else (a tab, a frame, a link), which a placeholder cannot span."""
    found: list[_Slot] = [_Slot(paragraph, False)]

    def walk(element: ET.Element) -> None:
        for child in element:
            if child.tag == _SPAN:
                found.append(_Slot(child, False))
                walk(child)
            found.append(_Slot(child, True))

    walk(paragraph)
    return found


def _paragraph_text(paragraph: ET.Element) -> str:
    return "".join(slot.get() for slot in _slots(paragraph))


def _find_tokens(text: str) -> list[tuple[int, int, str, bool]]:
    """(start, end, name, optional) for each placeholder, raising for one that is not
    written as a lowercase name or not in the catalogue."""
    found = []
    for match in _ANY_BRACES.finditer(text):
        inner = match.group(1)
        strict = _STRICT.fullmatch(inner)
        if strict is None or strict.group(1) not in TOKENS:
            raise TemplateError(f"Unknown placeholder {match.group(0)}")
        found.append(
            (match.start(), match.end(), strict.group(1), bool(strict.group(2)))
        )
    return found


def _replace_in_paragraph(paragraph: ET.Element, replacements: dict[str, str]) -> None:
    """Replaces every placeholder of the paragraph with its text. A replacement takes the
    formatting of the first character of the placeholder it replaces."""
    slots = _slots(paragraph)
    texts = [slot.get() for slot in slots]
    joined = "".join(texts)
    matches = _find_tokens(joined)
    if not matches:
        return
    owner = [index for index, text in enumerate(texts) for _ in text]
    out = list(joined)
    for start, end, name, _ in matches:
        out[start] = replacements.get(name, "")
        for position in range(start + 1, end):
            out[position] = ""
    pieces = [""] * len(slots)
    for position, piece in enumerate(out):
        pieces[owner[position]] += piece
    # Last slot first: a value with line breaks inserts elements, which would shift the
    # position of the slots that come after them.
    for slot, text in reversed(list(zip(slots, pieces, strict=True))):
        _set_slot_text(paragraph, slot, text)


def _set_slot_text(paragraph: ET.Element, slot: _Slot, text: str) -> None:
    parts = text.split("\n")
    slot.set(parts[0])
    if len(parts) == 1:
        return
    if slot.is_tail:
        parent = _parent_of(paragraph, slot.element)
        index = list(parent).index(slot.element) + 1
    else:
        parent = slot.element
        index = 0
    for offset, part in enumerate(parts[1:]):
        line_break = ET.Element(_LINE_BREAK)
        line_break.tail = part
        parent.insert(index + offset, line_break)


def _parent_of(root: ET.Element, target: ET.Element) -> ET.Element:
    for parent in root.iter():
        if target in list(parent):
            return parent
    raise AssertionError("element not under its paragraph")  # pragma: no cover


# --- filling one XML part ------------------------------------------------------------------


def _defined_paragraph_styles(*roots: ET.Element) -> set[str]:
    names = set()
    for root in roots:
        for style in root.iter(f"{{{STYLE_NS}}}style"):
            if style.get(f"{{{STYLE_NS}}}family") == "paragraph" and style.get(
                _STYLE_NAME
            ):
                names.add(style.get(_STYLE_NAME, ""))
    return names


def _fill_part(
    root: ET.Element,
    data: TemplateData,
    *,
    body: bool,
    defined_styles: set[str],
    automatic_styles: ET.Element | None,
) -> int:
    """Fills one part and returns how many line-item tables it placed."""
    parents = _parent_map(root)
    placed = 0
    paragraphs = [el for el in root.iter() if el.tag in (_P, _H)]
    for paragraph in paragraphs:
        text = _paragraph_text(paragraph)
        if "{{" not in text:
            continue
        matches = _find_tokens(text)
        if not matches:
            continue
        parent = parents.get(paragraph)
        if parent is None:
            continue
        alone = (
            len(matches) == 1 and text.strip() == text[matches[0][0] : matches[0][1]]
        )
        kinds = {TOKENS[name].kind for _, _, name, _ in matches}
        if "lines" in kinds:
            if not alone or not body:
                raise TemplateError(
                    "{{invoice_lines}} must be alone in its paragraph, in the body of the document"
                )
            _replace_with_table(
                paragraph, parent, data, defined_styles, automatic_styles
            )
            placed += 1
        elif "block" in kinds:
            if not alone:
                raise TemplateError(
                    f"{{{{{matches[0][2]}}}}} must be alone in its paragraph"
                )
            _expand_block(
                paragraph, parent, matches[0][2], data.blocks.get(matches[0][2], [])
            )
        else:
            replacements = {
                name: data.values.get(name, "") for _, _, name, _ in matches
            }
            empty_optional = any(
                optional and not replacements[name] for _, _, name, optional in matches
            )
            if empty_optional:
                _remove_paragraph(paragraph, parent)
            else:
                _replace_in_paragraph(paragraph, replacements)
    return placed


def _remove_paragraph(paragraph: ET.Element, parent: ET.Element) -> None:
    parent.remove(paragraph)
    # A table cell cannot be left without a paragraph.
    if parent.tag == _CELL and not any(child.tag in (_P, _H) for child in parent):
        keep = ET.SubElement(parent, _P)
        style = paragraph.get(_TEXT_STYLE_NAME)
        if style:
            keep.set(_TEXT_STYLE_NAME, style)


def _expand_block(
    paragraph: ET.Element, parent: ET.Element, name: str, items: list[str]
) -> None:
    index = list(parent).index(paragraph)
    parent.remove(paragraph)
    for offset, item in enumerate(items):
        copy = deepcopy(paragraph)
        _replace_in_paragraph(copy, {name: item})
        parent.insert(index + offset, copy)
    if (
        not items
        and parent.tag == _CELL
        and not any(child.tag in (_P, _H) for child in parent)
    ):
        keep = ET.SubElement(parent, _P)
        style = paragraph.get(_TEXT_STYLE_NAME)
        if style:
            keep.set(_TEXT_STYLE_NAME, style)


def _replace_with_table(
    paragraph: ET.Element,
    parent: ET.Element,
    data: TemplateData,
    defined_styles: set[str],
    automatic_styles: ET.Element | None,
) -> None:
    if automatic_styles is None:
        raise TemplateError(
            "The template has no automatic styles to build the table with"
        )
    table, after, styles = build_lines_table(data.lines, defined_styles)
    for style in styles:
        automatic_styles.append(style)
    index = list(parent).index(paragraph)
    parent.remove(paragraph)
    # The paragraph after the table keeps it apart from a table that follows, which Writer
    # would otherwise merge into this one.
    parent.insert(index, table)
    parent.insert(index + 1, after)


# --- the whole file ------------------------------------------------------------------------


def fill_template(template: bytes, data: TemplateData) -> bytes:
    """The template with its placeholders replaced, as the bytes of a new ODT file."""
    try:
        source = zipfile.ZipFile(io.BytesIO(template))
    except zipfile.BadZipFile as err:
        raise TemplateError("The template is not a valid ODT file") from err
    with source:
        names = source.namelist()
        if _MIMETYPE not in names or any(part not in names for part in _PARTS):
            raise TemplateError("The template is not a valid ODT file")
        content = _parse(source.read("content.xml"), "content.xml")
        styles = _parse(source.read("styles.xml"), "styles.xml")
        defined = _defined_paragraph_styles(content, styles)
        automatic = content.find(f"{{{OFFICE_NS}}}automatic-styles")

        placed = _fill_part(
            content, data, body=True, defined_styles=defined, automatic_styles=automatic
        )
        _fill_part(
            styles, data, body=False, defined_styles=defined, automatic_styles=None
        )
        if placed != 1:
            raise TemplateError(
                "{{invoice_lines}} must appear exactly once in the body of the template"
            )

        replaced = {
            "content.xml": _serialize(content),
            "styles.xml": _serialize(styles),
        }
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as target:
            # The mimetype entry comes first and is stored, so tools can identify the file.
            target.writestr(
                zipfile.ZipInfo(_MIMETYPE), source.read(_MIMETYPE), zipfile.ZIP_STORED
            )
            for name in names:
                if name == _MIMETYPE or name.endswith("/"):
                    continue
                payload = replaced.get(name) or source.read(name)
                target.writestr(name, payload, zipfile.ZIP_DEFLATED)
    return out.getvalue()


def placeholders_in(template: bytes) -> Iterable[str]:
    """The names of the placeholders a template uses, in order of first appearance."""
    seen: dict[str, None] = {}
    with zipfile.ZipFile(io.BytesIO(template)) as source:
        for part in _PARTS:
            root = _parse(source.read(part), part)
            for element in root.iter():
                if element.tag in (_P, _H):
                    for _, _, name, _ in _find_tokens(_paragraph_text(element)):
                        seen[name] = None
    return seen
