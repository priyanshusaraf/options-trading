import copy
import datetime as dt
import json
import sys
import time

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy import event as sqlalchemy_event
from sqlalchemy.engine import Engine
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.models import Organization
from app.db.session import SessionLocal, init_db
from app.db.session import engine as execution_engine
from app.editor.graph_artifacts import CATALOGUE_PROJECT_ID
from app.editor import graph_artifacts as graph_store
from app.editor import v2_editor_store
from app.engine.runner import EngineRunner
from app.ir.strategies.expanding_z import GRAPH
from app.ir.hashing import canonical_json, content_address
from app.ir.v2_graph_versions import V2GraphVerificationError
from research.config import research_db_path
from research.domain.base import (
    ResearchBase,
    init_research_db,
    make_engine,
    make_sessionmaker,
)
from research.domain.models import (
    ExperimentRun, ExperimentSpec, PromotionCandidate, ResearchStrategyAdmission,
)
from research.evidence import decode_terminal_evidence, encode_terminal_evidence
from tests.admitted_entry import persist_admitted_graph


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


def _v2_operation_route_fixture(monkeypatch):
    from app.core import strategy_admissions

    project_id, identifier, version = "project-v2", "graph-v2", 3
    document = {"format_version": 2, "strategy_id": identifier,
                "strategy_version": version, "metadata": {},
                "graph_inputs": [], "graph_outputs": [], "nodes": [], "edges": []}
    content = content_address(document)
    graph_address = content_address({
        "identity_scheme_version": 1,
        "graph": {key: document[key] for key in (
            "format_version", "graph_inputs", "graph_outputs", "nodes", "edges")},
    })
    binding = {
        "owner_id": "owner", "mode": "RESEARCH",
        "authored_ir_address": content,
        "registry_snapshot_address": "sha256:" + "1" * 64,
        "resolved_graph_address": "sha256:" + "2" * 64,
        "implementation_closure_address": "sha256:" + "3" * 64,
        "declaration_addresses": ["sha256:" + "4" * 64],
        "plan_address": "sha256:" + "5" * 64,
        "capability_assessment_address": "sha256:" + "6" * 64,
        "dataset_manifest_address": "sha256:" + "7" * 64,
        "market_truth_snapshot_address": "sha256:" + "8" * 64,
        "evaluation_policy_address": "sha256:" + "9" * 64,
    }
    admission = "sha256:" + "a" * 64
    saved = {"format_version": 2, "graph_identifier": identifier,
             "graph_version": version, "document": document,
             "content_address": content, "graph_address": graph_address,
             "registry_snapshot_address": binding["registry_snapshot_address"]}
    artifact = {
        "owner_id": "owner", "admission_address": admission,
        "graph_identifier": identifier, "graph_version": version,
        "content_address": content, "graph_address": graph_address,
        "phase4_data_binding": binding,
        "base_v2_admission": {"document": document},
    }
    monkeypatch.setattr(v2_editor_store, "read_version", lambda *args, **kwargs: saved)
    monkeypatch.setattr(strategy_admissions, "load_phase4_descriptor",
                        lambda *args, **kwargs: artifact)
    body = {
        "request_id": "9c074bb2-19e0-4690-a26e-16590f249888",
        "admission_address": admission,
        "dataset_manifest_address": binding["dataset_manifest_address"],
        "dataset_as_of": "2026-08-30T12:00:00+00:00",
        "hypothesis": "Saved V2 signals remain causal.",
        "research_capital": 50000.0, "seed": 17, "min_trades": 2,
        "n_folds": 2, "min_positive_fold_frac": 0.5,
    }
    url = (f"/api/ir/projects/{project_id}/graphs/{identifier}/versions/"
           f"{version}/research-operations")
    return url, body


def test_v2_operation_route_enqueues_before_any_dataset_object_load(client, monkeypatch):
    import research.data.canonical_dataset as datasets

    url, body = _v2_operation_route_fixture(monkeypatch)
    monkeypatch.setattr(
        datasets, "load_canonical_datasets",
        lambda *args, **kwargs: pytest.fail("enqueue loaded dataset object bytes"),
    )
    first = client.post(url, json=body)
    retry = client.post(url, json=body)
    assert first.status_code == retry.status_code == 202
    assert first.json() == retry.json()
    receipt = first.json()
    assert receipt["request_id"] == body["request_id"]
    assert len(receipt["operation_id"]) == 64
    assert receipt["status"] == "pending"
    assert receipt["status_url"].endswith(receipt["operation_id"])
    assert receipt["cancel_url"] == receipt["status_url"] + "/cancel"

    changed = copy.deepcopy(body)
    changed["hypothesis"] = "Changed content under the same request id."
    refused = client.post(url, json=changed)
    assert refused.status_code == 409
    assert refused.json()["code"] == "REQUEST_ID_REUSED"


def _input_set_request(addresses=None):
    addresses = addresses or ["sha256:" + "a" * 64, "sha256:" + "b" * 64]
    return {
        "request_id": "bc074bb2-19e0-4690-a26e-16590f249888",
        "input_datasets": [{"graph_input_id": name, "dataset_manifest_address": address}
                           for name, address in zip(("frame", "benchmark"), addresses)],
        "primary_input": "frame", "dataset_as_of": "2026-08-30T12:00:00+00:00",
        "hypothesis": "The benchmark gates the primary instrument.",
        "expected_workspace_revision": 0, "expected_strategy_revision": 0,
        "run_overrides": {},
    }


