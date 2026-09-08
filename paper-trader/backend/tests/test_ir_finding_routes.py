import json
import sys

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import SessionLocal, init_db
from app.editor.graph_artifacts import CATALOGUE_PROJECT_ID
from app.engine.runner import EngineRunner
from app.ir.hashing import content_address
from app.ir.strategies.expanding_z import GRAPH
from research.config import research_db_path
from research.domain.base import (
    ResearchBase,
    init_research_db,
    make_engine,
    make_sessionmaker,
)
from research.domain.models import ExperimentRun, Finding
from tests.admitted_entry import persist_admitted_graph


EXPERIMENT_URL = (
    f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/{GRAPH['identifier']}"
    f"/versions/{GRAPH['version']}/experiments"
)
FINDINGS_URL = f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/findings"


def _request():
    return {
        "program_name": "Finding tests",
        "hypothesis_statement": "The graph produces interpretable evidence",
        "datasets": [{"instrument_key": "NIFTY", "interval": "day", "days": 30}],
        "seed": 7,
        "gates": {
            "min_oos_trades": 10_000,
            "n_folds": 3,
            "min_positive_fold_fraction": 0.6,
            "optimize_search": False,
            "pbo_threshold": 0.3,
            "sibling_trials": 1,
        },
        "cost_assumptions": {
            "capital": 50_000.0,
            "slippage_bps": 5.0,
            "slippage_multiplier": 2.0,
            "charge_model": "zerodha_charges_v1",
            "sizing_model": "one_lot_or_cash_budget_v1",
        },
    }


@pytest.fixture(autouse=True)
def _databases(monkeypatch):
    init_db(reset=True)
    graph = GRAPH.copy()
    graph["identifier"] = "test.route.expanding_z_impulse"
    with SessionLocal.begin() as session:
        persist_admitted_graph(
            session, graph=graph, owner_id="owner", project_id=CATALOGUE_PROJECT_ID,
            display_name="Repository catalogue",
        )
    module = sys.modules[__name__]
    monkeypatch.setattr(
        module, "EXPERIMENT_URL",
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/"
        f"{graph['identifier']}/versions/{graph['version']}/experiments",
    )
    engine = make_engine(research_db_path())
    ResearchBase.metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE IF EXISTS research_schema_version")
    init_research_db(engine)
    engine.dispose()
    monkeypatch.setattr(get_settings(), "research_enabled", True)


@pytest.fixture
def client():
    from app.main import app

    app.state.runner = EngineRunner(owner_id="owner", broker_account_id="account.default")
    return TestClient(app)


def _start(client):
    response = client.post(EXPERIMENT_URL, json=_request())
    assert response.status_code == 201
    return response.json()


def _set_run(run_id: int, *, status: str, checkpoint: str | None) -> None:
    engine = make_engine(research_db_path())
    Session = make_sessionmaker(engine)
    with Session.begin() as session:
        run = session.get(ExperimentRun, run_id)
        run.status = status
        run.checkpoint_json = checkpoint
    engine.dispose()


def test_project_finding_list_and_detail_return_verified_persisted_lineage_only(
        client, monkeypatch):
    started = _start(client)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("finding reads must not recompute evidence")

    monkeypatch.setattr(client.app.state.runner.provider, "get_candles", forbidden)
    monkeypatch.setattr(
        "research.orchestrator.graph_experiment.build_graph_provenance", forbidden
    )
    monkeypatch.setattr("research.orchestrator.run.run_experiment", forbidden)

    response = client.get(FINDINGS_URL)
    assert response.status_code == 200
    findings = response.json()["findings"]
    assert len(findings) == 1
    finding = findings[0]
    assert finding["polarity"] == "negative"
    assert "NIFTY" in finding["statement"]
    assert finding["status"] == "active"
    assert finding["superseded_by"] is None
    assert finding["binding"] == {
        "run_id": started["run_id"],
        "spec_id": started["spec_id"],
        "evidence_content_address": finding["binding"]["evidence_content_address"],
        "graph": started["binding"]["graph"],
    }
    assert finding["binding"]["evidence_content_address"].startswith("sha256:")

    detail = client.get(f"{FINDINGS_URL}/{finding['finding_id']}")
    assert detail.status_code == 200
    assert detail.json() == finding
    mirrored = client.get(
        f"{FINDINGS_URL}/{finding['finding_id']}".replace("/api/", "/api/v1/", 1)
    )
    assert mirrored.status_code == 200
    assert mirrored.json() == finding


