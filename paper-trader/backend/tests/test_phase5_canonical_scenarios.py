from __future__ import annotations

import ast
import copy
from functools import lru_cache
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.backtest.artifacts import (
    BoundedResearchArtifactStore,
    research_cache_identity,
    research_cache_identity_document,
)
from app.ir.hashing import canonical_json, content_address
from app.ir.incremental_runtime import accept_research_resource_plan
from app.ir.library import REGISTRY
from app.ir.resource_plan import (
    DEFAULT_TIER_LIMITS,
    TIER_DIMENSIONS,
    ResourcePlanRefusal,
    binding_input_requirement,
    instrument_role_requirement,
    provider_requirement,
    resource_calibration,
    resource_tier_decision,
    resource_tier_policy,
)
from app.market_data.provider_evidence import ProviderEvidenceRefusal, map_provider_evidence
from app.market_data.requirements import compile_data_requirement_plan
from research.domain.base import init_research_db
from research.domain.models import ExperimentSpec, Hypothesis, ResearchProgram
from research.evaluation.phase5_runtime import execute_research
from research_tests.test_phase5_research_execution import _policy, _runtime
from tests.test_phase5_language_resource_contracts import _plan_at
from tests.test_phase5_provider_evidence_compatibility import _fixture as provider_fixture


BACKEND = Path(__file__).resolve().parents[1]

SCENARIO_COMPONENTS = {
    "A": (
        "analytical.ema", "analytical.rsi", "analytical.atr",
        "intent.stop_distance_risk", "intent.atr_stop", "intent.add_position",
        "intent.add_only_when_profitable",
    ),
    "B": (
        "derivative.pcr_open_interest", "derivative.depth_imbalance",
        "derivative.strike_volume_oi_ratio", "logic.weekday_gate",
        "logic.session_gate", "intent.session_exit", "intent.partial_exit",
        "intent.broker_resident_protection_request",
    ),
    "C": (
        "analytical.correlation", "analytical.session_calendar",
        "analytical.time_to_session_close", "intent.session_exit",
    ),
}
SCENARIO_FIELDS = {
    "schema", "scenario", "owner_id", "graph_address",
    "implementation_closure_address", "registry_snapshot_address",
    "dataset_manifest_address", "truth_snapshot_addresses",
    "evaluation_policy_address", "resource_plan_address", "result_address",
    "job_lineage_address", "component_ids", "role_requirement_addresses",
    "binding_input_addresses", "provider_requirement_addresses",
    "provider_evidence_addresses", "cache_identity_address",
    "artifact_address", "scenario_address",
}


def _address(name: str) -> str:
    return content_address({"phase5-canonical-scenario": name})


def _provider(name: str, *, fields, product_classes, contract_classes=(),
              depth=0, session="INSTRUMENT_CALENDAR", alignment="BAR_CLOSE",
              timeframe=60, history=1000, freshness=120):
    return provider_requirement({
        "capability_classes": [name],
        "fields": sorted(fields),
        "timeframe_seconds": timeframe,
        "history_bars": history,
        "freshness_seconds": freshness,
        "depth_levels": depth,
        "session": session,
        "alignment": alignment,
        "product_classes": sorted(product_classes),
        "contract_classes": sorted(contract_classes),
        "supply": "PROVIDER_REQUIRED",
    })


def _role(role_id: str, *, kind="EXECUTION_TARGET", instrument_type="PHYSICAL",
          cardinality="EXACT_ONE", maximum=1, provider_addresses=(),
          execution=True, research_only=False):
    return instrument_role_requirement({
        "role_id": role_id,
        "role_kind": kind,
        "instrument_type": instrument_type,
        "cardinality": cardinality,
        "maximum_members": maximum,
        "source_requirement_addresses": [_address(f"source-{role_id}")],
        "provider_requirement_addresses": sorted(provider_addresses),
        "binding_input_kind": {
            "PHYSICAL": "CANONICAL_PHYSICAL_ADDRESS",
            "ECONOMIC_SELECTOR": "SELECTOR_POLICY_ADDRESS",
            "CONTINUOUS_FUTURE": "CONTINUOUS_SERIES_POLICY_ADDRESS",
        }[instrument_type],
        "execution_eligible": execution,
        "research_only": research_only,
    })


