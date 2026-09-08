"""Optimization — nested walk-forward. Params are searched on each fold's in-sample
window and the winner is evaluated on the fold's UNTOUCHED out-of-sample window, so
the OOS record is never contaminated by selection. Every trial is recorded (the DSR
deflation ledger). Optimization runs only after qualification (the orchestrator gates
it); here we test the mechanics directly.
"""
import dataclasses
import math
from collections import defaultdict

import pytest

from research.evaluation import kernels
from research.pipeline.optimize import OptimizationResult, _objective, optimize
from research.strategy.spec import ParamSpec, grid, param_space


def _strat():
    return kernels.get_strategy("trend_impulse_v3")


class _M:
    """Minimal BTMetrics stand-in for objective unit tests."""
    def __init__(self, trades, expectancy, consistency):
        self.trades = trades
        self.expectancy = expectancy
        self.consistency = consistency


def test_objective_prefers_many_consistent_trades_over_one_big_trade():
    # The bug: raw expectancy makes a single huge buy-and-hold win beat a real
    # many-trade edge; that winner then completes 0 round-trips out-of-sample.
    one_big = _M(trades=1, expectancy=500_000.0, consistency=None)
    many_consistent = _M(trades=40, expectancy=1_500.0, consistency=0.5)
    assert _objective(many_consistent) > _objective(one_big)


def test_objective_excludes_too_few_trades():
    # a lone trade (or a handful) is not evidence of an edge, however big
    assert _objective(_M(trades=1, expectancy=1e9, consistency=None)) == float("-inf")
    assert _objective(_M(trades=3, expectancy=1e9, consistency=2.0)) == float("-inf")


def test_objective_is_a_trade_count_aware_t_stat():
    base = _M(trades=40, expectancy=100, consistency=0.3)
    more_consistent = _M(trades=40, expectancy=100, consistency=0.6)
    more_trades = _M(trades=90, expectancy=100, consistency=0.3)
    assert _objective(more_consistent) > _objective(base)   # higher per-trade Sharpe wins
    assert _objective(more_trades) > _objective(base)        # more trades at same edge wins (√n)


def test_optimize_records_every_trial_and_pools_oos(fake_inst, candles_factory):
    res = optimize(candles_factory(500), fake_inst, _strat(), n_folds=3)
    n_candidates = len(grid(param_space("trend_impulse_v3")))
    assert res.n_trials == 3 * n_candidates
    assert len(res.trials) == 3 * n_candidates
    assert len(res.per_fold_selected) == 3
    assert res.oos_metrics is not None


def test_optimize_selects_params_from_the_grid(fake_inst, candles_factory):
    res = optimize(candles_factory(500), fake_inst, _strat(), n_folds=3)
    g = grid(param_space("trend_impulse_v3"))
    assert all(sel in g for sel in res.per_fold_selected)
    assert len(res.final_trials) == len(g)
    assert sum(trial.selected for trial in res.final_trials) == 1
    assert all(trial.role == "final_development_selection"
               for trial in res.final_trials)
    assert next(trial.params for trial in res.final_trials if trial.selected) \
        == res.selected_params


def test_optimize_selection_does_not_inspect_locked_validation_prices(
        fake_inst, candles_factory):
    candles = candles_factory(500)
    cutoff = 350
    changed = candles[:cutoff] + [
        dataclasses.replace(
            candle, open=candle.open * 10, high=candle.high * 10,
            low=candle.low * 10, close=candle.close * 10,
        )
        for candle in candles[cutoff:]
    ]
    kwargs = {
        "n_folds": 3,
        "development_end": candles[cutoff].ts,
        "development_bars": cutoff,
    }

    original = optimize(candles, fake_inst, _strat(), **kwargs)
    altered = optimize(changed, fake_inst, _strat(), **kwargs)

    assert original.selected_params == altered.selected_params


def test_optimize_selected_is_best_in_sample_objective_per_fold(fake_inst, candles_factory):
    res = optimize(candles_factory(500), fake_inst, _strat(), n_folds=3)
    by_fold = defaultdict(list)
    for t in res.trials:
        by_fold[t.fold_index].append(t)
    for trials in by_fold.values():
        selected = [t for t in trials if t.selected]
        assert len(selected) == 1
        assert selected[0].is_objective == max(t.is_objective for t in trials)