def test_create_finding_accepts_interpretation_only_and_derives_binding(client):
    started = _start(client)
    create_url = (
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/experiments/"
        f"{started['run_id']}/findings"
    )
    response = client.post(create_url, json={
        "statement": "  The rejection is driven by insufficient trade breadth.  ",
        "polarity": "negative",
    })

    assert response.status_code == 201
    body = response.json()
    assert body["statement"] == "The rejection is driven by insufficient trade breadth."
    assert body["polarity"] == "negative"
    assert 0.0 <= body["confidence"] <= 0.95
    assert body["binding"]["run_id"] == started["run_id"]
    assert body["binding"]["spec_id"] == started["spec_id"]
    assert body["binding"]["graph"] == started["binding"]["graph"]

    engine = make_engine(research_db_path())
    Session = make_sessionmaker(engine)
    with Session() as session:
        persisted = session.get(Finding, body["finding_id"])
        assert persisted.evidence_run_id == started["run_id"]
        assert persisted.statement == body["statement"]
    engine.dispose()

    raw = client.post(create_url, json={
        "statement": "Client identity claim",
        "polarity": "positive",
        "confidence": 1.0,
        "binding": {"content_address": "client"},
    })
    assert raw.status_code == 422
    assert raw.json()["code"] == "EXPERIMENT_REQUEST_INVALID"


@pytest.mark.parametrize("state", ["running", "failed", "legacy", "corrupt"])
def test_create_finding_rejects_unverified_or_non_completed_runs(client, state):
    started = _start(client)
    engine = make_engine(research_db_path())
    Session = make_sessionmaker(engine)
    with Session() as session:
        original = session.get(ExperimentRun, started["run_id"]).checkpoint_json
    engine.dispose()
    if state == "running":
        _set_run(started["run_id"], status="running", checkpoint=None)
    elif state == "failed":
        _set_run(started["run_id"], status="failed", checkpoint=original)
    elif state == "legacy":
        _set_run(started["run_id"], status="completed", checkpoint=None)
    else:
        _set_run(started["run_id"], status="completed", checkpoint='{"tampered":true}')

    response = client.post(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/experiments/"
        f"{started['run_id']}/findings",
        json={"statement": "Unsupported claim", "polarity": "negative"},
    )
    assert response.status_code == 409
    expected = "FINDING_EVIDENCE_CORRUPT" if state == "corrupt" else (
        "FINDING_EVIDENCE_UNAVAILABLE"
    )
    assert response.json()["code"] == expected


def test_create_and_detail_hide_cross_project_run_and_finding_ids(client):
    started = _start(client)
    finding = client.get(FINDINGS_URL).json()["findings"][0]
    other = client.post(
        "/api/ir/projects", json={"name": "Other", "description": ""}
    ).json()

    create = client.post(
        f"/api/ir/projects/{other['project_id']}/experiments/"
        f"{started['run_id']}/findings",
        json={"statement": "Cross-project", "polarity": "positive"},
    )
    assert create.status_code == 404
    assert create.json()["code"] == "FINDING_RUN_NOT_FOUND"
    detail = client.get(
        f"/api/ir/projects/{other['project_id']}/findings/{finding['finding_id']}"
    )
    assert detail.status_code == 404
    assert detail.json()["code"] == "FINDING_NOT_FOUND"