def test_input_set_preparation_request_is_closed():
    from app.api.ir_experiment_routes import V2InputSetResearchPreparationRequest
    from app.api.request_actions import classify_request

    body = _input_set_request()
    assert V2InputSetResearchPreparationRequest.model_validate(body).primary_input == "frame"
    changes = [
        {"primary_input": "absent"}, {"dataset_as_of": "2026-08-30T12:00:00"},
        {"dataset_as_of": "2026-08-30T12:00:00.123+00:00"}, {"hypothesis": " "},
        {"owner_id": "other"}, {"expected_workspace_revision": True},
        {"input_datasets": [{"graph_input_id": "frame", "dataset_manifest_address": "sha256:" + "a" * 64}]},
    ]
    for change in changes:
        with pytest.raises(ValidationError):
            V2InputSetResearchPreparationRequest.model_validate({**body, **change})
    assert classify_request("POST", "/api/ir/projects/p/graphs/g/versions/1/research-preparations/from-inputs") == "start:research"


def test_input_set_preparation_rejects_duplicate_sources_and_ports():
    from app.api.ir_experiment_routes import V2InputSetResearchPreparationRequest

    body = _input_set_request()
    for field in ("graph_input_id", "dataset_manifest_address"):
        duplicate = copy.deepcopy(body)
        duplicate["input_datasets"][1][field] = duplicate["input_datasets"][0][field]
        with pytest.raises(ValidationError):
            V2InputSetResearchPreparationRequest.model_validate(duplicate)


def _input_set_route_fixture(monkeypatch):
    from app.ir.library import REGISTRY
    from research_tests.test_canonical_dataset import seed_canonical, AS_OF

    url, _ = _v2_operation_route_fixture(monkeypatch)
    saved = v2_editor_store.read_version()
    saved["registry_snapshot_address"] = REGISTRY.registry_snapshot_address
    saved["document"]["graph_inputs"] = [{"port_id": "frame"}, {"port_id": "benchmark"}]
    engine = make_engine(research_db_path())
    try:
        with SessionLocal() as es, make_sessionmaker(engine)() as rs:
            manifests = [seed_canonical(es, rs, owner="owner", instrument_namespace=name)
                         for name in ("primary-api-fixture", "benchmark-api-fixture")]
            foreign = seed_canonical(es, rs, owner="other-owner", instrument_namespace="private-api-fixture")
    finally:
        engine.dispose()
    body = _input_set_request([manifest.manifest_address for manifest in manifests])
    body["dataset_as_of"] = AS_OF.isoformat()
    return url.replace("research-operations", "research-preparations/from-inputs"), body, foreign.manifest_address


def test_input_set_preparation_pins_all_sources_and_retries_exactly(client, monkeypatch):
    from research.domain.operations import ResearchOperationRepository
    from research.orchestrator.v2_operation import operation_id_for_request

    url, body, _ = _input_set_route_fixture(monkeypatch)
    first = client.post(url, json=body)
    assert first.status_code == 202, first.text
    reordered = {**body, "input_datasets": list(reversed(body["input_datasets"]))}
    assert client.post(url, json=reordered).json() == first.json()
    engine = make_engine(research_db_path())
    try:
        with make_sessionmaker(engine)() as session:
            operation = ResearchOperationRepository(session).get(
                operation_id_for_request(owner_id="owner", request_id=body["request_id"]), owner_id="owner")
            assert operation.plan["schema"] == "v2-graph-research-operation/4"
            item = operation.plan["v2_graphs"][0]
            assert item["input_datasets"] == sorted(body["input_datasets"], key=lambda value: value["graph_input_id"])
            assert item["primary_input"] == "frame"
            assert "dataset_manifest_address" not in item
            assert item["settings_snapshot"]["owner_id"] == "owner"
    finally:
        engine.dispose()
    changed = client.post(url, json={**body, "primary_input": "benchmark"})
    assert changed.status_code == 409 and changed.json()["code"] == "REQUEST_ID_REUSED"
    scalar = {key: value for key, value in body.items() if key not in {"input_datasets", "primary_input"}}
    scalar.update(request_id="cc074bb2-19e0-4690-a26e-16590f249888",
                  dataset_manifest_address=body["input_datasets"][0]["dataset_manifest_address"])
    response = client.post(url.replace("from-inputs", "from-settings"), json=scalar)
    assert response.status_code == 202, response.text
    engine = make_engine(research_db_path())
    try:
        with make_sessionmaker(engine)() as session:
            legacy = ResearchOperationRepository(session).get(response.json()["operation_id"], owner_id="owner")
            assert legacy.plan["schema"] == "v2-graph-research-operation/3"
            assert legacy.plan["v2_graphs"][0]["dataset_manifest_address"] == scalar["dataset_manifest_address"]
            assert "input_datasets" not in legacy.plan["v2_graphs"][0]
    finally:
        engine.dispose()


