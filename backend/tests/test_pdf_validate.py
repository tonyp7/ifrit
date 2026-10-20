import io
import zipfile
from collections.abc import Callable

import pytest

from app.pdf.render import bundled_template
from app.pdf.tokens import TOKENS
from app.pdf.validate import (
    MAX_BYTES,
    Finding,
    ValidationResult,
    declared_fonts,
    parse_fc_list,
    validate_template,
)
from tests.odt_helpers import make_odt


def _rewrite(
    edit: Callable[[dict[str, bytes]], None], base: bytes | None = None
) -> bytes:
    """The bundled template with its parts changed by `edit` (name -> bytes, in place)."""
    source = zipfile.ZipFile(io.BytesIO(base or bundled_template()))
    parts = {name: source.read(name) for name in source.namelist()}
    edit(parts)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr(
            zipfile.ZipInfo("mimetype"), parts.pop("mimetype"), zipfile.ZIP_STORED
        )
        for name, payload in parts.items():
            archive.writestr(name, payload, zipfile.ZIP_DEFLATED)
    return out.getvalue()


def _replace(part: str, old: str, new: str) -> Callable[[dict[str, bytes]], None]:
    def edit(parts: dict[str, bytes]) -> None:
        text = parts[part].decode()
        assert old in text, old
        parts[part] = text.replace(old, new, 1).encode()

    return edit


def _messages(result: ValidationResult) -> list[str]:
    return [finding.message for finding in result.problems]


def _snippets(result: ValidationResult) -> list[str | None]:
    return [finding.snippet for finding in result.problems]


def test_the_bundled_template_passes_without_a_problem_or_a_warning() -> None:
    result = validate_template(bundled_template(), installed_fonts={"Liberation Sans"})
    assert result.problems == [] and result.warnings == []
    assert (
        "invoice_lines" in result.placeholders
        and "draft_watermark" in result.placeholders
    )
    assert set(result.placeholders) <= set(TOKENS)


# --- the container ---------------------------------------------------------------------------


def test_something_that_is_not_a_zip_is_rejected() -> None:
    result = validate_template(b"just some text")
    assert [f.part for f in result.problems] == ["file"]


def test_a_docx_with_an_odt_name_is_rejected() -> None:
    docx = _rewrite(
        lambda parts: parts.__setitem__("mimetype", b"application/vnd.openxmlformats")
    )
    assert "not an OpenDocument Text" in _messages(validate_template(docx))[0]


def test_a_missing_mimetype_is_rejected() -> None:
    def drop(parts: dict[str, bytes]) -> None:
        parts["mimetype"] = b""

    assert _messages(validate_template(_rewrite(drop)))


def test_a_file_over_5_mb_is_rejected() -> None:
    result = validate_template(b"0" * (MAX_BYTES + 1))
    assert "5 MB" in _messages(result)[0]


def test_too_many_parts_are_rejected() -> None:
    def add(parts: dict[str, bytes]) -> None:
        for i in range(201):
            parts[f"Pictures/p{i}.png"] = b"x"

    assert any(
        "more than 200" in m for m in _messages(validate_template(_rewrite(add)))
    )


def test_a_file_that_expands_to_more_than_50_mb_is_rejected() -> None:
    def bomb(parts: dict[str, bytes]) -> None:
        parts["Pictures/big.bin"] = b"\0" * (51 * 1024 * 1024)

    result = validate_template(_rewrite(bomb))
    assert any("50 MB" in m for m in _messages(result))


def test_a_missing_body_part_is_reported() -> None:
    def drop(parts: dict[str, bytes]) -> None:
        del parts["styles.xml"]

    assert any(
        "styles.xml is missing" in m
        for m in _messages(validate_template(_rewrite(drop)))
    )


# --- active content --------------------------------------------------------------------------


@pytest.mark.parametrize("directory", ["Scripts/", "Basic/", "Dialogs/"])
def test_macro_parts_are_rejected(directory: str) -> None:
    def add(parts: dict[str, bytes]) -> None:
        parts[f"{directory}x.xml"] = b"<x/>"

    result = validate_template(_rewrite(add))
    assert "macro" in _messages(result)[0]
    assert result.problems[0].part == f"{directory}x.xml"


