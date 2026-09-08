"""Bind one published Component IR graph to the existing research orchestrator."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import json
from typing import Any

from app.ir.experiment import record, validate_experiment
from app.ir.hashing import content_address
from app.ir.library import IMPLEMENTATIONS, LIBRARY, REGISTRY
from app.market_data.candles import candles_to_df
from app.strategy.admission import (
    AdmissionRefused,
    IRGraphAdmissionInput,
    admit_strategy,
    artifact_from_dict,
    verify_admission,
)
from research.domain.admissions import load_admission, store_admission
from research.orchestrator.run import run_experiment
from research.strategy.builder.ir_components import BAR_INPUTS
from research.strategy.builder.ir_strategy import IRGraphStrategy
from research.data.canonical_dataset import (
    CanonicalDataset, CanonicalDatasetRefused, canonical_provenance,
)


class GraphBindingRejected(Exception):
    """A published row cannot produce trustworthy experiment provenance."""


class GraphAdmissionRejected(GraphBindingRejected):
    """A stable owner-local receipt refusal before research data is consumed."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


_PRESENTATION_FIELDS = frozenset({"layout", "positions", "presentation"})


def _dataset_inputs(dataset) -> dict:
    frame = candles_to_df(dataset.candles)
    index = frame["date"]
    return {
        field: frame[field].set_axis(index)
        for field in BAR_INPUTS
    }


def build_graph_provenance(
    *,
    project_id: str,
    graph: Mapping[str, Any],
    declared_content_address: str,
    datasets: Sequence[tuple[object, object]],
) -> tuple[IRGraphStrategy, dict[str, Any]]:
    """Derive graph, resolution and F14 data evidence; trust no caller fields."""
    contaminated = sorted(_PRESENTATION_FIELDS.intersection(graph))
    if contaminated:
        raise GraphBindingRejected(
            f"non-executable graph fields are forbidden: {contaminated}"
        )
    actual_address = content_address(graph)
    if actual_address != declared_content_address:
        raise GraphBindingRejected(
            "declared graph content address does not match canonical graph bytes"
        )
    try:
        strategy = IRGraphStrategy(graph, (LIBRARY, IMPLEMENTATIONS))
    except Exception as exc:
        if isinstance(exc, GraphBindingRejected):
            raise
        raise GraphBindingRejected(f"published graph cannot be resolved: {exc}") from exc

    canonical = [isinstance(dataset, CanonicalDataset) for _, dataset in datasets]
    canonical_binding = None
    if any(canonical):
        if not all(canonical):
            raise GraphBindingRejected("mixed canonical and legacy datasets")
        try:
            canonical_binding = canonical_provenance(strategy, datasets)
        except CanonicalDatasetRefused as exc:
            raise GraphBindingRejected(str(exc)) from exc

    bindings: dict[str, dict[str, str]] = {}
    for _, dataset in datasets:
        bound = record(
            f"{graph['identifier']}@{graph['version']}/{dataset.instrument_key}",
            strategy.resolved,
            _dataset_inputs(dataset),
            {},
        )
        violations = validate_experiment(bound, strategy.resolved)
        if violations:
            first = violations[0]
            raise GraphBindingRejected(
                f"{first.clause} at {first.path}: {first.message}"
            )
        bindings[dataset.instrument_key] = {
            "data_digest": bound.data_digest,
            "binding": bound.binding,
        }

    provenance = {
        "graph": {
            "project_id": project_id,
            "identifier": str(graph["identifier"]),
            "version": int(graph["version"]),
            "content_address": actual_address,
        },
        "resolution": {
            "component_versions": [list(version) for version in strategy.resolved.versions],
            "node_identities": {
                node.instance_id: node.cache_id for node in strategy.resolved.nodes
            },
        },
        "dataset_bindings": bindings,
    }
    if canonical_binding is not None:
        provenance["canonical_dataset_bindings"] = canonical_binding
    return strategy, provenance


