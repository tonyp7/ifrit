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