def test_input_set_preparation_refuses_missing_source_ports_and_stale_settings(client, monkeypatch):
    url, body, foreign = _input_set_route_fixture(monkeypatch)
    missing = copy.deepcopy(body)
    missing["input_datasets"][1]["dataset_manifest_address"] = foreign
    response = client.post(url, json=missing)
    assert response.status_code == 404 and response.json()["code"] == "V2_DATASET_NOT_FOUND"
    missing["input_datasets"][1]["dataset_manifest_address"] = "sha256:" + "f" * 64
    absent = client.post(url, json=missing)
    assert absent.status_code == response.status_code and absent.json() == response.json()
    missing["input_datasets"][1]["graph_input_id"] = "wrong-port"
    response = client.post(url, json=missing)
    assert response.status_code == 422 and response.json()["code"] == "V2_PREPARATION_INVALID"
    response = client.post(url, json={**body, "expected_workspace_revision": 1})
    assert response.status_code == 409 and response.json()["code"] == "RESEARCH_SETTINGS_CONFLICT"


def test_v2_parameter_neighborhood_request_is_closed_and_changes_durable_identity(
    client, monkeypatch,
):
    url, body = _v2_operation_route_fixture(monkeypatch)
    body["robustness"] = {"parameter_neighborhood": {
        "enabled": True,
        "axes": [{
            "node_id": "rising", "parameter_id": "window",
            "step": "1", "minimum": "1", "maximum": "3",
        }],
        "maximum_score_drop_paise": 100,
        "minimum_stable_fraction_ppm": 500_000,
    }}
    accepted = client.post(url, json=body)
    assert accepted.status_code == 202, accepted.text
    changed = copy.deepcopy(body)
    changed["robustness"]["parameter_neighborhood"]["minimum_stable_fraction_ppm"] = 500_001
    reused = client.post(url, json=changed)
    assert reused.status_code == 409
    assert reused.json()["code"] == "REQUEST_ID_REUSED"
    opened = copy.deepcopy(body)
    opened["robustness"]["parameter_neighborhood"]["unknown"] = True
    assert client.post(url, json=opened).status_code == 422


def test_v2_operation_route_is_closed_and_does_not_change_v1_request_model(client, monkeypatch):
    url, body = _v2_operation_route_fixture(monkeypatch)
    for key, value in (("provider", "mock"), ("optimize", False),
                       ("parameters", {}), ("owner_id", "owner")):
        opened = copy.deepcopy(body)
        opened[key] = value
        assert client.post(url, json=opened).status_code == 422
    from app.api.ir_experiment_routes import GraphExperimentRequest
    assert GraphExperimentRequest.model_validate(_request()).model_dump() == \
        GraphExperimentRequest.model_validate(copy.deepcopy(_request())).model_dump()


def test_v1_experiment_route_never_calls_v2_loader(client, monkeypatch):
    monkeypatch.setattr(
        v2_editor_store, "read_version",
        lambda *args, **kwargs: pytest.fail("V1 experiment used the V2 version loader"),
    )
    response = client.post(URL, json=_request())
    assert response.status_code == 201, response.text


def test_v2_operation_route_refuses_manifest_binding_mismatch_before_enqueue(
    client, monkeypatch,
):
    url, body = _v2_operation_route_fixture(monkeypatch)
    body["dataset_manifest_address"] = "sha256:" + "f" * 64
    response = client.post(url, json=body)
    assert response.status_code == 422
    assert response.json()["code"] in {
        "V2_AUTHORITY_MISMATCH", "V2_OPERATION_INVALID",
    }
    engine = make_engine(research_db_path())
    try:
        from research.domain.models import ResearchOperation
        Session = make_sessionmaker(engine)
        with Session() as session:
            assert session.query(ResearchOperation).count() == 0
    finally:
        engine.dispose()


def test_v2_operation_route_never_substitutes_same_key_legacy_version(
    client, monkeypatch,
):
    url, body = _v2_operation_route_fixture(monkeypatch)
    monkeypatch.setattr(
        v2_editor_store, "read_version",
        lambda *args, **kwargs: (_ for _ in ()).throw(v2_editor_store.EditorNotFound()),
    )
    monkeypatch.setattr(
        graph_store, "load_owned_version_for_experiment",
        lambda *args, **kwargs: pytest.fail("V2 route attempted legacy substitution"),
    )
    response = client.post(url, json=body)
    assert response.status_code == 404
    assert response.json()["code"] == "V2_GRAPH_NOT_FOUND"


@pytest.mark.parametrize("failure,status_code,code", [
    (v2_editor_store.EditorNotFound(), 404, "V2_GRAPH_NOT_FOUND"),
    (V2GraphVerificationError("corrupt"), 409, "V2_GRAPH_CORRUPT"),
])
def test_v2_operation_route_refuses_private_or_corrupt_version_before_admission(
    client, monkeypatch, failure, status_code, code,
):
    url, body = _v2_operation_route_fixture(monkeypatch)
    monkeypatch.setattr(
        v2_editor_store, "read_version",
        lambda *args, **kwargs: (_ for _ in ()).throw(failure),
    )
    from app.core import strategy_admissions
    monkeypatch.setattr(
        strategy_admissions, "load_phase4_descriptor",
        lambda *args, **kwargs: pytest.fail("version refusal reached admission"),
    )
    response = client.post(url, json=body)
    assert response.status_code == status_code
    assert response.json()["code"] == code


