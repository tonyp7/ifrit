"""Checks an uploaded template before it can be used for invoices.

Everything here is a pure function of the file's bytes, so a hostile or broken file is
rejected before anything is stored and before LibreOffice ever opens it. Problems are grouped,
and the first group that has any is reported whole, so an author can fix them all at once."""

import io
import re
import zipfile
from collections.abc import Collection, Iterator
from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from app.pdf.odt import _ANY_BRACES, _H, _P, _STRICT, _paragraph_text
from app.pdf.tokens import TOKENS

MAX_BYTES = 5 * 1024 * 1024
MAX_ENTRIES = 200
MAX_EXPANDED_BYTES = 50 * 1024 * 1024
ODT_MIMETYPE = b"application/vnd.oasis.opendocument.text"

_XML_PARTS = ("content.xml", "styles.xml")
_ACTIVE_DIRS = ("Scripts/", "Basic/", "Dialogs/", "Object ", "ObjectReplacements/")
# Elements with these local names run code or embed another program.
_ACTIVE_ELEMENTS = {"plugin", "object", "object-ole", "applet"}
_XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
_SCRIPT_NS = "urn:oasis:names:tc:opendocument:xmlns:script:1.0"
_FONT_FACE = "{urn:oasis:names:tc:opendocument:xmlns:style:1.0}font-face"
_FONT_FAMILY = "{urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0}font-family"
_FONT_NAME = "{urn:oasis:names:tc:opendocument:xmlns:style:1.0}name"
# What a link may point at: a picture inside the file, or a place in the document.
_ALLOWED_LINKS = ("Pictures/", "./Pictures/", "#")
_SNIPPET = 80


@dataclass(frozen=True)
class Finding:
    part: str
    message: str
    snippet: str | None = None


@dataclass
class ValidationResult:
    problems: list[Finding] = field(default_factory=list)
    warnings: list[Finding] = field(default_factory=list)
    placeholders: list[str] = field(default_factory=list)


