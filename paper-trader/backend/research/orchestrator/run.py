"""Experiment orchestration — the loop that turns a hypothesis into recorded
knowledge. One `run_experiment` call: build (or reuse) the immutable ExperimentSpec,
open a mutable ExperimentRun, qualify across instruments, validate the qualifiers
through the hard gate battery, score the survivors by Deflated Sharpe, queue a
PromotionCandidate for the best, deposit Findings (positive AND negative), update
the hypothesis re-test priority, and return a report dict. Persists only to
research.db; never touches capital.

This is the M1 pipeline over fixed strategy params. Optimization (searching params
inside walk-forward folds) and the multi-program nightly scheduler are M2/M3 and hang
off this same shape.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import logging
import math
import os

from research.data.store import materialize
from research.domain.models import (
    ExperimentRun,
    ExperimentSpec,
    Finding,
    Hypothesis,
    OptimizationTrial,
    PromotionCandidate,
    ResearchProgram,
)
from research.evaluation import kernels
from research.orchestrator.report import write_report
from research.pipeline.optimize import optimize
from research.pipeline.qualify import qualify_instrument
from research.pipeline.score import build_scorecard
from research.pipeline.validate import gates_from_folds, gates_passed, validate
from research.stats.retest import retest_priority
from research.strategy.builder.describe import explanation_for

logger = logging.getLogger("research.orchestrator")


def spec_hash(recipe: dict) -> str:
    """Content address of an experiment recipe — the ExperimentSpec id."""
    return hashlib.sha256(
        json.dumps(recipe, sort_keys=True, default=str).encode()).hexdigest()[:32]


def _get_or_create_program(session, name: str) -> ResearchProgram:
    p = session.query(ResearchProgram).filter_by(name=name).one_or_none()
    if p is None:
        p = ResearchProgram(name=name, thesis="")
        session.add(p)
        session.flush()
    return p


def _get_or_create_hypothesis(session, program_id: int, statement: str) -> Hypothesis:
    h = (session.query(Hypothesis)
         .filter_by(program_id=program_id, statement=statement).one_or_none())
    if h is None:
        h = Hypothesis(program_id=program_id, statement=statement)
        session.add(h)
        session.flush()
    return h


def _confidence(trades: int) -> float:
    """Crude monotone-in-evidence confidence, saturating in trade count."""
    return round(min(0.95, trades / (trades + 30.0)), 3) if trades else 0.1


def run_experiment(session, *, program_name, hypothesis_statement, strategy, datasets,
                   params=None, git_commit="unknown", seed=0, min_trades=20, n_folds=4,
                   min_positive_fold_frac=0.6, capital=50_000.0, optimize_search=False,
                   qualifier_version="q1", optimizer_version="none",
                   validator_version="v1", scoring_version="s1") -> dict:
    """`datasets` = list of (instrument, Dataset). Returns a report dict."""
    params = params if params is not None else dict(strategy.default_params)
    program = _get_or_create_program(session, program_name)
    hyp = _get_or_create_hypothesis(session, program.id, hypothesis_statement)
    interval = datasets[0][1].interval if datasets else "day"

    recipe = {
        "strategy": strategy.key, "params": params, "interval": interval,
        "datasets": {ds.instrument_key: ds.content_hash for _, ds in datasets},
        "min_trades": min_trades, "n_folds": n_folds, "seed": seed,
        "optimize_search": optimize_search,
        "versions": [qualifier_version, optimizer_version, validator_version, scoring_version],
    }
    sid = spec_hash(recipe)
    spec = session.get(ExperimentSpec, sid)
    if spec is None:
        spec = ExperimentSpec(
            id=sid, hypothesis_id=hyp.id, recipe_json=json.dumps(recipe, default=str),
            git_commit=git_commit, qualifier_version=qualifier_version,
            optimizer_version=optimizer_version, validator_version=validator_version,
            scoring_version=scoring_version, rng_seed=seed)
        session.add(spec)
        session.flush()
        logger.info("[spec] built immutable spec %s (commit %s, seed %d)", sid, git_commit, seed)
    else:
        logger.info("[spec] reusing immutable spec %s (content-addressed cache hit)", sid)

    run = ExperimentRun(spec_id=sid, status="running", started_at=dt.datetime.now())
    session.add(run)
    session.flush()
    logger.info("[run] opened run #%d on %d instrument(s), strategy=%s%s",
                run.id, len(datasets), strategy.key,
                " (optimize)" if optimize_search else " (fixed params)")

    qualified: list[str] = []
    rejected: list[dict] = []
    validated: list[dict] = []
    total_bars = 0

    for inst, ds in datasets:
        total_bars += ds.bar_count
        ie = qualify_instrument(ds.candles, inst, interval, strategy, params,
                                min_trades=min_trades, seed=seed)
        if not ie.qualified:
            logger.info("[qualify] %-10s REJECT — %s (%d trades)",
                        ie.instrument_key, ie.reason, ie.trades)
            rejected.append({"instrument": ie.instrument_key, "reason": ie.reason})
            session.add(Finding(
                hypothesis_id=hyp.id, polarity="negative", confidence=_confidence(ie.trades),
                evidence_run_id=run.id,
                statement=f"{strategy.key} did not qualify on {ie.instrument_key} "
                          f"({interval}): {ie.reason}"))
            continue
        logger.info("[qualify] %-10s PASS   — %d trades clear the min-evidence bar",
                    ie.instrument_key, ie.trades)
        qualified.append(ie.instrument_key)
        # Optimization runs ONLY here — after qualification — and always as nested
        # walk-forward (search on each fold's IS, evaluate the winner on untouched OOS).
        if optimize_search:
            opt = optimize(ds.candles, inst, strategy, n_folds=n_folds, capital=capital)
            for tr in opt.trials:
                session.add(OptimizationTrial(
                    run_id=run.id, instrument_key=ie.instrument_key, fold_index=tr.fold_index,
                    params_json=json.dumps(tr.params),
                    is_objective=(tr.is_objective if math.isfinite(tr.is_objective) else -1e12),
                    is_trades=tr.is_trades, oos_trades=tr.oos_trades, selected=tr.selected))
            logger.info("[optimize] %-10s %d trials over %d folds; %d OOS trades pooled",
                        ie.instrument_key, len(opt.trials), n_folds, len(opt.oos_trades))
            gates = gates_from_folds(opt.per_fold_oos, min_oos_trades=min_trades,
                                     min_positive_fold_frac=min_positive_fold_frac, seed=seed)
            passed = gates_passed(gates)
            score_metrics, n_trials = opt.oos_metrics, opt.n_trials
        else:
            v = validate(ds.candles, inst, strategy, params, n_folds=n_folds, capital=capital,
                         min_oos_trades=min_trades, min_positive_fold_frac=min_positive_fold_frac,
                         seed=seed)
            gates, passed, score_metrics, n_trials = v.gates, v.passed, ie.metrics, 1

        gate_summary = " ".join(
            f"{g}={'✓' if r['passed'] else '✗'}({r['value']})" for g, r in gates.items())
        if not passed:
            failed = [g for g, r in gates.items() if not r["passed"]]
            logger.info("[validate] %-10s FAIL   — %s", ie.instrument_key, gate_summary)
            rejected.append({"instrument": ie.instrument_key,
                             "reason": f"failed validation: {', '.join(failed)}"})
            session.add(Finding(
                hypothesis_id=hyp.id, polarity="negative", confidence=_confidence(ie.trades),
                evidence_run_id=run.id,
                statement=f"{strategy.key} qualified but failed validation on "
                          f"{ie.instrument_key}: {', '.join(failed)}"))
            continue
        logger.info("[validate] %-10s PASS   — %s", ie.instrument_key, gate_summary)
        sc = build_scorecard(ie.instrument_key, score_metrics, n_trials=n_trials)
        logger.info("[score] %-10s DSR=%.4f (per-trade Sharpe %.3f, %d trials deflated)",
                    ie.instrument_key, sc.dsr, sc.components["per_trade_sharpe"], n_trials)
        validated.append({"instrument": ie.instrument_key, "dsr": sc.dsr,
                          "gates": gates, "scorecard": sc.components})
        session.add(Finding(
            hypothesis_id=hyp.id, polarity="positive", confidence=_confidence(ie.trades),
            evidence_run_id=run.id,
            statement=f"{strategy.key} validated on {ie.instrument_key} "
                      f"({interval}), DSR={sc.dsr:.3f}"))

    promotion = None
    if validated:
        best = max(validated, key=lambda x: x["dsr"])
        # The candidate must carry the VALIDATED universe (what earned promotion) with a
        # per-instrument score, so the human review — and the deploy that follows — act on
        # the instruments that actually cleared every gate, not merely the ones that
        # qualified. `qualifying_universe_json` keeps the qualified keys for context; the
        # scorecard payload carries {best, validated:[{instrument, dsr, scorecard}]}.
        validated_universe = [{"instrument": v["instrument"], "dsr": v["dsr"],
                               "scorecard": v["scorecard"]} for v in validated]
        session.add(PromotionCandidate(
            run_id=run.id,
            parameterization_hash=spec_hash({"strategy": strategy.key, "params": params}),
            qualifying_universe_json=json.dumps(qualified),
            scorecard_json=json.dumps({"best": best, "validated": validated_universe}),
            status="pending"))
        promotion = best
        logger.info("[promotion] queued %s (DSR=%.4f) for human review — NOT auto-deployed",
                    best["instrument"], best["dsr"])
    else:
        logger.info("[promotion] none — no candidate cleared every validation gate")

    # Update the hypothesis: just-tested -> priority near the floor; a decisive
    # miss (nothing even qualified) stays suppressed longer than a marginal one.
    kill_strength = 1.0 if not qualified else (0.5 if not validated else 0.0)
    hyp.last_tested_at = dt.datetime.now()
    hyp.status = "supported" if validated else ("rejected" if not qualified else "open")
    hyp.retest_priority = retest_priority(days_since_test=0, kill_strength=kill_strength)
    logger.info("[knowledge] deposited %d finding(s) (%d positive, %d negative); "
                "hypothesis -> status=%s retest_priority=%.3f",
                len(rejected) + len(validated), len(validated), len(rejected),
                hyp.status, hyp.retest_priority)

    run.status = "completed"
    run.decision = "propose" if validated else "archive"
    run.completed_at = dt.datetime.now()
    run.spent_bar_seconds = float(total_bars)
    session.commit()
    logger.info("[run] #%d completed: decision=%s · %d qualified · %d validated · %d bars",
                run.id, run.decision, len(qualified), len(validated), total_bars)

    # A result nobody can interpret is a result nobody should trust with capital:
    # attach the plain-language 'what this strategy does + the exact logic it used'.
    # Generated strategies are explained from their composition (exact); hand-written
    # ones route through the authored explanation.
    explanation = dataclasses.asdict(explanation_for(strategy, params))
    if optimize_search:
        explanation["note"] = ("Parameters were optimized within a bounded grid per "
                               "walk-forward fold; the values above are the search base — "
                               "see the OptimizationTrial ledger for each fold's winner.")

    return {
        "spec_id": sid, "run_id": run.id, "git_commit": git_commit,
        "program": program_name, "hypothesis": hypothesis_statement,
        "qualified": qualified, "rejected": rejected, "validated": validated,
        "promotion": promotion, "decision": run.decision, "total_bars": total_bars,
        "explanation": explanation,
    }


def run_nightly(session, source, plan, *, git_commit="unknown", report_dir=".") -> list:
    """Run every experiment in `plan` and write a report per run. Each plan item:
    {program, hypothesis, strategy_key, instruments:[inst], interval, ...gate knobs}.
    `source` (a DataSource) supplies candles for each instrument via `materialize`;
    it is only touched here (the collection phase), never inside the pipeline. An
    empty plan is a valid no-op. Returns the report dicts (with `report_path`)."""
    logger.info("nightly: %d experiment(s) queued", len(plan))
    reports = []
    for i, item in enumerate(plan, 1):
        logger.info("═══ experiment %d/%d · program=%r · hypothesis=%r",
                    i, len(plan), item["program"], item["hypothesis"])
        strat = kernels.get_strategy(item["strategy_key"])
        interval = item.get("interval", "day")
        days = item.get("days", 2000)
        datasets = [(inst, materialize(source, inst, interval, days))
                    for inst in item["instruments"]]
        logger.info("[data] materialized %d dataset(s) @ %s: %s",
                    len(datasets), interval,
                    ", ".join(f"{ds.instrument_key}({ds.bar_count}b,#{ds.content_hash[:8]})"
                              for _, ds in datasets))
        report = run_experiment(
            session, program_name=item["program"],
            hypothesis_statement=item["hypothesis"], strategy=strat, datasets=datasets,
            params=item.get("params"), git_commit=git_commit, seed=item.get("seed", 0),
            min_trades=item.get("min_trades", 20), n_folds=item.get("n_folds", 4),
            min_positive_fold_frac=item.get("min_positive_fold_frac", 0.6),
            optimize_search=item.get("optimize_search", False))
        path = os.path.join(report_dir, f"report_run_{report['run_id']}.md")
        write_report(report, path)
        report["report_path"] = path
        logger.info("[report] wrote %s", path)
        reports.append(report)
    return reports