def test_v2_operation_route_refuses_wrong_mode_and_version_bindings_before_enqueue(
    client, monkeypatch,
):
    from app.core import strategy_admissions

    url, body = _v2_operation_route_fixture(monkeypatch)
    original = strategy_admissions.load_phase4_descriptor
    for mutation in (
        lambda value: value["phase4_data_binding"].update(mode="PAPER"),
        lambda value: value.update(graph_version=99),
    ):
        value = copy.deepcopy(original(None))
        mutation(value)
        monkeypatch.setattr(
            strategy_admissions, "load_phase4_descriptor",
            lambda *args, value=value, **kwargs: value,
        )
        response = client.post(url, json=body)
        assert response.status_code == 422
    engine = make_engine(research_db_path())
    try:
        from research.domain.models import ResearchOperation
        Session = make_sessionmaker(engine)
        with Session() as session:
            assert session.query(ResearchOperation).count() == 0
    finally:
        engine.dispose()


def test_robustness_request_is_optional_closed_and_bounded():
    from app.api.ir_experiment_routes import GraphExperimentRequest

    legacy = GraphExperimentRequest.model_validate(_request())
    assert legacy.robustness is None
    request = _request()
    request["robustness"] = {"stationary_bootstrap": {
        "enabled": True,
        "iterations": 100,
        "restart_probability_ppm": 1,
    }}
    parsed = GraphExperimentRequest.model_validate(request)
    assert parsed.robustness.stationary_bootstrap.iterations == 100
    maximum = copy.deepcopy(request)
    maximum["robustness"]["stationary_bootstrap"].update({
        "iterations": 5_000,
        "restart_probability_ppm": 1_000_000,
    })
    maximum_parsed = GraphExperimentRequest.model_validate(maximum)
    assert maximum_parsed.robustness.stationary_bootstrap.iterations == 5_000

    for replacement in (
        {"iterations": 99},
        {"iterations": 5_001},
        {"restart_probability_ppm": 0},
        {"restart_probability_ppm": 1_000_001},
        {"unknown": 1},
    ):
        invalid = copy.deepcopy(request)
        invalid["robustness"]["stationary_bootstrap"].update(replacement)
        with pytest.raises(ValidationError):
            GraphExperimentRequest.model_validate(invalid)

    missing = copy.deepcopy(request)
    del missing["robustness"]["stationary_bootstrap"]["enabled"]
    with pytest.raises(ValidationError):
        GraphExperimentRequest.model_validate(missing)


def test_v2_version_comparison_loads_the_explicit_immutable_v2_authority(client):
    project = graph_store.create_project("V2 comparison", owner_id="owner")
    v2_editor_store.create_graph(
        project.project_id, "v2.compare", "V2 compare", "", owner_id="owner",
    )
    published = v2_editor_store.publish(
        project.project_id, "v2.compare", base_revision=0,
        expected_current_version=None, owner_id="owner",
    )
    selection = {
        "format_version": 2,
        "graph_identifier": "v2.compare",
        "graph_version": published["graph_version"],
        "run_id": None,
    }
    response = client.post(
        f"/api/ir/projects/{project.project_id}/version-comparisons",
        json={"left": selection, "right": selection},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "left": {
            "project_id": project.project_id,
            "graph_identifier": "v2.compare",
            "graph_version": 1,
            "content_address": published["content_address"],
            "run_id": None,
        },
        "right": {
            "project_id": project.project_id,
            "graph_identifier": "v2.compare",
            "graph_version": 1,
            "content_address": published["content_address"],
            "run_id": None,
        },
        "equivalent": True,
        "incomparable": [],
        "differences": [],
    }


