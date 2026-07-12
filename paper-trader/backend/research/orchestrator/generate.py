"""Generate-and-evaluate: the bot proposes its own strategies and runs them through the
research gauntlet.

For each enumerated composition it (1) persists the composition + emitted source (so a
resulting PromotionCandidate can carry its exact composition to the human review and, on
approval, into the engine), then (2) runs it through `run_experiment` exactly like a
hand-written strategy — qualify → validate → score → deposit Findings → queue a
candidate if it clears every hard gate. A generated strategy is never auto-deployed; it
becomes a human-gated candidate like any other.

Generation should run ONLY on research-eligible instruments — the permanent sandbox
(the always-allowed commodities) plus anything not committed to a live watchlist. The
caller supplies that instrument list; this module just evaluates it.
"""
from __future__ import annotations

import json
import logging

from research.domain.models import GeneratedStrategyRecord
from research.data.store import materialize
from research.orchestrator.run import run_experiment
from research.strategy.builder.load import build_strategy
from research.strategy.builder.search import enumerate_compositions

logger = logging.getLogger("research.orchestrator")


def _persist_record(session, strat) -> None:
    rec = session.get(GeneratedStrategyRecord, strat.key)
    payload = json.dumps(strat.composition.to_dict())
    if rec is None:
        session.add(GeneratedStrategyRecord(
            key=strat.key, composition_json=payload, source=strat.source))
    else:
        rec.composition_json = payload
        rec.source = strat.source
    session.flush()


def run_generated(session, source, instruments, interval, *, limit=24,
                  git_commit="unknown", program="Generated strategies",
                  min_trades=20, n_folds=4, min_positive_fold_frac=0.6) -> list:
    """Enumerate up to `limit` compositions, persist + evaluate each on `instruments`.
    Returns the per-strategy report dicts."""
    compositions = enumerate_compositions(limit=limit)
    logger.info("generate: enumerated %d composition(s) to evaluate on %d instrument(s) @ %s",
                len(compositions), len(instruments), interval)
    datasets = [(inst, materialize(source, inst, interval)) for inst in instruments]

    reports = []
    for comp in compositions:
        strat = build_strategy(comp)                 # emit → AST-validate → sandbox-load
        _persist_record(session, strat)
        logger.info("═══ generated %s", strat.key)
        report = run_experiment(
            session, program_name=program, strategy=strat,
            hypothesis_statement=f"generated composition {strat.key} has edge",
            datasets=datasets, params={}, git_commit=git_commit,
            min_trades=min_trades, n_folds=n_folds,
            min_positive_fold_frac=min_positive_fold_frac)
        reports.append(report)
    return reports
