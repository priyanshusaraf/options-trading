"""Promotion approval must freshly verify the exact causal receipt."""
from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace

import pytest

from app.core import research_read
from app.ir.hashing import canonical_json, content_address
from research.domain.admissions import store_admission
from research.domain.base import init_research_db, make_engine, make_sessionmaker
from research.domain.models import (
    ExperimentRun,
    ExperimentSpec,
    Hypothesis,
    PromotionCandidate,
    ResearchProgram,
)


OWNER = "owner"
PROJECT = "project.promotion-mutation"
GRAPH = "strategy.expanding_z_impulse"


def _source_graph(version: int = 1) -> dict:
    from app.ir.strategies.expanding_z import GRAPH as document

    return {**document, "version": version}


def _seed_candidate(path: str) -> tuple[int, str, dict]:
    """Persist one real candidate/run/receipt tuple for the approval boundary."""
    from app.ir.library import REGISTRY
    from app.strategy.admission import IRGraphAdmissionInput, admit_strategy

    graph = _source_graph()
    admission = admit_strategy(
        owner_id=OWNER,
        source_input=IRGraphAdmissionInput(graph=graph, parameters={}, risk_model=None),
        registry=REGISTRY,
    )
    assert admission.artifact is not None
    graph_address = content_address(graph)
    recipe = {"graph_provenance": {"graph": {
        "project_id": PROJECT,
        "identifier": GRAPH,
        "version": 1,
        "content_address": graph_address,
    }}}
    engine = make_engine(path)
    init_research_db(engine)
    Session = make_sessionmaker(engine)
    with Session.begin() as session:
        program = ResearchProgram(owner_id=OWNER, name="promotion", thesis="receipt")
        session.add(program)
        session.flush()
        hypothesis = Hypothesis(owner_id=OWNER, program_id=program.id, statement="edge")
        session.add(hypothesis)
        session.flush()
        spec_id = hashlib.sha256(canonical_json(recipe).encode()).hexdigest()
        session.add(ExperimentSpec(
            owner_id=OWNER, id=spec_id, hypothesis_id=hypothesis.id,
            recipe_json=canonical_json(recipe), git_commit="mutation"))
        session.flush()
        run = ExperimentRun(
            owner_id=OWNER, spec_id=spec_id, status="completed", decision="propose",
            admission_address=admission.artifact.admission_address)
        session.add(run)
        session.flush()
        candidate = PromotionCandidate(
            owner_id=OWNER, run_id=run.id, parameterization_hash="p",
            qualifying_universe_json="[]", scorecard_json="{}", status="pending",
            admission_address=admission.artifact.admission_address)
        session.add(candidate)
        store_admission(session, admission.artifact)
        session.flush()
        return candidate.id, admission.artifact.admission_address, graph


def test_promotion_approval_receipt_bypass_mutant_is_killed(tmp_path, monkeypatch):
    """Removing only fresh receipt verification approves forged published graph bytes."""
    path = str(tmp_path / "research.db")
    monkeypatch.setenv("PT_RESEARCH_DB_PATH", path)
    candidate_id, address, graph = _seed_candidate(path)
    forged_graph = {**graph, "version": 2}

    # All candidate, run, graph provenance, and research receipt fields agree. The
    # published graph falsely claims their address, so fresh verification is the one
    # remaining guard that can reject the substituted bytes.
    monkeypatch.setattr(
        "app.editor.graph_artifacts.load_version",
        lambda *_args, **_kwargs: SimpleNamespace(
            graph=forged_graph, content_address=content_address(graph),
            admission_address=address))
    monkeypatch.setattr("app.strategy.admission.verify_admission",
                        lambda **_kwargs: None)

    with pytest.raises(pytest.fail.Exception):
        with pytest.raises(research_read.CandidateDecisionConflict, match="ADMISSION_REQUIRED"):
            research_read.decide_project_candidate(
                PROJECT, candidate_id, owner_id=OWNER, expected_status="pending",
                decision="approved", reason="owner approval")
