import contextlib
import json

import pytest
from fastapi.testclient import TestClient

from app.core import research_read
from app.core.config import get_settings
from app.db.session import init_db
from app.editor.graph_artifacts import (
    CATALOGUE_PROJECT_ID,
    ProjectNotFound,
    list_project_version_events,
)
from app.engine.runner import EngineRunner
from app.ir.strategies.expanding_z import GRAPH
from research.config import research_db_path
from research.domain.base import (
    ResearchBase,
    init_research_db,
    make_engine,
    make_sessionmaker,
)
from research.domain.models import PromotionCandidate


IDENTIFIER = GRAPH["identifier"]
VERSION = GRAPH["version"]
EXPERIMENT_URL = (
    f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/{IDENTIFIER}/"
    f"versions/{VERSION}/experiments"
)


def _request():
    return {
        "program_name": "Daily review",
        "hypothesis_statement": "Review source remains linked",
        "datasets": [{"instrument_key": "NIFTY", "interval": "day", "days": 30}],
        "seed": 7,
        "gates": {
            "min_oos_trades": 10_000, "n_folds": 3,
            "min_positive_fold_fraction": 0.6, "optimize_search": False,
            "pbo_threshold": 0.3, "sibling_trials": 1,
        },
        "cost_assumptions": {
            "capital": 50_000.0, "slippage_bps": 5.0,
            "slippage_multiplier": 2.0, "charge_model": "zerodha_charges_v1",
            "sizing_model": "one_lot_or_cash_budget_v1",
        },
    }


@pytest.fixture(autouse=True)
def _databases(monkeypatch):
    init_db(reset=True)
    engine = make_engine(research_db_path())
    ResearchBase.metadata.drop_all(engine)
    init_research_db(engine)
    engine.dispose()
    monkeypatch.setattr(get_settings(), "research_enabled", True)


@pytest.fixture
def client():
    from app.main import app

    app.state.runner = EngineRunner(owner_id="owner", broker_account_id="account.default")
    return TestClient(app)


def _seed_candidates(run_id: int) -> tuple[int, int]:
    engine = make_engine(research_db_path())
    Session = make_sessionmaker(engine)
    with Session.begin() as session:
        pending = PromotionCandidate(
            run_id=run_id, parameterization_hash="p" * 64,
            qualifying_universe_json="[]", scorecard_json="{}", status="pending",
        )
        decided = PromotionCandidate(
            run_id=run_id, parameterization_hash="d" * 64,
            qualifying_universe_json="[]", scorecard_json="{}", status="pending",
        )
        session.add_all([pending, decided])
        session.flush()
        ids = (pending.id, decided.id)
    engine.dispose()
    return ids


def test_project_graph_version_source_verifies_owned_immutable_rows():
    events = list_project_version_events(CATALOGUE_PROJECT_ID)

    assert [(item.identifier, item.version) for item in events] == [(IDENTIFIER, VERSION)]
    assert events[0].content_address.startswith("sha256:")
    assert events[0].created_at is not None
    with pytest.raises(ProjectNotFound):
        list_project_version_events("project.other")


def test_project_review_source_derives_events_and_current_queues_once(client, monkeypatch):
    run_id = client.post(EXPERIMENT_URL, json=_request()).json()["run_id"]
    finding = client.post(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/experiments/{run_id}/findings",
        json={"statement": "Bounded review finding", "polarity": "negative"},
    )
    assert finding.status_code == 201
    pending_id, decided_id = _seed_candidates(run_id)
    decision = client.post(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/candidates/{decided_id}/decisions",
        json={
            "expected_status": "pending", "decision": "rejected",
            "reason": "Daily review rejected this candidate",
        },
    )
    assert decision.status_code == 200

    original_session = research_read._research_session
    calls = 0

    @contextlib.contextmanager
    def counted_session():
        nonlocal calls
        calls += 1
        with original_session() as session:
            yield session

    monkeypatch.setattr(research_read, "_research_session", counted_session)
    source = research_read.project_review_source(CATALOGUE_PROJECT_ID)

    types = [event["type"] for event in source["events"]]
    assert types.count("experiment_run") == 1
    assert types.count("finding_created") >= 1
    assert types.count("candidate_created") == 2
    assert types.count("candidate_decided") == 1
    assert [item["candidate_id"] for item in source["queues"]["pending_candidates"]] == [pending_id]
    assert finding.json()["finding_id"] in {
        item["finding_id"] for item in source["queues"]["active_findings"]
    }
    assert source["queues"]["review_needed_runs"] == []
    assert source["source_errors"] == []
    assert calls == 1
    assert research_read.project_review_source("project.other")["events"] == []


def test_corrupt_candidate_is_contained_without_hiding_other_events(client):
    run_id = client.post(EXPERIMENT_URL, json=_request()).json()["run_id"]
    pending_id, other_pending_id = _seed_candidates(run_id)
    engine = make_engine(research_db_path())
    Session = make_sessionmaker(engine)
    with Session.begin() as session:
        session.get(PromotionCandidate, pending_id).scorecard_json = json.dumps({
            "decision": {"tampered": True}
        })
    engine.dispose()

    source = research_read.project_review_source(CATALOGUE_PROJECT_ID)

    assert any(event["type"] == "experiment_run" for event in source["events"])
    assert [item["candidate_id"] for item in source["queues"]["pending_candidates"]] == [
        other_pending_id
    ]
    assert source["source_errors"] == [{
        "source": "candidate", "source_id": str(pending_id),
        "code": "CANDIDATE_DECISION_CORRUPT",
    }]


def test_an_unknown_run_decision_never_reaches_a_review_summary():
    """Review summaries are frozen verbatim into immutable content-addressed
    snapshots, so only the orchestrator's own decision vocabulary may reach them."""
    from app.core.research_read import RUN_DECISIONS, _run_outcome

    class _Unvalidated:
        decision = "<injected>"
        status = "completed"

    class _Known:
        decision = "propose"
        status = "completed"

    class _Absent:
        decision = None
        status = "running"

    assert _run_outcome(_Unvalidated()) == "completed"
    assert _run_outcome(_Known()) == "propose"
    assert _run_outcome(_Absent()) == "running"
    assert RUN_DECISIONS == {"propose", "archive", "needs_review"}
