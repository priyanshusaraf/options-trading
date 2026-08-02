"""
RFC 0001 F14 — result binding.

    "Every experiment and every finding MUST record the exact graph version and
    every resolved component version that produced it."

F14 carries the heaviest evidential weight in the RFC and was, until this
module, the one clause recorded as **unenforceable**: there was no experiment
artefact to validate. The RFC's note says it "becomes enforceable when the
experiment system defines one" — the experiment system, not §3. Nothing here
touches the grammar, and `format_version` does not move: an experiment record is
not a component or a graph, and §3 stays the size it was.

**The binding is derived, never supplied.** `record()` takes a `ResolvedGraph`
and reads the versions off it. There is no parameter for passing them in, which
is the point: F14's failure mode is not a missing field, it is a *stale* one —
someone writes down the versions beside the run and they drift, or the run is
re-parameterised and the record is not. Airflow reached `DagVersion` bound to
task instances only after roughly a decade, by retrofit, and **this platform has
already paid that exact price**: every research finding recorded before 2026-08
is unusable as a baseline. The clause exists so it is not paid twice, and a
constructor that cannot be told the wrong answer is how.

What a record binds, and why each is needed to re-derive the result:

- the **graph** `(identifier, version)` — what was run;
- every **resolved component version** — what it was made of, including versions
  reached only through a subgraph's body, which is why this comes from
  resolution (C5) rather than from reading the specification;
- every node's **cache identity** — which is transitive over its upstream (C8),
  so two records with the same node identity really did compute the same thing;
- a **data digest** of the inputs — the same graph over different bars is a
  different result, and a record that omits this looks reproducible and is not.
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
        """A single address for "this graph, these components, this data".

        Two records with the same binding are the same experiment, and one that
        differs anywhere differs here. This is what a finding points at.
        """
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
    different loader digests the same, and one changed bar does not.
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

    Note what this signature does *not* accept: the component versions, the node
    identities, and the data digest are all derived here. A caller cannot supply
    a wrong one, which is the difference between a clause and a guarantee.
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
    """Draw a finding from an experiment, carrying its binding with it.

    "Every experiment **and every finding**." A finding that outlives the record
    it came from is exactly the unusable-baseline state this platform is in for
    everything before 2026-08.
    """
    return Finding(finding_id=finding_id, experiment_id=experiment.experiment_id,
                   binding=experiment.binding, claim=MappingProxyType(dict(claim)))


# ── the clause, as a check ────────────────────────────────────────────────

def validate_experiment(experiment: Any,
                        graph: ResolvedGraph | None = None) -> list[Violation]:
    """Every way an experiment record can fail F14.

    Pass the `ResolvedGraph` to check the binding is not merely present but
    *correct* — present-but-stale is the failure mode that matters, and it is
    invisible without something to compare against.
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