def test_revision_inserts_successor_without_rewriting_original_and_reloads(client):
    started = _start(client)
    create_url = (
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/experiments/"
        f"{started['run_id']}/findings"
    )
    original = client.post(create_url, json={
        "statement": "Initial interpretation", "polarity": "positive"
    }).json()
    revision_url = f"{FINDINGS_URL}/{original['finding_id']}/revisions"
    response = client.post(revision_url, json={
        "expected_superseded_by": None,
        "statement": "Revised after reviewing the exact rejection evidence",
        "polarity": "negative",
    })

    assert response.status_code == 201
    successor = response.json()["successor"]
    prior = response.json()["superseded"]
    assert prior["finding_id"] == original["finding_id"]
    assert prior["statement"] == "Initial interpretation"
    assert prior["polarity"] == "positive"
    assert prior["confidence"] == original["confidence"]
    assert prior["superseded_by"] == successor["finding_id"]
    assert successor["evidence_run_id"] == original["evidence_run_id"]
    assert successor["binding"] == original["binding"]
    assert successor["status"] == "active"

    reloaded = client.get(FINDINGS_URL).json()["findings"]
    by_id = {item["finding_id"]: item for item in reloaded}
    assert by_id[original["finding_id"]] == prior
    assert by_id[successor["finding_id"]] == successor

    stale = client.post(revision_url, json={
        "expected_superseded_by": None,
        "statement": "Stale rewrite",
        "polarity": "positive",
    })
    assert stale.status_code == 409
    assert stale.json()["code"] == "FINDING_REVISION_CONFLICT"
    assert len(client.get(FINDINGS_URL).json()["findings"]) == len(reloaded)

    raw = client.post(
        f"{FINDINGS_URL}/{successor['finding_id']}/revisions",
        json={
            "expected_superseded_by": None,
            "statement": "Client rebinding attempt",
            "polarity": "negative",
            "evidence_run_id": 999,
            "binding": {"graph": "client"},
        },
    )
    assert raw.status_code == 422
    assert raw.json()["code"] == "EXPERIMENT_REQUEST_INVALID"


def test_finding_read_rejects_internally_consistent_but_contradictory_evidence(client):
    from research.evidence import decode_terminal_evidence, encode_terminal_evidence

    started = _start(client)
    engine = make_engine(research_db_path())
    Session = make_sessionmaker(engine)
    with Session.begin() as session:
        run = session.get(ExperimentRun, started["run_id"])
        evidence = decode_terminal_evidence(run.checkpoint_json)
        evidence["spec_id"] = "different-but-content-addressed-spec"
        run.checkpoint_json = encode_terminal_evidence(evidence)
    engine.dispose()

    response = client.get(FINDINGS_URL)
    assert response.status_code == 409
    assert response.json()["code"] == "FINDING_EVIDENCE_CORRUPT"


def test_failure_after_successor_insert_rolls_back_both_sides(client, monkeypatch):
    started = _start(client)
    original = client.post(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/experiments/"
        f"{started['run_id']}/findings",
        json={"statement": "Stable original", "polarity": "negative"},
    ).json()

    def fail_after_insert(*_args, **_kwargs):
        raise RuntimeError("injected successor failure")

    monkeypatch.setattr(
        "app.core.research_read._after_finding_successor_insert", fail_after_insert
    )
    with pytest.raises(RuntimeError, match="injected successor failure"):
        client.post(
            f"{FINDINGS_URL}/{original['finding_id']}/revisions",
            json={
                "expected_superseded_by": None,
                "statement": "Must roll back",
                "polarity": "positive",
            },
        )

    reloaded = client.get(FINDINGS_URL).json()["findings"]
    persisted = next(
        item for item in reloaded if item["finding_id"] == original["finding_id"]
    )
    assert persisted["superseded_by"] is None
    assert all(item["statement"] != "Must roll back" for item in reloaded)