def test_optimize_insufficient_data_is_safe(fake_inst, candles_factory):
    res = optimize(candles_factory(40), fake_inst, _strat(), n_folds=8)
    assert isinstance(res, OptimizationResult)
    assert res.oos_metrics is not None


def test_optimize_empty_development_window_returns_no_selected_trials(
        fake_inst, candles_factory):
    candles = candles_factory(100)
    res = optimize(
        candles, fake_inst, _strat(), n_folds=3,
        development_end=candles[0].ts, development_bars=0,
    )

    assert res.trials == []
    assert res.per_fold_selected == []
    assert res.oos_trades == []
    assert res.n_trials == 0
    assert res.selected_params == _strat().default_params


# ── var_sr: the deflation input that was never computed (Phase 0, 2026-08-01) ──

def test_optimize_populates_a_real_var_sr_from_its_trials(fake_inst, candles_factory):
    """End-to-end proof, not a dataclass unit test.

    `expected_max_sharpe()` returns exactly 0 whenever var_sr is 0, so for as long
    as nothing computed it the DSR degraded to a PSR against zero and a wider search
    could not raise the bar. Asserting the dataclass arithmetic alone would not have
    caught that — the gap was that the real search never filled the field in."""
    res = optimize(candles_factory(500), fake_inst, _strat(), n_folds=3)
    assert res.n_trials > 1
    assert res.var_sr > 0.0, "the search ran many trials but reported no dispersion"


def test_trials_carry_their_per_trade_sharpe(fake_inst, candles_factory):
    res = optimize(candles_factory(500), fake_inst, _strat(), n_folds=3)
    scored = [t for t in res.trials if t.is_sharpe is not None]
    assert scored, "no trial recorded a Sharpe"
    for t in scored:
        # _objective is per-trade Sharpe x sqrt(n); the two must stay consistent or
        # var_sr and the ranking would be describing different quantities.
        assert t.is_objective == pytest.approx(t.is_sharpe * math.sqrt(t.is_trades))


def test_var_sr_makes_the_deflation_benchmark_bite(fake_inst, candles_factory):
    """The consequence, stated as a number: with the measured var_sr the benchmark
    is strictly positive, so an identical result scores lower than it used to."""
    from research.stats.dsr import deflated_sharpe, expected_max_sharpe
    res = optimize(candles_factory(500), fake_inst, _strat(), n_folds=3)
    assert expected_max_sharpe(res.var_sr, res.n_trials) > 0.0
    kw = dict(sr=0.15, n=200)
    assert deflated_sharpe(**kw, n_trials=res.n_trials, var_sr=res.var_sr) < \
        deflated_sharpe(**kw, n_trials=1, var_sr=0.0)


def test_all_optimization_replays_preserve_explicit_policy(monkeypatch, fake_inst, candles_factory):
    strategy = _strat()
    monkeypatch.setattr(strategy, "replay_policy", "pine-reversal-fixed-unit/1", raising=False)
    seen = []
    def replay(*args, **kwargs):
        seen.append(kwargs["replay_policy"])
        return []
    monkeypatch.setattr(kernels, "run_trades", replay)
    result = optimize(candles_factory(100), fake_inst, strategy,
                      space={"ema_length": ParamSpec("ema_length", "int", 50, values=[20, 50])}, n_folds=2, pbo_blocks=2)
    assert result.n_trials == 4
    assert len(result.final_trials) == 2
    assert len(result.perf_matrix) == 2
    # Two folds × (two development candidates + one OOS winner), two final
    # candidates, and two PBO blocks × two candidates must all carry the policy.
    assert seen == ["pine-reversal-fixed-unit/1"] * 12


