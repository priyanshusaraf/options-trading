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
import copy
import datetime as dt
import functools
import hashlib
import json
import logging
import math
import os

from app.engine.charges import (
    CORRECTED_RESEARCH_CHARGE_SCHEDULE,
    charge_schedule_document,
)
from app.core.research_visualization_read import (
    build_visualization_projection,
    unavailable as unavailable_visualization,
)
from app.core.market_hours import ist_epoch
from app.market_data.candles import validate_candles

from research.data.store import Dataset, content_hash, materialize
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
from research.robustness.integration import (
    build_stationary_bootstrap_evidence,
    encode_terminal_evidence_with_robustness_fallback,
    stationary_bootstrap_recipe_binding,
)
from research.robustness.parameter_integration import (
    DISABLED,
    PROJECTION_SCHEMA,
    PreparedParameterNeighborhood,
    encode_terminal_evidence_with_parameter_fallback,
    evaluate_parameter_neighborhood,
    parameter_neighborhood_recipe_binding,
    parent_experiment_identity,
    unavailable as unavailable_parameter_neighborhood,
)
from research.orchestrator.report import write_report
from research.pipeline.optimize import optimize
from research.pipeline.qualify import qualify_instrument
from research.pipeline.score import build_scorecard
from research.stats.dsr import deflated_sharpe
from research.stats.neff import effective_sample_size, mean_pairwise_correlation
from research.shadow import STATUS_SHADOW
from research.stats.pbo import pbo
from research.pipeline.validate import gates_passed, validate
from research.stats.retest import retest_priority
from research.strategy.builder.describe import explanation_for

logger = logging.getLogger("research.orchestrator")

_ACTIVE_RUN_KEY = "research_active_terminal_run"
_EDGE_DELTA_KEY = "research_staged_edge_deltas"


