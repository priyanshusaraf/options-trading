from __future__ import annotations

import pytest
from fastapi import HTTPException, Response
from fastapi.testclient import TestClient

from app.core.research_visualization_read import build_visualization_projection
from app.backtest.metrics import compute_metrics
from app.core.config import get_settings
from app.api.principal import Principal
from app.ir.hashing import content_address
from app.db.models import Organization
from app.db.session import SessionLocal, init_db
from research.config import research_database_url
from research.domain.base import ResearchBase, init_research_db, make_engine, make_sessionmaker
from research.domain.models import ExperimentRun, ExperimentSpec, Hypothesis, ResearchProgram
from research.evidence import encode_terminal_evidence
from research.robustness.integration import (
    build_stationary_bootstrap_evidence,
    stationary_bootstrap_recipe_binding,
)
from research.robustness.neighborhood import (
    NeighborhoodCandidate, ParameterAxis, ParameterNeighborhoodInput,
    analyze_parameter_neighborhood,
)
from research.robustness.parameter_integration import (
    parameter_neighborhood_recipe_binding,
    parent_experiment_identity,
)
import json


def address(digit):
    return "sha256:" + digit * 64


def _run(evidence_state="verified", evidence=None, *, status="completed"):
    return {"run_id": 9, "spec_id": "a" * 32, "status": status, "decision": "archive",
            "evidence_state": evidence_state, "graph": {"project_id": "project.a",
            "identifier": "strategy.a", "version": 1, "content_address": address("b")},
            "candidate": None, "evidence": evidence}


def test_visualization_route_reads_persisted_projection_without_research_replay(monkeypatch):
    from app.main import app
    from app.api import research_visualization_routes as routes
    recipe = {"params": {}, "seed": 0, "versions": ["q", "o", "v", "s"],
              "cost_assumptions": {"capital": 100_000.0, "slippage_bps": 5.0,
                                   "slippage_multiplier": 2.0, "sizing_model": "one_lot_or_cash_budget_v1"},
              "resolved_charge_schedule": {"id": "schedule", "address": address("c")},
              "graph_provenance": {"graph": {"project_id": "project.a", "identifier": "strategy.a",
                  "version": 1, "content_address": address("b")},
                  "canonical_dataset_bindings": {"schema": "canonical-dataset-bindings/1", "bindings": {}}}}
    projection = build_visualization_projection(recipe=recipe, run_id=9, spec_id="a" * 32,
        metrics=compute_metrics([], 100_000.0), trades=[], folds=[], gate_results={})
    evidence = {"spec_id": "a" * 32, "run": {"id": 9}, "provenance": recipe,
                "results": {"visualization": projection}}
    monkeypatch.setattr(routes.research_read, "get_graph_run", lambda *_args, **_kwargs: _run(evidence=evidence))
    response = TestClient(app).get("/api/v1/ir/projects/project.a/experiments/9/visualization?trade_limit=10")
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "AVAILABLE"
    assert response.json()["summary"]["trades"] == 0
    assert response.json()["identity"]["terminal_evidence_address"].startswith("sha256:")


def test_visualization_route_keeps_pending_legacy_and_corrupt_states_distinct(monkeypatch):
    from app.main import app
    from app.api import research_visualization_routes as routes
    client = TestClient(app)
    monkeypatch.setattr(routes.research_read, "get_graph_run", lambda *_args, **_kwargs: _run("running", None))
    assert client.get("/api/v1/ir/projects/project.a/experiments/9/visualization").json()["state"] == "PENDING"
    monkeypatch.setattr(routes.research_read, "get_graph_run", lambda *_args, **_kwargs: _run("legacy_unbound", None))
    legacy = client.get("/api/v1/ir/projects/project.a/experiments/9/visualization").json()
    assert legacy["state"] == "UNAVAILABLE"
    assert legacy["reason_code"] == "LEGACY_TERMINAL_EVIDENCE_UNAVAILABLE"
    bad = {"spec_id": "a" * 32, "results": {"visualization": {"schema": "wrong"}}}
    monkeypatch.setattr(routes.research_read, "get_graph_run", lambda *_args, **_kwargs: _run("verified", bad))
    corrupt = client.get("/api/v1/ir/projects/project.a/experiments/9/visualization")
    assert corrupt.status_code == 409
    assert corrupt.json()["detail"]["code"] == "EXPERIMENT_VISUALIZATION_CORRUPT"