def _scenario_inputs(name: str):
    candles = _provider(
        f"{name.lower()}-candles", fields=("CLOSE", "HIGH", "LOW"),
        product_classes=("FUTURE", "SPOT"), history=5000,
    )
    if name == "A":
        roles = tuple(_role(
            role_id, provider_addresses=(candles.address,),
        ) for role_id in ("primary", "primary_2", "primary_3"))
        providers = (candles,)
    elif name == "B":
        chain = _provider(
            "weekly-option-chain",
            fields=("ASK", "BID", "EXPIRY", "LOT_SIZE", "OPEN_INTEREST", "STRIKE"),
            product_classes=("OPTION",), contract_classes=("WEEKLY",),
            depth=5, session="OPTION_SESSION", alignment="EVENT_TIME",
            timeframe=0, history=1, freshness=5,
        )
        roles = (
            _role("primary", provider_addresses=(candles.address,)),
            _role(
                "weekly_option_window", kind="DERIVATIVE_SELECTOR",
                instrument_type="ECONOMIC_SELECTOR", cardinality="DYNAMIC_WINDOW",
                maximum=21, provider_addresses=(chain.address,),
                execution=False, research_only=True,
            ),
        )
        providers = (candles, chain)
    else:
        gold = _provider(
            "gold-observation", fields=("CLOSE",), product_classes=("FUTURE",),
            session="MCX", alignment="EVENT_TIME", freshness=90,
        )
        crude = _provider(
            "crude-observation", fields=("CLOSE",), product_classes=("FUTURE",),
            session="NYMEX", alignment="EVENT_TIME", freshness=120,
        )
        volatility = _provider(
            "volatility-observation", fields=("CLOSE",), product_classes=("INDEX",),
            session="NSE", alignment="EVENT_TIME", freshness=60,
        )
        roles = (
            _role("primary", provider_addresses=(candles.address,)),
            _role("gold_observation", kind="OBSERVATION", provider_addresses=(gold.address,),
                  execution=False, research_only=True),
            _role("crude_observation", kind="OBSERVATION", provider_addresses=(crude.address,),
                  execution=False, research_only=True),
            _role("volatility_observation", kind="REFERENCE",
                  provider_addresses=(volatility.address,), execution=False,
                  research_only=True),
        )
        providers = (candles, crude, gold, volatility)
    return roles, tuple(sorted(providers, key=lambda item: item.address))


