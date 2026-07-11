"""Core domain spine: Program -> Hypothesis -> ExperimentSpec (immutable) ->
ExperimentRun (mutable), plus Finding (revisable, negative-evidence-first-class)
and PromotionCandidate. The immutability tests pin the architecture's central
promise: an ExperimentSpec, once written, can never be altered or deleted.
"""
import pytest
from sqlalchemy.exc import DatabaseError

from research.domain.models import (
    ExperimentRun,
    ExperimentSpec,
    Finding,
    Hypothesis,
    PromotionCandidate,
    ResearchProgram,
)


def _seed_spec(s):
    prog = ResearchProgram(name="Trend Following", thesis="trend persists in large-caps")
    s.add(prog)
    s.flush()
    hyp = Hypothesis(program_id=prog.id, statement="EMA trend in large-cap intraday")
    s.add(hyp)
    s.flush()
    spec = ExperimentSpec(
        id="hash-abc", hypothesis_id=hyp.id, recipe_json="{}", git_commit="221f0b0",
        qualifier_version="q1", optimizer_version="o1", validator_version="v1",
        scoring_version="s1", rng_seed=7)
    s.add(spec)
    s.flush()
    return prog, hyp, spec


def test_program_hypothesis_spec_run_graph(research_session):
    s = research_session
    _, hyp, spec = _seed_spec(s)
    run = ExperimentRun(spec_id=spec.id)
    s.add(run)
    s.commit()
    assert run.status == "pending"
    assert s.get(ExperimentSpec, "hash-abc").hypothesis_id == hyp.id


def test_experiment_spec_rejects_update(research_session):
    s = research_session
    _, _, spec = _seed_spec(s)
    s.commit()
    spec.git_commit = "tampered"
    with pytest.raises(DatabaseError):
        s.commit()
    s.rollback()


def test_experiment_spec_rejects_delete(research_session):
    s = research_session
    _, _, spec = _seed_spec(s)
    s.commit()
    s.delete(spec)
    with pytest.raises(DatabaseError):
        s.commit()
    s.rollback()


def test_experiment_run_is_mutable(research_session):
    s = research_session
    _, _, spec = _seed_spec(s)
    run = ExperimentRun(spec_id=spec.id)
    s.add(run)
    s.commit()
    run.status = "running"
    s.commit()
    run.status = "completed"
    run.decision = "propose"
    s.commit()
    assert s.get(ExperimentRun, run.id).decision == "propose"


def test_hypothesis_retest_priority_defaults_and_updates(research_session):
    s = research_session
    _, hyp, _ = _seed_spec(s)
    s.commit()
    assert hyp.retest_priority == pytest.approx(1.0)
    hyp.retest_priority = 0.2  # decays UP over time toward base; here we lower after a decisive test
    s.commit()
    assert s.get(Hypothesis, hyp.id).retest_priority == pytest.approx(0.2)


def test_finding_negative_polarity_and_supersession(research_session):
    s = research_session
    _, hyp, spec = _seed_spec(s)
    run = ExperimentRun(spec_id=spec.id)
    s.add(run)
    s.commit()
    neg = Finding(hypothesis_id=hyp.id, statement="no edge in pharma intraday",
                  polarity="negative", confidence=0.7, evidence_run_id=run.id)
    s.add(neg)
    s.commit()
    later = Finding(hypothesis_id=hyp.id, statement="edge re-emerged post-regime-shift",
                    polarity="positive", confidence=0.6, evidence_run_id=run.id)
    s.add(later)
    s.commit()
    neg.superseded_by = later.id
    s.commit()
    assert s.get(Finding, neg.id).superseded_by == later.id


def test_promotion_candidate_defaults_pending(research_session):
    s = research_session
    _, _, spec = _seed_spec(s)
    run = ExperimentRun(spec_id=spec.id)
    s.add(run)
    s.commit()
    pc = PromotionCandidate(run_id=run.id, parameterization_hash="p-123")
    s.add(pc)
    s.commit()
    assert pc.status == "pending"
    assert pc.approved_git_sha is None