def test_robustness_route_semantically_reconstructs_available_evidence(monkeypatch):
    from app.main import app
    from app.api import research_visualization_routes as routes

    settings = {
        "enabled": True,
        "iterations": 100,
        "restart_probability_ppm": 250_000,
    }
    stored = build_stationary_bootstrap_evidence(
        stationary_bootstrap_recipe_binding(settings),
        locked_oos_trades=[type("Trade", (), {"net_pnl": value})()
                           for value in range(1, 21)],
        starting_capital=50_000,
        seed=7,
        instrument_count=1,
    )
    evidence = {"results": {"robustness": stored}}
    monkeypatch.setattr(
        routes.research_read, "get_graph_run",
        lambda *_args, **_kwargs: _run(evidence=evidence),
    )
    response = TestClient(app).get(
        "/api/v1/ir/projects/project.a/experiments/9/robustness"
    )

    assert response.status_code == 200, response.text
    assert response.json()["state"] == "AVAILABLE"
    assert response.json()["method_address"] == stored["method"]["address"]
    assert response.json()["method"]["input"]["trade_net_pnl_paise"] == [
        value * 100 for value in range(1, 21)
    ]


def test_parameter_neighborhood_route_reconstructs_and_refuses_tamper(monkeypatch):
    from app.main import app
    from app.api import research_visualization_routes as routes

    request_binding = parameter_neighborhood_recipe_binding({
        "enabled": True, "axes": [{
            "node_id": "rising", "parameter_id": "window",
            "step": "1", "minimum": "1", "maximum": "3",
        }], "maximum_score_drop_paise": 100,
        "minimum_stable_fraction_ppm": 0,
    })
    parent_recipe = {
        "graph_provenance": {"graph": {"content_address": address("a")}},
        "datasets": {"SAME": {
            "instrument_key": "SAME", "content_hash": address("b"),
        }},
        "resolved_charge_schedule": {"address": address("d")},
        "robustness": request_binding,
    }
    evaluation_document = {
        "schema": "parameter-neighbourhood-evaluation-contract/2",
        "request_address": content_address(request_binding),
        "parent_experiment": parent_experiment_identity(
            spec_id="a" * 32, recipe=parent_recipe,
        ),
        "folds": [[0, 1, 2, 2]], "dataset_bars": 2, "n_folds": 2,
        "capital": 50_000.0, "min_trades": 1,
        "min_positive_fold_frac": 0.0, "slippage_bps": 5.0,
        "slippage_multiplier": 2.0, "seed": 7,
    }
    evaluation_contract = content_address(evaluation_document)
    points = (("axis_000", "1"),), (("axis_000", "2"),), (("axis_000", "3"),)
    graph_addresses = [address(str(index + 1)) for index in range(3)]
    candidates = tuple(NeighborhoodCandidate(
        address=content_address({
            "schema": "saved-v2-parameter-candidate/1",
            "candidate_graph_address": graph_addresses[index],
            "point": [list(pair) for pair in point],
            "evaluation_contract_address": evaluation_contract,
        }), parameters=point,
        oos_score=index * 100, passed=True,
    ) for index, point in enumerate(points))
    result = analyze_parameter_neighborhood(ParameterNeighborhoodInput(
        baseline=candidates[1], candidates=candidates,
        axes=(ParameterAxis("axis_000", "1", "1", "3"),),
        maximum_score_drop=100, minimum_stable_fraction_ppm=0,
    ))
    stored = {
        "schema": "strategy-os-parameter-neighbourhood-evidence/1",
        "state": "AVAILABLE", "evaluation_contract": {
            "address": evaluation_contract, "document": evaluation_document,
        },
        "population": [{
            "candidate_address": candidate.address,
            "candidate_graph_address": graph_addresses[index],
            "parameters": [list(pair) for pair in candidate.parameters],
            "folds": [[0, 1, 2, 2]], "lineage": {},
        } for index, candidate in enumerate(candidates)],
        "method": {
            "address": result.address,
            "canonical_payload": result.canonical_bytes.decode("utf-8"),
        },
    }
    evidence = {"spec_id": "a" * 32, "provenance": parent_recipe,
                "results": {"parameter_neighborhood": stored}}
    monkeypatch.setattr(
        routes.research_read, "get_graph_run",
        lambda *_args, **_kwargs: _run(evidence=evidence),
    )
    url = "/api/v1/ir/projects/project.a/experiments/9/robustness/parameter-neighborhood"
    response = TestClient(app).get(url)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["state"] == "AVAILABLE"
    assert response.json()["method_address"] == result.address

    stored["method"]["address"] = address("f")
    corrupt = TestClient(app).get(url)
    assert corrupt.status_code == 409
    assert corrupt.headers["cache-control"] == "no-store"
    assert corrupt.json()["detail"]["code"] == "EXPERIMENT_PARAMETER_NEIGHBORHOOD_CORRUPT"

    stored["method"]["address"] = result.address
    stale_recipe = parameter_neighborhood_recipe_binding({
        **{key: value for key, value in request_binding["parameter_neighborhood"].items()
           if key != "method"},
        "maximum_score_drop_paise": 101,
    })
    evidence["provenance"]["robustness"] = stale_recipe
    stale = TestClient(app).get(url)
    assert stale.status_code == 409
    assert stale.headers["cache-control"] == "no-store"

    evidence["provenance"]["robustness"] = request_binding
    stored["evaluation_contract"]["document"]["seed"] = 8
    stored["evaluation_contract"]["address"] = content_address(
        stored["evaluation_contract"]["document"]
    )
    readdressed = TestClient(app).get(url)
    assert readdressed.status_code == 409
    assert readdressed.headers["cache-control"] == "no-store"


