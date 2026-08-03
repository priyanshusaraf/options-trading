"""Capstone: an end-to-end autonomous experiment. run_experiment() must build an
immutable ExperimentSpec + a completed ExperimentRun, qualify/validate/score across
instruments, deposit Findings (positive AND negative), queue a PromotionCandidate
when something validates, update the hypothesis, and return a report — all in
research.db, touching no capital.
"""
import json

import pytest

from research.data.store import StaticDataSource, materialize
from research.domain.models import (
    ExperimentRun,
    ExperimentSpec,
    Finding,
    Hypothesis,
    PromotionCandidate,
)
from research.evaluation import kernels
from research.orchestrator.report import render_markdown
from research.orchestrator.run import run_experiment, spec_hash
from research.evidence import EvidenceRejected, decode_terminal_evidence


def _datasets(inst_factory, candles_factory, keys):
    src = StaticDataSource({(k, "day"): candles_factory(400) for k in keys})
    insts = [inst_factory(k) for k in keys]
    return src, [(i, materialize(src, i, "day")) for i in insts]


def _run(session, inst_factory, candles_factory, **kw):
    strat = kernels.get_strategy("trend_impulse_v3")
    _, datasets = _datasets(inst_factory, candles_factory, ["AAA", "BBB"])
    return run_experiment(session, program_name="Trend Following",
                          hypothesis_statement="EMA trend persists in large-caps",
                          strategy=strat, datasets=datasets,
                          params=dict(strat.default_params), git_commit="deadbeef",
                          seed=1, min_trades=1, n_folds=4, min_positive_fold_frac=0.0, **kw)


def test_run_experiment_persists_completed_run_and_spec(research_session, inst_factory, candles_factory):
    report = _run(research_session, inst_factory, candles_factory)
    runs = research_session.query(ExperimentRun).all()
    assert len(runs) == 1
    assert runs[0].status == "completed"
    assert runs[0].decision in ("propose", "archive")
    spec = research_session.get(ExperimentSpec, runs[0].spec_id)
    assert spec.git_commit == "deadbeef"
    assert report["spec_id"] == spec.id


def test_completed_run_persists_verified_terminal_evidence(
        research_session, inst_factory, candles_factory):
    report = _run(research_session, inst_factory, candles_factory)
    run = research_session.get(ExperimentRun, report["run_id"])
    evidence = decode_terminal_evidence(run.checkpoint_json)

    assert evidence["spec_id"] == report["spec_id"]
    assert evidence["run"] == {
        "id": report["run_id"],
        "status": "completed",
        "decision": report["decision"],
    }
    assert evidence["provenance"]["datasets"]
    assert evidence["results"]["qualified"] == report["qualified"]
    assert evidence["results"]["rejected"] == report["rejected"]
    assert evidence["results"]["validated"] == report["validated"]
    assert evidence["results"]["regimes"] == report["regimes"]
    assert evidence["results"]["explanation"] == report["explanation"]
    assert {item["instrument"] for item in evidence["results"]["instruments"]} == {
        "AAA", "BBB"
    }
    assert all("qualification" in item for item in evidence["results"]["instruments"])


def test_controlled_pipeline_failure_persists_safe_terminal_evidence(
        research_session, inst_factory, candles_factory, monkeypatch):
    def fail_qualification(*_args, **_kwargs):
        raise RuntimeError("provider secret must not be persisted")

    monkeypatch.setattr(
        "research.orchestrator.run.qualify_instrument", fail_qualification
    )

    with pytest.raises(RuntimeError, match="provider secret"):
        _run(research_session, inst_factory, candles_factory)

    research_session.expire_all()
    run = research_session.query(ExperimentRun).one()
    evidence = decode_terminal_evidence(run.checkpoint_json)
    assert run.status == "failed"
    assert run.decision == "needs_review"
    assert run.completed_at is not None
    assert evidence["run"] == {
        "id": run.id,
        "status": "failed",
        "decision": "needs_review",
    }
    assert evidence["provenance"]["datasets"]
    assert evidence["results"]["failure"] == {
        "stage": "qualification",
        "code": "RESEARCH_QUALIFICATION_FAILED",
        "message": "research qualification failed",
    }
    assert "secret" not in run.error
    assert "secret" not in run.checkpoint_json


def test_terminal_evidence_write_failure_cannot_leave_completed_run(
        research_session, inst_factory, candles_factory, monkeypatch):
    from research.orchestrator import run as run_module

    real_encode = run_module.encode_terminal_evidence
    calls = 0

    def fail_success_evidence_once(payload):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise EvidenceRejected("injected terminal write failure")
        return real_encode(payload)

    monkeypatch.setattr(
        run_module, "encode_terminal_evidence", fail_success_evidence_once
    )

    with pytest.raises(EvidenceRejected, match="injected terminal write failure"):
        _run(research_session, inst_factory, candles_factory)

    research_session.expire_all()
    run = research_session.query(ExperimentRun).one()
    evidence = decode_terminal_evidence(run.checkpoint_json)
    assert run.status == "failed"
    assert run.decision == "needs_review"
    assert evidence["results"]["failure"]["stage"] == "evidence_persistence"
    assert evidence["results"]["failure"]["code"] == (
        "RESEARCH_EVIDENCE_PERSISTENCE_FAILED"
    )


