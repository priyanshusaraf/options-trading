"""Immutable research-plane storage for Phase 3 causal-admission receipts.

This module records research evidence only. It deliberately imports no execution
session or execution persistence model; causal admission remains necessary but is
not complete Strategy Preflight or execution permission.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.concurrency import caller_owned_savepoint
from app.ir.hashing import canonical_json
from app.ir.schema import is_content_address
from app.ir.v2_graph_versions import PHASE4_SCHEMES
from research.domain.models import (
    ExperimentRun,
    PromotionCandidate,
    ResearchIrV2GraphVersion,
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
    format_version: int | None
    content_address: str | None

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
    format_version: int | None
    content_address: str | None


def _canonicalize(artifact: AdmissionArtifact) -> _CanonicalAdmission:
    from app.ir.v2_graph_versions import canonical_admission_values
    try:
        return _CanonicalAdmission(**canonical_admission_values(artifact))
    except (ValueError, TypeError, KeyError) as exc:
        raise AdmissionPersistenceError(str(exc)) from exc


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
        "format_version", "content_address",
    ))


def _require_same(row: ResearchStrategyAdmission | None,
                  expected: _CanonicalAdmission) -> ResearchStrategyAdmission:
    if row is None:
        raise AdmissionPersistenceError("admission receipt is absent for this owner")
    if not _same(row, expected):
        raise AdmissionPersistenceError("conflicting bytes for immutable admission receipt")
    return row


def _write_graph_facts(artifact, scheme):
    if scheme not in PHASE4_SCHEMES:
        return None
    from app.strategy.admission import derive_v2_graph_facts
    try:
        return derive_v2_graph_facts(artifact)
    except ValueError as exc:
        raise AdmissionPersistenceError("Phase 4 writes require the constructor-authorized admission artifact") from exc


def _existing_graph(session, facts, *, required=False):
    if facts is None:
        return None
    with session.no_autoflush:
        row = session.get(ResearchIrV2GraphVersion, (facts.owner_id, facts.graph_identifier, facts.graph_version))
    if row is not None or required:
        from app.ir.v2_graph_versions import require_row_matches
        try:
            require_row_matches(row, facts)
        except (TypeError, ValueError) as exc:
            raise AdmissionPersistenceError("conflicting bytes for immutable v2 graph version") from exc
    return row


def store_admission(session: Session, artifact: AdmissionArtifact) -> ResearchStrategyAdmission:
    """Insert one verified receipt; exact retries converge and conflicts refuse."""
    expected = _canonicalize(artifact)
    graph_facts = _write_graph_facts(artifact, expected.scheme)
    graph_row = _existing_graph(session, graph_facts)
    with session.no_autoflush:
        existing = load_admission(session, owner_id=expected.owner_id, admission_address=expected.admission_address)
    if existing is not None:
        if graph_facts is not None and graph_row is None:
            raise AdmissionPersistenceError("Phase 4 receipt is missing its immutable v2 graph version")
        return _require_same(existing, expected)
    return _insert_receipt(session, expected, graph_facts, graph_row)


def _insert_receipt(session, expected, graph_facts, graph_row):
    candidate = ResearchStrategyAdmission(**expected.__dict__)
    try:
        with caller_owned_savepoint(session, scope="research_strategy_admission"):
            if graph_facts is not None and graph_row is None:
                session.add(ResearchIrV2GraphVersion(**graph_facts.__dict__))
            session.add(candidate)
            session.flush()
        return candidate
    except IntegrityError:
        _existing_graph(session, graph_facts, required=True)
        return _require_same(load_admission(session, owner_id=expected.owner_id,
                                  admission_address=expected.admission_address), expected)


def require_admission(session: Session, artifact: AdmissionArtifact) -> ResearchStrategyAdmission:
    """Require exact canonical receipt bytes for one owner, never a key alone."""
    expected = _canonicalize(artifact)
    receipt = _require_same(load_admission(
        session, owner_id=expected.owner_id, admission_address=expected.admission_address), expected)
    if expected.scheme in PHASE4_SCHEMES:
        from app.ir.v2_graph_versions import V2GraphFacts, require_row_matches
        graph = session.get(ResearchIrV2GraphVersion, (
            expected.owner_id, expected.graph_identifier, expected.graph_version,
        ))
        try:
            require_row_matches(graph, V2GraphFacts(
                owner_id=expected.owner_id,
                graph_identifier=expected.graph_identifier,
                graph_version=expected.graph_version,
                artifact_json=canonical_json(
                    artifact.base_v2_admission.to_dict()["document"]),
                format_version=2,
                content_address=expected.content_address,
                graph_address=expected.graph_address,
                registry_snapshot_address=artifact.phase4_data_binding[
                    "registry_snapshot_address"
                ],
            ))
        except (AttributeError, TypeError, ValueError) as exc:
            raise AdmissionPersistenceError(
                "Phase 4 receipt has no matching immutable v2 graph version"
            ) from exc
    return receipt


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
