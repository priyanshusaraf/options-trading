"""Saved V2 bridge must remain distinct from the legacy graph experiment seam."""
from __future__ import annotations

import ast
import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from app.ir.hashing import canonical_json, content_address
from research.orchestrator.v2_operation import _BarOpenPositionProjectionStrategy


def test_v2_operation_bridge_has_no_provider_or_execution_import_reachability():
    path = Path(__file__).parents[1] / "research" / "orchestrator" / "v2_operation.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    forbidden = ("app.providers", "app.engine", "app.execution", "app.core.paper_authority")
    assert not any(name.startswith(forbidden) for name in imported)


def test_legacy_graph_experiment_function_remains_present_and_separate():
    path = Path(__file__).parents[1] / "research" / "orchestrator" / "graph_experiment.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert {"run_published_graph_experiment", "run_saved_v2_graph_experiment"} <= functions


@pytest.mark.parametrize("short", [False, True])
def test_availability_flags_map_by_position_then_fill_at_original_next_open(short):
    from app.backtest.engine import run_trades
    from research_tests.conftest import FakeInst

    bar_open = pd.date_range("2026-01-01T09:15:00Z", periods=5, freq="15min")
    available = bar_open + pd.Timedelta(minutes=15)
    manifest = "sha256:" + "1" * 64
    position_map = content_address({
        "schema": "bar-open-position-map/1",
        "dataset_manifest_address": manifest,
        "availability_index": [item.isoformat() for item in available],
        "bar_open_index": [item.isoformat() for item in bar_open],
    })

    class Adapter:
        key = "v2.test"
        display_name = "V2 test"
        declared_warmup = 0
        adapter_address = "sha256:" + "2" * 64
        adapter_policy_address = "sha256:" + "3" * 64

        def signals(self, frame):
            assert pd.DatetimeIndex(frame["date"]).equals(available)
            result = frame.copy()
            result["longEntry"] = [False if short else True, False, False, False, False]
            result["shortEntry"] = [True if short else False, False, False, False, False]
            result["longExit"] = [False, False, True if not short else False, False, False]
            result["shortExit"] = [False, False, True if short else False, False, False]
            return result

    strategy = _BarOpenPositionProjectionStrategy(
        Adapter(), manifest_address=manifest, availability_index=available,
        bar_open_index=bar_open, position_map_address=position_map,
    )
    frame = pd.DataFrame({
        "date": bar_open, "open": [100.0, 111.0, 120.0, 133.0, 140.0],
        "high": [141.0] * 5, "low": [90.0] * 5, "close": [101.0] * 5,
        "volume": [1000.0] * 5,
    })
    projected = strategy.signals(frame)
    assert pd.DatetimeIndex(projected["date"]).equals(bar_open)
    trades = run_trades(
        projected, FakeInst(), "NSE_EQ", 50_000.0, None,
        event_risk=False, slippage_pct=0.0,
    )
    assert len(trades) == 1
    assert trades[0].direction == ("SHORT" if short else "LONG")
    assert trades[0].entry_price == pytest.approx(111.0)  # signal row 0 -> row 1 open
    assert trades[0].exit_price == pytest.approx(133.0)   # exit row 2 -> row 3 open
    assert trades[0].net_pnl == pytest.approx(
        trades[0].gross_pnl - trades[0].charges
    )


def _plain(value):
    from collections.abc import Mapping
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _saved_v2_boolean_graph(registry):
    rising = _plain(registry.v2_components[("analytical.rising", 2)])
    frame = next(port for port in rising["ports"] if port["direction"] == "input")
    output = next(port for port in rising["ports"] if port["direction"] == "output")
    def graph_output(port_id, role):
        return {**output, "port_id": port_id, "semantic_role": role}
    return {
        "format_version": 2, "strategy_id": "v2.saved.research",
        "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "V2 saved research",
                     "description": None, "tags": []},
        "graph_inputs": [frame],
        "graph_outputs": [
            graph_output("entry", "research_long_entry"),
            graph_output("exit", "research_long_exit"),
        ],
        "nodes": [
            {"node_id": "rising", "component": {
                "component_id": "analytical.rising", "component_version": 2,
            }, "parameters": {"window": 2}},
            {"node_id": "falling", "component": {
                "component_id": "analytical.falling", "component_version": 2,
            }, "parameters": {"window": 2}},
        ],
        "edges": [
            {"edge_id": "frame-rising", "source": {
                "scope": "graph_input", "port_id": "frame",
            }, "target": {"scope": "node", "node_id": "rising", "port_id": "frame"},
             "binding": {"kind": "single"}},
            {"edge_id": "frame-falling", "source": {
                "scope": "graph_input", "port_id": "frame",
            }, "target": {"scope": "node", "node_id": "falling", "port_id": "frame"},
             "binding": {"kind": "single"}},
            {"edge_id": "rising-entry", "source": {
                "scope": "node", "node_id": "rising", "port_id": "value",
            }, "target": {"scope": "graph_output", "port_id": "entry"},
             "binding": {"kind": "single"}},
            {"edge_id": "falling-exit", "source": {
                "scope": "node", "node_id": "falling", "port_id": "value",
            }, "target": {"scope": "graph_output", "port_id": "exit"},
             "binding": {"kind": "single"}},
        ],
    }


