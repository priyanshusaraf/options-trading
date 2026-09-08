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

from app.db.concurrency import caller_owned_savepoint
from app.db.models import IrV2GraphVersion, StrategyAdmission
from app.ir.hashing import canonical_json, content_address
from app.ir.schema import is_content_address
from app.ir.v2_graph_versions import PHASE4_BOUND_SCHEME, PHASE4_SCHEMES, require_singular_phase4_assessment


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
        "format_version", "content_address",
    ))


def _require_same(row: StrategyAdmission | None, expected: _CanonicalAdmission) -> StrategyAdmission:
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
        row = session.get(IrV2GraphVersion, (facts.owner_id, facts.graph_identifier, facts.graph_version))
    if row is not None or required:
        from app.ir.v2_graph_versions import require_row_matches
        try:
            require_row_matches(row, facts)
        except (TypeError, ValueError) as exc:
            raise AdmissionPersistenceError("conflicting bytes for immutable v2 graph version") from exc
    return row


def put(session: Session, artifact: AdmissionArtifact) -> StrategyAdmission:
    """Insert one verified receipt; exact retries converge and conflicts refuse."""
    expected = _canonicalize(artifact)
    graph_facts = _write_graph_facts(artifact, expected.scheme)
    graph_row = _existing_graph(session, graph_facts)
    with session.no_autoflush:
        existing = get(session, owner_id=expected.owner_id, admission_address=expected.admission_address)
    if existing is not None:
        if graph_facts is not None and graph_row is None:
            raise AdmissionPersistenceError("Phase 4 receipt is missing its immutable v2 graph version")
        return _require_same(existing, expected)
    return _insert_receipt(session, expected, graph_facts, graph_row)


def _insert_receipt(session, expected, graph_facts, graph_row):
    candidate = StrategyAdmission(**expected.__dict__)
    try:
        with caller_owned_savepoint(session, scope="execution_strategy_admission"):
            if graph_facts is not None and graph_row is None:
                session.add(IrV2GraphVersion(**graph_facts.__dict__))
            session.add(candidate)
            session.flush()
        return candidate
    except IntegrityError:
        _existing_graph(session, graph_facts, required=True)
        return _require_same(get(session, owner_id=expected.owner_id,
                                  admission_address=expected.admission_address), expected)