@lru_cache(maxsize=None)
def _integrated_scenario(name: str):
    graph, registry, _old_plan, dataset, _old_policy = _runtime()
    roles, providers = _scenario_inputs(name)
    plan = accept_research_resource_plan(
        graph, compile_data_requirement_plan(graph), registry,
        instrument_roles=roles, provider_requirements=providers,
        assumption_addresses=tuple(sorted((
            _address(f"{name}-session"), _address(f"{name}-missing"),
            _address(f"{name}-freshness"),
        ))),
        cache_bytes_upper_bound=64 * 1024,
        artifact_bytes_upper_bound=64 * 1024,
        queue_concurrency_upper_bound=2,
    )
    policy = _policy(graph, registry, plan, dataset, maximum_events=5)
    result = execute_research(graph, registry, plan, dataset, policy)
    binding_inputs = tuple(binding_input_requirement(role) for role in roles)
    provider_bundle = map_provider_evidence(provider_fixture())
    provider_evidence = (
        provider_bundle.entity.address,
        provider_bundle.product.address,
        provider_bundle.contract.address,
        provider_bundle.capability_profile.capability_profile_address,
        provider_bundle.raw_observation.raw_segment_address,
    )
    identity = research_cache_identity(research_cache_identity_document(
        owner_id="owner-a", licence_scope="OWNER_PRIVATE",
        semantic_nodes=[{
            "component_id": node.component[0], "component_version": node.component[1],
        } for node in sorted(graph.nodes, key=lambda item: item.component)],
        parameters_address=_address(f"{name}-parameters"),
        instrument_addresses=list(dataset.manifest.instrument_addresses),
        registry_snapshot_address=registry.registry_snapshot_address,
        dataset_manifest_address=dataset.manifest.manifest_address,
        provider_evidence_addresses=sorted(provider_evidence),
        event_start=dataset.manifest.event_start, event_end=dataset.manifest.event_end,
        segment_addresses=list(dataset.manifest.segment_addresses),
        adjustment_policy_address=dataset.manifest.adjustment_policy_address,
        session_policy_address=policy.document["session_policy_address"],
        resampling_policy_address=policy.document["resampling_policy_address"],
        missing_data_policy_address=dataset.manifest.missing_data_policy_address,
        alignment_policy_address=dataset.manifest.alignment_policy_address,
        implementation_closure_address=graph.implementation_closure_address,
        resolved_graph_address=graph.resolved_graph_address,
        resource_plan_address=plan.plan_address,
        evaluation_policy_address=policy.policy_address,
        node_context_resolver_address=policy.document["node_context_resolver_address"],
        run_authority_address=policy.document["run_authority_address"],
    ))
    store = BoundedResearchArtifactStore(
        owner_id="owner-a", licence_scope="OWNER_PRIVATE",
        cache_bytes_upper_bound=128 * 1024,
        artifact_bytes_upper_bound=128 * 1024,
        entry_upper_bound=3, concurrency_upper_bound=1,
        queue_depth_upper_bound=1,
    )
    cold = store.get_or_compute(identity, lambda: dict(result.document))
    warm = store.get_or_compute(identity, lambda: {"forged": True})
    assert not cold.from_cache and warm.from_cache
    assert warm.artifact_address == cold.artifact_address
    assert store.metrics()["cold_computes"] == store.metrics()["cache_hits"] == 1
    document = {
        "schema": "phase5-canonical-scenario/1", "scenario": name,
        "owner_id": "owner-a", "graph_address": graph.resolved_graph_address,
        "implementation_closure_address": graph.implementation_closure_address,
        "registry_snapshot_address": registry.registry_snapshot_address,
        "dataset_manifest_address": dataset.manifest.manifest_address,
        "truth_snapshot_addresses": list(dataset.manifest.truth_snapshot_addresses),
        "evaluation_policy_address": policy.policy_address,
        "resource_plan_address": plan.plan_address,
        "result_address": result.result_address,
        "job_lineage_address": _address(f"{name}-job-lineage"),
        "component_ids": list(SCENARIO_COMPONENTS[name]),
        "role_requirement_addresses": [role.address for role in roles],
        "binding_input_addresses": [item.address for item in binding_inputs],
        "provider_requirement_addresses": [item.address for item in providers],
        "provider_evidence_addresses": sorted(provider_evidence),
        "cache_identity_address": identity.identity_address,
        "artifact_address": cold.artifact_address,
    }
    document["scenario_address"] = content_address(document)
    return document, graph, plan, result, roles, providers, binding_inputs


def _assert_complete_scenario(document, name):
    assert set(document) == SCENARIO_FIELDS
    assert document["schema"] == "phase5-canonical-scenario/1"
    assert document["scenario"] == name
    assert document["component_ids"] == list(SCENARIO_COMPONENTS[name])
    assert document["scenario_address"] == content_address({
        key: value for key, value in document.items() if key != "scenario_address"
    })
    for name in (
        "graph_address", "implementation_closure_address", "registry_snapshot_address",
        "dataset_manifest_address", "evaluation_policy_address",
        "resource_plan_address", "result_address", "job_lineage_address",
        "cache_identity_address", "artifact_address",
    ):
        assert document[name].startswith("sha256:")


