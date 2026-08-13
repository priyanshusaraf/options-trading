import copy
import inspect
import json

import pytest

from app.ir.hashing import content_address
from app.ir.resolve import resolve
from app.ir.strategies.expanding_z import GRAPH, LIBRARY
from research.data.store import StaticDataSource, materialize
from research.domain.models import ExperimentRun, ExperimentSpec
OWNER_ID = "test-owner"

from research.orchestrator.graph_experiment import (
    GraphAdmissionRejected,
    GraphBindingRejected,
    build_graph_provenance,
    enqueue_graph_admission,
    run_published_graph_experiment,
)


def _dataset(inst_factory, candles_factory):
    inst = inst_factory("AAA")
    source = StaticDataSource({("AAA", "day"): candles_factory(400)})
    return inst, materialize(source, inst, "day")


def _admission(session):
    return enqueue_graph_admission(
        session, owner_id=OWNER_ID, graph=GRAPH,
        graph_content_address=content_address(GRAPH),
        admission_address=__import__("app.strategy.admission", fromlist=["admit_strategy"])
        .admit_strategy(
            owner_id=OWNER_ID,
            source_input=__import__("app.strategy.admission", fromlist=["IRGraphAdmissionInput"])
            .IRGraphAdmissionInput(graph=GRAPH, parameters={}, risk_model=None),
            registry=__import__("app.ir.library", fromlist=["REGISTRY"]).REGISTRY,
        ).artifact.admission_address,
    )


def test_binding_is_derived_from_exact_graph_resolution_and_dataset(
        inst_factory, candles_factory):
    dataset = _dataset(inst_factory, candles_factory)
    resolved = resolve(GRAPH, LIBRARY)

    strategy, provenance = build_graph_provenance(
        project_id="project.alpha",
        graph=GRAPH,
        declared_content_address=content_address(GRAPH),
        datasets=[dataset],
    )

    assert strategy.resolved.identifier == GRAPH["identifier"]
    assert provenance["graph"] == {
        "project_id": "project.alpha",
        "identifier": GRAPH["identifier"],
        "version": GRAPH["version"],
        "content_address": content_address(GRAPH),
    }
    assert provenance["resolution"] == {
        "component_versions": [list(version) for version in resolved.versions],
        "node_identities": {
            node.instance_id: node.cache_id for node in resolved.nodes
        },
    }
    assert set(provenance["dataset_bindings"]) == {"AAA"}
    bound = provenance["dataset_bindings"]["AAA"]
    assert bound["data_digest"].startswith("sha256:")
    assert bound["binding"].startswith("sha256:")


def test_declared_graph_identity_must_match_canonical_bytes(
        inst_factory, candles_factory):
    with pytest.raises(GraphBindingRejected, match="content address"):
        build_graph_provenance(
            project_id="project.alpha",
            graph=GRAPH,
            declared_content_address="sha256:" + "0" * 64,
            datasets=[_dataset(inst_factory, candles_factory)],
        )


def test_published_graph_experiment_persists_binding_in_existing_spec(
        research_session, inst_factory, candles_factory):
    admission = _admission(research_session)
    report = run_published_graph_experiment(
        research_session,
        owner_id=OWNER_ID,
        project_id="project.alpha",
        graph=GRAPH,
        declared_content_address=content_address(GRAPH),
        admission_address=admission.admission_address,
        datasets=[_dataset(inst_factory, candles_factory)],
        program_name="Published graphs",
        hypothesis_statement="The immutable graph has edge",
        git_commit="deadbeef",
        seed=7,
        min_trades=10_000,
        n_folds=3,
        min_positive_fold_frac=0.6,
        capital=80_000.0,
        slippage_bps=6.0,
        slippage_multiplier=2.0,
        pbo_threshold=0.3,
        optimize_search=False,
    )

    spec = research_session.get(ExperimentSpec, (OWNER_ID, report["spec_id"]))
    recipe = json.loads(spec.recipe_json)
    assert recipe["graph_provenance"]["graph"]["version"] == GRAPH["version"]
    assert recipe["graph_provenance"]["graph"]["content_address"] == content_address(GRAPH)
    assert recipe["graph_provenance"]["resolution"]["node_identities"]
    assert recipe["graph_provenance"]["dataset_bindings"]["AAA"]["data_digest"]
    assert research_session.query(ExperimentRun).count() == 1
    assert report["explanation"]["strategy_key"].startswith(
        "ir.strategy.expanding_z_impulse."
    )
    assert report["explanation"]["display_name"] == GRAPH["display_name"]
    assert "immutable Component IR graph" in report["explanation"]["thesis"]