def test_run_experiment_deposits_a_finding_per_instrument(research_session, inst_factory, candles_factory):
    _run(research_session, inst_factory, candles_factory)
    findings = research_session.query(Finding).all()
    assert len(findings) == 2
    assert all(f.polarity in ("positive", "negative") for f in findings)


def test_run_experiment_updates_hypothesis(research_session, inst_factory, candles_factory):
    _run(research_session, inst_factory, candles_factory)
    hyp = research_session.query(Hypothesis).one()
    assert hyp.last_tested_at is not None
    assert 0.05 <= hyp.retest_priority <= 1.0


def test_spec_is_content_addressed_and_stable(research_session, inst_factory, candles_factory):
    # same inputs -> same spec id; a second run reuses the immutable spec, not a new one
    _run(research_session, inst_factory, candles_factory)
    _run(research_session, inst_factory, candles_factory)
    assert research_session.query(ExperimentSpec).count() == 1
    assert research_session.query(ExperimentRun).count() == 2


def test_spec_records_every_result_affecting_data_cost_and_gate_input(
        research_session, inst_factory, candles_factory):
    report = _run(
        research_session,
        inst_factory,
        candles_factory,
        capital=75_000.0,
        slippage_bps=7.5,
        slippage_multiplier=2.5,
        pbo_threshold=0.22,
        sibling_trials=3,
    )

    spec = research_session.get(ExperimentSpec, report["spec_id"])
    recipe = json.loads(spec.recipe_json)
    assert recipe["program"] == "Trend Following"
    assert recipe["hypothesis"] == "EMA trend persists in large-caps"
    assert recipe["git_commit"] == "deadbeef"
    assert recipe["datasets"] == {
        "AAA": {
            "bar_count": 400,
            "content_hash": recipe["datasets"]["AAA"]["content_hash"],
            "end_ts": recipe["datasets"]["AAA"]["end_ts"],
            "instrument_key": "AAA",
            "interval": "day",
            "requested_days": 2000,
            "start_ts": recipe["datasets"]["AAA"]["start_ts"],
        },
        "BBB": {
            "bar_count": 400,
            "content_hash": recipe["datasets"]["BBB"]["content_hash"],
            "end_ts": recipe["datasets"]["BBB"]["end_ts"],
            "instrument_key": "BBB",
            "interval": "day",
            "requested_days": 2000,
            "start_ts": recipe["datasets"]["BBB"]["start_ts"],
        },
    }
    assert recipe["cost_assumptions"] == {
        "capital": 75_000.0,
        "charge_model": "zerodha_charges_v1",
        "sizing_model": "one_lot_or_cash_budget_v1",
        "slippage_bps": 7.5,
        "slippage_multiplier": 2.5,
    }
    assert recipe["gates"] == {
        "min_oos_trades": 1,
        "min_positive_fold_fraction": 0.0,
        "n_folds": 4,
        "optimize_search": False,
        "pbo_threshold": 0.22,
        "sibling_trials": 3,
    }


def test_cost_or_gate_change_creates_a_distinct_immutable_spec(
        research_session, inst_factory, candles_factory):
    first = _run(research_session, inst_factory, candles_factory)
    second = _run(
        research_session,
        inst_factory,
        candles_factory,
        slippage_bps=6.0,
    )
    third = _run(
        research_session,
        inst_factory,
        candles_factory,
        pbo_threshold=0.25,
    )

    assert len({first["spec_id"], second["spec_id"], third["spec_id"]}) == 3
    assert research_session.query(ExperimentSpec).count() == 3


def test_hypothesis_or_build_change_cannot_reuse_a_spec_with_stale_provenance(
        research_session, inst_factory, candles_factory):
    strat = kernels.get_strategy("trend_impulse_v3")
    _, datasets = _datasets(inst_factory, candles_factory, ["AAA"])
    common = {
        "session": research_session,
        "program_name": "Programme A",
        "strategy": strat,
        "datasets": datasets,
        "params": dict(strat.default_params),
        "min_trades": 1,
    }
    first = run_experiment(
        **common, hypothesis_statement="Hypothesis A", git_commit="aaaaaaa"
    )
    second = run_experiment(
        **common, hypothesis_statement="Hypothesis B", git_commit="aaaaaaa"
    )
    third = run_experiment(
        **common, hypothesis_statement="Hypothesis A", git_commit="bbbbbbb"
    )

    assert len({first["spec_id"], second["spec_id"], third["spec_id"]}) == 3