def _prepared_canonical_search(monkeypatch):
    from app.ir.first_party.analytical_v2 import core_math as core
    from app.ir.registry import PlatformRegistry
    from app.editor import v2_mutations
    keys = (("analytical.rising", 2), ("analytical.falling", 2))
    registry = PlatformRegistry(components={}, bodies={}, registrations={}, v2_types=core.V2_TYPES,
        v2_components={key: core.V2_COMPONENTS[key] for key in keys},
        node_contracts={key: core.NODE_CONTRACTS[key] for key in keys},
        contract_bindings={key: core.CONTRACT_BINDINGS[key] for key in keys},
        v2_implementations={key: core.V2_IMPLEMENTATIONS[key] for key in keys})
    # This unit fixture closes only its two real leaves; the full-platform worker
    # journey remains separate evidence and must pass the actual library closure.
    monkeypatch.setattr(v2_mutations, "_catalogue_identities", lambda: frozenset(keys))
    from research_tests.test_v2_graph_experiment_bridge import _saved_v2_boolean_graph
    from research.pipeline.v2_parameter_search import prepare_canonical_search, SEARCH_SCHEMA
    request = {"schema": SEARCH_SCHEMA, "enabled": True,
        "axes": [{"node_id": "rising", "parameter_id": "window", "step": "1", "minimum": "1", "maximum": "3"}]}
    return prepare_canonical_search(request, document=_saved_v2_boolean_graph(registry), registry=registry)


def _canonical_test_evaluator(prepared, seen, fail_at=None, cancelled=False):
    from types import SimpleNamespace
    from research.robustness.parameter_integration import CandidateRuntime, CandidateEvaluationCancelled
    def evaluate(point):
        seen.append(point)
        if len(seen) == fail_at:
            if cancelled:
                raise CandidateEvaluationCancelled("cancelled test claim")
            raise ValueError("candidate evaluation failed")
        candidate = next(row for row in prepared.candidates if list(point) == row["parameters"])
        strategy = SimpleNamespace(key="canonical.test", default_params={}, risk_model=None,
            replay_policy=None, replay_slippage_pct=.0005, window=point[0]["value"])
        return CandidateRuntime(strategy, candidate["graph_address"], {
            "content_address": candidate["content_address"], "graph_address": candidate["graph_address"]})
    return evaluate


def _canonical_test_signals(candles, strategy, params):
    import pandas as pd
    assert params == {}, "canonical runtime must never receive ad hoc parameter overrides"
    frame = pd.DataFrame([{"date": candle.ts, "open": candle.open, "high": candle.high,
        "low": candle.low, "close": candle.close} for candle in candles])
    phase = pd.Series(range(len(frame))) % 8
    frame["longEntry"] = phase == strategy.window
    frame["longExit"] = phase == 6
    frame["shortEntry"] = False
    frame["shortExit"] = False
    return frame


def _canonical_search_case(monkeypatch, fake_inst, candles_factory, *, fail_at=None, cancelled=False):
    from types import SimpleNamespace
    from research.pipeline.v2_parameter_search import search_progress
    candles = candles_factory(300)
    partition = {"_validation_start": candles[210].ts, "development_bars": 210,
                 "validation_bars": 90, "validation_start_ts": int(candles[210].ts.timestamp())}
    prepared = _prepared_canonical_search(monkeypatch)
    progress = search_progress(prepared)
    monkeypatch.setattr(kernels, "compute_signals", _canonical_test_signals)
    seen = []
    evaluator = _canonical_test_evaluator(prepared, seen, fail_at, cancelled)
    kwargs = {"dataset": SimpleNamespace(candles=candles, bar_count=len(candles)),
              "instrument": fake_inst, "partition": partition,
              "settings": {"n_folds": 2, "capital": 50000.0}, "progress": progress}
    recipe = {"canonical_optimization": prepared.binding, "gates": {"n_folds": 2},
              "research_partition": {"datasets": {fake_inst.key: {key: value for key, value in partition.items() if not key.startswith("_")}}}}
    return prepared, evaluator, kwargs, seen, recipe


def _canonical_terminal_evidence(recipe, progress):
    selected = progress["selected"]
    if selected is None:
        return {"provenance": recipe, "run": {"status": "failed"},
                "results": {"canonical_optimization": progress, "failure": {"message": "candidate failed"}}}
    return {"provenance": recipe, "run": {"status": "completed"},
            "results": {"canonical_optimization": progress, "instruments": [{
                "qualification": {"qualified": True}, "research_partition": progress["partition"],
                "validation": {"params": {**selected["coordinates"],
                    "candidate_graph_address": selected["graph_address"]}}}]}}