def test_parameter_neighborhood_read_derives_owner_server_side(monkeypatch):
    from app.api import research_visualization_routes as routes

    observed = []
    monkeypatch.setattr(
        routes.research_read, "get_graph_run",
        lambda *_args, **kwargs: observed.append(kwargs["owner_id"]),
    )
    principal = Principal(
        id="principal-a", kind="owner", scopes=frozenset({"*"}),
        organization_id="tenant-a",
    )
    with pytest.raises(HTTPException) as missing:
        routes.get_parameter_neighborhood(
            "project-a", 9, Response(), principal=principal,
        )
    assert missing.value.status_code == 404
    from app.api.principal import owner_id_for
    assert observed == [owner_id_for(principal)]


def test_parameter_neighborhood_read_state_matrix_and_no_store(monkeypatch):
    from app.main import app
    from app.api import research_visualization_routes as routes

    client = TestClient(app)
    url = "/api/v1/ir/projects/project.a/experiments/9/robustness/parameter-neighborhood"
    enabled = parameter_neighborhood_recipe_binding({
        "enabled": True, "axes": [{
            "node_id": "rising", "parameter_id": "window",
            "step": "1", "minimum": "1", "maximum": "3",
        }], "maximum_score_drop_paise": 100,
        "minimum_stable_fraction_ppm": 0,
    })
    disabled = parameter_neighborhood_recipe_binding({
        "enabled": False, "axes": [], "maximum_score_drop_paise": 0,
        "minimum_stable_fraction_ppm": 0,
    })

    for evidence_state in ("pending", "running"):
        monkeypatch.setattr(
            routes.research_read, "get_graph_run",
            lambda *_args, state=evidence_state, **_kw: _run(state, None),
        )
        response = client.get(url)
        assert response.status_code == 200
        assert response.json()["reason_code"] == "RUN_NOT_TERMINAL"
        assert response.headers["cache-control"] == "no-store"

    cases = (
        ({"spec_id": "a" * 32, "provenance": {}, "results": {}},
         "completed", "NOT_REQUESTED", None),
        ({"spec_id": "a" * 32, "provenance": {"robustness": disabled}, "results": {}},
         "completed", "DISABLED", None),
        ({"spec_id": "a" * 32, "provenance": {"robustness": enabled}, "results": {
            "parameter_neighborhood": {
                "schema": "strategy-os-parameter-neighbourhood-evidence/1",
                "state": "UNAVAILABLE",
                "reason_code": "PARAMETER_NEIGHBORHOOD_METHOD_REFUSED",
            }}}, "completed", "UNAVAILABLE", "PARAMETER_NEIGHBORHOOD_METHOD_REFUSED"),
        ({"spec_id": "a" * 32, "provenance": {"robustness": enabled}, "results": {}},
         "failed", "UNAVAILABLE", "RUN_FAILED_BEFORE_PARAMETER_NEIGHBORHOOD_EVIDENCE"),
    )
    for evidence, status_value, state, reason in cases:
        monkeypatch.setattr(
            routes.research_read, "get_graph_run",
            lambda *_args, payload=evidence, run_status=status_value, **_kw:
                _run(evidence=payload, status=run_status),
        )
        response = client.get(url)
        assert response.status_code == 200, response.text
        assert response.json()["state"] == state
        if reason is not None:
            assert response.json()["reason_code"] == reason
        assert response.headers["cache-control"] == "no-store"

    monkeypatch.setattr(
        routes.research_read, "get_graph_run",
        lambda *_args, **_kw: _run("legacy_unbound", None),
    )
    legacy = client.get(url)
    assert legacy.json()["reason_code"] == "LEGACY_TERMINAL_EVIDENCE_UNAVAILABLE"
    assert legacy.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("evidence", [
    {"spec_id": "a" * 32, "provenance": {"robustness": {"forged": True}},
     "results": {}},
    {"spec_id": "a" * 32, "provenance": {}, "results": {
        "parameter_neighborhood": {
            "schema": "strategy-os-parameter-neighbourhood-evidence/1",
            "state": "DISABLED",
        }}},
    {"spec_id": "a" * 32, "provenance": {"robustness":
        parameter_neighborhood_recipe_binding({
            "enabled": True, "axes": [{
                "node_id": "rising", "parameter_id": "window",
                "step": "1", "minimum": "1", "maximum": "3",
            }], "maximum_score_drop_paise": 100,
            "minimum_stable_fraction_ppm": 0,
        })}, "results": {"parameter_neighborhood": {
            "schema": "strategy-os-parameter-neighbourhood-evidence/1",
            "state": "NOT_REQUESTED",
        }}},
])
def test_parameter_neighborhood_read_rejects_malformed_or_wrong_state_no_store(
    monkeypatch, evidence,
):
    from app.main import app
    from app.api import research_visualization_routes as routes

    monkeypatch.setattr(
        routes.research_read, "get_graph_run",
        lambda *_args, **_kw: _run(evidence=evidence),
    )
    response = TestClient(app).get(
        "/api/v1/ir/projects/project.a/experiments/9/robustness/parameter-neighborhood"
    )
    assert response.status_code == 409
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["detail"]["code"] == "EXPERIMENT_PARAMETER_NEIGHBORHOOD_CORRUPT"