@pytest.fixture(autouse=True)
def _databases(monkeypatch):
    original_init_db = init_db
    graph = copy.deepcopy(GRAPH)
    graph["identifier"] = "test.route.expanding_z_impulse"
    module = sys.modules[__name__]

    def seed_admitted_graph():
        with SessionLocal.begin() as session:
            persist_admitted_graph(
                session, graph=graph, owner_id="owner",
                project_id=CATALOGUE_PROJECT_ID, display_name="Repository catalogue",
            )

    original_init_db(reset=True)
    seed_admitted_graph()

    def reset_with_admitted_graph(*args, **kwargs):
        original_init_db(*args, **kwargs)
        if kwargs.get("reset"):
            seed_admitted_graph()

    monkeypatch.setattr(module, "init_db", reset_with_admitted_graph)
    monkeypatch.setattr(module, "IDENTIFIER", graph["identifier"])
    monkeypatch.setattr(
        module, "URL",
        f"/api/ir/projects/{CATALOGUE_PROJECT_ID}/graphs/"
        f"{graph['identifier']}/versions/{VERSION}/experiments",
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


def _persist_canonical_request(*, seed_research_admission=True):
    """Real synthetic authority + published graph + research admission, no loader mock."""
    from research_tests.test_canonical_dataset import seed_canonical, canonical_graph, AS_OF
    from research.orchestrator.graph_experiment import enqueue_graph_admission
    engine = make_engine(research_db_path())
    ResearchSession = make_sessionmaker(engine)
    try:
        with SessionLocal() as es, ResearchSession() as rs:
            manifest = seed_canonical(es, rs, owner="owner", count=64)
        project = graph_store.create_project("Synthetic canonical research", owner_id="owner")
        graph = canonical_graph(manifest.instrument_addresses[0])
        graph_store.create_artifact(project.project_id, graph["identifier"], graph, owner_id="owner")
        published = graph_store.publish_draft(project.project_id, graph["identifier"],
            base_revision=0, owner_id="owner")
        if seed_research_admission:
            with ResearchSession() as rs:
                enqueue_graph_admission(rs, owner_id="owner", graph=graph,
                    graph_content_address=published.content_address,
                    admission_address=published.admission_address)
                rs.commit()
        body = _request()
        body["datasets"] = [{"kind":"canonical_manifest_v2",
            "manifest_address":manifest.manifest_address, "as_of":AS_OF.isoformat()}]
        url = f"/api/ir/projects/{project.project_id}/graphs/{graph['identifier']}/versions/1/experiments"
        return url, body, project.project_id, manifest
    finally:
        engine.dispose()


def _persist_max_canonical_request():
    from research_tests.test_canonical_dataset import seed_canonical, canonical_graph, AS_OF
    engine = make_engine(research_db_path())
    ResearchSession = make_sessionmaker(engine)
    try:
        with SessionLocal() as es, ResearchSession() as rs:
            manifests = [seed_canonical(es,rs,owner="owner",count=250,
                instrument_namespace=f"synthetic-q03-max-{index}") for index in range(8)]
        project = graph_store.create_project("Synthetic maximum canonical research",owner_id="owner")
        graph = canonical_graph("*")
        graph_store.create_artifact(project.project_id,graph["identifier"],graph,owner_id="owner")
        published = graph_store.publish_draft(project.project_id,graph["identifier"],
            base_revision=0,owner_id="owner")
        body = _request()
        body["datasets"] = [{"kind":"canonical_manifest_v2",
            "manifest_address":manifest.manifest_address,"as_of":AS_OF.isoformat()}
            for manifest in manifests]
        url=f"/api/ir/projects/{project.project_id}/graphs/{graph['identifier']}/versions/{published.version}/experiments"
        return url,body,project.project_id,manifests
    finally:
        engine.dispose()


def _run_max_canonical_request(client):
    url,body,project_id,manifests=_persist_max_canonical_request()
    statements=[0]
    def counted(*_args): statements[0]+=1
    sqlalchemy_event.listen(Engine,"before_cursor_execute",counted)
    started=time.perf_counter()
    try:
        response=client.post(url,json=body)
    finally:
        elapsed=time.perf_counter()-started
        sqlalchemy_event.remove(Engine,"before_cursor_execute",counted)
    return response,{"rows":2000,"manifests":8,"segments":sum(
        len(manifest.segment_addresses) for manifest in manifests),
        "sql_statements":statements[0],"seconds":elapsed,"project_id":project_id}


def test_synchronous_maximum_is_batch_bounded(client,monkeypatch):
    import app.api.ir_experiment_routes as routes
    monkeypatch.setattr(get_settings(),"release_profile","v0_research_signal")
    def forbidden(*args,**kwargs):
        raise AssertionError("maximum canonical request reached provider")
    monkeypatch.setattr(routes,"local_execution_cell",forbidden)
    response,measurement=_run_max_canonical_request(client)
    assert response.status_code==201,response.text
    assert measurement["sql_statements"]<=128,measurement
    assert measurement["seconds"]<=10.0,measurement


def test_canonical_http_request_persists_bound_unavailable_robustness_without_losing_base(
    client, monkeypatch,
):
    import app.api.ir_experiment_routes as routes

    url, body, project_id, _manifest = _persist_canonical_request()
    body["robustness"] = {"stationary_bootstrap": {
        "enabled": True,
        "iterations": 100,
        "restart_probability_ppm": 250_000,
    }}
    monkeypatch.setattr(get_settings(), "release_profile", "v0_research_signal")
    monkeypatch.setattr(
        routes, "local_execution_cell",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("canonical robustness reached execution/provider")
        ),
    )
    response = client.post(url, json=body)

    assert response.status_code == 201, response.text
    binding = response.json()["binding"]["robustness"]["stationary_bootstrap"]
    assert binding["iterations"] == 100
    assert binding["method"]["schema"] == "strategy-os-stationary-trade-bootstrap/1"
    detail = client.get(
        f"/api/ir/projects/{project_id}/experiments/{response.json()['run_id']}"
    )
    assert detail.status_code == 200, detail.text
    results = detail.json()["evidence"]["results"]
    assert results["total_bars"] > 0
    assert results["robustness"] == {
        "schema": "strategy-os-run-robustness/1",
        "state": "UNAVAILABLE",
        "reason_code": "LOCKED_OOS_TRADES_UNAVAILABLE",
    }
    robustness = client.get(
        f"/api/ir/projects/{project_id}/experiments/{response.json()['run_id']}/robustness"
    )
    assert robustness.status_code == 200, robustness.text
    assert robustness.json() == results["robustness"]


