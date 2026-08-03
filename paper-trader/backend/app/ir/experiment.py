"""
RFC 0001 F14 — result binding: an experiment record ties a result to the graph
version, every resolved component version, every node's cache identity, and a
digest of the input data.

The binding is derived from a `ResolvedGraph`, never supplied — F14's failure
mode is a stale field, not a missing one.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

import pandas as pd

from app.ir.hashing import canonical_json, content_address
from app.ir.resolve import ResolvedGraph
from app.ir.validate import Violation


@dataclass(frozen=True)
class ExperimentRecord:
    """One run, bound to everything that produced it."""

    experiment_id: str
    graph: tuple[str, int]
    component_versions: tuple[tuple[str, int], ...]
    node_identities: Mapping[str, str]
    data_digest: str
    result: Mapping[str, Any]

    @property
    def binding(self) -> str:
        """A single address for "this graph, these components, this data"."""
        return content_address({
            "graph": list(self.graph),
            "components": [list(v) for v in self.component_versions],
            "nodes": dict(self.node_identities),
            "data": self.data_digest,
        })


@dataclass(frozen=True)
class Finding:
    """A claim, and the experiment that is allowed to support it."""

    finding_id: str
    experiment_id: str
    binding: str
    claim: Mapping[str, Any]


def data_digest(inputs: Mapping[str, pd.Series]) -> str:
    """A content address for the bars an experiment ran on.

    Hashed by value, per input, in name order — so the same data through a
    different loader digests the same.
    """
    digest = hashlib.sha256()
    for name in sorted(inputs):
        series = inputs[name]
        digest.update(name.encode())
        if isinstance(series, pd.Series):
            digest.update(pd.util.hash_pandas_object(series, index=True).values.tobytes())
        else:
            digest.update(canonical_json(series).encode())
    return f"sha256:{digest.hexdigest()}"


def record(experiment_id: str, graph: ResolvedGraph,
           inputs: Mapping[str, pd.Series],
           result: Mapping[str, Any]) -> ExperimentRecord:
    """Bind `result` to everything that produced it.

    Component versions, node identities and the data digest are derived here —
    there is deliberately no parameter for passing them in wrong.
    """
    return ExperimentRecord(
        experiment_id=experiment_id,
        graph=(graph.identifier, graph.version),
        component_versions=tuple(graph.versions),
        node_identities=MappingProxyType(
            {n.instance_id: n.cache_id for n in graph.nodes}),
        data_digest=data_digest(inputs),
        result=MappingProxyType(dict(result)),
    )


def conclude(finding_id: str, experiment: ExperimentRecord,
             claim: Mapping[str, Any]) -> Finding:
    """Draw a finding from an experiment, carrying its binding with it."""
    return Finding(finding_id=finding_id, experiment_id=experiment.experiment_id,
                   binding=experiment.binding, claim=MappingProxyType(dict(claim)))


# ── the clause, as a check ────────────────────────────────────────────────

def validate_experiment(experiment: Any,
                        graph: ResolvedGraph | None = None) -> list[Violation]:
    """Every way an experiment record can fail F14.

    Pass the `ResolvedGraph` to check the binding is correct, not merely present.
    """
    out: list[Violation] = []

    def add(path: str, message: str) -> None:
        out.append(Violation("F14", path, message))

    if not isinstance(experiment, ExperimentRecord):
        add("$", "an experiment record must be an ExperimentRecord")
        return out

    if not experiment.experiment_id:
        add("$.experiment_id", "missing")
    if not (isinstance(experiment.graph, tuple) and len(experiment.graph) == 2
            and isinstance(experiment.graph[0], str) and experiment.graph[0]
            and isinstance(experiment.graph[1], int)):
        add("$.graph", "must record the exact graph (identifier, version)")
    if not experiment.component_versions:
        add("$.component_versions",
            "must record every resolved component version; a result whose "
            "components are unknown is unattributable")
    if not experiment.node_identities:
        add("$.node_identities", "must record every node's cache identity")
    if not experiment.data_digest:
        add("$.data_digest",
            "must record the data it ran on; the same graph over different "
            "bars is a different result")

    if graph is not None:
        if experiment.graph != (graph.identifier, graph.version):
            add("$.graph",
                f"{experiment.graph} is not the graph that produced this "
                f"({(graph.identifier, graph.version)})")
        if tuple(experiment.component_versions) != tuple(graph.versions):
            missing = set(graph.versions) - set(experiment.component_versions)
            extra = set(experiment.component_versions) - set(graph.versions)
            add("$.component_versions",
                f"does not match what resolution recorded (missing {sorted(missing)}, "
                f"unexpected {sorted(extra)})")
        resolved = {n.instance_id: n.cache_id for n in graph.nodes}
        if dict(experiment.node_identities) != resolved:
            add("$.node_identities",
                "does not match the resolved graph's node identities")

    return out


def validate_finding(finding: Any,
                     experiment: ExperimentRecord | None = None) -> list[Violation]:
    """A finding must name an experiment and carry its binding."""
    out: list[Violation] = []

    def add(path: str, message: str) -> None:
        out.append(Violation("F14", path, message))

    if not isinstance(finding, Finding):
        add("$", "a finding must be a Finding")
        return out
    if not finding.finding_id:
        add("$.finding_id", "missing")
    if not finding.experiment_id:
        add("$.experiment_id",
            "a finding must name the experiment that produced it")
    if not finding.binding:
        add("$.binding", "a finding must carry its experiment's binding")

    if experiment is not None:
        if finding.experiment_id != experiment.experiment_id:
            add("$.experiment_id", "names a different experiment")
        if finding.binding != experiment.binding:
            add("$.binding",
                "does not match the experiment's binding; the experiment was "
                "re-run or re-parameterised and this finding was left behind")

    return out
