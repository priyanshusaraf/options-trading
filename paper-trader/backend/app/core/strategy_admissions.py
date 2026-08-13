"""Immutable execution-plane storage for Phase 3 causal-admission receipts.

This module persists evidence.  It does not turn causal admission into complete
Strategy Preflight or grant deployment/execution authority on its own.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import StrategyAdmission
from app.ir.hashing import canonical_json, content_address
from app.ir.schema import is_content_address


class AdmissionPersistenceError(ValueError):
    """An immutable receipt cannot be safely written or reused."""


class AdmissionArtifact(Protocol):
    owner_id: str
    admission_address: str
    graph_identifier: str
    graph_version: int
    graph_address: str
    scheme: str
    contract_suite: str
    parity_suite: str

    def to_dict(self) -> dict: ...


@dataclass(frozen=True)
class _CanonicalAdmission:
    owner_id: str
    admission_address: str
    graph_identifier: str
    graph_version: int
    graph_address: str
    artifact_json: str
    scheme: str
    contract_suite: str
    parity_suite: str


def _canonicalize(artifact: AdmissionArtifact) -> _CanonicalAdmission:
    """Derive every persisted identity from canonical receipt bytes, never hints."""
    try:
        document = artifact.to_dict()
    except Exception as exc:
        raise AdmissionPersistenceError("admission artifact cannot produce receipt bytes") from exc
    if not isinstance(document, Mapping):
        raise AdmissionPersistenceError("admission artifact must produce a mapping")
    try:
        artifact_json = canonical_json(document)
    except (TypeError, ValueError) as exc:
        raise AdmissionPersistenceError("admission artifact is not canonical JSON") from exc
    address = content_address(document)
    if not is_content_address(address) or artifact.admission_address != address:
        raise AdmissionPersistenceError("admission artifact address does not match canonical bytes")

    fields = ("owner_id", "graph_identifier", "graph_version", "graph_address", "scheme",
              "contract_suite", "parity_suite")
    values: dict[str, object] = {}
    for name in fields:
        value = document.get(name)
        if value != getattr(artifact, name, object()):
            raise AdmissionPersistenceError(
                f"admission artifact {name} does not match canonical bytes")
        values[name] = value
    if (not isinstance(values["owner_id"], str) or not values["owner_id"]
            or not isinstance(values["graph_identifier"], str)
            or not isinstance(values["graph_version"], int)
            or isinstance(values["graph_version"], bool)
            or values["graph_version"] < 1
            or not is_content_address(values["graph_address"])
            or any(not isinstance(values[name], str) or not values[name]
                   for name in ("scheme", "contract_suite", "parity_suite"))):
        raise AdmissionPersistenceError("admission artifact identity is invalid")
    return _CanonicalAdmission(
        owner_id=values["owner_id"], admission_address=address,
        graph_identifier=values["graph_identifier"], graph_version=values["graph_version"],
        graph_address=values["graph_address"], artifact_json=artifact_json,
        scheme=values["scheme"], contract_suite=values["contract_suite"],
        parity_suite=values["parity_suite"],
    )


def get(session: Session, *, owner_id: str, admission_address: str) -> StrategyAdmission | None:
    """Look up an exact owner-local receipt without exposing another owner's row."""
    if not isinstance(owner_id, str) or not owner_id or not is_content_address(admission_address):
        return None
    return session.scalar(select(StrategyAdmission).where(
        StrategyAdmission.owner_id == owner_id,
        StrategyAdmission.admission_address == admission_address,
    ))


def _same(row: StrategyAdmission, expected: _CanonicalAdmission) -> bool:
    return all(getattr(row, name) == getattr(expected, name) for name in (
        "owner_id", "admission_address", "graph_identifier", "graph_version", "graph_address",
        "artifact_json", "scheme", "contract_suite", "parity_suite",
    ))


def _require_same(row: StrategyAdmission | None, expected: _CanonicalAdmission) -> StrategyAdmission:
    if row is None:
        raise AdmissionPersistenceError("admission receipt is absent for this owner")
    if not _same(row, expected):
        raise AdmissionPersistenceError("conflicting bytes for immutable admission receipt")
    return row


def put(session: Session, artifact: AdmissionArtifact) -> StrategyAdmission:
    """Insert one verified receipt; exact retries converge and conflicts refuse."""
    expected = _canonicalize(artifact)
    existing = get(session, owner_id=expected.owner_id,
                   admission_address=expected.admission_address)
    if existing is not None:
        return _require_same(existing, expected)

    candidate = StrategyAdmission(**expected.__dict__)
    try:
        with session.begin_nested():
            session.add(candidate)
            session.flush()
        return candidate
    except IntegrityError:
        return _require_same(get(session, owner_id=expected.owner_id,
                                 admission_address=expected.admission_address), expected)


def require_current(session: Session, artifact: AdmissionArtifact) -> StrategyAdmission:
    """Require exact canonical bytes for this owner; no key-only receipt is trusted."""
    expected = _canonicalize(artifact)
    return _require_same(get(session, owner_id=expected.owner_id,
                             admission_address=expected.admission_address), expected)


__all__ = ["AdmissionPersistenceError", "get", "put", "require_current"]