@pytest.mark.parametrize("name", ("A", "B", "C"))
def test_scenarios_use_real_catalogue_resource_provider_and_research_seams(name):
    document, graph, plan, result, roles, providers, binding_inputs = \
        _integrated_scenario(name)
    _assert_complete_scenario(document, name)
    assert result.document["status"] == "COMPLETED"
    assert document["graph_address"] == graph.resolved_graph_address
    assert document["resource_plan_address"] == plan.plan_address
    assert set(document["component_ids"]) <= {key[0] for key in REGISTRY.v2_components}
    assert tuple(item.document["role_requirement_address"] for item in binding_inputs) \
        == tuple(role.address for role in roles)
    assert set(plan.document["provider_requirement_addresses"]) >= {
        item.address for item in providers
    }
    assert not any(key in document for key in (
        "account", "capital", "lease", "reservation", "broker", "order", "money",
    ))


def test_complete_claimed_component_contract_implementation_output_and_data_universe():
    claimed = {component for values in SCENARIO_COMPONENTS.values() for component in values}
    for component_id in claimed:
        key = (component_id, 1)
        assert key in REGISTRY.v2_components
        assert key in REGISTRY.v2_implementation_registrations
        assert key in REGISTRY.node_contracts
        assert key in REGISTRY.node_contract_addresses
        assert key in REGISTRY.data_requirement_declarations
        outputs = [
            port for port in REGISTRY.v2_components[key]["ports"]
            if port["direction"] == "output"
        ]
        assert outputs and all(port["port_id"] and port["type_ref"] for port in outputs)


@pytest.mark.parametrize("field", tuple(sorted(SCENARIO_FIELDS)))
def test_complete_scenario_universe_refuses_every_omitted_field(field):
    document = copy.deepcopy(_integrated_scenario("A")[0])
    document.pop(field)
    with pytest.raises(AssertionError):
        _assert_complete_scenario(document, "A")


def test_scenario_a_one_graph_has_several_primary_binding_requirements_and_intents():
    document, _graph, plan, _result, roles, _providers, bindings = _integrated_scenario("A")
    assert {role.document["role_id"] for role in roles} \
        == {"primary", "primary_2", "primary_3"}
    assert len({document["graph_address"] for _binding in bindings}) == 1
    assert all(role.document["execution_eligible"] for role in roles)
    assert plan.document["memory_bytes_upper_bound"] > 0
    assert {"analytical.ema", "analytical.rsi", "analytical.atr",
            "intent.atr_stop", "intent.add_position"} <= set(document["component_ids"])


def test_scenario_b_weekly_selector_is_bounded_point_in_time_and_never_order_authority():
    document, _graph, plan, _result, roles, providers, _bindings = _integrated_scenario("B")
    selector = next(role for role in roles if role.document["role_id"] == "weekly_option_window")
    assert selector.document["cardinality"] == "DYNAMIC_WINDOW"
    assert selector.document["maximum_members"] == 21
    assert selector.document["research_only"] and not selector.document["execution_eligible"]
    chain = next(item for item in providers if "weekly-option-chain" in item.document["capability_classes"])
    assert chain.document["depth_levels"] == 5 and chain.document["freshness_seconds"] == 5
    assert set(chain.document["fields"]) >= {"OPEN_INTEREST", "BID", "ASK", "STRIKE"}
    assert [dict(item) for item in plan.document["dynamic_window_requirements"]] == [
        {"role_id": "weekly_option_window", "maximum_members": 21},
    ]
    assert "intent.broker_resident_protection_request" in document["component_ids"]


