"""Credential extraction helpers.

Authentication authority lives only in ``app.api.principal.resolve_principal``.
This module intentionally does not compare bearer plaintext with configuration.
"""
from __future__ import annotations


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