def test_qualification_uses_the_recorded_capital_assumption(
        research_session, inst_factory, candles_factory, monkeypatch):
    from research.orchestrator import run as orchestrator

    seen = []
    original = orchestrator.qualify_instrument

    def spy(*args, **kwargs):
        seen.append(kwargs.get("capital"))
        return original(*args, **kwargs)

    monkeypatch.setattr(orchestrator, "qualify_instrument", spy)
    _run(
        research_session,
        inst_factory,
        candles_factory,
        capital=75_000.0,
    )
    assert seen == [75_000.0, 75_000.0]


def test_report_renders_markdown(research_session, inst_factory, candles_factory):
    report = _run(research_session, inst_factory, candles_factory)
    md = render_markdown(report)
    assert "# Research report" in md
    assert "Trend Following" in md
    assert report["hypothesis"] in md


def test_run_nightly_writes_report_files(research_session, inst_factory, candles_factory, tmp_path):
    import os

    from research.orchestrator.run import run_nightly
    keys = ["AAA", "BBB"]
    src = StaticDataSource({(k, "day"): candles_factory(400) for k in keys})
    plan = [{"program": "Trend Following", "hypothesis": "EMA trend persists",
             "strategy_key": "trend_impulse_v3",
             "instruments": [inst_factory(k) for k in keys], "interval": "day",
             "min_trades": 1, "n_folds": 4, "min_positive_fold_frac": 0.0}]
    reports = run_nightly(research_session, src, plan, git_commit="abc",
                          report_dir=str(tmp_path))
    assert len(reports) == 1
    assert os.path.exists(reports[0]["report_path"])
    assert research_session.query(ExperimentRun).count() == 1


def test_run_nightly_empty_plan_is_noop(research_session):
    from research.orchestrator.run import run_nightly
    assert run_nightly(research_session, source=None, plan=[]) == []


def _validating_run(session, inst_factory, uptrend_factory, keys=("UPA", "UPB")):
    strat = kernels.get_strategy("trend_impulse_v3")
    src = StaticDataSource({(k, "day"): uptrend_factory(400) for k in keys})
    datasets = [(inst_factory(k), materialize(src, inst_factory(k), "day")) for k in keys]
    return run_experiment(session, program_name="Trend Following",
                          hypothesis_statement="EMA trend persists", strategy=strat,
                          datasets=datasets, params=dict(strat.default_params),
                          git_commit="deadbeef", seed=1, min_trades=1, n_folds=3,
                          min_positive_fold_frac=0.0)


def test_promotion_candidate_carries_validated_universe_with_scores(
        research_session, inst_factory, uptrend_factory):
    """The queued candidate must describe the VALIDATED universe (what earned
    promotion) with a per-instrument score, not just the qualified keys + one best
    row — that is exactly what the human needs to review and what deploy assigns."""
    report = _validating_run(research_session, inst_factory, uptrend_factory)
    cand = research_session.query(PromotionCandidate).one()
    payload = json.loads(cand.scorecard_json)
    validated = payload["validated"]
    assert validated and all("instrument" in v and "dsr" in v for v in validated)
    # the stored validated universe matches exactly the run's validated instruments
    assert {v["instrument"] for v in validated} == {v["instrument"] for v in report["validated"]}
    # the headline best is still present and is one of the validated instruments
    assert payload["best"]["instrument"] in {v["instrument"] for v in validated}


def test_run_experiment_with_optimization_persists_immutable_trials(
        research_session, inst_factory, uptrend_factory):
    import pytest
    from sqlalchemy.exc import DatabaseError

    from research.domain.models import OptimizationTrial
    from research.orchestrator.run import run_experiment
    strat = kernels.get_strategy("trend_impulse_v3")
    keys = ["UPA", "UPB"]
    src = StaticDataSource({(k, "day"): uptrend_factory(400) for k in keys})
    datasets = [(inst_factory(k), materialize(src, inst_factory(k), "day")) for k in keys]
    run_experiment(research_session, program_name="Trend Following",
                   hypothesis_statement="EMA trend persists in large-caps", strategy=strat,
                   datasets=datasets, params=dict(strat.default_params), git_commit="deadbeef",
                   seed=1, min_trades=1, n_folds=3, min_positive_fold_frac=0.0,
                   optimize_search=True)
    trials = research_session.query(OptimizationTrial).all()
    assert len(trials) > 0
    assert any(t.selected for t in trials)
    # the trial ledger is immutable — tampering must abort
    trials[0].is_objective = 999.0
    with pytest.raises(DatabaseError):
        research_session.commit()
    research_session.rollback()
