"""SEC-1: shared token-auth helpers for the REST middleware gate and the two
WebSocket handlers. A single bearer token (PT_API_TOKEN) — empty disables auth
entirely, which is the default for local dev/mock/tests."""
from __future__ import annotations

import secrets

from app.core.config import get_settings


def extract_token(headers) -> str | None:
    """Bearer token from `Authorization: Bearer <t>`, or the raw `X-PT-Token`
    header. `headers` is any mapping with case-insensitive .get (Starlette's
    Headers implements this)."""
    auth = headers.get("Authorization") or headers.get("authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth[7:].strip()
    pt = headers.get("X-PT-Token") or headers.get("x-pt-token")
    if pt:
        return pt
    return None


def token_ok(supplied: str | None) -> bool:
    token = get_settings().api_token
    if not token:
        return True  # auth disabled
    return supplied is not None and secrets.compare_digest(supplied, token)


def ws_authorized(ws) -> bool:
    token = get_settings().api_token
    if not token:
        return True  # auth disabled
    supplied = ws.query_params.get("token")
    return supplied is not None and secrets.compare_digest(supplied, token)