def test_v0_real_canonical_http_run_reopen_without_execution_cell(client, monkeypatch):
    import app.api.ir_experiment_routes as routes
    url, body, project_id, manifest = _persist_canonical_request()
    def forbidden(*args, **kwargs):
        raise AssertionError("canonical research must not touch an execution cell/provider")
    monkeypatch.setattr(routes, "local_execution_cell", forbidden)
    monkeypatch.setattr(routes, "materialize", forbidden)
    monkeypatch.setattr(routes, "get_instrument", forbidden)
    monkeypatch.setattr(get_settings(), "release_profile", "v0_research_signal")
    first = client.post(url, json=body)
    assert first.status_code == 201, first.text
    second = client.post(url.replace("/api/", "/api/v1/", 1), json=body)
    assert second.status_code == 201, second.text
    assert first.json()["spec_id"] == second.json()["spec_id"]
    engine = make_engine(research_db_path())
    ResearchSession = make_sessionmaker(engine)
    try:
        with ResearchSession() as session:
            stored = json.loads(session.get(ExperimentSpec,("owner",first.json()["spec_id"])).recipe_json)
    finally:
        engine.dispose()
    replay_bindings = stored["graph_provenance"]["canonical_dataset_bindings"]["bindings"]
    replay_request = {"program_name":stored["program"], "hypothesis_statement":stored["hypothesis"],
        "datasets":[{"kind":"canonical_manifest_v2","manifest_address":binding["manifest_address"],
                     "as_of":binding["as_of"]} for _,binding in sorted(replay_bindings.items())],
        "seed":stored["seed"], "gates":stored["gates"], "cost_assumptions":stored["cost_assumptions"]}
    replay = client.post(url.replace("/api/", "/api/v1/", 1),json=replay_request)
    assert replay.status_code == 201, replay.text
    assert replay.json()["spec_id"] == first.json()["spec_id"]
    comparison = client.post(f"/api/ir/projects/{project_id}/experiments/comparisons",
        json={"left_run_id":first.json()["run_id"],"right_run_id":replay.json()["run_id"]})
    assert comparison.status_code == 200, comparison.text
    assert comparison.json() == {"equivalent":True,"incomparable":[],"differences":[]}
    as_of_changed = copy.deepcopy(body)
    as_of_changed["datasets"][0]["as_of"] = (
        dt.datetime.fromisoformat(body["datasets"][0]["as_of"])+dt.timedelta(seconds=1)).isoformat()
    as_of_response = client.post(url,json=as_of_changed)
    assert as_of_response.status_code == 201, as_of_response.text
    assert as_of_response.json()["spec_id"] != first.json()["spec_id"]
    assert as_of_response.json()["run_id"] != first.json()["run_id"]

    from research_tests.test_canonical_dataset import seed_canonical
    engine = make_engine(research_db_path())
    ResearchSession = make_sessionmaker(engine)
    try:
        with SessionLocal() as es, ResearchSession() as rs:
            volume = seed_canonical(es,rs,owner="owner",count=64,volume_delta=1)
            source = seed_canonical(es,rs,owner="owner",count=64,source_name="synthetic-ohlcv/2")
        identities = {first.json()["spec_id"]}
        for changed_manifest in (volume,source):
            changed = copy.deepcopy(body)
            changed["datasets"][0]["manifest_address"] = changed_manifest.manifest_address
            changed_response = client.post(url,json=changed)
            assert changed_response.status_code == 201, changed_response.text
            identities.add(changed_response.json()["spec_id"])
        assert len(identities) == 3
    finally:
        engine.dispose()
    bindings = first.json()["binding"]["canonical_dataset_bindings"]["bindings"]
    assert next(iter(bindings.values()))["manifest_address"] == manifest.manifest_address
    detail = client.get(f"/api/ir/projects/{project_id}/experiments/{first.json()['run_id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["evidence_state"] == "verified"
    assert detail.json()["evidence"]["provenance"]["graph_provenance"]["canonical_dataset_bindings"] == first.json()["binding"]["canonical_dataset_bindings"]


def test_v0_legacy_and_canonical_request_overrides_refuse_before_provider(client, monkeypatch):
    import app.api.ir_experiment_routes as routes
    def forbidden(*args, **kwargs):
        raise AssertionError("refused request reached provider")
    monkeypatch.setattr(routes, "local_execution_cell", forbidden)
    monkeypatch.setattr(get_settings(), "release_profile", "v0_research_signal")
    refused = client.post(URL, json=_request())
    assert refused.status_code == 422
    assert refused.json()["code"] == "EXPERIMENT_CANONICAL_DATASET_REQUIRED"
    body = _request()
    body["datasets"] = [{"kind":"canonical_manifest_v2", "manifest_address":"sha256:"+"a"*64,
                         "as_of":"2026-08-28T00:00:00+00:00", "owner_id":"other"}]
    assert client.post(URL, json=body).status_code == 422
    body["datasets"] = [{"kind":"canonical_manifest_v2","manifest_address":f"sha256:{i:064x}",
                         "as_of":"2026-08-28T00:00:00+00:00"} for i in range(1,10)]
    assert client.post(URL,json=body).status_code == 422


def test_cold_published_graph_starts_canonical_experiment_without_manual_receipt(client, monkeypatch):
    import app.api.ir_experiment_routes as routes
    url, body, _, _ = _persist_canonical_request(seed_research_admission=False)
    monkeypatch.setattr(get_settings(), "release_profile", "v0_research_signal")
    def forbidden(*args, **kwargs):
        raise AssertionError("cold canonical request reached execution provider")
    monkeypatch.setattr(routes, "local_execution_cell", forbidden)
    response = client.post(url, json=body)
    assert response.status_code == 201, response.text


def test_canonical_other_owner_and_missing_manifest_have_same_private_refusal(client, monkeypatch):
    from research_tests.test_canonical_dataset import seed_canonical
    from research.domain.models import ResearchProgram, Hypothesis
    import app.api.ir_experiment_routes as routes
    url, body, _, _ = _persist_canonical_request()
    engine = make_engine(research_db_path())
    ResearchSession = make_sessionmaker(engine)
    try:
        with SessionLocal() as es, ResearchSession() as rs:
            other = seed_canonical(es, rs, owner="unrelated-tenant")
        def counts():
            with ResearchSession() as rs:
                return tuple(rs.query(model).count() for model in (
                    ResearchProgram, Hypothesis, ExperimentSpec, ExperimentRun, ResearchStrategyAdmission))
        before = counts()
        def forbidden(*args, **kwargs):
            raise AssertionError("private refusal reached provider")
        monkeypatch.setattr(routes, "local_execution_cell", forbidden)
        monkeypatch.setattr(get_settings(), "release_profile", "v0_research_signal")
        responses = []
        for manifest_address in (other.manifest_address, "sha256:"+"f"*64):
            body["datasets"][0]["manifest_address"] = manifest_address
            response = client.post(url, json=body)
            assert response.status_code == 422, response.text
            responses.append(response.json())
            assert counts() == before
        assert responses[0] == responses[1]
        assert responses[0]["code"] == "EXPERIMENT_CANONICAL_DATASET_REFUSED"
    finally:
        engine.dispose()


def _research_counts():
    from research.domain.models import ResearchProgram, Hypothesis
    engine = make_engine(research_db_path())
    Session = make_sessionmaker(engine)
    try:
        with Session() as session:
            return tuple(session.query(model).count() for model in (
                ResearchProgram, Hypothesis, ExperimentSpec, ExperimentRun, ResearchStrategyAdmission))
    finally:
        engine.dispose()


def test_cold_invalid_dataset_writes_no_research_receipt_or_run(client, monkeypatch):
    import app.api.ir_experiment_routes as routes
    url, body, _, _ = _persist_canonical_request(seed_research_admission=False)
    body["datasets"][0]["manifest_address"] = "sha256:"+"f"*64
    monkeypatch.setattr(get_settings(), "release_profile", "v0_research_signal")
    def forbidden(*args, **kwargs):
        raise AssertionError("invalid canonical request reached provider")
    monkeypatch.setattr(routes, "local_execution_cell", forbidden)
    before = _research_counts()
    response = client.post(url,json=body)
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "EXPERIMENT_CANONICAL_DATASET_REFUSED"
    assert _research_counts() == before


def test_cold_mirror_failure_rolls_back_without_opening_run(client, monkeypatch):
    import research.orchestrator.graph_experiment as bridge
    url, body, _, _ = _persist_canonical_request(seed_research_admission=False)
    monkeypatch.setattr(get_settings(), "release_profile", "v0_research_signal")
    before = _research_counts()
    def fail_store(*args, **kwargs):
        raise ValueError("synthetic mirror failure")
    monkeypatch.setattr(bridge, "store_admission", fail_store)
    response = client.post(url,json=body)
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "RECEIPT_STALE"
    assert _research_counts() == before


def test_bad_existing_mirror_refuses_before_dataset_loading(client, monkeypatch):
    import app.api.ir_experiment_routes as routes
    from research_tests.test_canonical_dataset import canonical_graph
    from research.orchestrator.graph_experiment import enqueue_graph_admission
    from sqlalchemy import text
    url, body, _, manifest = _persist_canonical_request(seed_research_admission=False)
    graph = canonical_graph(manifest.instrument_addresses[0])
    engine = make_engine(research_db_path())
    try:
        Session = make_sessionmaker(engine)
        with Session() as session:
            artifact = enqueue_graph_admission(session,owner_id="owner",graph=graph,
                graph_content_address=content_address(graph),
                admission_address=__import__("app.strategy.admission",fromlist=["admit_strategy"])
                .admit_strategy(owner_id="owner",source_input=__import__(
                    "app.strategy.admission",fromlist=["IRGraphAdmissionInput"]
                ).IRGraphAdmissionInput(graph=graph,parameters={},risk_model=None),
                    registry=__import__("app.ir.library",fromlist=["REGISTRY"]).REGISTRY
                ).artifact.admission_address,persist=False)
        document = artifact.to_dict()
        document["graph_address"] = "sha256:"+"0"*64
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO research_strategy_admission "
                "(owner_id,admission_address,graph_identifier,graph_version,graph_address,artifact_json,"
                "scheme,contract_suite,parity_suite,created_at,format_version,content_address) VALUES "
                "(:owner,:admission,:identifier,:version,:graph,:artifact,:scheme,:contract,:parity,"
                "CURRENT_TIMESTAMP,:format,:content)"
            ), {"owner":"owner","admission":artifact.admission_address,
                "identifier":artifact.graph_identifier,"version":artifact.graph_version,
                "graph":document["graph_address"],
                "artifact":json.dumps(document,sort_keys=True,separators=(",",":")),
                "scheme":artifact.scheme,"contract":artifact.contract_suite,
                "parity":artifact.parity_suite,"format":getattr(artifact,"format_version",None),
                "content":getattr(artifact,"content_address",None)})
    finally:
        engine.dispose()
    monkeypatch.setattr(get_settings(), "release_profile", "v0_research_signal")
    before = _research_counts()
    def forbidden(*args, **kwargs):
        raise AssertionError("bad mirror reached dataset loading")
    monkeypatch.setattr(routes, "load_canonical_datasets", forbidden)
    response = client.post(url,json=body)
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "ARTEFACT_MISMATCH"
    assert _research_counts() == before


