"""Canonical terminal research evidence stored on ExperimentRun."""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from app.ir.hashing import canonical_json, content_address


MAX_EVIDENCE_BYTES = 2_000_000
SCHEMA_VERSION = 1


class EvidenceMissing(Exception):
    """A legacy run has no terminal evidence envelope."""


class EvidenceRejected(Exception):
    """Stored or newly produced evidence cannot be trusted."""


def _reject_constant(value: str):
    raise ValueError(f"non-finite JSON value {value}")


def encode_terminal_evidence(evidence: Mapping[str, Any]) -> str:
    if not isinstance(evidence, Mapping):
        raise EvidenceRejected("terminal evidence must be an object")
    try:
        canonical_evidence = json.loads(canonical_json(dict(evidence)))
        raw = canonical_json({
            "schema_version": SCHEMA_VERSION,
            "content_address": content_address(canonical_evidence),
            "evidence": canonical_evidence,
        })
    except (TypeError, ValueError) as exc:
        raise EvidenceRejected(f"terminal evidence is not canonical JSON: {exc}") from exc
    if len(raw.encode("utf-8")) > MAX_EVIDENCE_BYTES:
        raise EvidenceRejected("terminal evidence exceeds the persisted size limit")
    return raw


def decode_terminal_evidence(raw: str | None) -> dict[str, Any]:
    if raw is None or raw == "":
        raise EvidenceMissing("run is legacy-unbound: no terminal evidence exists")
    if not isinstance(raw, str):
        raise EvidenceRejected("terminal evidence storage must be JSON text")
    if len(raw.encode("utf-8")) > MAX_EVIDENCE_BYTES:
        raise EvidenceRejected("terminal evidence exceeds the persisted size limit")
    try:
        envelope = json.loads(raw, parse_constant=_reject_constant)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise EvidenceRejected(f"terminal evidence is invalid JSON: {exc}") from exc
    if not isinstance(envelope, dict) or set(envelope) != {
        "schema_version", "content_address", "evidence"
    }:
        raise EvidenceRejected("terminal evidence envelope has unknown or missing fields")
    if envelope["schema_version"] != SCHEMA_VERSION:
        raise EvidenceRejected("terminal evidence schema version is unsupported")
    evidence = envelope["evidence"]
    if not isinstance(evidence, dict):
        raise EvidenceRejected("terminal evidence payload must be an object")
    if envelope["content_address"] != content_address(evidence):
        raise EvidenceRejected("terminal evidence content address does not match its payload")
    if raw != canonical_json(envelope):
        raise EvidenceRejected("terminal evidence envelope is not canonical JSON")
    return evidence


__all__ = [
    "EvidenceMissing",
    "EvidenceRejected",
    "decode_terminal_evidence",
    "encode_terminal_evidence",
]
