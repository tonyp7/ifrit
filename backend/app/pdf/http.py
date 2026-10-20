from fastapi import Response

# A PDF is shown by the browser's own viewer, so it is sent as exactly that and nothing it
# contains can run in the application's origin: no sniffing, no scripts, no fetches.
_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "sandbox; default-src 'none'",
    "Cache-Control": "no-store",
}


def pdf_response(content: bytes, filename: str | None = None) -> Response:
    headers = dict(_HEADERS)
    if filename is not None:
        headers["Content-Disposition"] = f'inline; filename="{filename}"'
    return Response(content=content, media_type="application/pdf", headers=headers)


_UNSAFE_IN_NAME = str.maketrans({c: "-" for c in '/\\:*?"<>|'})


def pdf_filename(number: str) -> str:
    """`{number}.pdf` with the characters a file name cannot hold replaced, so a number such
    as `2026/0043` is still one name."""
    cleaned = "".join(ch for ch in number if ch.isprintable()).translate(
        _UNSAFE_IN_NAME
    )
    return f"{cleaned.strip() or 'invoice'}.pdf"