def test_robustness_route_distinguishes_pending_legacy_absent_and_tampered(monkeypatch):
    from app.main import app
    from app.api import research_visualization_routes as routes

    client = TestClient(app)
    url = "/api/v1/ir/projects/project.a/experiments/9/robustness"
    monkeypatch.setattr(
        routes.research_read, "get_graph_run",
        lambda *_args, **_kwargs: _run("running", None),
    )
    assert client.get(url).json()["reason_code"] == "RUN_NOT_TERMINAL"
    monkeypatch.setattr(
        routes.research_read, "get_graph_run",
        lambda *_args, **_kwargs: _run("legacy_unbound", None),
    )
    assert client.get(url).json()["reason_code"] == "LEGACY_TERMINAL_EVIDENCE_UNAVAILABLE"
    monkeypatch.setattr(
        routes.research_read, "get_graph_run",
        lambda *_args, **_kwargs: _run(evidence={"results": {}}),
    )
    assert client.get(url).json()["state"] == "NOT_REQUESTED"
    monkeypatch.setattr(
        routes.research_read, "get_graph_run",
        lambda *_args, **_kwargs: _run(evidence={
            "results": {"robustness": {
                "schema": "strategy-os-run-robustness/1",
                "state": "AVAILABLE",
                "method": {"address": address("f"), "canonical_payload": "{}"},
            }}
        }),
    )
    corrupt = client.get(url)
    assert corrupt.status_code == 409
    assert corrupt.headers["cache-control"] == "no-store"
    assert corrupt.json()["detail"]["code"] == "EXPERIMENT_ROBUSTNESS_CORRUPT"

