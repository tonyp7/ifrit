from fastapi import HTTPException, status
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings

# Room for a multipart body's framing (boundaries, headers, the other form fields)
# around a file of exactly MAX_UPLOAD_BYTES. The exact per-file limit is enforced by the
# upload service once the file is received.
MULTIPART_OVERHEAD_BYTES = 1024 * 1024

_TOO_LARGE_DETAIL = "The request is too large"


class RequestBodyLimitMiddleware:
    """Rejects any request whose body is larger than an upload can legitimately be.

    FastAPI hands an upload to the route only after the whole multipart body has been
    received and spooled by Starlette, whose own size limits cover form fields but not
    files. Without this, a client could send an arbitrarily large body even though
    every upload is size-limited later: the body is counted here as it streams in, and
    the request is cut off as soon as it exceeds the limit. This is the in-app layer
    behind the reverse proxy's own body limit.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit = settings.max_upload_bytes + MULTIPART_OVERHEAD_BYTES
        # Cheap rejection from the declared length, before reading anything.
        for name, value in scope["headers"]:
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    break
                if declared > limit:
                    await JSONResponse({"detail": _TOO_LARGE_DETAIL}, status_code=413)(
                        scope, receive, send
                    )
                    return
                break

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    # Chunked bodies have no declared length, so they are caught here,
                    # mid-stream. An HTTPException (rather than a custom one) is what
                    # FastAPI's body parsing re-raises as is, instead of turning it into
                    # a generic 400, and it is answered as a 413 by the exception layer.
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail=_TOO_LARGE_DETAIL,
                    )
            return message

        await self.app(scope, limited_receive, send)
