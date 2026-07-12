"""Capstone: an end-to-end autonomous experiment. run_experiment() must build an
immutable ExperimentSpec + a completed ExperimentRun, qualify/validate/score across
instruments, deposit Findings (positive AND negative), queue a PromotionCandidate
when something validates, update the hypothesis, and return a report — all in
research.db, touching no capital.
"""
import json

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
