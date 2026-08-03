"""
Generation 2 structure search: walk a lineage of proposals, evaluate each
graph, and bind every run to what produced it (RFC 0001 F14).

Binding comes first, before anything judges a graph: a run recorded without one
is permanently unattributable, and this platform already owns a corpus with that
defect. C14 — this explores and records; it never judges.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd

from app.ir.experiment import ExperimentRecord, record
from app.ir.resolve import Library, ResolvedGraph, resolve
from app.ir.runtime import Kernel, evaluate
from app.ir.validate import validate
from research.strategy.builder.propose import Proposal, Vocabulary, lineage


class SearchRejected(Exception):
    """A graph that must not reach a record: illegal, therefore unmeasurable."""


@dataclass(frozen=True)
class Explored:
    """One graph on the path: what produced it, and what it produced."""

    proposal: Proposal | None
    graph: Mapping[str, Any]
    resolved: ResolvedGraph
    record: ExperimentRecord


@dataclass(frozen=True)
class Exploration:
    """A whole walk. A finding about the endpoint is worth nothing alone."""

    seed: int
    steps: tuple[Explored, ...]

    @property
    def records(self) -> tuple[ExperimentRecord, ...]:
        return tuple(step.record for step in self.steps)

    @property
    def proposals(self) -> tuple[Proposal, ...]:
        return tuple(step.proposal for step in self.steps if step.proposal is not None)

    @property
    def graphs(self) -> tuple[Mapping[str, Any], ...]:
        return tuple(step.graph for step in self.steps)


def observe(outputs: Mapping[str, pd.Series], warmup: int) -> dict[str, Any]:
    """What the run measured — counts, never a judgement (C14)."""
    return {
        "warmup": int(warmup),
        "outputs": {name: {"bars": int(series.size), "true": int(series.sum())}
                    for name, series in sorted(outputs.items())},
    }


def run_once(graph: Mapping[str, Any], library: tuple[Library, Mapping[str, Kernel]],
             inputs: Mapping[str, pd.Series], *,
             experiment_id: str) -> tuple[ResolvedGraph, ExperimentRecord]:
    """Validate, resolve, evaluate, and bind the result to the resolved graph."""
    components, implementations = library

    violations = validate(graph, components.components)
    if violations:
        raise SearchRejected(
            f"{experiment_id}: {len(violations)} violation(s), first "
            f"{violations[0].clause} at {violations[0].path}")

    resolved = resolve(graph, components)
    evaluated = evaluate(resolved, inputs, implementations)
    return resolved, record(experiment_id, resolved, inputs,
                            observe(evaluated.outputs, evaluated.warmup))


def explore(graph: Mapping[str, Any], vocabulary: Vocabulary,
            library: tuple[Library, Mapping[str, Kernel]],
            inputs: Mapping[str, pd.Series], *, seed: int, steps: int,
            stem: str = "search") -> Exploration:
    """Record the seed graph, then every graph its lineage reaches."""
    walked: list[tuple[Proposal | None, Mapping[str, Any]]] = [(None, graph)]
    walked += [(proposal, proposal.graph)
               for proposal in lineage(graph, vocabulary, seed=seed, steps=steps)]

    explored: list[Explored] = []
    for index, (proposal, current) in enumerate(walked):
        resolved, bound = run_once(current, library, inputs,
                                   experiment_id=f"{stem}/{seed}/{index:03d}")
        explored.append(Explored(proposal=proposal, graph=current,
                                 resolved=resolved, record=bound))

    return Exploration(seed=seed, steps=tuple(explored))


__all__ = ["Explored", "Exploration", "SearchRejected", "explore", "observe",
           "run_once"]