def test_requested_run_failure_is_not_reported_as_not_requested(monkeypatch):
    from app.main import app
    from app.api import research_visualization_routes as routes

    requested = stationary_bootstrap_recipe_binding({
        "enabled": True,
        "iterations": 100,
        "restart_probability_ppm": 250_000,
    })
    failed = _run(evidence={
        "provenance": {"robustness": requested},
        "results": {"failure": {
            "stage": "validation",
            "code": "RESEARCH_VALIDATION_FAILED",
            "message": "research validation failed",
        }},
    }, status="failed")
    monkeypatch.setattr(
        routes.research_read, "get_graph_run", lambda *_args, **_kwargs: failed,
    )
    response = TestClient(app).get(
        "/api/v1/ir/projects/project.a/experiments/9/robustness"
    )

    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "schema": "strategy-os-run-robustness/1",
        "state": "UNAVAILABLE",
        "reason_code": "RUN_FAILED_BEFORE_ROBUSTNESS_EVIDENCE",
    }

    failed["status"] = "completed"
    corrupt = TestClient(app).get(
        "/api/v1/ir/projects/project.a/experiments/9/robustness"
    )
    assert corrupt.status_code == 409
    assert corrupt.headers["cache-control"] == "no-store"
    assert corrupt.json()["detail"]["code"] == "EXPERIMENT_ROBUSTNESS_CORRUPT"

    principal = Principal(
        id="owner", kind="owner", scopes=frozenset({"*"}),
        organization_id="owner",
    )
    with pytest.raises(HTTPException) as missing:
        routes.get_research_robustness(
            "project.a", 9, response=Response(), principal=principal,
        )
    assert missing.value.status_code == 409
    assert missing.value.headers == {"Cache-Control": "no-store"}

    failed["evidence"]["provenance"]["robustness"] = {"forged": True}
    with pytest.raises(HTTPException) as malformed:
        routes.get_research_robustness(
            "project.a", 9, response=Response(), principal=principal,
        )
    assert malformed.value.status_code == 409
    assert malformed.value.headers == {"Cache-Control": "no-store"}


def test_robustness_route_requires_configured_api_auth_before_private_read(monkeypatch):
    from app.main import app
    from app.api import research_visualization_routes as routes

    monkeypatch.setattr(get_settings(), "api_token", "robustness-secret")
    init_db(reset=True)
    monkeypatch.setattr(
        routes.research_read, "get_graph_run",
        lambda *_args, **_kwargs: _run(evidence={"results": {}}),
    )
    client = TestClient(app)
    url = "/api/v1/ir/projects/project.a/experiments/9/robustness"

    assert client.get(url).status_code == 401
    allowed = client.get(
        url, headers={"Authorization": "Bearer robustness-secret"}
    )
    assert allowed.status_code == 200
    assert allowed.headers["cache-control"] == "no-store"
    assert allowed.json()["state"] == "NOT_REQUESTED"


