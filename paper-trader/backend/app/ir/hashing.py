"""
Content addressing for the IR.

F2 requires a component's body to be "stored once and content-addressed"; F13
requires that "semantic content MUST be hashed" while presentation state lives
beside the graph. The grammar has nowhere to put a coordinate, so for an
artefact those two requirements collapse into one function: hash all of it,
canonically.

Canonical means the bytes are a function of the *value*, not of how it was
written. Key order and float formatting must not change an address, or
reformatting an artefact would silently be a semantic change — the exact trap
Appendix A.3 records ("identity MUST NOT be the definition").
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from app.ir.schema import CONTENT_ADDRESS_PREFIX


def canonical_json(value: Any) -> str:
    """A byte-stable rendering of `value`.

    `sort_keys` makes key order irrelevant; `separators` removes insignificant
    whitespace; `allow_nan=False` refuses the three float values JSON cannot
    round-trip, because an address that cannot be re-derived is not an address.
    """
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def content_address(value: Any) -> str:
    """The `sha256:<64 hex>` address of `value`. Satisfies `is_content_address`."""
    digest = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
    return f"{CONTENT_ADDRESS_PREFIX}{digest}"
