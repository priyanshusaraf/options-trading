"""Authenticated immutable transport for the global verified-language catalogue."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from app.editor.v2_catalogue import CATALOGUE_BYTES, CATALOGUE_ETAG


router = APIRouter(prefix="/api/ir")
_HEADERS = {
    "ETag": CATALOGUE_ETAG,
    "Cache-Control": "private, max-age=0, must-revalidate",
    "X-Content-Type-Options": "nosniff",
}


@router.get("/catalogue", response_class=Response)
def get_verified_language_catalogue(request: Request):
    if request.query_params:
        return JSONResponse(
            {"code": "CATALOGUE_QUERY_UNSUPPORTED"}, status_code=400,
            headers=_HEADERS,
        )
    if request.headers.get("if-none-match") == CATALOGUE_ETAG:
        return Response(status_code=304, headers=_HEADERS)
    return Response(
        content=CATALOGUE_BYTES,
        media_type="application/json",
        headers=_HEADERS,
    )


__all__ = ["get_verified_language_catalogue", "router"]