@pytest.mark.parametrize("public_preparation,dataset_source,settings_preparation", [
    (False, "canonical_fixture", False), (False, "user_csv", False),
    (True, "canonical_fixture", False), (True, "user_csv", False), (True, "user_csv", True),
    (True, "canonical_fixture", True),
], ids=["False-canonical_fixture", "False-user_csv", "True-canonical_fixture", "True-user_csv", "settings-user_csv", "settings-canonical-monitoring"])
def test_real_saved_v2_manifest_operation_completes_with_full_lineage(
    tmp_path, monkeypatch, dataset_source, public_preparation, settings_preparation,
):
    """One real saved graph and persisted synthetic manifest cross every authority."""
    import json
    from sqlalchemy import create_engine, func, select
    from sqlalchemy.orm import sessionmaker

    from app.core.strategy_admissions import put
    from app.db.models import Base, GraphArtifact, Organization, Project
    from app.editor import v2_editor_store
    from app.ir.library import REGISTRY
    from app.ir.resolve import resolve_v2
    from app.market_data.authority import (
        load_capability_profile, load_provider_conformance,
        persist_capability_assessment,
    )
    from app.market_data.capability import assess_capability
    from app.market_data.requirements import compile_data_requirement_plan
    from app.market_truth.identity import load_provider_identity
    from app.strategy.admission import admit_phase4_v2_strategy
    from research.domain.admissions import store_admission
    from research.data.canonical_dataset import (
        load_canonical_datasets, project_verified_research_inputs,
    )
    from research.data.user_csv_import import CsvColumnMapping, UserCsvSpec, persist_user_csv
    from research.domain.base import init_research_db
    from research.domain.models import ExperimentRun, ExperimentSpec, ResearchDatasetManifestV2
    from research.evidence import decode_terminal_evidence
    from research.orchestrator.v2_operation import operation_id_for_request
    import research_tests.test_canonical_dataset as canonical_fixture
    from research_tests.test_canonical_dataset import AS_OF, seed_canonical
    from tests.test_phase4_capability_admission import _evidence

    if settings_preparation and dataset_source == 'canonical_fixture':
        from tests.test_v0_monitoring_persistence import _engine
        execution_engine = _engine(tmp_path, 'execution.db')
    else:
        execution_engine = create_engine(f"sqlite:///{tmp_path / 'execution.db'}")
    research_engine = create_engine(f"sqlite:///{tmp_path / 'research.db'}")
    Base.metadata.create_all(execution_engine)
    init_research_db(research_engine)
    ExecutionSession = sessionmaker(execution_engine, expire_on_commit=False)
    ResearchSession = sessionmaker(research_engine, expire_on_commit=False)
    monkeypatch.setattr(v2_editor_store, "SessionLocal", ExecutionSession)
    original_offer = canonical_fixture._offer
    original_coverage = canonical_fixture._coverage

    def exact_offer(**kwargs):
        return {**original_offer(**kwargs), "maximum_freshness_seconds": 0,
                "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0}}

    def exact_coverage(**kwargs):
        return {**original_coverage(**kwargs), "maximum_freshness_seconds": 0,
                "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0}}

    monkeypatch.setattr(canonical_fixture, "_offer", exact_offer)
    monkeypatch.setattr(canonical_fixture, "_coverage", exact_coverage)
    owner = "owner-a"
    graph = _saved_v2_boolean_graph(REGISTRY)
    try:
        with ExecutionSession() as es, ResearchSession() as rs:
            dataset_as_of = AS_OF
            if dataset_source == "canonical_fixture":
                manifest = seed_canonical(es, rs, owner=owner, count=64)
            else:
                start = AS_OF.date() - dt.timedelta(days=100 if public_preparation else 90)
                rows = ["Symbol,Date,Open,High,Low,Close,Volume"]
                days = [start + dt.timedelta(days=index) for index in range(100)
                        if not public_preparation or (start + dt.timedelta(days=index)).weekday() < 5][:64]
                for index, day in enumerate(days):
                    price = 100 + index
                    rows.append(
                        f"SELF,{day.isoformat()},{price},{price+2},{price-1},"
                        f"{price+1},{1000+index}"
                    )
                imported = persist_user_csv(
                    es, rs, owner_id=owner, project_id="project-v2",
                    raw=("\n".join(rows) + "\n").encode(),
                    spec=UserCsvSpec(
                        "User CSV upload", "user-csv:XNSE:EQUITY:SELF", "1",
                        "SELF", "SELF", "XNSE", "EQUITY",
                        CsvColumnMapping(
                            "Symbol", "Date", "Open", "High", "Low", "Close", "Volume"),
                        date_format="%Y-%m-%d",
                    ),
                    observed_at=AS_OF,
                )
                manifest = imported.manifest
                dataset_as_of = imported.ready_as_of
            selection = type("Selection", (), {
                "manifest_address": manifest.manifest_address, "as_of": dataset_as_of,
            })()
            [(_instrument, canonical)] = load_canonical_datasets(
                rs, execution_session=es, owner_id=owner,
                selections=[selection], now=dataset_as_of,
            )
            projected = project_verified_research_inputs(
                canonical, owner_id=owner,
                graph_input_fields={"frame": ("CLOSE",)},
            )
            resolved = resolve_v2(graph, REGISTRY)
            phase4_plan = compile_data_requirement_plan(
                resolved, registry=REGISTRY,
                input_bindings=projected.input_bindings,
            )
            profile = load_capability_profile(
                es, manifest.capability_profile_address, at_time=dataset_as_of,
            )
            conformance = load_provider_conformance(
                es, profile.conformance_evidence_address,
            )
            _entity, _product, contract = load_provider_identity(
                es, profile.provider_contract_address,
            )
            wrapper = None
            if not public_preparation:
                assessment = assess_capability(
                    plan=phase4_plan, profile=profile, owner_id=owner, mode="RESEARCH",
                    dataset_manifest_address=manifest.manifest_address,
                    market_truth_snapshot_address=manifest.truth_snapshot_addresses[0],
                    evaluation_policy_address=content_address({"policy": "v2-test"}),
                    assessment_evidence_address=conformance.address,
                    at_time=int(dataset_as_of.timestamp()), conformance=conformance,
                    provider_contract=contract,
                )
                persist_capability_assessment(
                    es, assessment, plan=phase4_plan, at_time=dataset_as_of)
                wrapper = admit_phase4_v2_strategy(
                    owner_id=owner, mode="RESEARCH", document=graph, registry=REGISTRY,
                    evidence=_evidence(), plan=phase4_plan,
                    input_bindings=projected.input_bindings,
                    assessment_address=assessment.authority_address,
                    dataset_manifest_address=manifest.manifest_address,
                    market_truth_snapshot_address=manifest.truth_snapshot_addresses[0],
                    evaluation_policy_address=assessment.evaluation_policy_address,
                    research_session=rs, execution_session=es, at_time=dataset_as_of,
                )
            if es.get(Organization, owner) is None:
                es.add(Organization(organization_id=owner, name="V2 owner"))
                es.flush()
            es.add(Project(project_id="project-v2", owner_id=owner, name="V2 project"))
            es.flush()
            es.add(GraphArtifact(
                owner_id=owner, identifier=graph["strategy_id"], project_id="project-v2",
                display_name="V2 saved research", draft_json=canonical_json(graph),
                draft_revision=0, published_revision=None if public_preparation else 0,
                current_version=None if public_preparation else 1,
            ))
            es.flush()
            if wrapper is not None:
                put(es, wrapper)
                store_admission(rs, wrapper)
            es.commit(); rs.commit()
            if public_preparation:
                v2_editor_store.publish("project-v2", "v2.saved.research", base_revision=0,
                    expected_current_version=None, owner_id=owner)


            from fastapi.testclient import TestClient
            from app.core.config import get_settings
            from app.main import app
            import app.api.ir_experiment_routes as ir_routes
            import app.api.research_operation_routes as operation_routes
            import app.db.session as execution_db
            import scripts.research_run as research_run

            research_path = str(tmp_path / "research.db")
            monkeypatch.setattr(ir_routes, "SessionLocal", ExecutionSession)
            monkeypatch.setattr(ir_routes, "research_database_url", lambda: research_path)
            monkeypatch.setattr(ir_routes, "get_build_sha", lambda: "test-build")
            monkeypatch.setattr(operation_routes, "research_database_url", lambda: research_path)
            monkeypatch.setattr(execution_db, "SessionLocal", ExecutionSession)
            monkeypatch.setattr(get_settings(), "owner_id", owner)
            monkeypatch.setattr(get_settings(), "research_enabled", True)
            monkeypatch.setenv("PT_RESEARCH_OWNER_ID", owner)
            monkeypatch.setenv("PT_RESEARCH_DB_PATH", research_path)
            monkeypatch.setenv("PT_DISABLE_DOTENV", "1")
            monkeypatch.setenv("PT_PROVIDER", "mock")
            monkeypatch.setenv("PT_EXECUTION", "paper")
            monkeypatch.setenv("PT_LIVE_ACK", "")
            monkeypatch.setattr(research_run, "_git_commit", lambda: "test-build")
            if public_preparation:
                import research.orchestrator.v2_preparation as preparation
                monkeypatch.setattr(preparation, "_now", lambda: dataset_as_of)

            request_id = "947a323d-b590-4fb5-8cf1-91f6ae1856d1"
            phase4 = _plain(wrapper.phase4_data_binding) if wrapper is not None else None
            body = {
                "request_id": request_id,
                "admission_address": wrapper.admission_address if wrapper is not None else None,
                "dataset_manifest_address": manifest.manifest_address,
                "dataset_as_of": dataset_as_of.isoformat(),
                "hypothesis": "Rising closes retain causal next-open trades.",
                "research_capital": 50_000.0, "seed": 17, "min_trades": 1,
                "n_folds": 2, "min_positive_fold_frac": 0.0,
                "robustness": {"parameter_neighborhood": {
                    "enabled": True,
                    "axes": [{
                        "node_id": "rising", "parameter_id": "window",
                        "step": "1", "minimum": "1", "maximum": "3",
                    }],
                    "maximum_score_drop_paise": 100_000,
                    "minimum_stable_fraction_ppm": 0,
                }},
            }
            if public_preparation:
                body.pop("admission_address")
                body.pop("robustness")
                body["risk_policy"] = "none"
            operation_id = operation_id_for_request(owner_id=owner, request_id=request_id)
            published_before = v2_editor_store.read_version(
                "project-v2", "v2.saved.research", 1, owner_id=owner,
            )
            before_manifests = rs.scalar(select(func.count()).select_from(
                ResearchDatasetManifestV2))
            client = TestClient(app)
            url = ("/api/ir/projects/project-v2/graphs/v2.saved.research/"
                   "versions/1/research-operations")
            if public_preparation:
                url = url.replace("research-operations", "research-preparations")
            if settings_preparation:
                body = _saved_settings_request(ExecutionSession, owner, body)
                url += "/from-settings"
            accepted = client.post(url, json=body)
            assert accepted.status_code == 202, accepted.text
            assert accepted.json()["operation_id"] == operation_id
            if public_preparation:
                _assert_preparation_keeps_heartbeat_writable(operation_id, owner, ResearchSession, monkeypatch)
            if public_preparation and dataset_source == "canonical_fixture" and not settings_preparation:
                _interrupt_preparation_after_execution_receipt(
                    operation_id, owner, ExecutionSession, ResearchSession, monkeypatch)
            if settings_preparation:
                _change_settings_after_queue(ExecutionSession, owner)
                retry = client.post(url, json=body)
                assert retry.status_code == 202 and retry.json() == accepted.json()
                stale = client.post(url, json={**body, "request_id": "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"})
                assert stale.status_code == 409 and stale.json()["code"] == "RESEARCH_SETTINGS_CONFLICT"
                from research.domain.settings import ResearchSettingsRepository
                with monkeypatch.context() as guard:
                    guard.setattr(ResearchSettingsRepository, "read", lambda *_args, **_kwargs: pytest.fail("worker read mutable settings head"))
                    reports, mode = research_run._run_enabled_operation(research_path)
            else:
                reports, mode = research_run._run_enabled_operation(research_path)
            assert mode == "persisted-dataset" and len(reports) == 1
            report = reports[0]
            status = client.get(f"/api/research/operations/{operation_id}")
            assert status.status_code == 200
            assert status.json()["status"] == "completed"
            assert status.json()["completed_run_ids"] == [report["run_id"]]

            cancel_body = {**body,
                "request_id": "1b5db2d7-cf92-4812-9227-8a643ed5a1d4"}
            if settings_preparation:
                cancel_body["expected_workspace_revision"] = 2
            queued_cancel = client.post(url, json=cancel_body)
            assert queued_cancel.status_code == 202
            cancelled = client.post(queued_cancel.json()["cancel_url"])
            assert cancelled.status_code == 200
            assert cancelled.json()["status"] == "cancelled"
            assert client.get(queued_cancel.json()["status_url"]).json()[
                "status"] == "cancelled"

            rs.expire_all()
            after_manifests = rs.scalar(select(func.count()).select_from(
                ResearchDatasetManifestV2))
            assert before_manifests == after_manifests == 1
            spec = rs.get(ExperimentSpec, (owner, report["spec_id"]))
            recipe = json.loads(spec.recipe_json)
            provenance = recipe["graph_provenance"]
            if not public_preparation:
                assert recipe["robustness"]["parameter_neighborhood"]["enabled"] is True
                terminal = decode_terminal_evidence(
                    rs.get(ExperimentRun, report["run_id"]).checkpoint_json
                )
                neighborhood = terminal["results"]["parameter_neighborhood"]
                if dataset_source == "canonical_fixture":
                    assert neighborhood == {"schema": "strategy-os-parameter-neighbourhood-evidence/1",
                        "state": "UNAVAILABLE", "reason_code": "PARENT_NOT_QUALIFIED"}
                    assert terminal["results"]["qualified"] == []
                    assert terminal["results"]["rejected"][0]["reason"] == "edge not confidently positive (bootstrap LB<=0)"
                else:
                    assert neighborhood["state"] == "AVAILABLE"
                    assert len(neighborhood["population"]) == 3
                    assert len({row["candidate_address"] for row in neighborhood["population"]}) == 3
                    assert all(len(row["folds"]) == 2 for row in neighborhood["population"])
                parameter_read = client.get(
                    "/api/v1/ir/projects/project-v2/experiments/"
                    f"{report['run_id']}/robustness/parameter-neighborhood"
                )
                assert parameter_read.status_code == 200, parameter_read.text
                assert parameter_read.headers["cache-control"] == "no-store"
                assert parameter_read.json()["state"] == neighborhood["state"]
                if dataset_source == "canonical_fixture":
                    assert parameter_read.json()["reason_code"] == "PARENT_NOT_QUALIFIED"
                else:
                    assert parameter_read.json()["evaluation_contract"]["address"] \
                        == neighborhood["evaluation_contract"]["address"]
            else:
                from research.domain.operations import ResearchOperationRepository
                evidence = ResearchOperationRepository(rs).preparation_evidence(operation_id, owner_id=owner)
                assert evidence["documents"]["parity"]["status"] == "COMPLETED"
                assert evidence["addresses"]["dataset_address"] == manifest.manifest_address
                assert evidence["documents"]["risk"]["risk_policy"] == "none"
                assert provenance["execution_policy"]["risk"] == evidence["documents"]["risk"]
                _assert_produced_preparation_documents(evidence, projected, manifest, provenance, es, rs, owner)
                assert evidence["documents"]["risk"]["capital"] == recipe["cost_assumptions"]["capital"]
                if settings_preparation:
                    operation = ResearchOperationRepository(rs).get(operation_id, owner_id=owner)
                    snapshot = operation.plan["v2_graphs"][0]["settings_snapshot"]
                    assert operation.plan["schema"] == "v2-graph-research-operation/3"
                    assert snapshot["workspace"]["revision"] == snapshot["strategy"]["revision"] == 1
                    assert snapshot["sources"]["seed"] == "strategy"
                    assert recipe["cost_assumptions"]["capital"] == snapshot["values"]["research_capital"] == 50000.0
                _assert_research_monitoring_consumer(es, rs, owner, operation_id, provenance,
                    settings_preparation, evidence, monkeypatch)
                if settings_preparation and dataset_source == 'canonical_fixture':
                    _assert_real_research_watchlist_worker(es, rs, owner, operation_id, provenance, dataset_as_of,
                        projected.manifest.instrument_addresses[0])
                if dataset_source == "user_csv":
                    assert all(day.weekday() < 5 for day in days)
                    assert any((right - left).days > 1 for left, right in zip(days, days[1:]))
                    assert evidence["documents"]["causal"]["historical_source_availability"] == "NOT_ASSERTED"
                    assert dt.datetime.fromisoformat(evidence["documents"]["evaluation_policy"]["event_end"]) < dt.datetime.fromisoformat(manifest.availability_start)
                _assert_corrupt_preparation_refuses(operation_id, owner, rs)
                phase4 = provenance["phase4_binding"]
                assert client.post(url, json=body).json()["operation_id"] == operation_id
                forbidden = client.post(url, json={**body, "admission_address": "sha256:" + "a" * 64})
                assert forbidden.status_code == 422
            persisted = v2_editor_store.read_version(
                "project-v2", "v2.saved.research", 1, owner_id=owner,
            )
            assert canonical_json(persisted) == canonical_json(published_before)
            assert provenance["dataset_manifest_address"] == manifest.manifest_address
            assert provenance["phase4_binding"] == phase4
            for key in (
                "input_digest", "input_binding_context_address",
                "data_requirement_plan_address", "eligibility_address",
                "resource_plan_address", "resource_admission_address",
                "evaluation_policy_address", "research_result_address",
                "research_output_digest", "adapter_address", "position_map_address",
                "time_projection_algorithm_address",
            ):
                assert provenance[key].startswith("sha256:")
    finally:
        execution_engine.dispose()
        research_engine.dispose()


def _assert_real_research_watchlist_worker(es, rs, owner, operation_id, provenance, research_cutoff, physical_address):
    import json
    from uuid import uuid4
    from app.core import static_scopes
    from app.market_truth.identity import load_canonical_instrument
    from app.monitoring.repository import MonitoringRepository
    from app.monitoring.research_worker import activate_research_watchlist_row, evaluate_research_watchlist_row
    from app.monitoring.watchlist_config import WatchlistContext, WatchlistCommand, WatchlistSelection
    from app.monitoring.watchlist_store import write_watchlist_configuration
    from research_tests.test_canonical_dataset import _historical_capture_source, _research_prefix_publish
    from tests.test_v0_monitoring_read_routes import _client, _principal
    from app.db.models import Membership, User
    es.add(User(user_id='monitoring.user', email_normalized='monitoring@example.test', display_name='Monitoring tester'))
    es.flush()
    es.add(Membership(organization_id=owner, user_id='monitoring.user', role='owner', status='active'))
    es.commit()
    physical = load_canonical_instrument(es, physical_address)
    source = _historical_capture_source(es, count=4, owner=owner, project_id='project-v2', physical=physical,
        base_at=research_cutoff + dt.timedelta(days=1))
    rows = json.loads(source['raw_response'])['data']['candles']
    prefix, _ = _research_prefix_publish(es, rs, source, rows[:3], graph_input_fields={'frame': ('CLOSE',)})
    es.rollback()  # Start the command's reservation after the completed read-only acquisition.
    scope = static_scopes.create_scope(es, owner_id=owner, project_id='project-v2', name='Monitoring research',
        members=[physical.address], scope_id='scope.research-monitoring')
    context = WatchlistContext(project_id='project-v2', scope_id=scope['scope_id'],
        scope_revision=scope['snapshot']['revision'], scope_address=scope['address'], membership_address=scope['membership_address'])
    common = dict(owner_id=owner, created_by='monitoring.user', context=context,
        member={'kind': 'CANONICAL', 'instrument_address': physical.address}, now=prefix.cutoff_at)
    write_watchlist_configuration(es, **common, request_id=str(uuid4()),
        command=WatchlistCommand(operation='CONFIGURE', expected_revision=0,
            selection=WatchlistSelection(graph_id='v2.saved.research', graph_version=1, timeframe='15minute')))
    requested = write_watchlist_configuration(es, **common, request_id=str(uuid4()),
        command=WatchlistCommand(operation='MONITOR', expected_revision=1, flag=True))
    limits = dict(maximum_age_seconds=60, history_bytes_upper_bound=8*1024*1024,
        memory_bytes_upper_bound=8*1024*1024, cache_bytes_upper_bound=1024,
        queue_concurrency_upper_bound=1, event_rate_events=1, event_rate_per_seconds=60)
    from app.ir.evaluation_schedule import ScheduleRefusal
    with pytest.raises(ScheduleRefusal, match='resource ceiling exceeded: memory bytes'):
        activate_research_watchlist_row(es, rs, owner_id=owner, created_by='monitoring.user', requested=requested,
            operation_id=operation_id, admission_address=provenance['admission_address'],
            input_manifest_address=prefix.manifest_address, evaluation_limits=limits, request_id=str(uuid4()), now=prefix.cutoff_at)
    # Both registered analytical nodes together declare 8,455,680 bytes.
    limits['memory_bytes_upper_bound'] = 16*1024*1024
    bound = activate_research_watchlist_row(es, rs, owner_id=owner, created_by='monitoring.user', requested=requested,
        operation_id=operation_id, admission_address=provenance['admission_address'],
        input_manifest_address=prefix.manifest_address, evaluation_limits=limits, request_id=str(uuid4()), now=prefix.cutoff_at)
    repository = MonitoringRepository(es, owner_id=owner)
    initial = repository.get_latest_state(bound.assignment_id, physical.address)
    assert initial.snapshot_sequence == 0 and initial.entry_reference.value is None
    arguments = dict(owner_id=owner, requested=bound, operation_id=operation_id,
        input_manifest_address=prefix.manifest_address, display_symbol='SELF', cutoff_at=prefix.cutoff_at,
        publication_clock=lambda: prefix.cutoff_at)
    saved = evaluate_research_watchlist_row(es, rs, **arguments)
    assert len(saved) == 1 and saved[0].alert.action.value == 'BUY'
    assert saved[0].alert.admission_address == provenance['admission_address']
    assert saved[0].alert.stop_loss.status == saved[0].alert.take_profit.status == 'DISABLED'
    assert evaluate_research_watchlist_row(es, rs, **arguments) == ()
    es.commit()
    client = _client(es.get_bind(), _principal(owner, 'monitoring.user'), attributed=True)
    response = client.get('/api/v1/monitoring/alerts')
    assert response.status_code == 200, response.text
    item, = response.json()['items']
    assert item['schema'] == 'monitoring-research-alert-read/1'
    assert item['alert_address'] == saved[0].alert.address
    assert item['stop_loss'] == {'status': 'DISABLED', 'rules': []}
    assert item['simulated_position_state'] == 'FLAT'
    next_prefix, _ = _research_prefix_publish(es, rs, source, rows, graph_input_fields={'frame': ('CLOSE',)})
    es.rollback()
    arguments.update(input_manifest_address=next_prefix.manifest_address, cutoff_at=next_prefix.cutoff_at,
        publication_clock=lambda: next_prefix.cutoff_at)
    next_saved = evaluate_research_watchlist_row(es, rs, **arguments)
    assert len(next_saved) == 1 and next_saved[0].alert is None
    assert next_saved[0].snapshot.checkpoint.state.position is not None
    assert len(repository.list_alerts().items) == 1
    es.commit()


def _assert_research_monitoring_consumer(es, rs, owner, operation_id, provenance, pinned, evidence, monkeypatch):
    from app.monitoring import research_consumer as consumer
    arguments = dict(owner_id=owner, project_id='project-v2', graph_id='v2.saved.research',
        graph_version=1, admission_address=provenance['admission_address'],
        operation_id=operation_id, assignment_id='monitoring-research-test')
    if not pinned:
        with pytest.raises(consumer.ResearchMonitoringRefused) as failure:
            consumer.load_research_monitoring_context(es, rs, **arguments)
        assert failure.value.code == 'MONITORING_RESEARCH_FILL_SPREAD_UNBOUND'
        return
    context = consumer.load_research_monitoring_context(es, rs, **arguments)
    document = context.consumer.document
    assert document['execution_policy']['risk'] == evidence['documents']['risk']
    assert document['execution_policy']['risk']['risk_policy'] == 'none'
    assert document['execution_policy']['risk']['overlay']['risk_model'] is None
    assert document['slippage_pct'] == .0005
    assert document['original_admission_address'] == provenance['admission_address']
    assert document['original_dataset_address'] == provenance['dataset_manifest_address']
    assert document['original_risk_address'] == evidence['addresses']['risk_address']
    assert document['graph_version_address'] == context.graph.authored_ir_address
    assert document['initial_state'] == 'FLAT_AT_ACTIVATION'
    assert document['authority'] == 'NONE'
    assert consumer.load_research_monitoring_context(es, rs, **arguments).consumer.address == context.consumer.address
    for changes in ({'owner_id':'foreign-owner'}, {'project_id':'foreign-project'},
                    {'graph_version':2}, {'operation_id':'missing-operation'},
                    {'admission_address':'sha256:' + 'f'*64}):
        with pytest.raises(consumer.ResearchMonitoringRefused):
            consumer.load_research_monitoring_context(es, rs, **{**arguments, **changes})
    from app.backtest import identity
    from app.strategy import replay_decisions
    read = identity._module_bytes
    with monkeypatch.context() as patch:
        patch.setattr(identity, '_module_bytes', lambda module:
            read(module) + b'\n# changed consumer implementation\n' if module is replay_decisions else read(module))
        assert consumer.research_consumer_implementation_address() != document['consumer_implementation_address']


def _assert_produced_preparation_documents(evidence, projection, manifest, provenance, es, rs, owner):
    import json
    from app.core.strategy_admissions import get
    from app.engine.charges import CORRECTED_RESEARCH_CHARGE_SCHEDULE, charge_schedule_address
    from research.domain.admissions import load_admission
    docs = evidence["documents"]
    assert evidence["schema"] == "v2-research-preparation-evidence/1"
    assert docs["input"]["derivation_address"] == projection.derivation_address
    assert docs["evaluation_policy"]["event_start"] == projection.availability_index[0].isoformat()
    assert docs["evaluation_policy"]["event_end"] == projection.evaluation_window[1].isoformat()
    assert docs["slippage"] == {"schema":"research-slippage-assumption/1","basis_points":5.0,
        "challenge_multiplier":2.0,"application":"existing-research-kernel"}
    assert docs["risk"]["schema"] == "research-risk-assumption/1"
    assert docs["causal"]["scope"] == "prefix-consistency-on-selected-retrospective-dataset"
    expected = {
        "input_address": projection.input_digest, "dataset_address": manifest.manifest_address,
        "fee_address": charge_schedule_address(CORRECTED_RESEARCH_CHARGE_SCHEDULE),
        "slippage_address": content_address(docs["slippage"]), "risk_address": content_address(docs["risk"]),
        "parity_address": content_address({key: value for key, value in docs["parity"].items() if key != "result_address"}),
        "causal_evidence_address": content_address(docs["causal"]),
    }
    assert evidence["addresses"] == expected
    assert docs["input"]["input_bindings"] == _plain(projection.input_bindings.document)
    assert docs["parity"]["dataset_input_digest"] == projection.input_digest
    assert docs["causal"]["result_address"] == expected["parity_address"]
    execution = get(es, owner_id=owner, admission_address=provenance["admission_address"])
    research = load_admission(rs, owner_id=owner, admission_address=provenance["admission_address"])
    assert execution.artifact_json == research.artifact_json
    assert json.loads(execution.artifact_json)["base_v2_admission"]["evidence"] == expected


def _assert_corrupt_preparation_refuses(operation_id, owner, session):
    from research.domain.models import ResearchOperation
    from research.domain.operations import ResearchOperationRepository
    from research.orchestrator.v2_operation import V2OperationRefusal
    row = session.get(ResearchOperation, (owner, operation_id))
    original = row.preparation_evidence_json
    import copy
    import json
    wrong_owner = json.loads(original)
    wrong_owner["owner_id"] = "another-owner"
    wrong_owner["evidence_address"] = content_address({key: value for key, value in wrong_owner.items() if key != "evidence_address"})
    wrong_risk = copy.deepcopy(json.loads(original))
    wrong_risk["documents"]["risk"]["capital"] += 1
    wrong_risk["addresses"]["risk_address"] = content_address(wrong_risk["documents"]["risk"])
    wrong_risk["evidence_address"] = content_address({key: value for key, value in wrong_risk.items() if key != "evidence_address"})
    mutations = ["[", "{}", original.replace('"status":"COMPLETED"', '"status":"CANCELLED"'),
                 canonical_json(wrong_owner), canonical_json(wrong_risk)]
    for mutated in mutations:
        row.preparation_evidence_json = mutated
        session.commit()
        with pytest.raises(V2OperationRefusal, match="could not be verified"):
            ResearchOperationRepository(session).preparation_evidence(operation_id, owner_id=owner)
    row.preparation_evidence_json = original
    session.commit()


def _interrupt_preparation_after_execution_receipt(operation_id, owner, ExecutionSession, ResearchSession, monkeypatch):
    from sqlalchemy import select, func
    from research.domain.models import ResearchOperation, ExperimentRun
    from research.domain.operations import DurableOperationRecorder, ResearchOperationRepository
    from research.orchestrator.v2_preparation import prepare_operation
    import research.domain.admissions as admissions
    def interrupted(_session, _artifact):
        raise RuntimeError("synthetic interruption after execution admission commit")
    with ResearchSession() as rs, ExecutionSession() as es:
        repository = ResearchOperationRepository(rs)
        claim = repository.claim_operation(operation_id, owner_id=owner, worker_id="interrupted-preparation")
        recorder = DurableOperationRecorder(repository, owner_id=owner, operation_id=operation_id, token=claim.claim_token)
        def heartbeat(identifier, scoped_owner, token):
            with ResearchSession() as heartbeat_session:
                return ResearchOperationRepository(heartbeat_session).heartbeat(
                    identifier, owner_id=scoped_owner, token=token)
        recorder.start_watchdog(heartbeat)
        try:
            with monkeypatch.context() as patch:
                patch.setattr(admissions, "store_admission", interrupted)
                with pytest.raises(RuntimeError, match="synthetic interruption"):
                    prepare_operation(operation=claim, recorder=recorder, repository=repository,
                        execution_session=es, research_session=rs)
        finally:
            recorder.close_watchdog()
        rs.rollback()
        assert repository.preparation_evidence(operation_id, owner_id=owner) is not None
        assert rs.scalar(select(func.count()).select_from(ExperimentRun)) == 0
        row = rs.get(ResearchOperation, (owner, operation_id))
        row.claim_expires_at = dt.datetime.now(dt.UTC).replace(tzinfo=None) - dt.timedelta(seconds=1)
        rs.commit()
        assert not repository.claim_active(operation_id, owner_id=owner, token=claim.claim_token)


@pytest.mark.parametrize("side", ["availability", "opened"])
@pytest.mark.parametrize("fault", ["list", "duplicate", "unordered", "length"])
def test_position_projection_rejects_invalid_clocks_before_adapting(side, fault):
    from types import SimpleNamespace
    good = pd.date_range("2026-01-01T00:00:00Z", periods=2, freq="D")
    bad = {"list": list(good), "duplicate": pd.DatetimeIndex([good[0], good[0]]),
           "unordered": good[::-1], "length": good[:1]}[fault]
    available, opened = (bad, good) if side == "availability" else (good, bad)
    manifest = "sha256:" + "a" * 64
    position_map = content_address({"schema":"bar-open-position-map/1","dataset_manifest_address":manifest,
        "availability_index":[value.isoformat() for value in available],
        "bar_open_index":[value.isoformat() for value in opened]})
    adapter = SimpleNamespace(key="a", display_name="a", declared_warmup=0, adapter_address=manifest, adapter_policy_address=manifest)
    with pytest.raises(ValueError, match="V2_TIME_PROJECTION_MISMATCH"):
        _BarOpenPositionProjectionStrategy(adapter, manifest_address=manifest, availability_index=available,
            bar_open_index=opened, position_map_address=position_map)


def _assert_preparation_keeps_heartbeat_writable(operation_id, owner, ResearchSession, monkeypatch):
    import app.core.strategy_admissions as execution_admissions
    from research.domain.models import ResearchOperation
    from research.domain.operations import ResearchOperationRepository
    original_put = execution_admissions.put
    def checked_put(session, artifact):
        # A separate real writer must still work during expensive canonical validation.
        with ResearchSession() as heartbeat_session:
            row = heartbeat_session.get(ResearchOperation, (owner, operation_id))
            assert ResearchOperationRepository(heartbeat_session).heartbeat(
                operation_id, owner_id=owner, token=row.claim_token)
        return original_put(session, artifact)
    monkeypatch.setattr(execution_admissions, "put", checked_put)


def _saved_settings_request(Session, owner, body):
    from app.db.models import User
    from research.domain.settings import ResearchSettingsRepository
    fields = {key: body[key] for key in ("research_capital", "seed", "min_trades", "n_folds", "min_positive_fold_frac", "risk_policy")}
    with Session() as session:
        session.add(User(user_id="settings-author", email_normalized="bridge-settings@example.test", display_name="Author"))
        session.commit()
        repository = ResearchSettingsRepository(session)
        repository.update(owner_id=owner, created_by="settings-author", expected_revision=0,
            request_id="00000000-0000-4000-8000-000000000001", values={**fields, "seed": 0})
        repository.update(owner_id=owner, created_by="settings-author", graph_identifier="v2.saved.research",
            expected_revision=0, request_id="00000000-0000-4000-8000-000000000002", values={"seed": fields["seed"]})
    return {**{key: body[key] for key in ("request_id", "dataset_manifest_address", "dataset_as_of", "hypothesis")},
            "expected_workspace_revision": 1, "expected_strategy_revision": 1, "run_overrides": {}}


def _change_settings_after_queue(Session, owner):
    from research.domain.settings import ResearchSettingsRepository
    with Session() as session:
        repository = ResearchSettingsRepository(session)
        original = repository.read(owner_id=owner)
        repository.update(owner_id=owner, created_by="settings-author", expected_revision=1,
            request_id="00000000-0000-4000-8000-000000000003", values={**original["values"], "research_capital": 999999.0})


@pytest.mark.parametrize("snapshot_schema,active,expected", [
    ("research-settings-snapshot/1", False, None),
    ("research-settings-snapshot/2", False, .0005),
    ("research-settings-snapshot/2", True, .0005),
    ("research-settings-snapshot/3", False, .0005),
    ("research-settings-snapshot/3", True, .0005),
    ("research-settings-snapshot/1", True, .0005),
])
def test_new_settings_pin_fill_spread_while_old_snapshot_keeps_legacy_behavior(snapshot_schema, active, expected):
    from research.orchestrator.v2_preparation import execution_policy
    from research.orchestrator.v2_operation import _pinned_replay_slippage
    descriptor = {"settings_snapshot": {"schema": snapshot_schema},
                  "execution_policy": execution_policy(10000.0, stop_loss_pct=.01 if active else 0.0)}
    assert _pinned_replay_slippage(descriptor) == expected
    assert _pinned_replay_slippage({}) is None


def test_pinned_percentage_fill_does_not_read_mutable_runtime_slippage(monkeypatch):
    from types import SimpleNamespace
    from app.backtest import engine
    from research.evaluation import kernels
    from research.evaluation.walkforward import walk_forward
    from research.orchestrator.v2_operation import _pinned_replay_slippage
    from research.orchestrator.v2_preparation import execution_policy
    rows = [{"date": dt.datetime(2026, 8, 3, 9, 15) + dt.timedelta(minutes=15 * index),
        "open": 100.0, "high": 103.0, "low": 99.0, "close": 100.0,
        "longEntry": False, "shortEntry": False, "longExit": False, "shortExit": False} for index in range(5)]
    rows[0]["longEntry"] = True
    rows[2]["close"] = 102.1
    rows[3]["open"] = 103.0
    rows[4]["close"] = 101.0
    signals = pd.DataFrame(rows)
    policy = execution_policy(10000.0, stop_loss_pct=.01, take_profit_pct=.02)
    strategy = SimpleNamespace(protective_band_document=policy["risk"]["protective_band"],
        replay_slippage_pct=_pinned_replay_slippage({"execution_policy": policy}), risk_model=None, replay_policy=None)
    monkeypatch.setattr(kernels, "compute_signals", lambda *_args, **_kwargs: signals)
    monkeypatch.setattr(engine, "get_settings", lambda: pytest.fail("pinned replay read mutable fill assumptions"))
    inst = SimpleNamespace(key="PINNED_EQ", segment="NSE", lot_size=1)
    trade = walk_forward([], inst, strategy, {}, n_folds=1, capital=10000).folds[0].trades[0]
    assert trade.reason == "TARGET"
    assert trade.entry_price == pytest.approx(100.025)
    assert trade.exit_price == pytest.approx(102.97425)
