"""Exact-only legacy admission backfill predicates."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.ir.hashing import canonical_json
from app.db.models import ExecutionIntent, GraphVersion
from app.db.session import SessionLocal, init_db
from app.core.instruments import get_instrument
from app.engine.broker import PaperBroker
from app.ir.library import REGISTRY
from app.ir.strategies.expanding_z import GRAPH as EXPANDING_Z_GRAPH
from app.providers.mock import MockProvider
from scripts.backfill_strategy_admissions import (
    classify, expanding_z_adapter_input, handwritten_adapter, predicate_for, run_backfill,
)


ADDRESS = "sha256:" + "a" * 64
GRAPH = "sha256:" + "b" * 64
OWNER = "owner"


def _artifact():
    return SimpleNamespace(
        owner_id=OWNER, graph_identifier="alpha", graph_version=1,
        graph_address=GRAPH, admission_address=ADDRESS, bound_parameters={},
    )


def _admit(**_):
    return SimpleNamespace(artifact=_artifact(), refusal_code=None)


def _row(**values):
    return SimpleNamespace(admission_address=None, **values)


def test_graph_version_backfill_recomputes_exact_graph_bytes_only():
    graph = {"identifier": "alpha", "version": 1}
    exact = _row(owner_id=OWNER, content_address=GRAPH)
    mismatch = _row(owner_id=OWNER, content_address="sha256:" + "c" * 64)

    assert classify(exact, owner_id=OWNER, graph=graph, parameters={}, risk_model=None,
                    registry=object(), admit=_admit).status == "exact"
    assert classify(mismatch, owner_id=OWNER, graph=graph, parameters={}, risk_model=None,
                    registry=object(), admit=_admit).reason == "ARTEFACT_MISMATCH"


def test_each_consumer_requires_its_own_durable_positive_proof():
    """Every predicate has one exact current-schema proof, not a label-only shortcut."""
    artifact = _artifact()
    request = {
        "owner_id": OWNER, "graph_address": GRAPH, "parameters": {},
        "engine_manifest": "sha256:" + "d" * 64,
        "strategies": [{"key": "ir.alpha", "version": GRAPH}],
    }
    run = _row(id=7, owner_id=OWNER, request_json=canonical_json(request))
    intent = _row(
        client_intent_id="intent-1", owner_id=OWNER, broker_account_id="account",
        strategy_key="ir.alpha", strategy_version=GRAPH,
        context_json=canonical_json({"deployment_receipt_snapshot": ADDRESS,
                                     "graph_address": GRAPH, "parameters": {}}),
    )
    admitted_intent = SimpleNamespace(**{**vars(intent), "admission_address": ADDRESS})
    fixtures = {
        "GraphVersion": _row(owner_id=OWNER, graph_identifier="alpha", version=1,
                               content_address=GRAPH, artifact_json=canonical_json(
                                   {"identifier": "alpha", "version": 1})),
        "Deployment": _row(owner_id=OWNER, broker_account_id="account", strategy_key="ir.alpha",
                             strategy_version=GRAPH, params_json="{}"),
        "ExecutionIntent": intent,
        "Position": _row(owner_id=OWNER, broker_account_id="account", entry_intent_id="intent-1",
                           strategy_key="ir.alpha", strategy_version=GRAPH),
        "Trade": _row(owner_id=OWNER, broker_account_id="account", entry_intent_id="intent-1",
                      strategy_key="ir.alpha", strategy_version=GRAPH),
    }
    for consumer, row in fixtures.items():
        decision = predicate_for(consumer, row, artifact=artifact,
                                 exact_runs={7: run}, exact_intents={"intent-1": admitted_intent})
        assert decision.status == "exact", consumer


@pytest.mark.parametrize("consumer,row,expected", [
    ("GraphVersion", _row(owner_id=OWNER, graph_identifier="alpha", version=1,
                            content_address=GRAPH, artifact_json='{"version":1,"identifier":"alpha"}'),
     "NONCANONICAL_GRAPH"),
    ("BacktestRun", _row(owner_id=OWNER, request_json=canonical_json({"strategies": []})),
     "MISSING_ENGINE_MANIFEST"),
    ("BacktestResult", _row(owner_id=OWNER, run_id=7, graph_address=GRAPH,
                              strategy_key="ir.alpha", strategy_version=GRAPH,
                              authoritative_json="{}"), "PARENT_RUN_UNPROVEN"),
    ("Deployment", _row(owner_id=OWNER, broker_account_id="account", strategy_key="ir.alpha",
                          strategy_version=GRAPH, params_json=""), "MISSING_HISTORICAL_PROVENANCE"),
    ("ExecutionIntent", _row(owner_id=OWNER, broker_account_id="account", strategy_key="ir.alpha",
                              strategy_version=GRAPH, context_json="{}"), "MISSING_INTENT_SNAPSHOT"),
    ("Position", _row(owner_id=OWNER, broker_account_id="account", entry_intent_id=None,
                       strategy_key="ir.alpha", strategy_version=GRAPH), "ENTRY_SOURCE_UNPROVEN"),
    ("Trade", _row(owner_id=OWNER, broker_account_id="account", entry_intent_id=None,
                    strategy_key="ir.alpha", strategy_version=GRAPH), "ENTRY_SOURCE_UNPROVEN"),
])
def test_missing_historical_fact_quarantines_each_provable_consumer(consumer, row, expected):
    decision = predicate_for(consumer, row, artifact=_artifact(),
                             exact_runs={}, exact_intents={})
    assert (decision.status, decision.reason) == ("quarantined", expected)


def test_backtest_rows_with_plausible_extra_json_still_quarantine():
    """The actual pre-Phase-3 producer never persisted the required manifests."""
    run = _row(id=7, owner_id=OWNER, request_json=canonical_json({
        "owner_id": OWNER, "graph_address": GRAPH, "parameters": {},
        "engine_manifest": "sha256:" + "d" * 64,
        "strategies": [{"key": "ir.alpha", "version": GRAPH}],
    }))
    result = _row(owner_id=OWNER, run_id=7, graph_address=GRAPH,
                  strategy_key="ir.alpha", strategy_version=GRAPH,
                  authoritative_json=canonical_json({"admission_address": ADDRESS}))
    assert predicate_for("BacktestRun", run, artifact=_artifact()).reason == "MISSING_ENGINE_MANIFEST"
    assert predicate_for("BacktestResult", result, artifact=_artifact(),
                         exact_runs={7: run}).reason == "PARENT_RUN_UNPROVEN"


@pytest.mark.parametrize("consumer", ["IrShadowDeployment", "IrPaperDeployment"])
def test_schema_without_research_receipt_quarantines_shadow_and_paper(consumer):
    """An appended graph receipt cannot replace the paper/shadow research proof."""
    row = _row(owner_id=OWNER, graph_identifier="alpha", graph_version=1,
               graph_content_address=GRAPH, strategy_key="ir.alpha",
               evidence_content_address=GRAPH, admission_ok=True)
    decision = predicate_for(consumer, row, artifact=_artifact())
    assert (decision.status, decision.reason) == ("quarantined", "MISSING_RESEARCH_RECEIPT")


def test_current_deployment_never_proves_historical_money_rows():
    current_deployment = _row(owner_id=OWNER, broker_account_id="account",
                              strategy_key="ir.alpha", strategy_version=GRAPH,
                              params_json="{}")
    for consumer in ("ExecutionIntent", "Position", "Trade"):
        row = _row(owner_id=OWNER, broker_account_id="account", strategy_key="ir.alpha",
                   strategy_version=GRAPH, deployment=current_deployment,
                   entry_intent_id=None, context_json="{}")
        assert predicate_for(consumer, row, artifact=_artifact()).status == "quarantined"


def test_handwritten_adapter_dispositions_are_explicit_not_key_inference():
    assert handwritten_adapter("expanding_z_v4", "anything") == "EXPANDING_Z_EQUIVALENT_IR_REQUIRED"
    assert handwritten_adapter("trend_impulse_v3", "anything") == "LEGACY_UNADMITTED"
    assert handwritten_adapter("other", "v1") == "NO_EQUIVALENT_IR"


def test_expanding_z_adapter_mapping_requires_exact_handwritten_version_and_graph():
    exact = expanding_z_adapter_input(
        strategy_key="expanding_z_v4",
        strategy_version=__import__("app.strategy.registry.expanding_z_v4", fromlist=["ExpandingZImpulseV4"])
        .ExpandingZImpulseV4().version,
        graph=EXPANDING_Z_GRAPH,
    )
    assert exact is not None
    assert expanding_z_adapter_input(
        strategy_key="expanding_z_v4", strategy_version="wrong", graph=EXPANDING_Z_GRAPH) is None
    altered = {**EXPANDING_Z_GRAPH, "display_name": "other bytes"}
    assert expanding_z_adapter_input(
        strategy_key="expanding_z_v4", strategy_version=exact.strategy_version, graph=altered) is None


def test_run_backfill_dry_run_does_not_write_but_apply_fills_exact_graph_version():
    """Exercise real SQL enumeration, receipt persistence, and apply in separate transactions."""
    init_db(reset=True)
    from app.editor import graph_artifacts

    graph = {**EXPANDING_Z_GRAPH, "identifier": "strategy.backfill_exact"}
    project = graph_artifacts.create_project("Backfill", owner_id="owner")
    graph_artifacts.create_artifact(
        project.project_id, graph["identifier"], graph, owner_id="owner")
    published = graph_artifacts.publish_draft(
        project.project_id, graph["identifier"], base_revision=0, owner_id="owner")
    key = ("owner", published.identifier, published.version)

    with SessionLocal() as session:
        dry = run_backfill(session, registry=REGISTRY, apply=False)
        assert dry["exact"] >= 0
        before = session.get(GraphVersion, key).admission_address

    with SessionLocal.begin() as session:
        applied = run_backfill(session, registry=REGISTRY, apply=True)
        assert applied["exact"] >= 0
    with SessionLocal() as session:
        address = session.get(GraphVersion, key).admission_address
        assert address == before
        from app.backtest.repository import load_verified_admission
        assert load_verified_admission(session, owner_id="owner", admission_address=address).admission_address == address


def test_null_graph_version_uses_exact_appended_receipt_but_conflict_refuses(monkeypatch):
    """Append-only legacy graph rows may load only an exact, non-conflicting receipt."""
    init_db(reset=True)
    from app.editor import graph_artifacts
    from app.backtest.repository import AdmissionRequired, load_verified_admission

    graph = {**EXPANDING_Z_GRAPH, "identifier": "strategy.backfill_loader"}
    project = graph_artifacts.create_project("Backfill loader", owner_id="owner")
    graph_artifacts.create_artifact(project.project_id, graph["identifier"], graph, owner_id="owner")
    published = graph_artifacts.publish_draft(
        project.project_id, graph["identifier"], base_revision=0, owner_id="owner")
    key = ("owner", published.identifier, published.version)
    with SessionLocal() as session:
        version = session.get(GraphVersion, key)
        address = version.admission_address
        original_get = session.get
        # Preserve every immutable field the loader re-derives.  Only the nullable
        # receipt column models the pre-backfill legacy row.
        row_fields = {
            "owner_id": version.owner_id,
            "graph_identifier": version.graph_identifier,
            "version": version.version,
            "artifact_json": version.artifact_json,
            "content_address": version.content_address,
            "visibility": version.visibility,
        }
        null_version = SimpleNamespace(**row_fields, admission_address=None)
        monkeypatch.setattr(session, "get", lambda model, identity: (
            null_version if model is GraphVersion else original_get(model, identity)))
        assert load_verified_admission(session, owner_id="owner", admission_address=address).admission_address == address

        conflicting = SimpleNamespace(**row_fields, admission_address="sha256:" + "f" * 64)
        monkeypatch.setattr(session, "get", lambda model, identity: (
            conflicting if model is GraphVersion else original_get(model, identity)))
        with pytest.raises(AdmissionRequired, match="ARTEFACT_MISMATCH"):
            load_verified_admission(session, owner_id="owner", admission_address=address)


def test_real_expanding_z_intent_maps_only_exact_handwritten_identity():
    """The one adapter backfill is a reviewed graph+code identity, not a key guess."""
    init_db(reset=True)
    from app.strategy.admission import admit_strategy

    with SessionLocal.begin() as session:
        version = session.get(GraphVersion, ("owner", EXPANDING_Z_GRAPH["identifier"],
                                             EXPANDING_Z_GRAPH["version"]))
        assert version is not None
        version.admission_address = None
        adapter_input = expanding_z_adapter_input(
            strategy_key="expanding_z_v4",
            strategy_version=__import__("app.strategy.registry.expanding_z_v4", fromlist=["ExpandingZImpulseV4"])
            .ExpandingZImpulseV4().version,
            graph=EXPANDING_Z_GRAPH)
        admitted = admit_strategy(owner_id="owner", source_input=adapter_input, registry=REGISTRY)
        assert admitted.artifact is not None
        intent = ExecutionIntent(
            client_intent_id="backfill-expanding-z", deployment_id=1, owner_id="owner",
            broker_account_id="account.default", broker="mock", account_scope="paper",
            connection_scope="mock:paper", broker_tag="backfill-expanding-z", intent="ENTRY",
            instrument_key="NIFTY", tradingsymbol="NIFTYOPT", exchange="NFO", side="BUY",
            product=None, order_type="MARKET", requested_qty=1, limit_price=None,
            decision_price=100.0, signal_at=None, strategy_key="expanding_z_v4",
            strategy_version=adapter_input.strategy_version,
            context_json=canonical_json({"deployment_receipt_snapshot": admitted.artifact.admission_address,
                                         "graph_address": admitted.artifact.graph_address,
                                         "parameters": {}}), admission_address=None)
        session.add(intent)

    with SessionLocal.begin() as session:
        report = run_backfill(session, registry=REGISTRY, apply=True)
        restored = session.get(ExecutionIntent, "backfill-expanding-z")
        assert restored.admission_address == admitted.artifact.admission_address
        version = session.get(GraphVersion, ("owner", EXPANDING_Z_GRAPH["identifier"],
                                             EXPANDING_Z_GRAPH["version"]))
        assert version.admission_address in (None, restored.admission_address)
        assert report["exact"] >= 2

    with SessionLocal() as session:
        from app.backtest.repository import load_verified_admission
        assert load_verified_admission(
            session, owner_id="owner", admission_address=admitted.artifact.admission_address
        ).artifact.source_evidence.strategy_key == "expanding_z_v4"

    with SessionLocal.begin() as session:
        session.get(ExecutionIntent, "backfill-expanding-z").admission_address = None
        session.get(ExecutionIntent, "backfill-expanding-z").strategy_version = "wrong"
    with SessionLocal() as session:
        report = run_backfill(session, registry=REGISTRY, apply=False)
        row = next(item for item in report["rows"] if item["identity"] == "owner:backfill-expanding-z")
        assert row["reason"] == "NO_EXACT_GRAPH_PROOF"
