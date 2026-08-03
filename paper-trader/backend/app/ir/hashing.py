"""
Content addressing for the IR (F2, F13).

Addresses are a function of the value, not of how it was written: reformatting
an artefact must never change its address.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from app.ir.schema import CONTENT_ADDRESS_PREFIX


def canonical_json(value: Any) -> str:
    """A byte-stable rendering of `value`."""
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