def require_graph_admission(session, *, owner_id: str, graph: Mapping[str, Any],
                            graph_content_address: str, admission_address: str | None):
    """Re-load and re-verify the exact research-plane receipt before provider data."""
    if not admission_address:
        raise GraphAdmissionRejected("RECEIPT_STALE")
    receipt = load_admission(
        session, owner_id=owner_id, admission_address=admission_address
    )
    if receipt is None:
        raise GraphAdmissionRejected("RECEIPT_STALE")
    try:
        artifact = artifact_from_dict(json.loads(receipt.artifact_json))
        if (artifact.owner_id != owner_id
                or artifact.admission_address != admission_address
                or artifact.graph_address != graph_content_address
                or graph_content_address != content_address(graph)):
            raise GraphAdmissionRejected("ARTEFACT_MISMATCH")
        verify_admission(
            artifact=artifact, owner_id=owner_id,
            source_input=IRGraphAdmissionInput(graph=graph, parameters={}, risk_model=None),
            registry=REGISTRY,
        )
    except AdmissionRefused as exc:
        raise GraphAdmissionRejected(exc.code.value) from exc
    except (ValueError, TypeError, KeyError):
        raise GraphAdmissionRejected("ARTEFACT_MISMATCH") from None
    return artifact


def _prepare_graph_admission(session, *, owner_id: str, graph: Mapping[str, Any],
                             graph_content_address: str,
                             admission_address: str | None):
    """Verify exact admission without writing; reject a bad existing mirror."""
    decision = admit_strategy(
        owner_id=owner_id,
        source_input=IRGraphAdmissionInput(graph=graph, parameters={}, risk_model=None),
        registry=REGISTRY,
    )
    if decision.artifact is None:
        raise GraphAdmissionRejected(
            decision.refusal_code.value if decision.refusal_code else "RECEIPT_STALE")
    artifact = decision.artifact
    if (admission_address != artifact.admission_address
            or artifact.graph_address != graph_content_address
            or graph_content_address != content_address(graph)):
        raise GraphAdmissionRejected("RECEIPT_STALE")
    if load_admission(session, owner_id=owner_id, admission_address=admission_address) is not None:
        return require_graph_admission(session, owner_id=owner_id, graph=graph,
            graph_content_address=graph_content_address, admission_address=admission_address)
    return artifact


def enqueue_graph_admission(session, *, owner_id: str, graph: Mapping[str, Any],
                            graph_content_address: str,
                            admission_address: str | None, persist: bool = True):
    """Prepare exactly one receipt; persistence defaults to the existing behavior."""
    artifact = _prepare_graph_admission(session, owner_id=owner_id, graph=graph,
        graph_content_address=graph_content_address, admission_address=admission_address)
    if not persist:
        return artifact
    try:
        store_admission(session, artifact)
    except ValueError as exc:
        raise GraphAdmissionRejected("RECEIPT_STALE") from exc
    return artifact


def run_published_graph_experiment(
    session,
    *,
    project_id: str,
    graph: Mapping[str, Any],
    declared_content_address: str,
    admission_address: str | None,
    datasets: Sequence[tuple[object, object]],
    **experiment_inputs: Any,
) -> dict:
    """Run the accepted orchestrator once against an exact immutable graph."""
    artifact = require_graph_admission(
        session, owner_id=experiment_inputs["owner_id"], graph=graph,
        graph_content_address=declared_content_address,
        admission_address=admission_address,
    )
    strategy, provenance = build_graph_provenance(
        project_id=project_id,
        graph=graph,
        declared_content_address=declared_content_address,
        datasets=datasets,
    )
    return run_experiment(
        session,
        strategy=strategy,
        datasets=datasets,
        params={},
        graph_provenance={**provenance, "admission_address": artifact.admission_address},
        **experiment_inputs,
    )


def run_saved_v2_graph_experiment(**operation_context: Any) -> dict[str, Any]:
    """Run only the closed durable V2 operation path.

    Kept as a distinct entry point so the legacy request/loader/strategy remains
    observable and cannot fall through into V2 behavior.
    """
    from research.orchestrator.v2_operation import execute_v2_graph_operation

    return execute_v2_graph_operation(**operation_context)


__all__ = [
    "GraphBindingRejected",
    "GraphAdmissionRejected",
    "build_graph_provenance",
    "enqueue_graph_admission",
    "run_published_graph_experiment",
    "run_saved_v2_graph_experiment",
]