def _snippet(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= _SNIPPET else text[: _SNIPPET - 1] + "…"


def _local(tag: str) -> str:
    return tag.rpartition("}")[2]


def _namespace(tag: str) -> str:
    return tag[1:].partition("}")[0] if tag.startswith("{") else ""


# --- group 1: the container ----------------------------------------------------------------


def _container(data: bytes) -> tuple[zipfile.ZipFile | None, list[Finding]]:
    if len(data) > MAX_BYTES:
        return None, [Finding("file", "The file is larger than 5 MB")]
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return None, [
            Finding("file", "The file is not an OpenDocument Text (.odt) file")
        ]
    problems: list[Finding] = []
    names = archive.namelist()
    if len(names) > MAX_ENTRIES:
        problems.append(Finding("file", f"The file has more than {MAX_ENTRIES} parts"))
    # Sizes come from the zip's directory, so nothing is decompressed to check them.
    if sum(info.file_size for info in archive.infolist()) > MAX_EXPANDED_BYTES:
        problems.append(Finding("file", "The file expands to more than 50 MB"))
    try:
        mimetype = archive.read("mimetype") if "mimetype" in names else b""
    except zipfile.BadZipFile, NotImplementedError, RuntimeError:
        mimetype = b""
    if mimetype.strip() != ODT_MIMETYPE:
        problems.append(
            Finding("mimetype", "The file is not an OpenDocument Text (.odt) file")
        )
    for part in _XML_PARTS:
        if part not in names:
            problems.append(Finding(part, f"The part {part} is missing"))
    return (archive if not problems else None), problems


def _read_xml(
    archive: zipfile.ZipFile, name: str
) -> tuple[bytes | None, ET.Element | None, Finding | None]:
    """The raw part and its parsed tree, or the problem with it."""
    try:
        raw = archive.read(name)
    except zipfile.BadZipFile, NotImplementedError, RuntimeError, OSError:
        return None, None, Finding(name, "The part cannot be read")
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        return (
            raw,
            None,
            Finding(name, "The part has a document type or entity declaration"),
        )
    if name not in _XML_PARTS:
        # Other parts (document properties, settings, the manifest) are only checked for
        # declarations: the converter reads them, this check does not need their content.
        return raw, ET.Element("skipped"), None
    try:
        return raw, ET.fromstring(raw), None
    except ET.ParseError as err:
        return raw, None, Finding(name, f"The part is not well-formed XML: {err}")


# --- group 2 and 3: active content and outside references -------------------------------------


def _active(archive: zipfile.ZipFile, trees: dict[str, ET.Element]) -> list[Finding]:
    problems = [
        Finding(name, "The file contains a macro, script, dialog or embedded object")
        for name in archive.namelist()
        if name.startswith(_ACTIVE_DIRS)
    ]
    for part, root in trees.items():
        for element in root.iter():
            local = _local(element.tag)
            if _namespace(element.tag) == _SCRIPT_NS:
                problems.append(
                    Finding(part, "The file contains a script", f"<script:{local}>")
                )
            elif local in _ACTIVE_ELEMENTS:
                problems.append(
                    Finding(part, "The file embeds an object or plug-in", f"<{local}>")
                )
            elif local in ("scripts", "event-listeners") and len(element):
                problems.append(
                    Finding(
                        part,
                        "The file contains a script or event listener",
                        f"<{local}>",
                    )
                )
    return problems


def _external(trees: dict[str, ET.Element]) -> list[Finding]:
    problems = []
    for part, root in trees.items():
        for element in root.iter():
            href = element.get(_XLINK_HREF)
            if href is not None and not href.startswith(_ALLOWED_LINKS):
                problems.append(
                    Finding(
                        part,
                        "The file refers to something outside the document",
                        _snippet(href),
                    )
                )
    return problems


# --- group 5: placeholders --------------------------------------------------------------------


def _paragraphs(root: ET.Element) -> Iterator[ET.Element]:
    return (element for element in root.iter() if element.tag in (_P, _H))


def _tokens(trees: dict[str, ET.Element]) -> tuple[list[Finding], list[str]]:
    problems: list[Finding] = []
    used: dict[str, None] = {}
    lines_in_body = 0
    for part, root in trees.items():
        for paragraph in _paragraphs(root):
            text = _paragraph_text(paragraph)
            for match in _ANY_BRACES.finditer(text):
                written = match.group(0)
                strict = _STRICT.fullmatch(match.group(1))
                if strict is None:
                    problems.append(
                        Finding(
                            part,
                            "A placeholder is written with capitals, spaces or other characters",
                            written,
                        )
                    )
                    continue
                name = strict.group(1)
                token = TOKENS.get(name)
                if token is None:
                    problems.append(Finding(part, "Unknown placeholder", written))
                    continue
                used[name] = None
                alone = text.strip() == written
                if token.kind == "lines":
                    if part == "content.xml":
                        lines_in_body += 1
                    if part != "content.xml":
                        problems.append(
                            Finding(
                                part,
                                "{{invoice_lines}} must be in the body of the document",
                                written,
                            )
                        )
                    elif not alone:
                        problems.append(
                            Finding(
                                part,
                                "{{invoice_lines}} must be alone in its paragraph",
                                _snippet(text),
                            )
                        )
                elif token.kind == "block" and not alone:
                    problems.append(
                        Finding(
                            part,
                            f"{written} must be alone in its paragraph",
                            _snippet(text),
                        )
                    )
    if lines_in_body != 1:
        message = (
            "{{invoice_lines}} is missing from the body of the template"
            if lines_in_body == 0
            else "{{invoice_lines}} appears more than once in the body of the template"
        )
        problems.append(Finding("content.xml", message))
    return problems, list(used)


# --- warnings ---------------------------------------------------------------------------------


def declared_fonts(trees: dict[str, ET.Element]) -> list[str]:
    """The font families the template names."""
    fonts: dict[str, None] = {}
    for root in trees.values():
        for face in root.iter(_FONT_FACE):
            family = (face.get(_FONT_FAMILY) or face.get(_FONT_NAME) or "").strip(
                "'\" "
            )
            if family:
                fonts[family] = None
    return list(fonts)


def _warnings(
    trees: dict[str, ET.Element],
    used: Collection[str],
    installed_fonts: Collection[str] | None,
) -> list[Finding]:
    warnings: list[Finding] = []
    if "draft_watermark" not in used:
        warnings.append(
            Finding(
                "template",
                "The template has no {{draft_watermark}}, so previews carry no DRAFT mark",
            )
        )
    if installed_fonts is not None:
        installed = {font.lower() for font in installed_fonts}
        for family in declared_fonts(trees):
            if family.lower() not in installed:
                warnings.append(
                    Finding(
                        "styles.xml",
                        "This font is not installed and will be replaced",
                        family,
                    )
                )
    return warnings


def validate_template(
    data: bytes, installed_fonts: Collection[str] | None = None
) -> ValidationResult:
    """Everything that can be checked without converting the file. `installed_fonts` lets
    the caller supply the families the converter can use; None skips the font warning."""
    archive, problems = _container(data)
    if archive is None:
        return ValidationResult(problems=problems)
    with archive:
        trees: dict[str, ET.Element] = {}
        xml_problems: list[Finding] = []
        for name in archive.namelist():
            if not name.endswith(".xml"):
                continue
            raw, tree, problem = _read_xml(archive, name)
            if problem is not None:
                xml_problems.append(problem)
            elif tree is not None and raw is not None and name in _XML_PARTS:
                trees[name] = tree
        # The groups run in order and the first one with problems is reported whole. The
        # parse is done once up front, but its problems belong to the XML group.
        active = _active(archive, trees)
        if active:
            return ValidationResult(problems=active)
        external = _external(trees)
        if external:
            return ValidationResult(problems=external)
        if xml_problems:
            return ValidationResult(problems=xml_problems)
        token_problems, used = _tokens(trees)
        if token_problems:
            return ValidationResult(problems=token_problems, placeholders=used)
        return ValidationResult(
            warnings=_warnings(trees, used, installed_fonts), placeholders=used
        )


_FONT_LINE = re.compile(r"[^,\n]+")


def parse_fc_list(output: str) -> set[str]:
    """Family names from the output of `fc-list : family`, one line per font, each line
    holding the family and its aliases separated by commas."""
    return {name.strip() for name in _FONT_LINE.findall(output) if name.strip()}
