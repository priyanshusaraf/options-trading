import copy
import json

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.models import Organization
from app.db.session import SessionLocal, init_db
from app.db.session import engine as execution_engine
from app.editor.graph_artifacts import CATALOGUE_PROJECT_ID
from app.editor import graph_artifacts as graph_store
from app.engine.runner import EngineRunner
from app.ir.strategies.expanding_z import GRAPH
from app.ir.hashing import canonical_json, content_address
from research.config import research_db_path
from research.domain.base import (
    ResearchBase,
    init_research_db,
    make_engine,
    make_sessionmaker,
)
from research.domain.models import ExperimentRun, ExperimentSpec, PromotionCandidate
from research.evidence import decode_terminal_evidence, encode_terminal_evidence


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

    app.state.runner = EngineRunner(owner_id="owner", broker_account_id="account.default")
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


def test_experiment_route_loads_a_graph_owned_by_the_resolved_principal(client, monkeypatch):
    owner_id = "owner.experiment"
    identifier = "strategy.experiment_owner"
    monkeypatch.setattr(get_settings(), "owner_id", owner_id)
    with SessionLocal.begin() as session:
        session.add(Organization(organization_id=owner_id, name="Experiment owner"))
    project = graph_store.create_project("Experiment", owner_id=owner_id)
    graph = copy.deepcopy(GRAPH)
    graph["identifier"] = identifier
    graph["version"] = 1
    graph.pop("parent_version", None)
    graph_store.create_artifact(project.project_id, identifier, graph, owner_id=owner_id)
    published = graph_store.publish_draft(
        project.project_id, identifier, base_revision=0, owner_id=owner_id
    )

    response = client.post(
        f"/api/ir/projects/{project.project_id}/graphs/{identifier}/versions/"
        f"{published.version}/experiments",
        json=_request(),
    )

    assert response.status_code == 201
    assert response.json()["binding"]["graph"]["project_id"] == project.project_id


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
    draft = graph_store.load_draft(CATALOGUE_PROJECT_ID, IDENTIFIER, owner_id="owner")
    graph = copy.deepcopy(draft.graph)
    graph["display_name"] = "Unpublished mutable intent"
    graph_store.save_draft(
        CATALOGUE_PROJECT_ID,
        IDENTIFIER,
        base_revision=draft.revision,
        graph=graph,
        owner_id="owner",
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


def _set_run_checkpoint(run_id: int, checkpoint: str | None) -> None:
    engine = make_engine(research_db_path())
    Session = make_sessionmaker(engine)
    with Session.begin() as session:
        session.get(ExperimentRun, run_id).checkpoint_json = checkpoint
    engine.dispose()


def _set_run_status(run_id: int, status: str) -> None:
    engine = make_engine(research_db_path())
    Session = make_sessionmaker(engine)
    with Session.begin() as session:
        session.get(ExperimentRun, run_id).status = status
    engine.dispose()


def _seed_pending_candidate(run_id: int, *, status: str = "pending") -> tuple[int, dict]:
    scorecard = {
        "best": {"instrument": "NIFTY", "dsr": 0.31},
        "validated": [{"instrument": "NIFTY", "dsr": 0.31}],
        "breadth": {"n_validated": 1},
    }
    engine = make_engine(research_db_path())
    Session = make_sessionmaker(engine)
    with Session.begin() as session:
        candidate = PromotionCandidate(
            run_id=run_id,
            parameterization_hash="candidate-parameterization",
            qualifying_universe_json='["NIFTY"]',
            scorecard_json=json.dumps(scorecard),
            status=status,
        )
        session.add(candidate)
        session.flush()
        candidate_id = candidate.id
    engine.dispose()
    return candidate_id, scorecard


def test_project_owned_evidence_list_and_detail_return_persisted_results_only(
        client, monkeypatch):
    started = client.post(URL, json=_request()).json()
    list_url = f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/experiments"
    detail_url = f"{list_url}/{started['run_id']}"

    def forbidden(*_args, **_kwargs):
        raise AssertionError("evidence reads must not recompute or fetch data")

    monkeypatch.setattr(client.app.state.runner.provider, "get_candles", forbidden)
    monkeypatch.setattr(
        "research.orchestrator.graph_experiment.build_graph_provenance", forbidden
    )
    monkeypatch.setattr("research.orchestrator.run.run_experiment", forbidden)

    listed = client.get(list_url)
    assert listed.status_code == 200
    assert listed.json()["runs"] == [{
        "run_id": started["run_id"],
        "spec_id": started["spec_id"],
        "status": "completed",
        "decision": "archive",
        "evidence_state": "verified",
        "graph": started["binding"]["graph"],
        "candidate": None,
    }]

    detail = client.get(detail_url)
    assert detail.status_code == 200
    body = detail.json()
    assert body["evidence_state"] == "verified"
    assert body["evidence"]["spec_id"] == started["spec_id"]
    assert body["evidence"]["provenance"]["graph_provenance"]["graph"] == (
        started["binding"]["graph"]
    )
    assert body["evidence"]["results"]["instruments"]

    mirrored = client.get(detail_url.replace("/api/", "/api/v1/", 1))
    assert mirrored.status_code == 200
    assert mirrored.json() == body


def test_evidence_detail_hides_cross_project_run_ids(client):
    started = client.post(URL, json=_request()).json()
    other = client.post(
        "/api/ir/projects", json={"name": "Other", "description": ""}
    ).json()
    response = client.get(
        f"/api/ir/projects/{other['project_id']}/experiments/{started['run_id']}"
    )
    assert response.status_code == 404
    assert response.json()["code"] == "EXPERIMENT_RUN_NOT_FOUND"


def test_legacy_missing_evidence_is_visible_but_not_treated_as_empty_success(client):
    started = client.post(URL, json=_request()).json()
    _set_run_checkpoint(started["run_id"], None)

    response = client.get(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/experiments/{started['run_id']}"
    )
    assert response.status_code == 200
    assert response.json()["evidence_state"] == "legacy_unbound"
    assert response.json()["evidence"] is None


def test_running_and_failed_run_states_are_explicit_on_list_and_detail(client):
    running = client.post(URL, json=_request()).json()
    _set_run_checkpoint(running["run_id"], None)
    _set_run_status(running["run_id"], "running")

    failed = client.post(URL, json=_request()).json()
    engine = make_engine(research_db_path())
    Session = make_sessionmaker(engine)
    with Session.begin() as session:
        run = session.get(ExperimentRun, failed["run_id"])
        evidence = decode_terminal_evidence(run.checkpoint_json)
        evidence["run"] = {
            "id": run.id, "status": "failed", "decision": "needs_review"
        }
        evidence["results"] = {"failure": {
            "stage": "validation",
            "code": "RESEARCH_VALIDATION_FAILED",
            "message": "research validation failed",
        }}
        run.status = "failed"
        run.decision = "needs_review"
        run.checkpoint_json = encode_terminal_evidence(evidence)
    engine.dispose()

    list_url = f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/experiments"
    listed = client.get(list_url)
    by_id = {item["run_id"]: item for item in listed.json()["runs"]}
    assert by_id[running["run_id"]]["status"] == "running"
    assert by_id[running["run_id"]]["evidence_state"] == "running"
    assert by_id[failed["run_id"]]["status"] == "failed"
    assert by_id[failed["run_id"]]["evidence_state"] == "verified"

    running_detail = client.get(f"{list_url}/{running['run_id']}")
    assert running_detail.status_code == 200
    assert running_detail.json()["evidence_state"] == "running"
    assert running_detail.json()["evidence"] is None

    failed_detail = client.get(f"{list_url}/{failed['run_id']}")
    assert failed_detail.status_code == 200
    assert failed_detail.json()["evidence"]["results"]["failure"]["code"] == (
        "RESEARCH_VALIDATION_FAILED"
    )


def test_corrupt_persisted_evidence_fails_closed(client):
    started = client.post(URL, json=_request()).json()
    _set_run_checkpoint(started["run_id"], '{"tampered":true}')

    response = client.get(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/experiments/{started['run_id']}"
    )
    assert response.status_code == 409
    assert response.json() == {
        "code": "EXPERIMENT_EVIDENCE_CORRUPT",
        "message": "persisted experiment evidence failed integrity verification",
    }


def test_project_owned_comparison_reports_exact_graph_difference(client):
    first = client.post(URL, json=_request()).json()
    editor_url = (
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/{IDENTIFIER}/editor"
    )
    editor = client.get(editor_url).json()
    changed = client.post(
        editor_url.removesuffix("/editor") + "/edits",
        json={
            "base_revision": editor["draft_revision"],
            "base_presentation_revision": editor["layout"]["revision"],
            "edits": [{"operation": "set_display_name", "display_name": "Compare"}],
            "presentation_edits": [],
        },
    ).json()
    second = client.post(
        URL.replace(f"/{VERSION}/", f"/{changed['version']}/"), json=_request()
    ).json()
    compare_url = f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/experiments/comparisons"

    response = client.post(compare_url, json={
        "left_run_id": first["run_id"],
        "right_run_id": second["run_id"],
    })
    assert response.status_code == 200
    result = response.json()
    assert result["equivalent"] is False
    # The live materializer supplies an exact snapshot identity. A later run may
    # therefore differ in both graph and data, even with the same requested days.
    assert "DATASET_IDENTITY_CHANGED" in result["incomparable"]
    assert any(item["dimension"] == "graph" for item in result["differences"])

    same = client.post(compare_url.replace("/api/", "/api/v1/", 1), json={
        "left_run_id": first["run_id"],
        "right_run_id": first["run_id"],
    })
    assert same.status_code == 200
    assert same.json() == {"equivalent": True, "incomparable": [], "differences": []}


def test_comparison_marks_changed_dataset_contract_incomparable(client):
    first = client.post(URL, json=_request()).json()
    changed_request = _request()
    changed_request["datasets"][0]["days"] = 31
    second = client.post(URL, json=changed_request).json()

    response = client.post(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/experiments/comparisons",
        json={"left_run_id": first["run_id"], "right_run_id": second["run_id"]},
    )
    assert response.status_code == 200
    assert "DATASET_IDENTITY_CHANGED" in response.json()["incomparable"]


def test_comparison_rejects_legacy_cross_project_and_raw_evidence(client):
    first = client.post(URL, json=_request()).json()
    _set_run_checkpoint(first["run_id"], None)
    compare_url = f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/experiments/comparisons"
    legacy = client.post(compare_url, json={
        "left_run_id": first["run_id"], "right_run_id": first["run_id"]
    })
    assert legacy.status_code == 409
    assert legacy.json()["code"] == "EXPERIMENT_EVIDENCE_UNAVAILABLE"

    raw = client.post(compare_url, json={
        "left_run_id": first["run_id"],
        "right_run_id": first["run_id"],
        "evidence": {"client": "claim"},
    })
    assert raw.status_code == 422
    assert raw.json()["code"] == "EXPERIMENT_REQUEST_INVALID"

    other = client.post(
        "/api/ir/projects", json={"name": "Other", "description": ""}
    ).json()
    hidden = client.post(
        compare_url.replace(CATALOGUE_PROJECT_ID, other["project_id"]),
        json={"left_run_id": first["run_id"], "right_run_id": first["run_id"]},
    )
    assert hidden.status_code == 404
    assert hidden.json()["code"] == "EXPERIMENT_RUN_NOT_FOUND"


def test_comparison_rejects_corrupt_and_running_evidence(client):
    corrupt_run = client.post(URL, json=_request()).json()
    _set_run_checkpoint(corrupt_run["run_id"], '{"tampered":true}')
    compare_url = f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/experiments/comparisons"

    corrupt = client.post(compare_url, json={
        "left_run_id": corrupt_run["run_id"],
        "right_run_id": corrupt_run["run_id"],
    })
    assert corrupt.status_code == 409
    assert corrupt.json()["code"] == "EXPERIMENT_EVIDENCE_CORRUPT"

    running = client.post(URL, json=_request()).json()
    _set_run_checkpoint(running["run_id"], None)
    _set_run_status(running["run_id"], "running")
    unavailable = client.post(compare_url, json={
        "left_run_id": running["run_id"],
        "right_run_id": running["run_id"],
    })
    assert unavailable.status_code == 409
    assert unavailable.json()["code"] == "EXPERIMENT_EVIDENCE_UNAVAILABLE"


def _publish_label_change(client):
    editor_url = (
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/{IDENTIFIER}/editor"
    )
    before = client.get(editor_url).json()
    response = client.post(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/{IDENTIFIER}/edits",
        json={
            "base_revision": before["draft_revision"],
            "base_presentation_revision": before["layout"]["revision"],
            "edits": [{"operation": "set_display_name", "display_name": "Compared"}],
            "presentation_edits": [],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _selection(version, run_id=None):
    selected = {"graph_identifier": IDENTIFIER, "graph_version": version}
    if run_id is not None:
        selected["run_id"] = run_id
    return selected


def test_combined_version_and_verified_evidence_comparison_is_server_derived(client):
    first = client.post(URL, json=_request()).json()
    changed = _publish_label_change(client)
    second_url = URL.replace(f"/{VERSION}/experiments", f"/{changed['version']}/experiments")
    second = client.post(second_url, json=_request()).json()
    compare_url = f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/version-comparisons"

    response = client.post(compare_url, json={
        "left": _selection(VERSION, first["run_id"]),
        "right": _selection(changed["version"], second["run_id"]),
    })

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["left"]["content_address"] == first["binding"]["graph"]["content_address"]
    assert body["right"]["content_address"] == changed["content_address"]
    assert body["left"]["run_id"] == first["run_id"]
    assert body["right"]["run_id"] == second["run_id"]
    assert any(item["dimension"] == "metadata" for item in body["differences"])
    assert any(item["dimension"] == "graph" for item in body["differences"])
    assert client.post(
        compare_url.replace("/api/", "/api/v1/", 1),
        json={"left": _selection(VERSION), "right": _selection(VERSION)},
    ).json()["equivalent"] is True


def test_combined_comparison_rejects_raw_claims_one_sided_runs_and_mismatch(client):
    started = client.post(URL, json=_request()).json()
    changed = _publish_label_change(client)
    compare_url = f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/version-comparisons"

    raw = client.post(compare_url, json={
        "left": {**_selection(VERSION), "graph": GRAPH},
        "right": _selection(VERSION),
    })
    assert raw.status_code == 422
    assert raw.json()["code"] == "EXPERIMENT_REQUEST_INVALID"

    one_sided = client.post(compare_url, json={
        "left": _selection(VERSION, started["run_id"]),
        "right": _selection(VERSION),
    })
    assert one_sided.status_code == 422

    mismatch = client.post(compare_url, json={
        "left": _selection(changed["version"], started["run_id"]),
        "right": _selection(changed["version"], started["run_id"]),
    })
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "EXPERIMENT_GRAPH_BINDING_MISMATCH"

    other = client.post(
        "/api/ir/projects", json={"name": "Other comparison", "description": ""}
    ).json()
    hidden = client.post(
        compare_url.replace(CATALOGUE_PROJECT_ID, other["project_id"]),
        json={"left": _selection(VERSION), "right": _selection(VERSION)},
    )
    assert hidden.status_code == 404
    assert hidden.json()["code"] == "EXPERIMENT_GRAPH_VERSION_NOT_FOUND"


def test_combined_comparison_rejects_running_and_legacy_evidence(client):
    started = client.post(URL, json=_request()).json()
    compare_url = f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/version-comparisons"
    body = {
        "left": _selection(VERSION, started["run_id"]),
        "right": _selection(VERSION, started["run_id"]),
    }

    _set_run_checkpoint(started["run_id"], None)
    _set_run_status(started["run_id"], "running")
    running = client.post(compare_url, json=body)
    assert running.status_code == 409
    assert running.json()["code"] == "EXPERIMENT_EVIDENCE_UNAVAILABLE"

    _set_run_status(started["run_id"], "completed")
    legacy = client.post(compare_url, json=body)
    assert legacy.status_code == 409
    assert legacy.json()["code"] == "EXPERIMENT_EVIDENCE_UNAVAILABLE"


def test_combined_comparison_never_resolves_executes_collects_or_loads_presentation(
    client, monkeypatch,
):
    from app.api import ir_experiment_routes
    from app.editor import graph_artifacts
    from app.editor import layouts
    from app.ir import resolve as resolve_module
    from app.providers import factory
    from research.orchestrator import run as orchestrator_run

    editor_url = f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/{IDENTIFIER}/editor"
    editor = client.get(editor_url).json()
    grouped = client.post(editor_url.removesuffix("/editor") + "/presentation-edits", json={
        "base_revision": editor["draft_revision"],
        "base_presentation_revision": editor["layout"]["revision"],
        "edits": [{
            "operation": "create_group", "identifier": "comparison_visual",
            "display_name": "Comparison visual", "members": ["n_ema"],
            "frame": {"x": 10, "y": 10, "width": 200, "height": 100},
            "collapsed": False,
        }],
    })
    assert grouped.status_code == 201

    forbidden = lambda *args, **kwargs: pytest.fail("comparison recomputed state")
    monkeypatch.setattr(resolve_module, "resolve", forbidden)
    monkeypatch.setattr(layouts, "load_layout_in_session", forbidden)
    monkeypatch.setattr(factory, "get_provider", forbidden)
    monkeypatch.setattr(orchestrator_run, "run_nightly", forbidden)
    monkeypatch.setattr(
        ir_experiment_routes, "run_published_graph_experiment", forbidden
    )
    monkeypatch.setattr(graph_artifacts, "publish_draft", forbidden)

    response = client.post(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/version-comparisons",
        json={"left": _selection(VERSION), "right": _selection(VERSION)},
    )

    assert response.status_code == 200
    assert response.json()["equivalent"] is True


def test_combined_comparison_rejects_corrupt_declared_graph_identity(client):
    with execution_engine.begin() as connection:
        connection.exec_driver_sql("DROP TRIGGER graph_versions_refuse_update")
        connection.exec_driver_sql(
            "UPDATE graph_versions SET content_address = ? "
            "WHERE graph_identifier = ? AND version = ?",
            ("sha256:" + "0" * 64, IDENTIFIER, VERSION),
        )

    response = client.post(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/version-comparisons",
        json={"left": _selection(VERSION), "right": _selection(VERSION)},
    )

    assert response.status_code == 409
    assert response.json()["code"] == "GRAPH_VERSION_CORRUPT"


def test_combined_comparison_verifies_evidence_graph_binding_not_only_recipe(client):
    started = client.post(URL, json=_request()).json()
    engine = make_engine(research_db_path())
    Session = make_sessionmaker(engine)
    with Session.begin() as session:
        run = session.get(ExperimentRun, started["run_id"])
        evidence = decode_terminal_evidence(run.checkpoint_json)
        evidence["provenance"]["graph_provenance"]["graph"]["version"] += 1
        run.checkpoint_json = encode_terminal_evidence(evidence)
    engine.dispose()

    response = client.post(
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/version-comparisons",
        json={
            "left": _selection(VERSION, started["run_id"]),
            "right": _selection(VERSION, started["run_id"]),
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "EXPERIMENT_GRAPH_BINDING_MISMATCH"


@pytest.mark.parametrize("decision", ["approved", "rejected"])
def test_candidate_decision_is_canonical_project_owned_and_research_only(
        client, decision):
    started = client.post(URL, json=_request()).json()
    candidate_id, original_scorecard = _seed_pending_candidate(started["run_id"])
    decision_url = (
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/candidates/"
        f"{candidate_id}/decisions"
    )

    response = client.post(decision_url, json={
        "expected_status": "pending",
        "decision": decision,
        "reason": "  Evidence reviewed against the stated gate.  ",
    })

    assert response.status_code == 200
    body = response.json()
    assert body["candidate_id"] == candidate_id
    assert body["status"] == decision
    evidence = body["decision"]["evidence"]
    assert evidence == {
        "actor": "owner",
        "candidate_id": candidate_id,
        "decision": decision,
        "decided_at": evidence["decided_at"],
        "expected_status": "pending",
        "reason": "Evidence reviewed against the stated gate.",
        "run_id": started["run_id"],
    }
    assert body["decision"]["content_address"] == content_address(evidence)

    engine = make_engine(research_db_path())
    Session = make_sessionmaker(engine)
    with Session() as session:
        candidate = session.get(PromotionCandidate, candidate_id)
        persisted = json.loads(candidate.scorecard_json)
        assert candidate.status == decision
        assert {key: persisted[key] for key in original_scorecard} == original_scorecard
        assert persisted["decision"] == body["decision"]
        assert candidate.scorecard_json == canonical_json(persisted)
    engine.dispose()

    # A research decision creates no application-side watchlist or deployment state.
    assert client.get("/api/portfolio/watchlists").json()["watchlists"] == []


def test_candidate_decision_rejects_stale_shadow_cross_project_and_raw_scorecard(client):
    started = client.post(URL, json=_request()).json()
    candidate_id, _ = _seed_pending_candidate(started["run_id"])
    decision_url = (
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/candidates/"
        f"{candidate_id}/decisions"
    )
    accepted = client.post(decision_url.replace("/api/", "/api/v1/", 1), json={
        "expected_status": "pending",
        "decision": "rejected",
        "reason": "Insufficient breadth.",
    })
    assert accepted.status_code == 200

    stale = client.post(decision_url, json={
        "expected_status": "pending",
        "decision": "approved",
        "reason": "Overwrite the first decision.",
    })
    assert stale.status_code == 409
    assert stale.json()["code"] == "CANDIDATE_STATUS_CONFLICT"

    shadow_id, _ = _seed_pending_candidate(started["run_id"], status="shadow")
    shadow = client.post(decision_url.replace(str(candidate_id), str(shadow_id)), json={
        "expected_status": "pending", "decision": "approved", "reason": "Bypass"
    })
    assert shadow.status_code == 409

    other = client.post(
        "/api/ir/projects", json={"name": "Other", "description": ""}
    ).json()
    hidden = client.post(decision_url.replace(
        CATALOGUE_PROJECT_ID, other["project_id"]
    ), json={
        "expected_status": "pending", "decision": "approved", "reason": "Hidden"
    })
    assert hidden.status_code == 404
    assert hidden.json()["code"] == "CANDIDATE_NOT_FOUND"

    raw = client.post(decision_url, json={
        "expected_status": "pending",
        "decision": "approved",
        "reason": "Client replacement",
        "scorecard": {"best": "client claim"},
    })
    assert raw.status_code == 422
    assert raw.json()["code"] == "EXPERIMENT_REQUEST_INVALID"
