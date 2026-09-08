"""Strict format-version selection for the one public IR façade."""
from __future__ import annotations

from typing import Any, Mapping

from app.ir.formats.v1 import FORMAT_VERSION as V1_FORMAT_VERSION
from app.ir.schema import V2_FORMAT_VERSION


class UnsupportedFormatVersion(ValueError):
    """A document or resolved graph cannot be interpreted by this build."""


def select_format(document: Mapping[str, Any]) -> int:
    """Return the selected implemented format or fail before interpretation.

    Python bool is deliberately excluded even though it subclasses int.  V2 is
    not selected until its separate implementation capsule accepts it.
    """
    if "format_version" not in document:
        raise UnsupportedFormatVersion("missing")
    version = document["format_version"]
    if isinstance(version, bool) or not isinstance(version, int) \
            or version not in {V1_FORMAT_VERSION, V2_FORMAT_VERSION}:
        raise UnsupportedFormatVersion(
            f"{version!r} is not understood (this reader knows {V1_FORMAT_VERSION})")
    return version


def require_resolved_v1(format_version: Any) -> None:
    """Refuse a resolved graph that did not originate from the frozen v1 path."""
    if isinstance(format_version, bool) or not isinstance(format_version, int) \
            or format_version != V1_FORMAT_VERSION:
        raise UnsupportedFormatVersion(
            f"{format_version!r} is not understood (this reader knows {V1_FORMAT_VERSION})")
