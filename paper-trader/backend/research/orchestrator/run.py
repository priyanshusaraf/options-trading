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
import functools
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
from research.evidence import confidence_from_trades, encode_terminal_evidence
from research.orchestrator.report import write_report
from research.pipeline.optimize import optimize
from research.pipeline.qualify import qualify_instrument
from research.pipeline.score import build_scorecard
from research.stats.dsr import deflated_sharpe, expected_max_sharpe
from research.stats.neff import effective_sample_size, mean_pairwise_correlation
from research.shadow import STATUS_SHADOW
from research.stats.pbo import pbo
from research.pipeline.validate import gates_from_folds, gates_passed, validate
from research.stats.retest import retest_priority
from research.strategy.builder.describe import explanation_for

logger = logging.getLogger("research.orchestrator")

_ACTIVE_RUN_KEY = "research_active_terminal_run"


def _failure_contract(stage: str) -> dict[str, str]:
    normalized = stage if stage in {
        "qualification", "validation", "promotion", "finalization",
        "evidence_persistence",
    } else "pipeline"
    return {
        "stage": normalized,
        "code": f"RESEARCH_{normalized.upper()}_FAILED",
        "message": f"research {normalized.replace('_', ' ')} failed",
    }


def _persist_failed_run(fn):
    """Make a started run terminal without persisting partial pipeline writes."""
    @functools.wraps(fn)
    def wrapped(session, *args, **kwargs):
        session.info.pop(_ACTIVE_RUN_KEY, None)
        try:
            return fn(session, *args, **kwargs)
        except Exception:
            active = session.info.get(_ACTIVE_RUN_KEY)
            if active is None:
                raise
            session.rollback()
            run = session.get(ExperimentRun, active["run_id"])
            if run is not None and run.status != "completed":
                failure = _failure_contract(active["stage"])
                run.status = "failed"
                run.decision = "needs_review"
                run.completed_at = dt.datetime.now()
                run.spent_bar_seconds = float(active["spent_bar_seconds"])
                run.error = failure["code"]
                try:
                    run.checkpoint_json = encode_terminal_evidence({
                        "spec_id": run.spec_id,
                        "run": {
                            "id": run.id,
                            "status": run.status,
                            "decision": run.decision,
                        },
                        "provenance": active["recipe"],
                        "results": {"failure": failure},
                    })
                    session.commit()
                except Exception:
                    # A broken evidence encoder must still never leave a false
                    # completed state. Missing failed evidence then fails closed.
                    session.rollback()
                    run = session.get(ExperimentRun, active["run_id"])
                    run.status = "failed"
                    run.decision = "needs_review"
                    run.completed_at = dt.datetime.now()
                    run.error = "RESEARCH_FAILURE_EVIDENCE_PERSISTENCE_FAILED"
                    run.checkpoint_json = None
                    session.commit()
            raise
        finally:
            session.info.pop(_ACTIVE_RUN_KEY, None)
    return wrapped


def spec_hash(recipe: dict) -> str:
    """Content address of an experiment recipe — the ExperimentSpec id."""
    return hashlib.sha256(
        json.dumps(
            recipe,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
            allow_nan=False,
        ).encode()
    ).hexdigest()[:32]


def _dataset_identity(dataset) -> dict:
    """The exact frozen data selection that fed an experiment recipe."""
    return {
        "instrument_key": dataset.instrument_key,
        "interval": dataset.interval,
        "requested_days": dataset.requested_days,
        "bar_count": dataset.bar_count,
        "start_ts": dataset.start_ts,
        "end_ts": dataset.end_ts,
        "content_hash": dataset.content_hash,
    }


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


def _record_edge(session, strategy, instrument_key: str, validated: bool,
                 run_id: int | None) -> None:
    """Feed the block-family x instrument edge map.

    Only GENERATED strategies carry a composition; a handwritten one has no block
    decomposition to learn from, so it contributes nothing here rather than
    contributing something wrong. Never fatal: the reinforcement loop is an
    optimisation, and a bookkeeping failure must not lose an experiment's real
    result.
    """
    comp = getattr(strategy, "composition", None)
    if comp is None:
        return
    try:
        from research.knowledge import record_outcome
        payload = comp.to_dict() if hasattr(comp, "to_dict") else comp
        record_outcome(session, payload, instrument_key,
                       validated=validated, run_id=run_id)
    except Exception as e:            # noqa: BLE001
        logger.warning("edge-map update failed for %s/%s: %s",
                       getattr(strategy, "key", "?"), instrument_key, e)


