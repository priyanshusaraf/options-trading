"""Bound CSV upload bytes before FastAPI starts multipart parsing."""
from __future__ import annotations

import re

from starlette._utils import get_route_path
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.versioning import unversioned_path


CSV_MULTIPART_ALLOWANCE = 64 * 1024
_CSV_UPLOAD = re.compile(
    r"^/api/ir/projects/[^/]+/research-datasets/(?:inspect-csv|import-csv)$"
)


class _BodyTooLarge(Exception):
    pass


def _is_csv_upload(scope: Scope) -> bool:
    return (scope["type"] == "http" and scope["method"] == "POST"
            and _CSV_UPLOAD.match(unversioned_path(get_route_path(scope))) is not None)


def _size_refusal(limit: int) -> JSONResponse:
    return JSONResponse(status_code=413, content={"detail": {
        "code": "CSV_REQUEST_TOO_LARGE",
        "message": f"The CSV upload exceeds the {limit:,}-byte request limit. "
                   "Use a smaller file and include only its metadata.",
    }})


def _length_refusal() -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": {
        "code": "CSV_REQUEST_INVALID",
        "message": "The upload has an invalid Content-Length header. "
                   "Send the file again without overriding upload headers.",
    }})


def _declared_size_refusal(scope: Scope, limit: int) -> JSONResponse | None:
    values = [value for name, value in scope.get("headers", ())
              if name.lower() == b"content-length"]
    if not values:
        return None
    if len(values) != 1 or not values[0].isdigit():
        return _length_refusal()
    try:
        declared = int(values[0])
    except ValueError:
        return _length_refusal()
    return _size_refusal(limit) if declared > limit else None


async def _bounded_body(receive: Receive, limit: int) -> bytes | None:
    body = bytearray()
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            return None
        chunk = message.get("body", b"")
        if len(body) + len(chunk) > limit:
            raise _BodyTooLarge
        body.extend(chunk)
        if not message.get("more_body", False):
            return bytes(body)


def _replay_body(body: bytes, receive: Receive) -> Receive:
    sent = False

    async def replay() -> Message:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return await receive()

    return replay


class CsvRequestBodyLimitMiddleware:
    """CSV-only bound, registered inside the authentication/capability gate.

    Accepted requests are buffered within one fixed request budget, then replayed
    once. Oversized requests never reach multipart parsing or temporary files.
    The route retains its separate accepted-file limit.
    """

    def __init__(self, app: ASGIApp, *, max_file_bytes: int):
        self.app = app
        self.max_body_bytes = max_file_bytes + CSV_MULTIPART_ALLOWANCE

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not _is_csv_upload(scope):
            await self.app(scope, receive, send)
            return
        refusal = _declared_size_refusal(scope, self.max_body_bytes)
        if refusal is not None:
            await refusal(scope, receive, send)
            return
        try:
            body = await _bounded_body(receive, self.max_body_bytes)
        except _BodyTooLarge:
            await _size_refusal(self.max_body_bytes)(scope, receive, send)
            return
        if body is None:
            return
        await self.app(scope, _replay_body(body, receive), send)
