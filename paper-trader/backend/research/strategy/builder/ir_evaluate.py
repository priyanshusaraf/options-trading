"""
The Generation 2 search loop: an exploration scored through the Generation 1 gates.

Every explored graph becomes a `Strategy` and goes through
`orchestrator.run.run_experiment` — qualify, walk-forward, DSR deflated by the
lineage's own size, PBO fail-closed, N_eff — because a second gate pipeline is
the defect RFC 0001 C12 exists to name. Nothing is scored here; the gates score,
and no report leaves this module without the `ExperimentRecord` that binds it.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping

from app.ir.experiment import ExperimentRecord, validate_experiment
from research.knowledge import record_outcome
from research.orchestrator.run import run_experiment
from research.strategy.builder.ir_search import Explored, Exploration
from research.strategy.builder.ir_strategy import IRGraphStrategy

logger = logging.getLogger("research.orchestrator")

BLOCK_PREFIX = "block."


class UnboundResult(Exception):
    """F14 — a candidate whose record does not bind the graph about to be scored."""


@dataclass(frozen=True)
class Scored:
    """One candidate's report, inseparable from what produced it."""

    explored: Explored
    strategy_key: str
    report: Mapping[str, Any]

    @property
    def record(self) -> ExperimentRecord:
        return self.explored.record

    @property
    def binding(self) -> str:
        return self.explored.record.binding


def block_refs(graph: Mapping[str, Any]) -> list[str]:
    """Every block node as a `name(args)` reference, the form `knowledge.py` reads."""
    out = []
    for node in graph["nodes"]:
        identifier = node["component"]["identifier"]
        if not identifier.startswith(BLOCK_PREFIX):
            continue
        args = ", ".join(str(v) for _, v in sorted((node.get("overrides") or {}).items()))
        out.append(f"{identifier[len(BLOCK_PREFIX):]}({args})")
    return sorted(out)


def knowledge_payload(graph: Mapping[str, Any],
                      mapping: Mapping[str, str]) -> dict[str, Any]:
    """The graph's blocks under the canonical columns they actually drive."""
    refs = block_refs(graph)
    return {column: {"all": refs} for column in sorted(mapping)}


def _feed_knowledge(session, graph: Mapping[str, Any], mapping: Mapping[str, str],
                    report: Mapping[str, Any]) -> None:
    """Credit the graph's block families where it validated, debit where it did not."""
    payload = knowledge_payload(graph, mapping)
    run_id = report.get("run_id")
    for entry in report.get("validated", []):
        record_outcome(session, payload, entry["instrument"], validated=True, run_id=run_id)
    for entry in report.get("rejected", []):
        record_outcome(session, payload, entry["instrument"], validated=False, run_id=run_id)
    session.commit()


def score_exploration(session, exploration: Exploration,
                      library, datasets, *,
                      program: str = "Generated IR graphs",
                      git_commit: str = "unknown", min_trades: int = 20,
                      n_folds: int = 4, min_positive_fold_frac: float = 0.6,
                      capital: float = 50_000.0, optimize_search: bool = False,
                      pbo_threshold: float = 0.30,
                      feed_knowledge: bool = True) -> list[Scored]:
    """Score every graph of `exploration` through the one existing gate pipeline."""
    # Every candidate in a lineage is a trial for every other one — the whole walk
    # is searched and the best of it is what a human would look at, which is exactly
    # the selection `run_generated` corrects for with `len(compositions)`. Scoring a
    # step as though it were the only graph ever tried understates the search by the
    # size of the lineage.
    siblings = len(exploration.steps)
    scored: list[Scored] = []

    for step in exploration.steps:
        strategy = IRGraphStrategy(step.graph, library)
        violations = validate_experiment(step.record, strategy.resolved)
        if violations:
            raise UnboundResult(
                f"{step.record.experiment_id}: {len(violations)} F14 violation(s), "
                f"first {violations[0].path} — {violations[0].message}")

        logger.info("═══ ir graph %s (%s)", strategy.key, step.record.experiment_id)
        report = dict(run_experiment(
            session, program_name=program, strategy=strategy,
            hypothesis_statement=f"IR graph {strategy.key} has edge",
            datasets=datasets, params={}, git_commit=git_commit,
            seed=exploration.seed, min_trades=min_trades, n_folds=n_folds,
            min_positive_fold_frac=min_positive_fold_frac, capital=capital,
            optimize_search=optimize_search, sibling_trials=siblings,
            pbo_threshold=pbo_threshold))

        report["strategy_key"] = strategy.key
        report["experiment_id"] = step.record.experiment_id
        report["binding"] = step.record.binding
        report["graph_version"] = list(step.record.graph)
        report["sibling_trials"] = siblings
        if feed_knowledge:
            _feed_knowledge(session, step.graph, strategy.mapping, report)
        scored.append(Scored(explored=step, strategy_key=strategy.key, report=report))

    return scored


__all__ = ["Scored", "UnboundResult", "block_refs", "knowledge_payload",
           "score_exploration"]