def test_real_foreign_visualization_endpoint_matches_guessed_private_absence(monkeypatch):
    from app.main import app
    settings = get_settings()
    init_db(reset=True)
    engine = make_engine(research_database_url())
    ResearchBase.metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE IF EXISTS research_schema_version")
    init_research_db(engine)
    Session = make_sessionmaker(engine)
    try:
        with SessionLocal.begin() as execution:
            execution.add_all([Organization(organization_id="owner.visual-a", name="A"),
                               Organization(organization_id="owner.visual-b", name="B")])
        monkeypatch.setattr(settings, "owner_id", "owner.visual-a")
        client = TestClient(app)
        project = client.post("/api/v1/ir/projects", json={"name": "Private result", "description": ""}).json()
        graph = {"project_id": project["project_id"], "identifier": "strategy.private",
                 "version": 1, "content_address": address("b")}
        with Session() as session:
            program = ResearchProgram(owner_id="owner.visual-a", name="Private", thesis="")
            session.add(program); session.flush()
            hypothesis = Hypothesis(owner_id="owner.visual-a", program_id=program.id,
                                    statement="Private evidence")
            session.add(hypothesis); session.flush()
            recipe = {"graph_provenance": {"graph": graph}}
            spec = ExperimentSpec(owner_id="owner.visual-a", id="a" * 32,
                hypothesis_id=hypothesis.id, recipe_json=json.dumps(recipe), git_commit="test",
                qualifier_version="q", optimizer_version="o", validator_version="v",
                scoring_version="s", rng_seed=0)
            session.add(spec); session.flush()
            run = ExperimentRun(owner_id="owner.visual-a", spec_id=spec.id,
                status="completed", decision="archive", checkpoint_json=encode_terminal_evidence({
                    "spec_id": spec.id, "run": {"id": 1, "status": "completed", "decision": "archive"},
                    "provenance": recipe, "results": {},
                }))
            session.add(run); session.commit(); run_id = run.id
        monkeypatch.setattr(settings, "owner_id", "owner.visual-b")
        foreign = client.get(f"/api/v1/ir/projects/{project['project_id']}/experiments/{run_id}/visualization")
        guessed = client.get(f"/api/v1/ir/projects/project.guessed/experiments/{run_id}/visualization")
        assert foreign.status_code == guessed.status_code == 404
        assert foreign.json() == guessed.json()
        foreign_robustness = client.get(
            f"/api/v1/ir/projects/{project['project_id']}/experiments/{run_id}/robustness"
        )
        guessed_robustness = client.get(
            f"/api/v1/ir/projects/project.guessed/experiments/{run_id}/robustness"
        )
        assert foreign_robustness.status_code == guessed_robustness.status_code == 404
        assert foreign_robustness.json() == guessed_robustness.json()
        assert foreign_robustness.headers["cache-control"] == "no-store"
        assert guessed_robustness.headers["cache-control"] == "no-store"
        suffix = "/robustness/parameter-neighborhood"
        foreign_parameter = client.get(
            f"/api/v1/ir/projects/{project['project_id']}/experiments/{run_id}{suffix}"
        )
        guessed_parameter = client.get(
            f"/api/v1/ir/projects/project.guessed/experiments/{run_id}{suffix}"
        )
        assert foreign_parameter.status_code == guessed_parameter.status_code == 404
        assert foreign_parameter.json() == guessed_parameter.json()
        assert foreign_parameter.headers["cache-control"] == "no-store"
        assert guessed_parameter.headers["cache-control"] == "no-store"
    finally:
        engine.dispose()
