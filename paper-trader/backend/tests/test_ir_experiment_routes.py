import copy
import json

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import init_db
from app.editor.graph_artifacts import CATALOGUE_PROJECT_ID
from app.editor import graph_artifacts as graph_store
from app.engine.runner import EngineRunner
from app.ir.strategies.expanding_z import GRAPH
from research.config import research_db_path
from research.domain.base import (
    ResearchBase,
    init_research_db,
    make_engine,
    make_sessionmaker,
)
from research.domain.models import ExperimentSpec


IDENTIFIER = GRAPH["identifier"]
VERSION = GRAPH["version"]
URL = (
    f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/"
    f"{IDENTIFIER}/versions/{VERSION}/experiments"
)


def _request():
    return {
        "program_name": "Published graphs",
        "hypothesis_statement": "The immutable graph has edge",
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
    engine = make_engine(research_db_path())
    ResearchBase.metadata.drop_all(engine)
    init_research_db(engine)
    engine.dispose()
    monkeypatch.setattr(get_settings(), "research_enabled", True)


@pytest.fixture
def client():
    from app.main import app

    app.state.runner = EngineRunner()
    return TestClient(app)


def test_starts_existing_experiment_from_exact_project_owned_version(client):
    response = client.post(URL, json=_request())

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"spec_id", "run_id", "decision", "binding"}
    assert body["binding"]["graph"] == {
        "project_id": CATALOGUE_PROJECT_ID,
        "identifier": IDENTIFIER,
        "version": VERSION,
        "content_address": body["binding"]["graph"]["content_address"],
    }
    assert body["binding"]["datasets"]["NIFTY"]["content_hash"]
    assert body["binding"]["cost_assumptions"] == _request()["cost_assumptions"]
    assert body["binding"]["gates"] == _request()["gates"]

    mirrored = client.post(URL.replace("/api/", "/api/v1/", 1), json=_request())
    assert mirrored.status_code == 201
    assert mirrored.json()["spec_id"] == body["spec_id"]
    assert mirrored.json()["run_id"] != body["run_id"]


def test_raw_graph_and_client_selected_identity_are_rejected(client):
    for forbidden in (
        {"graph": copy.deepcopy(GRAPH)},
        {"graph_version": VERSION},
        {"content_address": "sha256:" + "0" * 64},
    ):
        body = {**_request(), **forbidden}
        response = client.post(URL, json=body)
        assert response.status_code == 422
        assert response.json()["code"] == "EXPERIMENT_REQUEST_INVALID"
        assert response.json()["errors"][0]["path"] == [next(iter(forbidden))]


def test_request_bounds_and_dataset_coherence_have_closed_feedback(client):
    invalid = _request()
    invalid["datasets"] = [
        {"instrument_key": "NIFTY", "interval": "day", "days": 30},
        {"instrument_key": "NIFTY", "interval": "15minute", "days": 30},
    ]
    response = client.post(URL, json=invalid)
    assert response.status_code == 422
    assert response.json()["code"] == "EXPERIMENT_REQUEST_INVALID"

    invalid_version = client.post(URL.replace(f"/{VERSION}/", "/0/"), json=_request())
    assert invalid_version.status_code == 422
    assert invalid_version.json() == {
        "code": "EXPERIMENT_VERSION_INVALID",
        "message": "graph version must be greater than zero",
    }


def test_research_freeze_gate_is_exact(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "research_enabled", False)
    response = client.post(URL, json=_request())
    assert response.status_code == 403
    assert response.json() == {
        "detail": "research plane disabled (set PT_RESEARCH_ENABLED=1)"
    }


def test_archived_owner_and_unknown_version_are_rejected(client):
    archived = client.put(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/status",
        json={"status": "archived"},
    )
    assert archived.status_code == 200
    response = client.post(URL, json=_request())
    assert response.status_code == 409
    assert response.json()["code"] == "EXPERIMENT_PROJECT_ARCHIVED"

    init_db(reset=True)
    missing = client.post(URL.replace(f"/{VERSION}/", "/999/"), json=_request())
    assert missing.status_code == 404
    assert missing.json()["code"] == "EXPERIMENT_GRAPH_VERSION_NOT_FOUND"


