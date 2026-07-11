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
