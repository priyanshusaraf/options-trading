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

from app.ir.hashing import content_address
from research.domain.models import GeneratedStrategyRecord
from research.data.store import materialize
from research.orchestrator.run import run_experiment
from research.strategy.builder.load import build_strategy
from research.strategy.builder.search import (enumerate_compositions,
                                              sample_compositions)

logger = logging.getLogger("research.orchestrator")
_MAX_GENERATED_OPERATION_ITEMS = 64


def _enumerate_for_owner(session, instruments, *, owner_id: str, limit: int,
                         seed: int | None):
    """Resolve today's bounded composition search once, before durable admission."""
    suppressed = set()
    weights: dict = {}
    if seed is not None:
        from research.knowledge import edge_weights, suppressed_blocks
        for inst in instruments:
            key = getattr(inst, "key", str(inst))
            suppressed |= suppressed_blocks(session, key, owner_id=owner_id)
            for block, weight in edge_weights(session, key, owner_id=owner_id).items():
                previous = weights.get(block)
                weights[block] = weight if previous is None else (previous + weight) / 2.0
    compositions = (enumerate_compositions(limit=limit) if seed is None
                    else sample_compositions(limit=limit, seed=seed,
                                             suppressed=suppressed, weights=weights))
    return compositions, suppressed


def generated_descriptors(session, instruments, interval, *, owner_id: str, limit: int,
                          seed: int | None, git_commit: str, provider_mode: str,
                          program: str = "Generated strategies", min_trades: int = 20,
                          n_folds: int = 4, min_positive_fold_frac: float = 0.6) -> list[dict]:
    """Freeze the exact generated workload before queue admission or provider IO.

    The manifest intentionally contains only public strategy grammar and scalar
    execution choices.  It holds the resolved composition rather than enough
    input to regenerate it, because knowledge weights can legitimately change
    between a crash and a replay.
    """
    if (not isinstance(limit, int) or isinstance(limit, bool)
            or not 0 <= limit <= _MAX_GENERATED_OPERATION_ITEMS):
        raise ValueError("generated descriptor limit is invalid")
    compositions, _ = _enumerate_for_owner(session, instruments, owner_id=owner_id,
                                            limit=limit, seed=seed)
    universe = [getattr(instrument, "key", str(instrument)) for instrument in instruments]
    return [{
        "build": str(git_commit)[:40] or "unknown",
        "composition": composition.to_dict(),
        "composition_identity": content_address(composition.to_dict()),
        "interval": interval,
        "limit": limit,
        "min_positive_fold_frac": min_positive_fold_frac,
        "min_trades": min_trades,
        "n_folds": n_folds,
        "owner_universe": universe,
        "program": program,
        "provider_mode": str(provider_mode)[:80] or "unknown",
        "seed": seed,
    } for composition in compositions]


def compositions_from_descriptors(descriptors: list[dict]) -> list:
    """Parse a persisted manifest without performing a fresh search."""
    from research.strategy.builder.grammar import Composition

    if not isinstance(descriptors, list):
        raise RuntimeError("generated durable descriptor payload is invalid")
    compositions = []
    for descriptor in descriptors:
        if not isinstance(descriptor, dict):
            raise RuntimeError("generated durable descriptor payload is invalid")
        composition = descriptor.get("composition")
        if (not isinstance(composition, dict)
                or descriptor.get("composition_identity") != content_address(composition)):
            raise RuntimeError("generated durable descriptor identity is invalid")
        parsed = Composition.from_dict(composition)
        # A builder key is a second semantic identity check; a malformed grammar
        # cannot be smuggled in under a content address for some other object.
        if parsed.to_dict() != composition:
            raise RuntimeError("generated durable descriptor is not canonical")
        compositions.append(parsed)
    return compositions


def _persist_record(session, strat, *, owner_id: str) -> None:
    rec = session.get(GeneratedStrategyRecord, (owner_id, strat.key))
    payload = json.dumps(strat.composition.to_dict())
    if rec is None:
        session.add(GeneratedStrategyRecord(
            owner_id=owner_id, key=strat.key, composition_json=payload, source=strat.source))
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