@_persist_failed_run
def run_experiment(session, *, program_name, hypothesis_statement, strategy, datasets,
                   params=None, git_commit="unknown", seed=0, min_trades=20, n_folds=4,
                   min_positive_fold_frac=0.6, capital=50_000.0, optimize_search=False,
                   qualifier_version="q1", optimizer_version="none",
                   validator_version="v1", scoring_version="s1",
                   sibling_trials: int = 1, pbo_threshold: float = 0.30,
                   slippage_bps: float = 5.0,
                   slippage_multiplier: float = 2.0,
                   graph_provenance: dict | None = None) -> dict:
    """`datasets` = list of (instrument, Dataset). Returns a report dict.

    `sibling_trials` — how many OTHER candidates were searched alongside this one in
    the same session, outside this call. A single `run_experiment` can only see its
    own parameter grid, so when `run_generated` enumerates 24 compositions and keeps
    the best, each is scored as though it were the only thing ever tried. That is
    selection bias the DSR exists to price in, and it is invisible from in here.
    Multiplying the trial count by the sibling count is the correction; 1 (the
    default) leaves single-strategy runs exactly as they were."""
    params = params if params is not None else dict(strategy.default_params)
    program = _get_or_create_program(session, program_name)
    hyp = _get_or_create_hypothesis(session, program.id, hypothesis_statement)
    interval = datasets[0][1].interval if datasets else "day"

    recipe = {
        "program": program_name,
        "hypothesis": hypothesis_statement,
        "git_commit": git_commit,
        "strategy": strategy.key, "params": params, "interval": interval,
        "datasets": {ds.instrument_key: _dataset_identity(ds) for _, ds in datasets},
        "cost_assumptions": {
            "capital": capital,
            "charge_model": "zerodha_charges_v1",
            "sizing_model": "one_lot_or_cash_budget_v1",
            "slippage_bps": slippage_bps,
            "slippage_multiplier": slippage_multiplier,
        },
        "gates": {
            "min_oos_trades": min_trades,
            "n_folds": n_folds,
            "min_positive_fold_fraction": min_positive_fold_frac,
            "optimize_search": optimize_search,
            "pbo_threshold": pbo_threshold,
            "sibling_trials": sibling_trials,
        },
        "seed": seed,
        "versions": [qualifier_version, optimizer_version, validator_version, scoring_version],
    }
    if graph_provenance is not None:
        recipe["graph_provenance"] = graph_provenance
    sid = spec_hash(recipe)
    spec = session.get(ExperimentSpec, sid)
    if spec is None:
        spec = ExperimentSpec(
            id=sid,
            hypothesis_id=hyp.id,
            recipe_json=json.dumps(
                recipe,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
                allow_nan=False,
            ),
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
    run_id = run.id
    session.commit()
    session.info[_ACTIVE_RUN_KEY] = {
        "run_id": run_id,
        "recipe": recipe,
        "stage": "qualification",
        "spent_bar_seconds": 0,
    }
    logger.info("[run] opened run #%d on %d instrument(s), strategy=%s%s",
                run.id, len(datasets), strategy.key,
                " (optimize)" if optimize_search else " (fixed params)")

    qualified: list[str] = []
    rejected: list[dict] = []
    validated: list[dict] = []
    instrument_evidence: list[dict] = []
    total_bars = 0

    for inst, ds in datasets:
        session.info[_ACTIVE_RUN_KEY]["stage"] = "qualification"
        total_bars += ds.bar_count
        session.info[_ACTIVE_RUN_KEY]["spent_bar_seconds"] = total_bars
        ie = qualify_instrument(ds.candles, inst, interval, strategy, params,
                                min_trades=min_trades, seed=seed, capital=capital)
        evidence_item = {
            "instrument": ie.instrument_key,
            "interval": interval,
            "dataset_content_hash": ds.content_hash,
            "qualification": {
                "qualified": ie.qualified,
                "trades": ie.trades,
                "reason": ie.reason,
            },
            "validation": None,
            "scorecard": None,
        }
        instrument_evidence.append(evidence_item)
        if not ie.qualified:
            logger.info("[qualify] %-10s REJECT — %s (%d trades)",
                        ie.instrument_key, ie.reason, ie.trades)
            rejected.append({"instrument": ie.instrument_key, "reason": ie.reason})
            session.add(Finding(
                hypothesis_id=hyp.id, polarity="negative", confidence=confidence_from_trades(ie.trades),
                evidence_run_id=run.id,
                statement=f"{strategy.key} did not qualify on {ie.instrument_key} "
                          f"({interval}): {ie.reason}"))
            # A qualification failure is negative evidence about these blocks on
            # this instrument too — arguably the most common kind. Recording only
            # validation failures would leave the edge map blind to every idea
            # that never even produced enough trades to be judged.
            _record_edge(session, strategy, ie.instrument_key, False, run.id)
            continue
        logger.info("[qualify] %-10s PASS   — %d trades clear the min-evidence bar",
                    ie.instrument_key, ie.trades)
        qualified.append(ie.instrument_key)
        session.info[_ACTIVE_RUN_KEY]["stage"] = "validation"
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
            gates = gates_from_folds(
                opt.per_fold_oos,
                min_oos_trades=min_trades,
                min_positive_fold_frac=min_positive_fold_frac,
                slippage_bps=slippage_bps,
                slippage_mult=slippage_multiplier,
                seed=seed,
            )
            # PBO asks what the DSR cannot: does the IN-SAMPLE ranking carry any
            # out-of-sample information at all, or does picking the winner just
            # pick noise? A search can clear every gate above and still be pure
            # overfit if the ranking scrambles. Fails CLOSED — a matrix that
            # cannot be evaluated does not pass.
            if opt.perf_matrix:
                res = pbo(opt.perf_matrix, n_splits=len(opt.perf_matrix))
                gates["pbo"] = {"passed": res.pbo <= pbo_threshold,
                                "value": round(res.pbo, 3)}
            else:
                gates["pbo"] = {"passed": False,
                                "value": "not computable (single candidate / too little data)"}
            passed = gates_passed(gates)
            # var_sr is the OTHER half of DSR deflation: expected_max_sharpe()
            # returns 0 whenever it is 0, so passing n_trials alone left the
            # deflation benchmark at zero on every candidate ever scored.
            score_metrics, n_trials = opt.oos_metrics, opt.n_trials * max(1, sibling_trials)
            var_sr = opt.var_sr
        else:
            v = validate(ds.candles, inst, strategy, params, n_folds=n_folds, capital=capital,
                         min_oos_trades=min_trades, min_positive_fold_frac=min_positive_fold_frac,
                         slippage_bps=slippage_bps,
                         slippage_mult=slippage_multiplier, seed=seed)
            # Single-pass validation searches nothing, so there is no selection
            # to deflate: n_trials=1 makes the DSR reduce to a PSR against zero,
            # which is correct here rather than a gap.
            gates, passed, score_metrics = v.gates, v.passed, ie.metrics
            n_trials = max(1, sibling_trials)
            var_sr = 0.0

        evidence_item["validation"] = {
            "passed": passed,
            "gates": gates,
        }

        gate_summary = " ".join(
            f"{g}={'✓' if r['passed'] else '✗'}({r['value']})" for g, r in gates.items())
        if not passed:
            failed = [g for g, r in gates.items() if not r["passed"]]
            logger.info("[validate] %-10s FAIL   — %s", ie.instrument_key, gate_summary)
            rejected.append({"instrument": ie.instrument_key,
                             "reason": f"failed validation: {', '.join(failed)}"})
            session.add(Finding(
                hypothesis_id=hyp.id, polarity="negative", confidence=confidence_from_trades(ie.trades),
                evidence_run_id=run.id,
                statement=f"{strategy.key} qualified but failed validation on "
                          f"{ie.instrument_key}: {', '.join(failed)}"))
            _record_edge(session, strategy, ie.instrument_key, False, run.id)
            continue
        logger.info("[validate] %-10s PASS   — %s", ie.instrument_key, gate_summary)
        sc = build_scorecard(ie.instrument_key, score_metrics,
                             n_trials=n_trials, var_sr=var_sr)
        logger.info("[score] %-10s DSR=%.4f (per-trade Sharpe %.3f, %d trials, "
                    "var_sr=%.4f, benchmark SR0=%.4f)",
                    ie.instrument_key, sc.dsr, sc.components["per_trade_sharpe"],
                    n_trials, var_sr, expected_max_sharpe(var_sr, n_trials))
        validated.append({"instrument": ie.instrument_key, "dsr": sc.dsr,
                          "gates": gates, "scorecard": sc.components})
        evidence_item["scorecard"] = {
            "dsr": sc.dsr,
            "components": sc.components,
        }
        _record_edge(session, strategy, ie.instrument_key, True, run.id)
        session.add(Finding(
            hypothesis_id=hyp.id, polarity="positive", confidence=confidence_from_trades(ie.trades),
            evidence_run_id=run.id,
            statement=f"{strategy.key} validated on {ie.instrument_key} "
                      f"({interval}), DSR={sc.dsr:.3f}"))

    promotion = None
    breadth = None
    session.info[_ACTIVE_RUN_KEY]["stage"] = "promotion"
    if validated:
        # Picking the best of N validated instruments is ITSELF a selection, and it
        # was unaccounted: each instrument's DSR was deflated for its own parameter
        # search, then the winner of a cross-instrument beauty contest was promoted
        # as though that contest never happened. Deflating by raw N would overstate
        # the fix, because these names move together — N_eff is the honest count
        # (rho ~ 0.4 turns 200 large-caps into ~2.5 independent bets).
        val_keys = {v["instrument"] for v in validated}
        returns = []
        for inst_obj, ds in datasets:
            if getattr(inst_obj, "key", None) in val_keys:
                closes = [float(c.close) for c in ds.candles]
                returns.append([b / a - 1.0 for a, b in zip(closes, closes[1:]) if a])
        rho = mean_pairwise_correlation(returns)
        n_eff = effective_sample_size(rho, len(validated))
        breadth_trials = max(1, int(round(n_eff)))
        # var_sr for THIS selection is the dispersion of Sharpes ACROSS INSTRUMENTS —
        # that is the pool the winner was chosen from. Reusing the loop variable
        # `var_sr` here would silently apply the LAST instrument's parameter-search
        # dispersion to a cross-instrument decision: a different quantity entirely,
        # and whichever instrument happened to be iterated last.
        inst_sharpes = [v["scorecard"]["per_trade_sharpe"] for v in validated]
        if len(inst_sharpes) >= 2:
            _m = sum(inst_sharpes) / len(inst_sharpes)
            breadth_var_sr = sum((x - _m) ** 2 for x in inst_sharpes) / len(inst_sharpes)
        else:
            breadth_var_sr = 0.0
        for v in validated:
            v["dsr_breadth_deflated"] = round(deflated_sharpe(
                v["scorecard"]["per_trade_sharpe"], max(2, v["scorecard"]["trades"]),
                n_trials=breadth_trials, var_sr=breadth_var_sr), 4)
        logger.info("[breadth] %d validated instrument(s), mean rho=%.3f -> N_eff=%.2f "
                    "(deflating the cross-instrument pick by %d)",
                    len(validated), rho, n_eff, breadth_trials)
        best = max(validated, key=lambda x: x["dsr"])
        # The candidate must carry the VALIDATED universe (what earned promotion) with a
        # per-instrument score, so the human review — and the deploy that follows — act on
        # the instruments that actually cleared every gate, not merely the ones that
        # qualified. `qualifying_universe_json` keeps the qualified keys for context; the
        # scorecard payload carries {best, validated:[{instrument, dsr, scorecard}]}.
        validated_universe = [{"instrument": v["instrument"], "dsr": v["dsr"],
                               "scorecard": v["scorecard"]} for v in validated]
        breadth = {
            "n_validated": len(validated),
            "mean_correlation": round(rho, 4),
            "n_effective": round(n_eff, 3),
            "var_sr_across_instruments": round(breadth_var_sr, 6),
        }
        session.add(PromotionCandidate(
            run_id=run.id,
            parameterization_hash=spec_hash({"strategy": strategy.key, "params": params}),
            qualifying_universe_json=json.dumps(qualified),
            # STATUS_SHADOW, not "pending". A validated candidate has cleared a
            # retrospective bar: every parameter was chosen with the whole series
            # visible, and deflation/PBO can only discount that, never remove it.
            # It must survive sessions it has never seen before a human is asked
            # to look — see research/shadow.py.
            status=STATUS_SHADOW,
            scorecard_json=json.dumps({
                "best": best, "validated": validated_universe,
                # Recorded so a human reviewing the queue can see that "validated on
                # 12 instruments" was really ~N_eff independent bets.
                "breadth": breadth}),
            ))
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

    # A result nobody can interpret is a result nobody should trust with capital:
    # attach the plain-language 'what this strategy does + the exact logic it used'.
    # Generated strategies are explained from their composition (exact); hand-written
    # ones route through the authored explanation.
    session.info[_ACTIVE_RUN_KEY]["stage"] = "finalization"
    explanation = dataclasses.asdict(explanation_for(strategy, params))
    if optimize_search:
        explanation["note"] = ("Parameters were optimized within a bounded grid per "
                               "walk-forward fold; the values above are the search base — "
                               "see the OptimizationTrial ledger for each fold's winner.")
    regimes = _regime_context(datasets)
    run.status = "completed"
    run.decision = "propose" if validated else "archive"
    run.completed_at = dt.datetime.now()
    run.spent_bar_seconds = float(total_bars)
    report = {
        "spec_id": sid, "run_id": run.id, "git_commit": git_commit,
        "program": program_name, "hypothesis": hypothesis_statement,
        "qualified": qualified, "rejected": rejected, "validated": validated,
        "promotion": promotion, "decision": run.decision, "total_bars": total_bars,
        "explanation": explanation,
        "regimes": regimes,
        "breadth": breadth,
    }
    session.info[_ACTIVE_RUN_KEY]["stage"] = "evidence_persistence"
    run.checkpoint_json = encode_terminal_evidence({
        "spec_id": sid,
        "run": {
            "id": run.id,
            "status": run.status,
            "decision": run.decision,
        },
        "provenance": recipe,
        "results": {
            "qualified": qualified,
            "rejected": rejected,
            "validated": validated,
            "instruments": instrument_evidence,
            "promotion": promotion,
            "breadth": breadth,
            "total_bars": total_bars,
            "regimes": regimes,
            "explanation": explanation,
        },
    })
    session.commit()
    logger.info("[run] #%d completed: decision=%s · %d qualified · %d validated · %d bars",
                run.id, run.decision, len(qualified), len(validated), total_bars)
    return report


def _regime_context(datasets) -> dict:
    """What market conditions this experiment was actually measured in.

    DIAGNOSTIC ONLY, and the distinction matters. Nothing selects on regime yet —
    the generator does not condition on it — so this does NOT inflate the trial
    count. The moment generation starts choosing per regime, that becomes a
    selection over N regimes and `regime.regime_trial_multiplier` has to feed
    `sibling_trials`, or the DSR will be told a smaller search happened than did.

    Reported because "the edge only appeared in high-vol trend" is the single most
    useful thing to know about a result that looks mediocre in aggregate — and it
    is invisible in any aggregate statistic.
    """
    from research.regime import label_regimes, regime_distribution
    out = {}
    for inst, ds in datasets or []:
        try:
            frame = kernels.compute_signals(ds.candles, kernels.get_strategy(None), {})
            if frame is None or len(frame) == 0:
                continue
            out[getattr(inst, "key", "?")] = regime_distribution(label_regimes(frame))
        except Exception as e:            # noqa: BLE001
            logger.warning("regime labelling failed for %s: %s",
                           getattr(inst, "key", "?"), e)
    return out


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
