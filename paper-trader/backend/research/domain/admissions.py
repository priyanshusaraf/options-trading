"""Immutable research-plane storage for Phase 3 causal-admission receipts.

This module records research evidence only. It deliberately imports no execution
session or execution persistence model; causal admission remains necessary but is
not complete Strategy Preflight or execution permission.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ir.hashing import canonical_json, content_address
from app.ir.schema import is_content_address
from research.domain.models import (
    ExperimentRun,
    PromotionCandidate,
    ResearchStrategyAdmission,
)


class AdmissionPersistenceError(ValueError):
    """An immutable research receipt cannot be safely written or reused."""


class AdmissionBindingError(ValueError):
    """A run or candidate does not name its exact owner-local receipt."""


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
    """Derive persisted identity from canonical receipt bytes, never hints."""
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


def load_admission(session: Session, *, owner_id: str,
                   admission_address: str) -> ResearchStrategyAdmission | None:
    """Look up one owner-local receipt without exposing another owner's row."""
    if not isinstance(owner_id, str) or not owner_id or not is_content_address(admission_address):
        return None
    return session.scalar(select(ResearchStrategyAdmission).where(
        ResearchStrategyAdmission.owner_id == owner_id,
        ResearchStrategyAdmission.admission_address == admission_address,
    ))


def _same(row: ResearchStrategyAdmission, expected: _CanonicalAdmission) -> bool:
    return all(getattr(row, name) == getattr(expected, name) for name in (
        "owner_id", "admission_address", "graph_identifier", "graph_version", "graph_address",
        "artifact_json", "scheme", "contract_suite", "parity_suite",
    ))


def _require_same(row: ResearchStrategyAdmission | None,
                  expected: _CanonicalAdmission) -> ResearchStrategyAdmission:
    if row is None:
        raise AdmissionPersistenceError("admission receipt is absent for this owner")
    if not _same(row, expected):
        raise AdmissionPersistenceError("conflicting bytes for immutable admission receipt")
    return row


def store_admission(session: Session, artifact: AdmissionArtifact) -> ResearchStrategyAdmission:
    """Insert one verified receipt; exact retries converge and conflicts refuse."""
    expected = _canonicalize(artifact)
    existing = load_admission(session, owner_id=expected.owner_id,
                              admission_address=expected.admission_address)
    if existing is not None:
        return _require_same(existing, expected)

    candidate = ResearchStrategyAdmission(**expected.__dict__)
    try:
        with session.begin_nested():
            session.add(candidate)
            session.flush()
        return candidate
    except IntegrityError:
        return _require_same(load_admission(
            session, owner_id=expected.owner_id, admission_address=expected.admission_address), expected)


def require_admission(session: Session, artifact: AdmissionArtifact) -> ResearchStrategyAdmission:
    """Require exact canonical receipt bytes for one owner, never a key alone."""
    expected = _canonicalize(artifact)
    return _require_same(load_admission(
        session, owner_id=expected.owner_id, admission_address=expected.admission_address), expected)


def require_candidate_admission(session: Session, candidate: PromotionCandidate, *,
                                owner_id: str) -> ResearchStrategyAdmission:
    """Require a candidate, its supporting run, and its receipt to bind exactly.

    Task 7 has no independent graph provenance columns on runs or candidates. The
    receipt's canonical graph identity is therefore the sole graph evidence in
    this slice; Task 8 carries it into worker descriptors before provider use.
    """
    if not isinstance(owner_id, str) or not owner_id or candidate.owner_id != owner_id:
        raise AdmissionBindingError("candidate owner does not match requested owner")
    run = session.scalar(select(ExperimentRun).where(
        ExperimentRun.owner_id == owner_id,
        ExperimentRun.id == candidate.run_id,
    ))
    if run is None:
        raise AdmissionBindingError("candidate run is absent for this owner")
    if candidate.admission_address is None or run.admission_address is None:
        raise AdmissionBindingError("LEGACY_UNADMITTED")
    if candidate.admission_address != run.admission_address:
        raise AdmissionBindingError("candidate admission address does not match its run")
    receipt = load_admission(session, owner_id=owner_id,
                             admission_address=candidate.admission_address)
    if receipt is None:
        raise AdmissionBindingError("candidate receipt is absent for this owner")
    return receipt


__all__ = [
    "AdmissionBindingError", "AdmissionPersistenceError", "load_admission",
    "require_admission", "require_candidate_admission", "store_admission",
]