def run_generated(session, source, instruments, interval, *, owner_id: str, limit=24,
                  git_commit="unknown", program="Generated strategies",
                  min_trades=20, n_folds=4, min_positive_fold_frac=0.6,
                  seed: int | None = None, claim_guard=None,
                  durable_item_keys=None, durable_descriptors=None, completed_item_run=None,
                  bound_item_run=None, reclaim_bound_item=None,
                  bind_item_run=None, finalize_item=None) -> list:
    """Enumerate up to `limit` compositions, persist + evaluate each on `instruments`.
    Returns the per-strategy report dicts."""
    # A generated composition is work just like a handwritten plan item.  A
    # durable caller must supply pre-admitted descriptors and receipt callbacks;
    # otherwise its deterministic enumeration is not a replay contract. Refuse
    # before source materialization rather than silently creating untracked runs.
    if claim_guard is not None and (durable_item_keys is None or durable_descriptors is None):
        raise RuntimeError("generated research replay is refused without admitted durable item descriptors")
    # `seed=None` keeps the deterministic hand-picked grid — a stable control the
    # sampler can be compared against. A seed draws from the BLOCK REGISTRY
    # instead, which is what makes a newly registered block reachable at all: the
    # fixed grid names its blocks as literal strings, so widening BLOCKS widened
    # the whitelist and the search not at all.
    # THE LOOP CLOSING: read what previous nights learned, and let it shape what
    # tonight draws. Without this the sampler re-rolls the same distribution
    # forever and the Findings corpus is write-only.
    if durable_descriptors is None:
        # `_enumerate_for_owner` invokes `sample_compositions(...,
        # weights=weights)` after reading the owner-local edge map. Keep the
        # resolution here, before any materialization, so durable callers can
        # freeze it into their manifest at admission time.
        compositions, suppressed = _enumerate_for_owner(
            session, instruments, owner_id=owner_id, limit=limit, seed=seed)
    else:
        compositions = compositions_from_descriptors(durable_descriptors)
        suppressed = set()
        if len(compositions) != limit:
            raise RuntimeError("generated durable descriptor count does not match limit")
        # The stored descriptor is authoritative on recovery.  Reject ambient
        # caller drift before materializing a provider-backed dataset.
        if durable_descriptors:
            universe = [getattr(inst, "key", str(inst)) for inst in instruments]
            # Every descriptor is executable authority, not merely the first
            # member of a convenient group.  Refuse mixed universe/interval or
            # provenance manifests before materializing shared datasets.
            if any(
                descriptor["owner_universe"] != universe
                or descriptor["interval"] != interval
                or descriptor["build"] != git_commit
                or descriptor["limit"] != len(durable_descriptors)
                for descriptor in durable_descriptors
            ):
                raise RuntimeError("generated durable replay provenance drift")
    if durable_item_keys is not None and len(durable_item_keys) != len(compositions):
        raise RuntimeError("generated durable item descriptors do not match enumeration")
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
    # A recovery can be terminal purely from durable receipts.  Resolve the
    # claim fence and every item boundary before creating any provider-backed
    # dataset, otherwise a cancelled/all-complete operation still consumes data
    # I/O despite having no admissible work left.
    pending = []
    for ordinal, comp in enumerate(compositions):
        item_key = durable_item_keys[ordinal] if durable_item_keys is not None else None
        descriptor = durable_descriptors[ordinal] if durable_descriptors is not None else None
        if claim_guard is not None:
            claim_guard()
        if item_key is not None and completed_item_run is not None:
            if completed_item_run(item_key) is not None:
                continue
        if item_key is not None and bound_item_run is not None:
            abandoned = bound_item_run(item_key)
            if abandoned is not None:
                if reclaim_bound_item is None or reclaim_bound_item(item_key) != abandoned:
                    raise RuntimeError(
                        f"generated operation item {item_key} is bound to interrupted run "
                        f"#{abandoned}; replay takeover was refused")
        pending.append((comp, item_key, descriptor))
    if not pending:
        return []
    if claim_guard is not None:
        claim_guard()
    datasets = [(inst, materialize(source, inst, interval)) for inst in instruments]

    reports = []
    for comp, item_key, descriptor in pending:
        if claim_guard is not None:
            claim_guard()
        strat = build_strategy(comp)                 # emit → AST-validate → sandbox-load
        _persist_record(session, strat, owner_id=owner_id)
        logger.info("═══ generated %s", strat.key)
        report = run_experiment(
            session, owner_id=owner_id,
            program_name=descriptor["program"] if descriptor else program, strategy=strat,
            hypothesis_statement=f"generated composition {strat.key} has edge",
            datasets=datasets, params={}, git_commit=git_commit,
            seed=descriptor["seed"] if descriptor and descriptor["seed"] is not None else 0,
            min_trades=descriptor["min_trades"] if descriptor else min_trades,
            n_folds=descriptor["n_folds"] if descriptor else n_folds,
            min_positive_fold_frac=(descriptor["min_positive_fold_frac"]
                                   if descriptor else min_positive_fold_frac),
            bind_run=(lambda run_id, key=item_key: bind_item_run(key, run_id))
            if item_key is not None and bind_item_run is not None else None,
            finalize_run=(lambda run_id, key=item_key: finalize_item(key, run_id))
            if item_key is not None and finalize_item is not None else None,
            # Every composition in this session is a trial for every other one: we
            # keep the best of `len(compositions)`, so scoring each as if it were
            # the only attempt understates the selection bias by exactly that factor.
            # Choosing WHICH regime to condition on is a selection over the four
            # regimes, on top of the composition search. Phase 5 was gated behind
            # Phase 0 precisely so this could be counted: before deflation
            # actually engaged, regime conditioning would have been a machine for
            # manufacturing regime-specific mirages.
            sibling_trials=len(compositions) * _regime_multiplier(comp))
        if claim_guard is not None:
            # A watchdog loss between the expensive item and reporting prevents
            # any further generated work from being accepted as authoritative.
            claim_guard()
        # Attach the knowledge state so the report explains WHY this run searched
        # what it did — see report.render_markdown.
        try:
            from research.knowledge import edge_report
            report["edge_map"] = edge_report(session, owner_id=owner_id)
            report["suppressed_blocks"] = sorted(suppressed)
        except Exception as e:            # noqa: BLE001
            logger.warning("edge-map render failed: %s", e)
        reports.append(report)
    return reports