def test_a_script_element_is_rejected() -> None:
    edit = _replace(
        "content.xml",
        "<office:body>",
        '<office:body><script:script xmlns:script="urn:oasis:names:tc:opendocument:xmlns:script:1.0"/>',
    )
    assert "script" in _messages(validate_template(_rewrite(edit)))[0]


def test_an_event_listener_is_rejected() -> None:
    edit = _replace(
        "content.xml",
        "<office:body>",
        "<office:body><office:event-listeners><script:event-listener "
        'xmlns:script="urn:oasis:names:tc:opendocument:xmlns:script:1.0"/></office:event-listeners>',
    )
    assert _messages(validate_template(_rewrite(edit)))


@pytest.mark.parametrize("element", ["draw:plugin", "draw:object", "draw:object-ole"])
def test_embedded_objects_and_plugins_are_rejected(element: str) -> None:
    edit = _replace("content.xml", "<office:body>", f"<office:body><{element}/>")
    assert "embeds" in _messages(validate_template(_rewrite(edit)))[0]


def test_an_embedded_object_part_is_rejected() -> None:
    def add(parts: dict[str, bytes]) -> None:
        parts["Object 1/content.xml"] = b"<x/>"

    assert _messages(validate_template(_rewrite(add)))


def test_an_empty_scripts_element_is_normal_and_accepted() -> None:
    edit = _replace("content.xml", "<office:body>", "<office:scripts/><office:body>")
    assert validate_template(_rewrite(edit)).problems == []


# --- outside references ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "href",
    ["http://example.com/logo.png", "file:///etc/passwd", "../logo.png", "//host/x"],
)
def test_a_link_to_the_outside_is_rejected(href: str) -> None:
    edit = _replace(
        "content.xml", 'xlink:href="Pictures/logo.png"', f'xlink:href="{href}"'
    )
    result = validate_template(_rewrite(edit))
    assert "outside the document" in _messages(result)[0]
    assert _snippets(result) == [href]


def test_a_web_hyperlink_is_rejected_and_an_anchor_is_not() -> None:
    link = '<text:p><text:a xlink:type="simple" xlink:href="{}">x</text:a></text:p>'
    base = _replace(
        "content.xml",
        "<office:body><office:text>",
        "<office:body><office:text>" + link.format("https://x.example"),
    )
    assert _messages(validate_template(_rewrite(base)))
    anchor = _replace(
        "content.xml",
        "<office:body><office:text>",
        "<office:body><office:text>" + link.format("#Section1"),
    )
    assert validate_template(_rewrite(anchor)).problems == []


# --- the XML ---------------------------------------------------------------------------------


def test_a_doctype_is_rejected_in_any_xml_part() -> None:
    def add(parts: dict[str, bytes]) -> None:
        parts["meta.xml"] = b'<!DOCTYPE x [<!ENTITY a "b">]><x/>'

    result = validate_template(_rewrite(add))
    assert result.problems[0].part == "meta.xml"
    assert "declaration" in result.problems[0].message


def test_malformed_xml_is_rejected() -> None:
    def break_it(parts: dict[str, bytes]) -> None:
        parts["content.xml"] = parts["content.xml"] + b"<unclosed>"

    assert "not well-formed" in _messages(validate_template(_rewrite(break_it)))[0]


# --- placeholders ----------------------------------------------------------------------------


def test_an_unknown_placeholder_is_reported_with_its_part_and_text() -> None:
    result = validate_template(
        _rewrite(_replace("content.xml", "{{invoice_number}}", "{{invoice_numbr}}"))
    )
    assert result.problems == [
        Finding("content.xml", "Unknown placeholder", "{{invoice_numbr}}")
    ]


@pytest.mark.parametrize(
    "written", ["{{Invoice_Number}}", "{{ invoice_number }}", "{{}}"]
)
def test_a_badly_written_placeholder_is_reported(written: str) -> None:
    result = validate_template(
        _rewrite(_replace("content.xml", "{{invoice_number}}", written))
    )
    assert "capitals, spaces" in _messages(result)[0] and _snippets(result) == [written]