def test_wrong_owner_and_unpublished_graph_are_rejected(client):
    project = client.post(
        "/api/ir/projects", json={"name": "Other", "description": ""}
    ).json()
    wrong_owner = client.post(
        URL.replace(CATALOGUE_PROJECT_ID, project["project_id"]), json=_request()
    )
    assert wrong_owner.status_code == 404
    assert wrong_owner.json()["code"] == "EXPERIMENT_GRAPH_NOT_FOUND"

    graph = copy.deepcopy(GRAPH)
    graph["identifier"] = "strategy.unpublished_experiment"
    graph["version"] = 1
    graph.pop("parent_version", None)
    created = client.post(
        f"/api/ir/projects/{project['project_id']}/graphs",
        json={"identifier": graph["identifier"], "graph": graph},
    )
    assert created.status_code == 201
    unpublished_url = (
        f"/api/ir/projects/{project['project_id']}/graphs/{graph['identifier']}"
        "/versions/1/experiments"
    )
    unpublished = client.post(unpublished_url, json=_request())
    assert unpublished.status_code == 409
    assert unpublished.json()["code"] == "EXPERIMENT_GRAPH_UNPUBLISHED"


def test_unpublished_draft_cannot_be_mistaken_for_the_selected_version(client):
    draft = graph_store.load_draft(CATALOGUE_PROJECT_ID, IDENTIFIER)
    graph = copy.deepcopy(draft.graph)
    graph["display_name"] = "Unpublished mutable intent"
    graph_store.save_draft(
        CATALOGUE_PROJECT_ID,
        IDENTIFIER,
        base_revision=draft.revision,
        graph=graph,
    )

    response = client.post(URL, json=_request())
    assert response.status_code == 409
    assert response.json() == {
        "code": "EXPERIMENT_GRAPH_DRAFT",
        "message": "graph has unpublished draft changes",
    }


def test_selected_version_and_persisted_evidence_do_not_follow_a_newer_head(client):
    first = client.post(URL, json=_request())
    assert first.status_code == 201
    first_body = first.json()

    editor_url = (
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/{IDENTIFIER}/editor"
    )
    editor = client.get(editor_url).json()
    changed = client.post(
        editor_url.removesuffix("/editor") + "/edits",
        json={
            "base_revision": editor["draft_revision"],
            "base_presentation_revision": editor["layout"]["revision"],
            "edits": [
                {"operation": "set_display_name", "display_name": "Newer head"}
            ],
            "presentation_edits": [],
        },
    )
    assert changed.status_code == 201
    assert changed.json()["version"] == VERSION + 1

    old_again = client.post(URL, json=_request())
    assert old_again.status_code == 201
    assert old_again.json()["spec_id"] == first_body["spec_id"]
    assert old_again.json()["binding"]["graph"] == first_body["binding"]["graph"]

    new_url = URL.replace(f"/{VERSION}/", f"/{VERSION + 1}/")
    newer = client.post(new_url, json=_request())
    assert newer.status_code == 201
    assert newer.json()["spec_id"] != first_body["spec_id"]

    engine = make_engine(research_db_path())
    Session = make_sessionmaker(engine)
    with Session() as session:
        spec = session.get(ExperimentSpec, first_body["spec_id"])
        recipe = json.loads(spec.recipe_json)
        assert recipe["graph_provenance"]["graph"] == first_body["binding"]["graph"]
        assert recipe["datasets"] == first_body["binding"]["datasets"]
        assert recipe["cost_assumptions"] == first_body["binding"]["cost_assumptions"]
        assert recipe["gates"] == first_body["binding"]["gates"]
    engine.dispose()