def test_valid_run_failure_retains_durable_failed_evidence(client, monkeypatch):
    import research.orchestrator.run as runner
    url, body, _, _ = _persist_canonical_request(seed_research_admission=False)
    monkeypatch.setattr(get_settings(), "release_profile", "v0_research_signal")
    def fail_after_open(*args, **kwargs):
        raise RuntimeError("synthetic post-open failure")
    monkeypatch.setattr(runner, "qualify_instrument", fail_after_open)
    failed_client = TestClient(client.app, raise_server_exceptions=False)
    response = failed_client.post(url,json=body)
    assert response.status_code == 500
    engine = make_engine(research_db_path())
    Session = make_sessionmaker(engine)
    try:
        with Session() as session:
            rows = session.query(ExperimentRun).all()
            assert len(rows) == 1
            assert rows[0].status == "failed" and rows[0].checkpoint_json
            assert session.query(ResearchStrategyAdmission).count() == 1
    finally:
        engine.dispose()


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
        # Durable-execution contract: research starts only for owners with an
        # ACTIVE broker account row.
        from app.db.models import BrokerAccount
        account_id = "account.experiment"   # PK is globally unique across owners
        if session.get(BrokerAccount, account_id) is None:
            session.add(BrokerAccount(broker_account_id=account_id,
                                      owner_id=owner_id, broker="mock",
                                      external_account_id=account_id,
                                      display_name="experiment", status="active"))
        from app.db.models import Deployment
        deployment = Deployment(owner_id=owner_id, name="experiment",
                                broker_account_id=account_id, status="active")
        session.add(deployment)
        session.flush()
        deployment_id = deployment.id
    # The process-local cell is served only to its owning principal: the
    # runner's owner must match the resolved principal, not the fixture's
    # default. Built AFTER the durable rows above exist for it.
    from app.engine.runner import EngineRunner
    client.app.state.runner = EngineRunner(owner_id=owner_id,
                                           broker_account_id=account_id,
                                           deployment_id=deployment_id)
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

    assert response.status_code == 201, response.text
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
        spec = session.get(ExperimentSpec, ("owner", first_body["spec_id"]))
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
        run = session.get(ExperimentRun, run_id)
        spec = session.get(ExperimentSpec, ("owner", run.spec_id))
        graph_identity = json.loads(spec.recipe_json)["graph_provenance"]["graph"]
        admission_address = session.scalar(select(
            ResearchStrategyAdmission.admission_address,
        ).where(
            ResearchStrategyAdmission.owner_id == "owner",
            ResearchStrategyAdmission.graph_identifier == graph_identity["identifier"],
            ResearchStrategyAdmission.graph_version == graph_identity["version"],
        ))
        run.admission_address = admission_address
        candidate = PromotionCandidate(
            owner_id="owner", run_id=run_id,
            parameterization_hash="candidate-parameterization",
            qualifying_universe_json='["NIFTY"]',
            scorecard_json=json.dumps(scorecard),
            status=status,
            admission_address=admission_address,
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


@pytest.mark.parametrize("field", ["id", "status", "decision", "spec_id"])
def test_canonical_search_reader_binds_terminal_evidence_to_persisted_run(monkeypatch, field):
    from types import SimpleNamespace
    from app.core.research_read import _verify_search_evidence
    from research.evidence import EvidenceRejected
    import research.pipeline.v2_parameter_search as search
    monkeypatch.setattr(search, "verify_canonical_search_evidence", lambda *args: None)
    run = SimpleNamespace(id=1, status="failed", decision="needs_review", spec_id="spec")
    evidence = {"run": {"id": 1, "status": "failed", "decision": "needs_review"}, "spec_id": "spec"}
    _verify_search_evidence(None, run, {"canonical_optimization": {}}, evidence)
    if field == "spec_id": evidence[field] = "other"
    else: evidence["run"][field] = "other"
    with pytest.raises(EvidenceRejected):
        _verify_search_evidence(None, run, {"canonical_optimization": {}}, evidence)


@pytest.mark.parametrize("fault", ["missing", "fold_index", "params", "objective", "trades", "selected"])
def test_canonical_search_reader_compares_every_immutable_trial_field(fault):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from app.core.research_read import _verify_search_trial_ledger
    from research.evidence import EvidenceRejected
    trial = {"fold_index": -1, "params": {"axis_000": "2"}, "objective": None, "trades": 0, "selected": True}
    row = SimpleNamespace(fold_index=-1, params_json=canonical_json(trial["params"]),
                          is_objective=-1e12, is_trades=0, selected=True)
    session = MagicMock()
    session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [row]
    run = SimpleNamespace(id=1, owner_id="owner", status="completed")
    evidence = {"results": {"canonical_optimization": {"nested_trials": [], "final_development_trials": [trial]}}}
    _verify_search_trial_ledger(session, run, evidence)
    if fault == "missing": session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    else:
        column = {"params": "params_json", "objective": "is_objective", "trades": "is_trades"}.get(fault, fault)
        setattr(row, column, "{}" if fault == "params" else 999)
    with pytest.raises(EvidenceRejected):
        _verify_search_trial_ledger(session, run, evidence)


def test_fixed_research_evidence_cannot_inject_an_unrequested_search():
    from app.core.research_read import _verify_search_evidence
    from research.evidence import EvidenceRejected
    _verify_search_evidence(None, None, {}, {"results": {}})
    with pytest.raises(EvidenceRejected):
        _verify_search_evidence(None, None, {}, {"results": {"canonical_optimization": {"state": "selected"}}})
