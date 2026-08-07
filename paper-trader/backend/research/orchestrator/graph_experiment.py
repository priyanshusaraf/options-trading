"""Bind one published Component IR graph to the existing research orchestrator."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.ir.experiment import record, validate_experiment
from app.ir.hashing import content_address
from app.ir.library import IMPLEMENTATIONS, LIBRARY
from app.market_data.candles import candles_to_df
from research.orchestrator.run import run_experiment
from research.strategy.builder.ir_components import BAR_INPUTS
from research.strategy.builder.ir_strategy import IRGraphStrategy


class GraphBindingRejected(Exception):
    """A published row cannot produce trustworthy experiment provenance."""


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

    return strategy, {
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


def run_published_graph_experiment(
    session,
    *,
    project_id: str,
    graph: Mapping[str, Any],
    declared_content_address: str,
    datasets: Sequence[tuple[object, object]],
    **experiment_inputs: Any,
) -> dict:
    """Run the accepted orchestrator once against an exact immutable graph."""
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
        graph_provenance=provenance,
        **experiment_inputs,
    )


__all__ = [
    "GraphBindingRejected",
    "build_graph_provenance",
    "run_published_graph_experiment",
]