def test_canonical_development_search_records_every_point_and_never_replays_holdout(monkeypatch, fake_inst, candles_factory):
    from research.pipeline.v2_parameter_search import optimize_canonical, verify_canonical_search_evidence
    prepared, evaluator, kwargs, seen, recipe = _canonical_search_case(monkeypatch, fake_inst, candles_factory)
    windows = []
    replay = kernels.run_trades
    def observe(frame, *args, **options):
        windows.append(frame["date"].max())
        return replay(frame, *args, **options)
    monkeypatch.setattr(kernels, "run_trades", observe)
    result, runtime = optimize_canonical(prepared, evaluator, **kwargs)
    assert len(seen) == 3
    assert result.n_trials == len(result.trials) == 6
    assert len(result.final_trials) == 3
    assert len(result.perf_matrix) == 8
    assert max(windows) < kwargs["partition"]["_validation_start"]
    assert result.selected_params["candidate_graph_address"] == runtime.candidate_graph_address
    assert kwargs["progress"]["selected"]["graph_address"] == runtime.candidate_graph_address
    verify_canonical_search_evidence(recipe, _canonical_terminal_evidence(recipe, kwargs["progress"]))


def test_canonical_selection_is_unchanged_by_later_holdout_prices(monkeypatch, fake_inst, candles_factory):
    from research.pipeline.v2_parameter_search import optimize_canonical, search_progress
    prepared, evaluator, kwargs, _, _ = _canonical_search_case(monkeypatch, fake_inst, candles_factory)
    original, _ = optimize_canonical(prepared, evaluator, **kwargs)
    candles = kwargs["dataset"].candles
    kwargs["dataset"].candles = candles[:210] + [dataclasses.replace(candle,
        open=candle.open * 100, high=candle.high * 100, low=candle.low * 100, close=candle.close * 100)
        for candle in candles[210:]]
    kwargs["progress"] = search_progress(prepared)
    changed, _ = optimize_canonical(prepared, evaluator, **kwargs)
    assert changed.selected_params == original.selected_params
    assert changed.final_trials == original.final_trials
    assert changed.perf_matrix == original.perf_matrix


@pytest.mark.parametrize("cancelled", [False, True])
def test_canonical_candidate_failure_retains_complete_population(monkeypatch, fake_inst, candles_factory, cancelled):
    from research.pipeline.v2_parameter_search import optimize_canonical, verify_canonical_search_evidence
    from research.robustness.parameter_integration import CandidateEvaluationCancelled
    prepared, evaluator, kwargs, seen, recipe = _canonical_search_case(monkeypatch, fake_inst, candles_factory,
                                                                    fail_at=2, cancelled=cancelled)
    with pytest.raises((ValueError, CandidateEvaluationCancelled)):
        optimize_canonical(prepared, evaluator, **kwargs)
    progress = kwargs["progress"]
    assert len(seen) == 2 and len(progress["candidates"]) == 3
    assert [row["state"] for row in progress["candidates"]] == ["evaluated", "cancelled" if cancelled else "failed", "pending"]
    assert progress["selected"] is None
    assert progress["reason_code"] == ("CANDIDATE_CANCELLED" if cancelled else "CANONICAL_SEARCH_FAILED")
    verify_canonical_search_evidence(recipe, _canonical_terminal_evidence(recipe, progress))


@pytest.mark.parametrize("failure", ["budget", "history", "no_trades"])
def test_canonical_search_refusals_do_not_invent_a_winner(monkeypatch, fake_inst, candles_factory, failure):
    from research.pipeline.v2_parameter_search import optimize_canonical, CanonicalSearchRefusal
    prepared, evaluator, kwargs, _, _ = _canonical_search_case(monkeypatch, fake_inst, candles_factory)
    if failure == "budget": kwargs["dataset"].bar_count = 1000000
    elif failure == "history": kwargs["partition"]["development_bars"] = 1
    else: monkeypatch.setattr(kernels, "run_trades", lambda *args, **options: [])
    with pytest.raises(CanonicalSearchRefusal):
        optimize_canonical(prepared, evaluator, **kwargs)
    assert kwargs["progress"]["state"] == "refused"
    assert kwargs["progress"]["selected"] is None


