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
from research.strategy.builder.search import (enumerate_compositions,
                                              sample_compositions)

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


def _regime_multiplier(comp) -> int:
    """4 if this composition conditions on a regime, else 1.

    Deliberately keyed on the composition ACTUALLY USING the block, not on the
    feature being available: inflating every candidate's trial count because
    regime blocks exist would deflate ideas that never made that choice."""
    try:
        from research.regime import REGIMES
        blob = str(comp.to_dict() if hasattr(comp, "to_dict") else comp)
        return len(REGIMES) if "regime_is(" in blob else 1
    except Exception:
        return 1


def run_generated(session, source, instruments, interval, *, limit=24,
                  git_commit="unknown", program="Generated strategies",
                  min_trades=20, n_folds=4, min_positive_fold_frac=0.6,
                  seed: int | None = None) -> list:
    """Enumerate up to `limit` compositions, persist + evaluate each on `instruments`.
    Returns the per-strategy report dicts."""
    # `seed=None` keeps the deterministic hand-picked grid — a stable control the
    # sampler can be compared against. A seed draws from the BLOCK REGISTRY
    # instead, which is what makes a newly registered block reachable at all: the
    # fixed grid names its blocks as literal strings, so widening BLOCKS widened
    # the whitelist and the search not at all.
    # THE LOOP CLOSING: read what previous nights learned, and let it shape what
    # tonight draws. Without this the sampler re-rolls the same distribution
    # forever and the Findings corpus is write-only.
    suppressed = set()
    if seed is not None:
        from research.knowledge import suppressed_blocks
        for inst in instruments:
            suppressed |= suppressed_blocks(session, getattr(inst, "key", str(inst)))
        if suppressed:
            logger.info("knowledge: suppressing %d block family/families with a "
                        "well-powered negative record: %s",
                        len(suppressed), ", ".join(sorted(suppressed)))
    compositions = (enumerate_compositions(limit=limit) if seed is None
                    else sample_compositions(limit=limit, seed=seed,
                                             suppressed=suppressed))
    # The exploration floor is allowed to override suppression entirely (a night
    # that searches nothing learns nothing). Say so when it does — a silent
    # override makes the next person unable to explain why a suppressed family
    # reappeared.
    if suppressed and any(
            ref.split("(")[0] in suppressed
            for c in compositions
            for clause in c.to_dict().values() if isinstance(clause, dict)
            for refs in clause.values() for ref in refs):
        logger.info("knowledge: exploration floor ENGAGED — suppression blocked every "
                    "lawful draw, so suppressed families are back in this round")
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
            min_positive_fold_frac=min_positive_fold_frac,
            # Every composition in this session is a trial for every other one: we
            # keep the best of `len(compositions)`, so scoring each as if it were
            # the only attempt understates the selection bias by exactly that factor.
            # Choosing WHICH regime to condition on is a selection over the four
            # regimes, on top of the composition search. Phase 5 was gated behind
            # Phase 0 precisely so this could be counted: before deflation
            # actually engaged, regime conditioning would have been a machine for
            # manufacturing regime-specific mirages.
            sibling_trials=len(compositions) * _regime_multiplier(comp))
        # Attach the knowledge state so the report explains WHY this run searched
        # what it did — see report.render_markdown.
        try:
            from research.knowledge import edge_report
            report["edge_map"] = edge_report(session)
            report["suppressed_blocks"] = sorted(suppressed)
        except Exception as e:            # noqa: BLE001
            logger.warning("edge-map render failed: %s", e)
        reports.append(report)
    return reports