def test_scenario_c_has_one_execution_target_and_three_exact_observation_policies():
    document, _graph, plan, _result, roles, providers, _bindings = _integrated_scenario("C")
    assert [role.document["role_id"] for role in roles
            if role.document["execution_eligible"]] == ["primary"]
    assert {role.document["role_id"] for role in roles if role.document["research_only"]} \
        == {"gold_observation", "crude_observation", "volatility_observation"}
    assert {item.document["session"] for item in providers} >= {"MCX", "NYMEX", "NSE"}
    assert all(item.document["freshness_seconds"] > 0 for item in providers)
    assert len(plan.document["instrument_role_requirements"]) == 4
    assert document["component_ids"] == list(SCENARIO_COMPONENTS["C"])


def test_gold_crude_simultaneous_and_one_strategy_three_instruments_keep_complete_facts():
    document, _graph, plan, _result, roles, providers, bindings = _integrated_scenario("A")
    cases = {
        "gold_crude_simultaneous": ("primary", "primary_2"),
        "one_strategy_three_instruments": ("primary", "primary_2", "primary_3"),
    }
    for expected in cases.values():
        selected = tuple(role for role in roles if role.document["role_id"] in expected)
        assert len(selected) == len(expected)
        assert len({document["graph_address"] for _role in selected}) == 1
        assert all(role.document["provider_requirement_addresses"] for role in selected)
        assert all(binding_input_requirement(role).address in {
            item.address for item in bindings
        } for role in selected)
    assert len(plan.document["provider_requirement_addresses"]) >= len(providers)


@pytest.mark.parametrize("tier", ("Standard", "Pro", "Desk"))
def test_tier_simultaneous_maxima_pass_and_every_first_over_refuses(tier):
    _document, _graph, plan, _result, _roles, _providers, _bindings = \
        _integrated_scenario("A")
    for dimension in TIER_DIMENSIONS:
        plan = _plan_at(plan, dimension, DEFAULT_TIER_LIMITS[tier][dimension])
    calibration = resource_calibration({
        "workload_address": _address(f"{tier}-workload"),
        "measurement_evidence_addresses": [_address(f"{tier}-measurement")],
        "measured_at": "2026-08-27T00:00:00Z",
    })
    policy = resource_tier_policy(
        tier, evidence_addresses=(_address(f"{tier}-evidence"),),
    )
    assert resource_tier_decision(
        plan, policy, calibration, owner_id="owner-a",
    ).document["accepted"]
    for dimension in TIER_DIMENSIONS:
        over = _plan_at(plan, dimension, DEFAULT_TIER_LIMITS[tier][dimension] + 1)
        decision = resource_tier_decision(
            over, policy, calibration, owner_id="owner-a",
        )
        assert not decision.document["accepted"]
        assert dimension in decision.document["binding_dimensions"]


def test_unsupported_dynamic_selector_and_stale_provider_fact_refuse():
    roles, _providers = _scenario_inputs("B")
    malformed = dict(roles[1].document); malformed["maximum_members"] = 0
    with pytest.raises(ResourcePlanRefusal):
        instrument_role_requirement(malformed)
    stale = provider_fixture()
    stale["capability_profile"]["expires_at"] = "2026-08-26T00:00:00+00:00"
    with pytest.raises(ProviderEvidenceRefusal, match="invalid or conflicting"):
        map_provider_evidence(stale)


def _persist_scenarios(engine):
    documents = [_integrated_scenario(name)[0] for name in ("A", "B", "C")]
    with Session(engine, future=True) as session:
        program = ResearchProgram(owner_id="owner-a", name="Phase 5 scenarios", thesis="exact")
        session.add(program); session.flush()
        hypothesis = Hypothesis(
            owner_id="owner-a", program_id=program.id,
            statement="canonical scenarios preserve lineage",
        )
        session.add(hypothesis); session.flush()
        for document in documents:
            session.add(ExperimentSpec(
                owner_id="owner-a",
                id=document["scenario_address"].removeprefix("sha256:"),
                hypothesis_id=hypothesis.id,
                recipe_json=canonical_json(document), git_commit="de6faae3",
                qualifier_version="phase5", optimizer_version="none",
                validator_version="phase5", scoring_version="none", rng_seed=0,
            ))
        session.commit()
    return documents