@pytest.mark.parametrize("fault", ["population", "document", "objective", "partition", "count", "matrix", "pending", "winner"])
def test_rehashed_canonical_search_evidence_cannot_change_selection_truth(monkeypatch, fake_inst, candles_factory, fault):
    import copy
    from research.pipeline.v2_parameter_search import optimize_canonical, verify_canonical_search_evidence, CanonicalSearchRefusal
    prepared, evaluator, kwargs, _, recipe = _canonical_search_case(monkeypatch, fake_inst, candles_factory)
    optimize_canonical(prepared, evaluator, **kwargs)
    progress = copy.deepcopy(kwargs["progress"])
    if fault == "population": progress["candidates"].pop()
    elif fault == "document": progress["selected"]["canonical_document"]["metadata"]["name"] = "Different graph"
    elif fault == "objective": progress["final_development_trials"][0]["objective"] = 123.0
    elif fault == "partition": progress["partition"]["development_bars"] = 211
    elif fault == "count": progress["n_trials"] = 1
    elif fault == "matrix": progress["performance_matrix"][0].pop()
    elif fault == "pending": progress["candidates"][0]["state"] = "pending"
    else: progress["final_development_trials"][0]["selected"] = not progress["final_development_trials"][0]["selected"]
    with pytest.raises(CanonicalSearchRefusal):
        verify_canonical_search_evidence(recipe, _canonical_terminal_evidence(recipe, progress))


@pytest.mark.parametrize("fault", ["qualification", "holdout_candidate", "holdout_partition", "missing_failure", "nonterminal"])
def test_canonical_terminal_evidence_cannot_contradict_search(monkeypatch, fake_inst, candles_factory, fault):
    import copy
    from research.pipeline.v2_parameter_search import optimize_canonical, verify_canonical_search_evidence, CanonicalSearchRefusal
    prepared, evaluator, kwargs, _, recipe = _canonical_search_case(monkeypatch, fake_inst, candles_factory)
    optimize_canonical(prepared, evaluator, **kwargs)
    evidence = copy.deepcopy(_canonical_terminal_evidence(recipe, kwargs["progress"]))
    result = evidence["results"]["instruments"][0]
    if fault == "qualification": result["qualification"]["qualified"] = False
    elif fault == "holdout_candidate": result["validation"]["params"]["candidate_graph_address"] = "sha256:other"
    elif fault == "holdout_partition": result["research_partition"] = {}
    elif fault == "missing_failure": evidence["run"]["status"] = "failed"
    else: evidence["run"]["status"] = "running"
    with pytest.raises(CanonicalSearchRefusal):
        verify_canonical_search_evidence(recipe, evidence)


def test_ineligible_canonical_trial_cannot_invent_sharpe_dispersion():
    from research.pipeline.v2_parameter_search import _verify_trial_objective, CanonicalSearchRefusal
    row = {"trades": 4, "objective": None, "is_sharpe": None}
    _verify_trial_objective(row)
    row["is_sharpe"] = 100.0
    with pytest.raises(CanonicalSearchRefusal):
        _verify_trial_objective(row)


def test_canonical_search_without_intent_does_not_resolve_a_graph():
    from research.pipeline.v2_parameter_search import prepare_canonical_search, disabled_search
    assert prepare_canonical_search(None, document=None, registry=None) is None
    assert prepare_canonical_search(disabled_search(), document=None, registry=None) is None


def test_unqualified_canonical_baseline_retains_only_pending_population(monkeypatch):
    from research.pipeline.v2_parameter_search import search_progress, verify_canonical_search_evidence, CanonicalSearchRefusal
    prepared = _prepared_canonical_search(monkeypatch)
    progress = search_progress(prepared)
    progress.update(state="not_qualified", reason_code="BASELINE_NOT_QUALIFIED")
    recipe = {"canonical_optimization": prepared.binding, "gates": {"n_folds": 2}}
    evidence = {"provenance": recipe, "run": {"status": "completed"}, "results": {
        "canonical_optimization": progress, "instruments": [{"qualification": {"qualified": False}}]}}
    verify_canonical_search_evidence(recipe, evidence)
    progress["n_trials"] = 1
    with pytest.raises(CanonicalSearchRefusal):
        verify_canonical_search_evidence(recipe, evidence)