def require_current(session: Session, artifact: AdmissionArtifact) -> StrategyAdmission:
    """Require exact canonical bytes for this owner; no key-only receipt is trusted."""
    expected = _canonicalize(artifact)
    receipt = _require_same(get(session, owner_id=expected.owner_id,
                                admission_address=expected.admission_address), expected)
    if expected.scheme in PHASE4_SCHEMES:
        from app.ir.v2_graph_versions import V2GraphFacts, require_row_matches
        graph = session.get(IrV2GraphVersion, (
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


def load_current_phase4_artifact(
    session: Session, *, owner_id: str, admission_address: str,
    registry, research_session, input_bindings=None,
):
    """Reconstruct the common current Phase 4 artifact without loading data bytes.

    This is the shared restart seam for the closed V2 research operation and the
    existing lifecycle repository.  Dataset object traversal remains a later,
    explicitly fenced step in :func:`require_phase4_current`.
    """
    from app.strategy.admission import reconstruct_phase4_artifact, reconstruct_phase4_bound_artifact
    from research.domain.admissions import require_admission as require_research_admission
    _require_phase4_context(owner_id, admission_address, registry, research_session)
    receipt = get(session, owner_id=owner_id, admission_address=admission_address)
    if receipt is None:
        raise AdmissionPersistenceError("Phase 4 admission receipt is absent")
    try:
        import json

        document = json.loads(receipt.artifact_json)
        if not isinstance(document, dict) or document.get("scheme") not in PHASE4_SCHEMES:
            raise ValueError("wrong admission scheme")
        reconstruct = (reconstruct_phase4_bound_artifact if document["scheme"] == PHASE4_BOUND_SCHEME
                       else reconstruct_phase4_artifact)
        artifact = reconstruct(
            document, owner_id=owner_id, registry=registry,
            input_bindings=input_bindings,
        )
        if artifact.owner_id != owner_id \
                or artifact.admission_address != admission_address:
            raise ValueError("admission identity differs")
        require_current(session, artifact)
        require_research_admission(research_session, artifact)
        return artifact
    except (TypeError, ValueError, KeyError) as exc:
        raise AdmissionPersistenceError("Phase 4 persisted artifact is not current") from exc


def load_phase4_descriptor(
    session: Session, *, owner_id: str, admission_address: str,
) -> dict:
    """Load closed persisted Phase 4 descriptor bytes before dataset object I/O.

    Dynamic contract reconstruction deliberately happens later with the exact
    canonical projection bindings.  This seam proves only the immutable row and
    its internally repeated owner/version/graph/manifest/policy facts; it grants
    no evaluation authority by itself.
    """
    import json
    receipt = get(session, owner_id=owner_id, admission_address=admission_address)
    if receipt is None:
        raise AdmissionPersistenceError("Phase 4 admission receipt is absent")
    try:
        document = json.loads(receipt.artifact_json)
        if document.get("scheme") == PHASE4_BOUND_SCHEME:
            return _bound_descriptor(document, receipt, owner_id, admission_address)
        _singular_descriptor(document, receipt, owner_id, admission_address)
        return document
    except (KeyError, TypeError, ValueError) as exc:
        raise AdmissionPersistenceError("Phase 4 persisted descriptor is not current") from exc


def _require_phase4_context(owner_id, admission_address, registry, research_session):
    from app.ir.registry import PlatformRegistry
    if (not isinstance(owner_id, str) or not owner_id or not isinstance(admission_address, str)
            or not is_content_address(admission_address) or not isinstance(registry, PlatformRegistry)
            or not isinstance(research_session, Session)):
        raise AdmissionPersistenceError("Phase 4 authority context is invalid")


def _descriptor_record(document, receipt, owner_id, admission_address):
    repeated = ("owner_id", "graph_identifier", "graph_version", "graph_address", "content_address",
                "scheme", "contract_suite", "parity_suite", "format_version")
    if (document["owner_id"] != owner_id or canonical_json(document) != receipt.artifact_json
            or content_address(document) != admission_address
            or any(document.get(name) != getattr(receipt, name) for name in repeated)):
        raise ValueError("descriptor identity differs")


def _singular_descriptor(document, receipt, owner_id, admission_address):
    from app.ir.v2_graph_versions import PHASE4_SCHEME
    binding, base = document["phase4_data_binding"], document["base_v2_admission"]
    if (document.get("scheme") != PHASE4_SCHEME or not isinstance(binding, Mapping)
            or not isinstance(base, Mapping) or binding.get("owner_id") != owner_id
            or binding.get("mode") != "RESEARCH" or binding.get("authored_ir_address") != document.get("content_address")):
        raise ValueError("descriptor identity differs")
    _descriptor_record(document, receipt, owner_id, admission_address)
    _descriptor_graph(document, base, binding)
    require_singular_phase4_assessment(document, binding)


def _descriptor_graph(document, base, binding):
    from app.strategy.admission import is_closed_phase4_registry_snapshot
    snapshot = base["registry_snapshot"]
    repeated = ("owner_id", "graph_identifier", "graph_version", "graph_address", "content_address", "format_version")
    if (not is_closed_phase4_registry_snapshot(snapshot, expected_address=binding.get("registry_snapshot_address"))
            or snapshot.get("address") != binding.get("registry_snapshot_address")
            or content_address(snapshot.get("snapshot")) != snapshot.get("address")
            or any(document.get(name) != base.get(name) for name in repeated)):
        raise ValueError("descriptor identity differs")


def require_phase4_current(
    session: Session,
    artifact: AdmissionArtifact,
    *,
    research_session,
    plan,
    at_time,
) -> StrategyAdmission:
    """Freshly reload a Phase 4 receipt, dataset bytes, and typed assessment."""
    if getattr(artifact, "scheme", None) != "strategy-admission/phase4-data/1":
        raise AdmissionPersistenceError("Phase 4 authority requires a Phase 4 receipt")
    receipt = require_current(session, artifact)
    binding = artifact.phase4_data_binding
    from app.market_data.authority import load_capability_assessment
    from research.domain.admissions import (
        AdmissionPersistenceError as ResearchAdmissionPersistenceError,
        require_admission as require_research_admission,
    )
    from research.domain.strategy_admissions import load_verified_dataset_authority

    try:
        require_research_admission(research_session, artifact)
    except ResearchAdmissionPersistenceError as exc:
        raise AdmissionPersistenceError(
            "Phase 4 research receipt or graph is not current"
        ) from exc
    dataset = load_verified_dataset_authority(
        research_session, owner_id=artifact.owner_id,
        manifest_address=binding["dataset_manifest_address"], execution_session=session,
        at_time=at_time)
    assessment = load_capability_assessment(
        session, binding["capability_assessment_address"], plan=plan, at_time=at_time)
    if (dataset.manifest.manifest_address != binding["dataset_manifest_address"]
            or assessment.authority_address != binding["capability_assessment_address"]
            or assessment.owner_id != artifact.owner_id
            or assessment.dataset_manifest_address != dataset.manifest.manifest_address
            or assessment.plan_address != binding["plan_address"]
            or assessment.registry_snapshot_address != binding["registry_snapshot_address"]
            or assessment.market_truth_snapshot_address != binding["market_truth_snapshot_address"]
            or assessment.evaluation_policy_address != binding["evaluation_policy_address"]):
        raise AdmissionPersistenceError("Phase 4 persisted dependency chain is stale")
    return receipt


def _bound_descriptor(document, receipt, owner_id, admission_address):
    from app.ir.v2_graph_versions import require_bound_phase4_receipt
    checked = require_bound_phase4_receipt(document)
    _descriptor_record(checked, receipt, owner_id, admission_address)
    return checked


def load_current_phase4_bound_artifact(session, *, owner_id, admission_address, registry,
                                     research_session, projection, at_time):
    """Reload both receipts and recompute every original source's current evidence."""
    from app.ir.v2_graph_versions import _plain
    from app.market_data.capability import bound_capability_assessment_envelope
    from app.strategy.admission import reload_phase4_bound_projection, _recompute_bound_assessment
    from app.ir.resolve import resolve_v2
    try:
        artifact = load_current_phase4_artifact(session, owner_id=owner_id, admission_address=admission_address,
            registry=registry, research_session=research_session, input_bindings=projection.input_bindings)
        if artifact.scheme != PHASE4_BOUND_SCHEME:
            raise ValueError("wrong bound receipt scheme")
        graph = _plain(artifact.base_v2_admission.document)
        rebuilt = reload_phase4_bound_projection(projection=projection, owner_id=owner_id, document=graph,
            research_session=research_session, execution_session=session, at_time=at_time)
        if (_plain(rebuilt.dataset_selection_document) != _plain(artifact.dataset_selection)
                or rebuilt.input_digest != artifact.base_v2_admission.evidence.input_address):
            raise ValueError("recorded bound dataset selection differs")
        assessment = _recompute_bound_assessment(projection=rebuilt, resolved=resolve_v2(graph, registry),
            registry=registry, plan=artifact.plan,
            evaluation_policy_address=artifact.phase4_data_binding["evaluation_policy_address"],
            execution_session=session, at_time=at_time)
        if bound_capability_assessment_envelope(assessment) != _plain(artifact.capability_assessment):
            raise ValueError("recorded bound assessment differs from current sources")
        return artifact
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise AdmissionPersistenceError("Bound Phase 4 source authority is not current") from exc


__all__ = ["AdmissionPersistenceError", "get", "load_current_phase4_artifact",
           "load_current_phase4_bound_artifact",
           "load_phase4_descriptor", "put",
           "require_current", "require_phase4_current"]
