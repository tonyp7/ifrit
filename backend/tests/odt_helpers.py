"""Builds tiny ODT files for the template engine tests."""

import io
import zipfile

NS = (
    'xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
    'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
    'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
    'xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" '
    'xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0" '
    'xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0"'
)
LINES_PARAGRAPH = "<text:p>{{invoice_lines}}</text:p>"


def make_odt(
    body: str = LINES_PARAGRAPH,
    master: str = "",
    *,
    styles_extra: str = "",
    content_prefix: str = "",
) -> bytes:
    content = (
        f'<?xml version="1.0" encoding="UTF-8"?>{content_prefix}'
        f"<office:document-content {NS}><office:automatic-styles/>"
        f"<office:body><office:text>{body}</office:text></office:body>"
        "</office:document-content>"
    )
    styles = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f"<office:document-styles {NS}><office:styles>{styles_extra}</office:styles>"
        f"<office:master-styles>{master}</office:master-styles></office:document-styles>"
    )
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        archive.writestr(
            zipfile.ZipInfo("mimetype"),
            "application/vnd.oasis.opendocument.text",
            zipfile.ZIP_STORED,
        )
        archive.writestr("content.xml", content)
        archive.writestr("styles.xml", styles)
    return out.getvalue()


def read_part(odt: bytes, name: str = "content.xml") -> str:
    with zipfile.ZipFile(io.BytesIO(odt)) as archive:
        return archive.read(name).decode("utf-8")