def test_presentation_metadata_cannot_change_experiment_identity(
        research_session, inst_factory, candles_factory):
    admission = _admission(research_session)
    dataset = _dataset(inst_factory, candles_factory)
    first = run_published_graph_experiment(
        research_session,
        owner_id=OWNER_ID,
        project_id="project.alpha",
        graph=GRAPH,
        declared_content_address=content_address(GRAPH),
        admission_address=admission.admission_address,
        datasets=[dataset],
        program_name="Published graphs",
        hypothesis_statement="The immutable graph has edge",
        git_commit="deadbeef",
        min_trades=10_000,
    )
    contaminated = copy.deepcopy(GRAPH)
    contaminated["layout"] = {"revision": 99, "positions": {}}

    with pytest.raises(GraphBindingRejected, match="executable graph fields"):
        run_published_graph_experiment(
            research_session,
            owner_id=OWNER_ID,
            project_id="project.alpha",
            graph=contaminated,
            declared_content_address=content_address(contaminated),
            admission_address=admission.admission_address,
            datasets=[dataset],
            program_name="Published graphs",
            hypothesis_statement="The immutable graph has edge",
            git_commit="deadbeef",
            min_trades=10_000,
        )

    assert research_session.query(ExperimentSpec).count() == 1
    assert first["spec_id"] == research_session.query(ExperimentSpec).one().id


def test_graph_bridge_calls_the_existing_orchestrator_instead_of_copying_gates():
    source = inspect.getsource(run_published_graph_experiment)
    assert "run_experiment(" in source
    assert "qualify_instrument" not in source
    assert "gates_from_folds" not in source
    assert "build_scorecard" not in source


def test_missing_graph_receipt_refuses_before_the_experiment_can_touch_data(
        research_session, monkeypatch):
    """Hypothesis: a graph worker constructs a provider before receipt verification."""
    import research.orchestrator.graph_experiment as bridge

    monkeypatch.setattr(
        bridge,
        "build_graph_provenance",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("provider/data path reached")),
    )
    with pytest.raises(GraphAdmissionRejected, match="RECEIPT_STALE"):
        run_published_graph_experiment(
            research_session, owner_id=OWNER_ID, project_id="project.alpha", graph=GRAPH,
            declared_content_address=content_address(GRAPH),
            admission_address="sha256:" + "0" * 64, datasets=[],
        )


def test_graph_worker_freshly_verifies_the_persisted_receipt(
        research_session, monkeypatch):
    """Hypothesis: a worker checks receipt existence but skips registry re-verification."""
    import research.orchestrator.graph_experiment as bridge

    admission = _admission(research_session)
    monkeypatch.setattr(
        bridge,
        "verify_admission",
        lambda **_kwargs: (_ for _ in ()).throw(
            __import__("app.strategy.admission", fromlist=["AdmissionRefused"])
            .AdmissionRefused(
                __import__("app.strategy.admission", fromlist=["AdmissionRefusalCode"])
                .AdmissionRefusalCode.RECEIPT_STALE, "stale registry"
            )
        ),
    )
    with pytest.raises(GraphAdmissionRejected, match="RECEIPT_STALE"):
        bridge.require_graph_admission(
            research_session, owner_id=OWNER_ID, graph=GRAPH,
            graph_content_address=content_address(GRAPH),
            admission_address=admission.admission_address,
        )