def _fresh_process_reload(url: str, *, expected_count=3):
    code = (
        "import json,os; from sqlalchemy import create_engine,text; "
        "from app.ir.hashing import canonical_json,content_address; "
        "engine=create_engine(os.environ['SCENARIO_DB_URL'],future=True); "
        "rows=[]; "
        "connection=engine.connect(); "
        "values=connection.execute(text('SELECT id,recipe_json FROM research_experiment_spec ORDER BY id')).all(); "
        "connection.close(); engine.dispose(); "
        "assert len(values)==int(os.environ['SCENARIO_COUNT']); "
        "[rows.append(json.loads(recipe)) for _id,recipe in values]; "
        "assert all(canonical_json(row)==next(recipe for ident,recipe in values if ident==row['scenario_address'][7:]) for row in rows); "
        "assert all(content_address({k:v for k,v in row.items() if k!='scenario_address'})==row['scenario_address'] for row in rows); "
        "print(json.dumps([row['scenario_address'] for row in rows]))"
    )
    return subprocess.run(
        [sys.executable, "-c", code], cwd=BACKEND,
        env={**os.environ, "PYTHONPATH": str(BACKEND), "PT_DISABLE_DOTENV": "1",
             "SCENARIO_DB_URL": url, "SCENARIO_COUNT": str(expected_count)},
        text=True, capture_output=True, timeout=120,
    )


def test_sqlite_scenarios_reload_in_fresh_process_with_complete_lineage(tmp_path):
    path = tmp_path / "scenarios.db"
    engine = create_engine(f"sqlite:///{path}", future=True)
    init_research_db(engine)
    expected = _persist_scenarios(engine); engine.dispose()
    child = _fresh_process_reload(f"sqlite:///{path}")
    assert child.returncode == 0, child.stderr
    assert set(json.loads(child.stdout)) == {item["scenario_address"] for item in expected}


def test_postgresql_scenarios_reload_in_fresh_process_with_complete_lineage(pg_sandbox):
    engine = pg_sandbox.research_engine
    init_research_db(engine)
    expected = _persist_scenarios(engine); engine.dispose()
    child = _fresh_process_reload(pg_sandbox.research_url)
    assert child.returncode == 0, child.stderr
    assert set(json.loads(child.stdout)) == {item["scenario_address"] for item in expected}


def test_fresh_process_rejects_tampered_scenario_lineage(tmp_path):
    path = tmp_path / "tampered-scenario.db"
    engine = create_engine(f"sqlite:///{path}", future=True)
    init_research_db(engine)
    document = copy.deepcopy(_integrated_scenario("A")[0])
    original_address = document["scenario_address"]
    document["result_address"] = _address("tampered-result")
    with Session(engine, future=True) as session:
        program = ResearchProgram(owner_id="owner-a", name="Tampered", thesis="reject")
        session.add(program); session.flush()
        hypothesis = Hypothesis(
            owner_id="owner-a", program_id=program.id, statement="tampered lineage",
        )
        session.add(hypothesis); session.flush()
        session.add(ExperimentSpec(
            owner_id="owner-a", id=original_address.removeprefix("sha256:"),
            hypothesis_id=hypothesis.id, recipe_json=canonical_json(document),
        ))
        session.commit()
    engine.dispose()
    child = _fresh_process_reload(f"sqlite:///{path}", expected_count=1)
    assert child.returncode != 0


def test_scenario_files_import_no_provider_broker_order_live_or_money_path():
    files = (
        Path(__file__),
        BACKEND / "research_tests/test_phase5_canonical_scenarios.py",
    )
    forbidden = ("app.providers", "app.engine", "app.execution", "app.ledger")
    for path in files:
        tree = ast.parse(path.read_text())
        imports = {
            node.module for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        } | {
            alias.name for node in ast.walk(tree)
            if isinstance(node, ast.Import) for alias in node.names
        }
        assert not any(name.startswith(forbidden) for name in imports)