def test_a_placeholder_in_a_header_is_checked_too() -> None:
    result = validate_template(
        _rewrite(_replace("styles.xml", "{{bill_to_name}}", "{{bill_to_nam}}"))
    )
    assert result.problems[0].part == "styles.xml"


def test_a_block_placeholder_must_be_alone_in_its_paragraph() -> None:
    edit = _replace("content.xml", "{{references}}", "Refs: {{references}}")
    result = validate_template(_rewrite(edit))
    assert "must be alone" in _messages(result)[0]


def test_the_lines_placeholder_is_required_once_and_alone() -> None:
    missing = _rewrite(_replace("content.xml", "{{invoice_lines}}", ""))
    assert "missing" in _messages(validate_template(missing))[0]
    twice = _rewrite(
        _replace(
            "content.xml",
            "{{invoice_lines}}",
            "{{invoice_lines}}</text:p><text:p>{{invoice_lines}}",
        )
    )
    assert "more than once" in _messages(validate_template(twice))[0]
    mixed = _rewrite(
        _replace("content.xml", "{{invoice_lines}}", "x {{invoice_lines}}")
    )
    assert "alone" in _messages(validate_template(mixed))[0]


def test_the_lines_placeholder_in_a_header_is_rejected() -> None:
    edit = _replace("styles.xml", "{{bill_to_name}}", "{{invoice_lines}}")
    assert any(
        "body of the document" in m
        for m in _messages(validate_template(_rewrite(edit)))
    )


def test_every_problem_of_the_failing_group_is_reported_together() -> None:
    def both(parts: dict[str, bytes]) -> None:
        text = parts["content.xml"].decode()
        parts["content.xml"] = (
            text.replace("{{invoice_number}}", "{{nope}}")
            .replace("{{due_date}}", "{{nada}}")
            .encode()
        )

    snippets = _snippets(validate_template(_rewrite(both)))
    # The number is used twice in the template, so it is reported where it is used.
    assert set(snippets) == {"{{nada}}", "{{nope}}"} and len(snippets) == 3


def test_an_earlier_group_hides_the_later_ones() -> None:
    def both(parts: dict[str, bytes]) -> None:
        parts["Scripts/m.xml"] = b"<x/>"
        parts["content.xml"] = parts["content.xml"].replace(
            b"{{invoice_number}}", b"{{nope}}"
        )

    result = validate_template(_rewrite(both))
    assert all("macro" in f.message for f in result.problems)


# --- warnings ---------------------------------------------------------------------------------


def test_a_template_without_the_draft_mark_is_accepted_with_a_warning() -> None:
    def no_mark(parts: dict[str, bytes]) -> None:
        parts["styles.xml"] = parts["styles.xml"].replace(b"{{draft_watermark}}", b"")

    result = validate_template(_rewrite(no_mark))
    assert result.problems == []
    assert [w.message for w in result.warnings] == [
        "The template has no {{draft_watermark}}, so previews carry no DRAFT mark"
    ]


def test_a_font_that_is_not_installed_is_a_warning() -> None:
    result = validate_template(bundled_template(), installed_fonts={"DejaVu Sans"})
    assert [w.snippet for w in result.warnings] == ["Liberation Sans"]
    assert result.problems == []


def test_fonts_are_not_checked_without_a_list_of_installed_ones() -> None:
    assert validate_template(bundled_template()).warnings == []


def test_the_declared_fonts_of_the_bundled_template() -> None:
    import xml.etree.ElementTree as ET

    root = ET.fromstring(
        zipfile.ZipFile(io.BytesIO(bundled_template())).read("styles.xml")
    )
    assert declared_fonts({"styles.xml": root}) == ["Liberation Sans"]


def test_fc_list_output_is_split_into_families() -> None:
    assert parse_fc_list("Liberation Sans,Liberation Sans Narrow\nDejaVu Sans\n") == {
        "Liberation Sans",
        "Liberation Sans Narrow",
        "DejaVu Sans",
    }


def test_a_minimal_valid_template_passes() -> None:
    assert validate_template(make_odt()).problems == []