def _failure_contract(stage: str) -> dict[str, str]:
    normalized = stage if stage in {
        "qualification", "optimization", "validation", "promotion", "finalization",
        "parameter_neighborhood", "evidence_persistence",
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
                        "results": {"failure": failure, **_search_result(active)},
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


def _get_or_create_program(session, name: str, *, owner_id: str) -> ResearchProgram:
    p = session.query(ResearchProgram).filter_by(owner_id=owner_id, name=name).one_or_none()
    if p is None:
        p = ResearchProgram(owner_id=owner_id, name=name, thesis="")
        session.add(p)
        session.flush()
    return p


def _get_or_create_hypothesis(session, program_id: int, statement: str, *, owner_id: str) -> Hypothesis:
    h = (session.query(Hypothesis)
         .filter_by(owner_id=owner_id, program_id=program_id, statement=statement).one_or_none())
    if h is None:
        h = Hypothesis(owner_id=owner_id, program_id=program_id, statement=statement)
        session.add(h)
        session.flush()
    return h


def _record_edge(session, strategy, instrument_key: str, validated: bool,
                 run_id: int | None, *, owner_id: str) -> None:
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
    # Do not flush while validation is still computing: SQLite's single writer
    # would otherwise block the independent lease watchdog for an entire
    # experiment.  The terminal transaction applies these compact deltas beside
    # evidence and its operation receipt.
    payload = comp.to_dict() if hasattr(comp, "to_dict") else comp
    session.info.setdefault(_EDGE_DELTA_KEY, []).append(
        (payload, instrument_key, owner_id, validated, run_id))


def _flush_staged_edges(session) -> None:
    deltas = session.info.pop(_EDGE_DELTA_KEY, [])
    if not deltas:
        return
    try:
        from research.knowledge import record_outcome
        for payload, instrument_key, owner_id, validated, run_id in deltas:
            record_outcome(session, payload, instrument_key, owner_id=owner_id,
                           validated=validated, run_id=run_id)
    except Exception as exc:  # noqa: BLE001
        # This is terminal evidence territory now: accepting an experiment while
        # silently losing a scheduled knowledge delta would make replay lie.
        raise RuntimeError("research edge delta persistence failed") from exc


def _research_partitions(datasets, development_fraction: float) -> dict:
    partitions = {}
    for _, dataset in datasets:
        development_bars = min(
            dataset.bar_count,
            max(1, int(dataset.bar_count * development_fraction)),
        ) if dataset.bar_count else 0
        validation_bars = dataset.bar_count - development_bars
        validation_start = (
            dataset.candles[development_bars].ts if validation_bars else None
        )
        partitions[dataset.instrument_key] = {
            "development_bars": development_bars,
            "development_end_ts": (
                ist_epoch(dataset.candles[development_bars - 1].ts)
                if development_bars else None
            ),
            "validation_bars": validation_bars,
            "validation_start_ts": (
                ist_epoch(validation_start) if validation_start is not None else None
            ),
            "validation_end_ts": (
                ist_epoch(dataset.candles[-1].ts) if validation_bars else None
            ),
            "_validation_start": validation_start,
        }
    return partitions


def _canonical_sequence_changed(dataset, candles, report) -> bool:
    anomaly = (report.duplicates or report.dropped_corrupt or report.repaired
               or report.reordered or len(candles) != dataset.bar_count)
    if anomaly or not candles:
        return bool(anomaly)
    return (int(candles[0].ts.timestamp()) != dataset.start_ts
            or int(candles[-1].ts.timestamp()) != dataset.end_ts)


def _frozen_dataset(dataset, candles):
    if dataclasses.is_dataclass(dataset):
        return dataclasses.replace(dataset, candles=tuple(candles))
    frozen = copy.copy(dataset)
    frozen.candles = tuple(candles)
    return frozen


def _canonical_datasets(datasets):
    frozen = []
    for instrument, dataset in datasets:
        candles, report = validate_candles(dataset.candles)
        if _canonical_sequence_changed(dataset, candles, report):
            raise ValueError("dataset does not match its canonical candle sequence")
        if isinstance(dataset, Dataset) and content_hash(candles) != dataset.content_hash:
            raise ValueError("dataset content identity does not match canonical candles")
        frozen.append((instrument, _frozen_dataset(dataset, candles)))
    return frozen


def _validated_development_fraction(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or not math.isfinite(value) or not 0.0 < value < 1.0:
        raise ValueError("development_fraction must be between zero and one")
    return value


def _challenge_disposition(datasets, prepared, binding, optimize_search, state):
    if binding is None:
        return None
    if not binding["parameter_neighborhood"]["enabled"]:
        return {"schema": PROJECTION_SCHEMA, "state": DISABLED}
    if len(datasets) != 1:
        return unavailable_parameter_neighborhood("MULTI_INSTRUMENT_AMBIGUITY")
    if optimize_search:
        return unavailable_parameter_neighborhood("OPTIMIZED_PARENT_UNSUPPORTED")
    if prepared is None:
        return unavailable_parameter_neighborhood("LEGACY_V1_GRAPH_UNSUPPORTED")
    if not state.qualified:
        return unavailable_parameter_neighborhood("PARENT_NOT_QUALIFIED")
    if state.locked_validation is None or not state.locked_validation.wf.folds:
        return unavailable_parameter_neighborhood("INSUFFICIENT_HOLDOUT")
    return False


def _parameter_challenge(
    datasets, partitions, prepared, binding, evaluator, state, *, spec_id, recipe,
    optimize_search, n_folds, capital, min_trades, min_positive_fold_frac,
    slippage_bps, slippage_multiplier, seed,
):
    disposition = _challenge_disposition(
        datasets, prepared, binding, optimize_search, state,
    )
    if disposition is not False:
        return disposition
    instrument, dataset = datasets[0]
    partition = partitions[dataset.instrument_key]
    fold_signature = tuple(
        (fold.fold_index, fold.start_ts, fold.end_ts, fold.n_bars)
        for fold in state.locked_validation.wf.folds
    )
    return evaluate_parameter_neighborhood(
        prepared, candidate_evaluator=evaluator, candles=dataset.candles,
        instrument=instrument, dataset_bars=dataset.bar_count,
        parent_fold_signature=fold_signature,
        parent_identity=parent_experiment_identity(spec_id=spec_id, recipe=recipe),
        n_folds=n_folds, capital=capital, min_trades=min_trades,
        min_positive_fold_frac=min_positive_fold_frac,
        slippage_bps=slippage_bps, slippage_multiplier=slippage_multiplier,
        seed=seed, evaluation_start=partition["_validation_start"],
        evaluation_bars=partition["validation_bars"],
        evaluation_start_ts=partition["validation_start_ts"],
    )


@dataclasses.dataclass
class _EvaluationState:
    qualified: list = dataclasses.field(default_factory=list)
    rejected: list = dataclasses.field(default_factory=list)
    validated: list = dataclasses.field(default_factory=list)
    evidence: list = dataclasses.field(default_factory=list)
    total_bars: int = 0
    locked_trades: tuple | None = None
    locked_validation: object | None = None
    visualization: object = None


def _optimization_trials(session, run, instrument_key, optimization) -> None:
    for trial in optimization.trials:
        session.add(OptimizationTrial(
            owner_id=run.owner_id, run_id=run.id, instrument_key=instrument_key,
            fold_index=trial.fold_index, params_json=json.dumps(trial.params),
            is_objective=(trial.is_objective if math.isfinite(trial.is_objective)
                          else -1e12),
            is_trades=trial.is_trades, oos_trades=trial.oos_trades,
            selected=trial.selected,
        ))
    for trial in optimization.final_trials:
        session.add(OptimizationTrial(
            owner_id=run.owner_id, run_id=run.id, instrument_key=instrument_key,
            fold_index=-1, params_json=json.dumps(trial.params),
            is_objective=(trial.objective if trial.objective is not None else -1e12),
            is_trades=trial.trades, oos_trades=0, selected=trial.selected,
        ))


def _pbo_gate(optimization, threshold: float) -> dict:
    if not optimization.perf_matrix:
        return {"passed": False,
                "value": "not computable (single candidate / too little data)"}
    result = pbo(optimization.perf_matrix, n_splits=len(optimization.perf_matrix))
    return {"passed": result.pbo <= threshold, "value": round(result.pbo, 3)}


def _search_result(active):
    progress = active.get("canonical_optimization")
    return {} if progress is None else {"canonical_optimization": copy.deepcopy(progress)}


def _development_optimization(session, run, instrument, dataset, strategy, params, partition, settings):
    prepared = settings.get("canonical_search")
    if prepared is None:
        optimized = optimize(dataset.candles, instrument, strategy, n_folds=settings["n_folds"],
            capital=settings["capital"], base_params=params,
            development_end=partition["_validation_start"], development_bars=partition["development_bars"])
        execution_strategy, execution_params = strategy, optimized.selected_params
    else:
        from research.pipeline.v2_parameter_search import optimize_canonical
        session.info[_ACTIVE_RUN_KEY]["stage"] = "optimization"
        optimized, runtime = optimize_canonical(prepared, settings["canonical_candidate_evaluator"],
            dataset=dataset, instrument=instrument, partition=partition, settings=settings,
            progress=session.info[_ACTIVE_RUN_KEY]["canonical_optimization"])
        execution_strategy, execution_params = runtime.strategy, {}
    _optimization_trials(session, run, dataset.instrument_key, optimized)
    session.info[_ACTIVE_RUN_KEY]["stage"] = "validation"
    return optimized, execution_strategy, execution_params


def _validate_candidate(session, run, instrument, dataset, strategy, params,
                        partition, settings) -> dict:
    optimized = None
    evaluated_params, evaluated_strategy = params, strategy
    if settings["optimize_search"]:
        optimized, evaluated_strategy, evaluated_params = _development_optimization(
            session, run, instrument, dataset, strategy, params, partition, settings)
    validation = validate(
        dataset.candles, instrument, evaluated_strategy, evaluated_params,
        n_folds=settings["n_folds"], capital=settings["capital"],
        min_oos_trades=settings["min_trades"],
        min_positive_fold_frac=settings["min_positive_fold_frac"],
        slippage_bps=settings["slippage_bps"],
        slippage_mult=settings["slippage_multiplier"], seed=settings["seed"],
        evaluation_start=partition["_validation_start"],
        evaluation_bars=partition["validation_bars"],
    )
    gates = dict(validation.gates)
    if optimized is not None:
        gates["pbo"] = _pbo_gate(optimized, settings["pbo_threshold"])
    trades = [trade for fold in validation.wf.folds for trade in fold.trades]
    return {
        "validation": validation, "gates": gates,
        "passed": gates_passed(gates), "trades": trades,
        "metrics": kernels.compute_metrics(trades, settings["capital"]),
        "params": optimized.selected_params if optimized is not None else evaluated_params,
        "execution_strategy": evaluated_strategy, "execution_params": evaluated_params,
        "n_trials": ((optimized.n_trials if optimized else 1)
                     * max(1, settings["sibling_trials"])),
        "var_sr": optimized.var_sr if optimized else 0.0,
        "optimization": optimized,
    }


def _qualification_evidence(dataset, interval, partition, evaluation) -> dict:
    return {
        "instrument": evaluation.instrument_key, "interval": interval,
        "dataset_content_hash": dataset.content_hash,
        "research_partition": {
            name: value for name, value in partition.items()
            if not name.startswith("_")
        },
        "qualification": {
            "qualified": evaluation.qualified, "trades": evaluation.trades,
            "reason": evaluation.reason,
        },
        "validation": None, "scorecard": None,
    }


def _record_qualification_rejection(session, run, hypothesis, strategy,
                                    interval, evaluation, state) -> None:
    state.rejected.append({"instrument": evaluation.instrument_key,
                           "reason": evaluation.reason})
    session.add(Finding(
        owner_id=run.owner_id, hypothesis_id=hypothesis.id, polarity="negative",
        confidence=confidence_from_trades(evaluation.trades),
        evidence_run_id=run.id,
        statement=f"{strategy.key} did not qualify on {evaluation.instrument_key} "
                  f"({interval}): {evaluation.reason}",
    ))
    _record_edge(session, strategy, evaluation.instrument_key, False, run.id,
                 owner_id=run.owner_id)


def _record_validation(session, run, hypothesis, strategy, interval,
                       evaluation, evidence, result, state) -> None:
    evidence["validation"] = {
        "passed": result["passed"], "gates": result["gates"],
        "params": result["params"],
    }
    summary = " ".join(
        f"{name}={'✓' if gate['passed'] else '✗'}({gate['value']})"
        for name, gate in result["gates"].items()
    )
    if not result["passed"]:
        failed = [name for name, gate in result["gates"].items()
                  if not gate["passed"]]
        state.rejected.append({
            "instrument": evaluation.instrument_key,
            "reason": f"failed validation: {', '.join(failed)}",
        })
        session.add(Finding(
            owner_id=run.owner_id, hypothesis_id=hypothesis.id,
            polarity="negative",
            confidence=confidence_from_trades(result["metrics"].trades),
            evidence_run_id=run.id,
            statement=f"{strategy.key} qualified but failed validation on "
                      f"{evaluation.instrument_key}: {', '.join(failed)}",
        ))
        _record_edge(session, strategy, evaluation.instrument_key, False, run.id,
                     owner_id=run.owner_id)
        return
    score = build_scorecard(
        evaluation.instrument_key, result["metrics"],
        n_trials=result["n_trials"], var_sr=result["var_sr"],
    )
    state.validated.append({
        "instrument": evaluation.instrument_key, "dsr": score.dsr,
        "params": result["params"], "gates": result["gates"],
        "scorecard": score.components,
    })
    evidence["scorecard"] = {"dsr": score.dsr, "components": score.components}
    _record_edge(session, strategy, evaluation.instrument_key, True, run.id,
                 owner_id=run.owner_id)
    session.add(Finding(
        owner_id=run.owner_id, hypothesis_id=hypothesis.id, polarity="positive",
        confidence=confidence_from_trades(result["metrics"].trades),
        evidence_run_id=run.id,
        statement=f"{strategy.key} validated on {evaluation.instrument_key} "
                  f"({interval}), DSR={score.dsr:.3f}",
    ))


def _search_not_qualified(session):
    progress = session.info[_ACTIVE_RUN_KEY].get("canonical_optimization")
    if progress is not None:
        progress.update(state="not_qualified", reason_code="BASELINE_NOT_QUALIFIED")


def _selected_visualization_recipe(recipe, result, progress):
    value = {**recipe, "params": result["params"]}
    if progress is not None and progress["selected"] is not None:
        selected = progress["selected"]
        original = recipe["graph_provenance"]["graph"]
        graph = {**original, "content_address": selected["content_address"],
                 "graph_address": selected["graph_address"],
                 "publication_state": "unpublished_candidate",
                 "source_graph_content_address": original["content_address"]}
        value["graph_provenance"] = {**recipe["graph_provenance"], "graph": graph}
    return value


def _evaluate_instrument(session, run, hypothesis, strategy, params, interval,
                         instrument, dataset, partition, settings, state, recipe,
                         spec_id, instrument_count) -> None:
    session.info[_ACTIVE_RUN_KEY]["stage"] = "qualification"
    state.total_bars += dataset.bar_count
    session.info[_ACTIVE_RUN_KEY]["spent_bar_seconds"] = state.total_bars
    evaluation = qualify_instrument(
        dataset.candles, instrument, interval, strategy, params,
        min_trades=settings["min_trades"], seed=settings["seed"],
        capital=settings["capital"],
        development_end=partition["_validation_start"],
        development_bars=partition["development_bars"],
    )
    evidence = _qualification_evidence(dataset, interval, partition, evaluation)
    state.evidence.append(evidence)
    if not evaluation.qualified:
        _search_not_qualified(session)
        _record_qualification_rejection(
            session, run, hypothesis, strategy, interval, evaluation, state,
        )
        if instrument_count == 1 and evaluation.trades == 0:
            state.visualization = build_visualization_projection(
                recipe=recipe, run_id=run.id, spec_id=spec_id,
                metrics=evaluation.metrics, trades=(), folds=(), gate_results={},
            )
        return
    state.qualified.append(evaluation.instrument_key)
    session.info[_ACTIVE_RUN_KEY]["stage"] = "validation"
    result = _validate_candidate(
        session, run, instrument, dataset, strategy, params, partition, settings,
    )
    if result["optimization"] is not None:
        optimization = result["optimization"]
        evidence["optimization"] = {
            "selected_params": result["params"], "selection_data": "development",
            "final_selection_budget": len(optimization.final_trials),
            "final_development_trials": [dataclasses.asdict(trial)
                                         for trial in optimization.final_trials],
            "explanation": dataclasses.asdict(
                explanation_for(result["execution_strategy"], result["execution_params"])
            ),
        }
    if instrument_count == 1:
        state.locked_trades = tuple(result["trades"])
        state.locked_validation = result["validation"]
        visualization_recipe = _selected_visualization_recipe(recipe, result,
            session.info[_ACTIVE_RUN_KEY].get("canonical_optimization"))
        state.visualization = build_visualization_projection(
            recipe=visualization_recipe, run_id=run.id, spec_id=spec_id,
            metrics=result["metrics"], trades=result["trades"],
            folds=result["validation"].wf.folds, gate_results=result["gates"],
        )
    _record_validation(
        session, run, hypothesis, strategy, interval, evaluation, evidence,
        result, state,
    )


def _evaluate_datasets(session, run, hypothesis, strategy, params, interval,
                       datasets, partitions, settings, recipe, spec_id):
    state = _EvaluationState(visualization=unavailable_visualization(
        "MULTI_INSTRUMENT_VISUALIZATION_UNAVAILABLE"
        if len(datasets) != 1 else "TERMINAL_VISUALIZATION_NOT_PRODUCED"
    ))
    for instrument, dataset in datasets:
        _evaluate_instrument(
            session, run, hypothesis, strategy, params, interval, instrument,
            dataset, partitions[dataset.instrument_key], settings, state, recipe,
            spec_id, len(datasets),
        )
    return state


def _breadth_variance(validated) -> float:
    sharpes = [row["scorecard"]["per_trade_sharpe"] for row in validated]
    if len(sharpes) < 2:
        return 0.0
    mean = sum(sharpes) / len(sharpes)
    return sum((value - mean) ** 2 for value in sharpes) / len(sharpes)


def _validated_returns(datasets, validated_keys) -> list:
    returns = []
    for instrument, dataset in datasets:
        if getattr(instrument, "key", None) in validated_keys:
            closes = [float(candle.close) for candle in dataset.candles]
            returns.append([later / earlier - 1.0
                            for earlier, later in zip(closes, closes[1:]) if earlier])
    return returns


def _deflate_breadth(validated, trials, variance) -> None:
    for row in validated:
        row["dsr_breadth_deflated"] = round(deflated_sharpe(
            row["scorecard"]["per_trade_sharpe"],
            max(2, row["scorecard"]["trades"]),
            n_trials=trials, var_sr=variance,
        ), 4)


def _promotion(session, run, strategy, datasets, qualified, validated):
    if not validated:
        return None, None
    validated_keys = {row["instrument"] for row in validated}
    returns = _validated_returns(datasets, validated_keys)
    correlation = mean_pairwise_correlation(returns)
    effective = effective_sample_size(correlation, len(validated))
    breadth_trials = max(1, int(round(effective)))
    variance = _breadth_variance(validated)
    _deflate_breadth(validated, breadth_trials, variance)
    best = max(validated, key=lambda row: row["dsr"])
    best["holdout_selection"] = {
        "selection_affected": True,
        "basis": "highest_raw_holdout_dsr",
        "breadth_adjusted_dsr": best["dsr_breadth_deflated"],
        "next_confirmatory_evidence": "untouched_shadow_period",
    }
    breadth = {
        "n_validated": len(validated), "mean_correlation": round(correlation, 4),
        "n_effective": round(effective, 3),
        "var_sr_across_instruments": round(variance, 6),
        "selection_basis": "raw_holdout_dsr",
        "selected_estimate_state": "selection_affected",
    }
    universe = [{"instrument": row["instrument"], "dsr": row["dsr"],
                 "dsr_breadth_deflated": row["dsr_breadth_deflated"],
                 "scorecard": row["scorecard"]} for row in validated]
    session.add(PromotionCandidate(
        owner_id=run.owner_id, run_id=run.id,
        parameterization_hash=spec_hash({
            "strategy": strategy.key, "params": best["params"],
        }),
        qualifying_universe_json=json.dumps(qualified), status=STATUS_SHADOW,
        scorecard_json=json.dumps({
            "best": best, "validated": universe, "breadth": breadth,
        }),
    ))
    return best, breadth


def _update_hypothesis(hypothesis, qualified, validated, rejected) -> None:
    kill_strength = 1.0 if not qualified else (0.5 if not validated else 0.0)
    hypothesis.last_tested_at = dt.datetime.now()
    hypothesis.status = (
        "supported" if validated else "rejected" if not qualified else "open"
    )
    hypothesis.retest_priority = retest_priority(
        days_since_test=0, kill_strength=kill_strength,
    )


def _checked_parameter_evidence(binding, evidence, locked_validation):
    if binding is None:
        return None
    if locked_validation is None or evidence.get("state") != "AVAILABLE":
        return evidence
    parent_folds = [[fold.fold_index, fold.start_ts, fold.end_ts, fold.n_bars]
                    for fold in locked_validation.wf.folds]
    if any(row.get("folds") != parent_folds for row in evidence["population"]):
        return unavailable_parameter_neighborhood(
            "PARAMETER_NEIGHBORHOOD_CANDIDATE_REFUSED"
        )
    return evidence


def _encode_checkpoint(evidence, parameter_binding, robustness_binding) -> str:
    if parameter_binding is not None:
        return encode_terminal_evidence_with_parameter_fallback(evidence)
    if robustness_binding is not None:
        return encode_terminal_evidence_with_robustness_fallback(evidence)
    return encode_terminal_evidence(evidence)


def _append_completion_events(session, run, rejected, validated, promotion) -> None:
    from app.events.producers import append_research_change

    append_research_change(
        session, owner_id=run.owner_id, aggregate_type="experiment_run",
        aggregate_id=str(run.id), event_type="research.run.changed",
        projection="research_runs", producer_key=f"research-run:{run.id}:completed",
        facts={"state": "completed", "decision": run.decision},
    )
    append_research_change(
        session, owner_id=run.owner_id,
        aggregate_type="experiment_run_findings", aggregate_id=str(run.id),
        event_type="research.finding.changed", projection="research_findings",
        producer_key=f"research-findings:{run.id}:completed",
        facts={"state": "completed", "count": len(rejected) + len(validated)},
    )
    if promotion is not None:
        append_research_change(
            session, owner_id=run.owner_id, aggregate_type="promotion_run",
            aggregate_id=str(run.id), event_type="research.promotion.changed",
            projection="research_promotions",
            producer_key=f"research-promotion:{run.id}:shadow",
            facts={"state": "shadow"},
        )


def _parameter_recipe_binding(parameter_neighborhood):
    prepared = (parameter_neighborhood
                if isinstance(parameter_neighborhood, PreparedParameterNeighborhood)
                else None)
    binding = (prepared.recipe_binding if prepared is not None
               else parameter_neighborhood_recipe_binding(parameter_neighborhood))
    return prepared, binding


def _public_partitions(partitions) -> dict:
    return {
        key: {name: value for name, value in partition.items()
              if not name.startswith("_")}
        for key, partition in partitions.items()
    }


def _add_recipe_provenance(document, robustness_binding, parameter_binding,
                           graph_provenance) -> None:
    combined = {}
    if robustness_binding is not None:
        combined.update(robustness_binding)
    if parameter_binding is not None:
        combined.update(parameter_binding)
    if combined:
        document["robustness"] = combined
    if graph_provenance is not None:
        document["graph_provenance"] = graph_provenance


def _recipe(
    program_name, hypothesis_statement, strategy, datasets, params, interval,
    git_commit, partitions, development_fraction, robustness,
    parameter_neighborhood, graph_provenance, settings, versions,
):
    schedule = charge_schedule_document(CORRECTED_RESEARCH_CHARGE_SCHEDULE)
    prepared, parameter_binding = _parameter_recipe_binding(parameter_neighborhood)
    document = {
        "program": program_name, "hypothesis": hypothesis_statement,
        "git_commit": git_commit, "strategy": strategy.key, "params": params,
        "interval": interval,
        "datasets": {dataset.instrument_key: _dataset_identity(dataset)
                     for _, dataset in datasets},
        "cost_assumptions": {
            "capital": settings["capital"], "charge_model": "zerodha_charges_v1",
            "sizing_model": "one_lot_or_cash_budget_v1",
            "slippage_bps": settings["slippage_bps"],
            "slippage_multiplier": settings["slippage_multiplier"],
        },
        "resolved_charge_schedule": {
            "id": schedule["id"], "address": schedule["address"],
            "effective_from": schedule["effective_from"],
            "rounding_policy": schedule["rounding_policy"],
            "profile": schedule["profile"],
            "application_mode": schedule["application_mode"],
        },
        "gates": {
            "min_oos_trades": settings["min_trades"],
            "n_folds": settings["n_folds"],
            "min_positive_fold_fraction": settings["min_positive_fold_frac"],
            "optimize_search": settings["optimize_search"],
            "pbo_threshold": settings["pbo_threshold"],
            "sibling_trials": settings["sibling_trials"],
        },
        "research_partition": {
            "schema": "chronological-development-validation/1",
            "development_fraction": development_fraction,
            "validation_use": (
                "locked_holdout_then_parameter_neighborhood_challenge"
                if parameter_binding is not None
                and parameter_binding["parameter_neighborhood"]["enabled"]
                else "locked_holdout"
            ),
            "datasets": _public_partitions(partitions),
        },
        "seed": settings["seed"], "versions": versions,
    }
    robustness_binding = stationary_bootstrap_recipe_binding(robustness)
    _add_recipe_provenance(
        document, robustness_binding, parameter_binding, graph_provenance,
    )
    if settings.get("canonical_search") is not None:
        document["canonical_optimization"] = settings["canonical_search"].binding
    return document, prepared, parameter_binding, robustness_binding


def _open_experiment(session, owner_id, hypothesis, recipe, git_commit,
                     versions, seed, bind_run):
    from app.events.producers import append_research_change

    spec_id = spec_hash(recipe)
    spec = session.query(ExperimentSpec).filter(
        ExperimentSpec.owner_id == owner_id, ExperimentSpec.id == spec_id,
    ).one_or_none()
    created = spec is None
    if created:
        spec = ExperimentSpec(
            owner_id=owner_id, id=spec_id, hypothesis_id=hypothesis.id,
            recipe_json=json.dumps(recipe, sort_keys=True, separators=(",", ":"),
                                   default=str, allow_nan=False),
            git_commit=git_commit, qualifier_version=versions[0],
            optimizer_version=versions[1], validator_version=versions[2],
            scoring_version=versions[3], rng_seed=seed,
        )
        session.add(spec)
        session.flush()
    run = ExperimentRun(
        owner_id=owner_id, spec_id=spec_id, status="running",
        started_at=dt.datetime.now(),
    )
    session.add(run)
    session.flush()
    if created:
        append_research_change(
            session, owner_id=owner_id, aggregate_type="experiment_spec",
            aggregate_id=spec_id, event_type="research.spec.changed",
            projection="research_specs",
            producer_key="research-spec:" + hashlib.sha256(
                f"{owner_id}\x1f{spec_id}".encode("utf-8")
            ).hexdigest(),
            facts={"state": "created", "content_address": f"sha256:{spec_id}"},
        )
    append_research_change(
        session, owner_id=owner_id, aggregate_type="experiment_run",
        aggregate_id=str(run.id), event_type="research.run.changed",
        projection="research_runs", producer_key=f"research-run:{run.id}:opened",
        facts={"state": "running"},
    )
    session.info[_ACTIVE_RUN_KEY] = {
        "run_id": run.id, "recipe": recipe, "stage": "qualification",
        "spent_bar_seconds": 0,
    }
    session.info[_EDGE_DELTA_KEY] = []
    if bind_run is not None and bind_run(run.id) is not True:
        raise RuntimeError("research operation claim was lost before run binding")
    session.commit()
    return spec_id, run


def _open_search_progress(session, prepared, optimize_search, datasets):
    if prepared is None:
        return
    if not optimize_search or len(datasets) != 1:
        raise ValueError("Canonical optimization requires one exact primary dataset and enabled search.")
    from research.pipeline.v2_parameter_search import search_progress
    session.info[_ACTIVE_RUN_KEY]["canonical_optimization"] = search_progress(prepared)


@_persist_failed_run
def run_experiment(session, *, owner_id: str, program_name, hypothesis_statement, strategy, datasets,
                   params=None, git_commit="unknown", seed=0, min_trades=20, n_folds=4,
                   min_positive_fold_frac=0.6, capital=50_000.0, optimize_search=False,
                   qualifier_version="q1", optimizer_version="none",
                   validator_version="v1", scoring_version="s1",
                   sibling_trials: int = 1, pbo_threshold: float = 0.30,
                   slippage_bps: float = 5.0,
                   slippage_multiplier: float = 2.0,
                   robustness: dict | None = None,
                   parameter_neighborhood: dict | PreparedParameterNeighborhood | None = None,
                   parameter_neighborhood_evaluator=None,
                   canonical_search=None, canonical_candidate_evaluator=None,
                   development_fraction: float = 0.7,
                   graph_provenance: dict | None = None,
                   bind_run=None, finalize_run=None) -> dict:
    """`datasets` = list of (instrument, Dataset). Returns a report dict.

    `sibling_trials` — how many OTHER candidates were searched alongside this one in
    the same session, outside this call. A single `run_experiment` can only see its
    own parameter grid, so when `run_generated` enumerates 24 compositions and keeps
    the best, each is scored as though it were the only thing ever tried. That is
    selection bias the DSR exists to price in, and it is invisible from in here.
    Multiplying the trial count by the sibling count is the correction; 1 (the
    default) leaves single-strategy runs exactly as they were."""
    development_fraction = _validated_development_fraction(development_fraction)
    params = params if params is not None else dict(strategy.default_params)
    datasets = _canonical_datasets(datasets)
    program = _get_or_create_program(session, program_name, owner_id=owner_id)
    hyp = _get_or_create_hypothesis(session, program.id, hypothesis_statement, owner_id=owner_id)
    interval = datasets[0][1].interval if datasets else "day"

    partitions = _research_partitions(datasets, development_fraction)
    settings = {
        "optimize_search": optimize_search, "n_folds": n_folds,
        "capital": capital, "min_trades": min_trades,
        "min_positive_fold_frac": min_positive_fold_frac,
        "slippage_bps": slippage_bps,
        "slippage_multiplier": slippage_multiplier, "seed": seed,
        "pbo_threshold": pbo_threshold, "sibling_trials": sibling_trials,
        "canonical_search": canonical_search,
        "canonical_candidate_evaluator": canonical_candidate_evaluator,
    }
    versions = [qualifier_version, optimizer_version, validator_version, scoring_version]
    recipe, parameter_prepared, parameter_binding, robustness_binding = _recipe(
        program_name, hypothesis_statement, strategy, datasets, params, interval,
        git_commit, partitions, development_fraction, robustness,
        parameter_neighborhood, graph_provenance, settings, versions,
    )
    sid, run = _open_experiment(
        session, owner_id, hyp, recipe, git_commit, versions, seed, bind_run,
    )

    _open_search_progress(session, canonical_search, optimize_search, datasets)
    state = _evaluate_datasets(
        session, run, hyp, strategy, params, interval, datasets, partitions,
        settings, recipe, sid,
    )
    qualified, rejected, validated = state.qualified, state.rejected, state.validated
    instrument_evidence, total_bars = state.evidence, state.total_bars
    locked_oos_trades, locked_oos_validation = (
        state.locked_trades, state.locked_validation
    )
    visualization = state.visualization
    session.info[_ACTIVE_RUN_KEY]["stage"] = "parameter_neighborhood"
    parameter_evidence = _parameter_challenge(
        datasets, partitions, parameter_prepared, parameter_binding,
        parameter_neighborhood_evaluator, state, spec_id=sid, recipe=recipe,
        optimize_search=optimize_search, n_folds=n_folds, capital=capital,
        min_trades=min_trades,
        min_positive_fold_frac=min_positive_fold_frac,
        slippage_bps=slippage_bps, slippage_multiplier=slippage_multiplier,
        seed=seed,
    )

    session.info[_ACTIVE_RUN_KEY]["stage"] = "promotion"
    promotion, breadth = _promotion(
        session, run, strategy, datasets, qualified, validated,
    )
    _update_hypothesis(hyp, qualified, validated, rejected)

    # A result nobody can interpret is a result nobody should trust with capital:
    # attach the plain-language 'what this strategy does + the exact logic it used'.
    # Generated strategies are explained from their composition (exact); hand-written
    # ones route through the authored explanation.
    session.info[_ACTIVE_RUN_KEY]["stage"] = "finalization"
    explanation = dataclasses.asdict(explanation_for(strategy, params))
    if optimize_search:
        explanation["parameter_role"] = "development_search_start"
        explanation["note"] = (
            "The logic above uses the starting parameters for the development search. "
            "Each instrument records its frozen selected parameters and explanation. "
            "Validation and scoring used only the later locked holdout."
        )
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
    _flush_staged_edges(session)
    terminal_evidence = {
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
            "visualization": visualization,
            **_search_result(session.info[_ACTIVE_RUN_KEY]),
        },
    }
    parameter_evidence = _checked_parameter_evidence(
        parameter_binding, parameter_evidence, locked_oos_validation,
    )
    if parameter_evidence is not None:
        terminal_evidence["results"]["parameter_neighborhood"] = parameter_evidence
    if robustness_binding is not None:
        terminal_evidence["results"]["robustness"] = build_stationary_bootstrap_evidence(
            robustness_binding,
            locked_oos_trades=locked_oos_trades,
            starting_capital=capital,
            seed=seed,
            instrument_count=len(datasets),
        )
    from research.pipeline.v2_parameter_search import verify_canonical_search_evidence
    verify_canonical_search_evidence(recipe, terminal_evidence)
    run.checkpoint_json = _encode_checkpoint(
        terminal_evidence, parameter_binding, robustness_binding,
    )
    if finalize_run is not None and not finalize_run(run.id):
        raise RuntimeError("research operation claim was lost before terminal receipt")
    _append_completion_events(session, run, rejected, validated, promotion)
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


def run_nightly(
    session, source, plan, *, owner_id: str, git_commit="unknown", report_dir=".",
    progress=None, stage=None, item_keys=None, completed_item_run=None,
    checkpoint_item=None, bind_item_run=None, bound_item_run=None, reclaim_bound_item=None,
    finalize_item=None,
) -> list:
    """Run every experiment in `plan` and write a report per run. Each plan item:
    {program, hypothesis, strategy_key, instruments:[inst], interval, ...gate knobs}.
    `source` (a DataSource) supplies candles for each instrument via `materialize`;
    it is only touched here (the collection phase), never inside the pipeline. An
    empty plan is a valid no-op. Returns the report dicts (with `report_path`)."""
    logger.info("nightly: %d experiment(s) queued", len(plan))
    reports = []
    if item_keys is not None and len(item_keys) != len(plan):
        raise ValueError("research operation item keys must match the bounded plan")
    for i, item in enumerate(plan, 1):
        item_key = item_keys[i - 1] if item_keys is not None else None
        if item_key is not None and completed_item_run is not None:
            run_id = completed_item_run(item_key)
            if run_id is not None:
                logger.info("[resume] skipping checkpointed item %s (run #%d)", item_key, run_id)
                continue
        if item_key is not None and bound_item_run is not None:
            run_id = bound_item_run(item_key)
            if run_id is not None:
                if reclaim_bound_item is None or reclaim_bound_item(item_key) != run_id:
                    raise RuntimeError(
                        f"research operation item {item_key} is bound to interrupted run #{run_id}; "
                        "automatic duplicate replay is refused")
        logger.info("═══ experiment %d/%d · program=%r · hypothesis=%r",
                    i, len(plan), item["program"], item["hypothesis"])
        strat = kernels.get_strategy(item["strategy_key"])
        interval = item.get("interval", "day")
        days = item.get("days", 2000)
        if stage is not None:
            stage("collection")
        datasets = [(inst, materialize(source, inst, interval, days))
                    for inst in item["instruments"]]
        logger.info("[data] materialized %d dataset(s) @ %s: %s",
                    len(datasets), interval,
                    ", ".join(f"{ds.instrument_key}({ds.bar_count}b,#{ds.content_hash[:8]})"
                              for _, ds in datasets))
        if stage is not None:
            stage("experiments")
        report = run_experiment(
            session, owner_id=owner_id, program_name=item["program"],
            hypothesis_statement=item["hypothesis"], strategy=strat, datasets=datasets,
            params=item.get("params"), git_commit=git_commit, seed=item.get("seed", 0),
            min_trades=item.get("min_trades", 20), n_folds=item.get("n_folds", 4),
            min_positive_fold_frac=item.get("min_positive_fold_frac", 0.6),
            capital=item.get("capital", 50_000.0),
            optimize_search=item.get("optimize_search", False),
            bind_run=(lambda run_id, key=item_key: bind_item_run(key, run_id))
            if item_key is not None and bind_item_run is not None else None,
            finalize_run=(lambda run_id, key=item_key: finalize_item(key, run_id))
            if item_key is not None and finalize_item is not None else None)
        if item_key is not None and checkpoint_item is not None and finalize_item is None:
            # The completion receipt is the replay fence.  If it cannot be
            # written, stop before the next item rather than duplicate work.
            checkpoint_item(item_key, report["run_id"])
        if progress is not None:
            progress(report["run_id"])
        if stage is not None:
            stage("reports")
        path = os.path.join(report_dir, f"report_run_{report['run_id']}.md")
        write_report(report, path)
        report["report_path"] = path
        logger.info("[report] wrote %s", path)
        reports.append(report)
    return reports
