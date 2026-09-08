"""Three-field session-context grammar correction and transitive identity proof.

The session-data implementation remains a protected consumer.  This file proves
the closed registry grammar and the already accepted unpublished core58,
recursive17 and multi-output9 identity consequences without publishing them.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.ir import hashing, node_contracts, registry as registry_module
from app.ir.first_party.analytical_v2 import core_math, multi_output, recursive_state, remaining_oracles, session_data
from app.ir.first_party.analytical_v2.contracts import (
    ResolvedNodeContract,
    canonical_input_bindings,
    materialize_node_contract,
)
from app.ir.library import REGISTRY as DEFAULT_REGISTRY
from app.ir.registry import PlatformRegistry
from app.ir.resolve import resolve_v2
from app.ir.state_snapshots import (
    ResearchSnapshotRefusal,
    _create_research_snapshot_authority,
    create_research_checkpoint,
    restore_research_checkpoint,
)
from app.market_data.requirements import (
    DataRequirementPlan,
    DataRequirementRefusal,
    compile_data_requirement_plan,
    verify_data_requirement_plan,
)


ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / ".agent/runs/post-phase5-indicator-accuracy-session-context-binding-correction"
BEFORE = Path(os.environ.get("SESSION_CONTEXT_BASELINE", RUN / "pre-mutation.json"))
CATALOGUE = Path(os.environ.get(
    "SESSION_CONTEXT_CATALOGUE",
    ROOT / ".agent/runs/post-phase5-indicator-accuracy-correction-replan/current-catalogue.json",
))
SESSION_FIELDS = frozenset({"SESSION_ID", "SESSION_OPEN_AT", "SESSION_CLOSE_AT"})
WAVES = (core_math, recursive_state, multi_output)
REPRESENTATIVES = (
    (core_math, "SMA", {"window": 2}),
    (recursive_state, "EMA", {"window": 2}),
    (multi_output, "MACD", {"fast_length": 2, "slow_length": 3, "signal_length": 2, "source": "close"}),
)


def plain(value):
    if hasattr(value, "items"):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, frozenset)):
        return [plain(item) for item in value]
    return value


def closed(value):
    if isinstance(value, dict):
        return {key: closed(item) for key, item in value.items()}
    if isinstance(value, list):
        return tuple(closed(item) for item in value)
    return value


def address(label):
    return hashing.content_address({"session_context_binding_correction": label})


def combined_identities():
    records = {}
    for wave in WAVES:
        for key in sorted(wave.V2_COMPONENTS):
            marker = f"{key[0]}@{key[1]}"
            records[marker] = {
                "component_address": hashing.content_address(plain(wave.V2_COMPONENTS[key])),
                "source_contract_address": hashing.content_address(plain(wave.NODE_CONTRACTS[key])),
                "binding_source_contract_address": wave.CONTRACT_BINDINGS[key].source_contract_address,
                "binding_implementation_address": wave.CONTRACT_BINDINGS[key].implementation_address,
                "implementation_address": wave.V2_IMPLEMENTATIONS[key].implementation_address,
            }
    assert len(records) == 84
    return records


def parameters_for(wave, name, parameters=None):
    return plain(wave.parameters_for(name, parameters))


def fields_for(wave, name, parameters):
    return plain(
        wave.fields_by_port(name)
        if wave in {core_math, recursive_state, remaining_oracles}
        else wave.fields_by_port(name, parameters)
    )


def canonical_fact(*, role, fields, derived_local=False, session="INSTRUMENT_CALENDAR"):
    owner = "org.session-context-correction"
    return {
        "schema": "canonical-input-binding/1",
        "owner_id": owner,
        "dataset_context_address": address("dataset"),
        "evaluation_context_address": address("evaluation"),
        "dataset_manifest_address": address("manifest"),
        "market_truth_address": address("market-truth"),
        "provider_product_address": address("provider-product"),
        "provider_contract_address": address("provider-contract"),
        "canonical_instrument_address": address("instrument:" + role),
        "instrument": {"role": role, "type": "PHYSICAL"},
        "timeframe": 900,
        "fields": sorted(fields),
        "freshness": {"maximum_age_seconds": 900},
        "depth": {"kind": "NONE", "levels": None},
        "session": session,
        "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0},
        "derived_local": derived_local,
    }


def component_registry(wave, name):
    key = wave.component_key(name)
    return PlatformRegistry(
        components={},
        bodies={},
        registrations={},
        v2_types=wave.V2_TYPES,
        v2_components={key: wave.V2_COMPONENTS[key]},
        node_contracts={key: wave.NODE_CONTRACTS[key]},
        contract_bindings={key: wave.CONTRACT_BINDINGS[key]},
        v2_implementations={key: wave.V2_IMPLEMENTATIONS[key]},
    )


def graph_document(wave, name, parameters):
    key = wave.component_key(name)
    ports = plain(wave.V2_COMPONENTS[key]["ports"])
    inputs = [port for port in ports if port["direction"] == "input"]
    outputs = [port for port in ports if port["direction"] == "output"]
    return {
        "format_version": 2,
        "strategy_id": "session-context-identity-proof",
        "strategy_version": 1,
        "metadata": {"metadata_version": 1, "name": "Session context identity proof", "description": None, "tags": []},
        "graph_inputs": inputs,
        "graph_outputs": outputs,
        "nodes": [{"node_id": "probe", "component": {"component_id": key[0], "component_version": 2}, "parameters": parameters}],
        "edges": [
            {
                "edge_id": "input:" + port["port_id"],
                "source": {"scope": "graph_input", "port_id": port["port_id"]},
                "target": {"scope": "node", "node_id": "probe", "port_id": port["port_id"]},
                "binding": {"kind": "single"},
            }
            for port in inputs
        ] + [
            {
                "edge_id": "output:" + port["port_id"],
                "source": {"scope": "node", "node_id": "probe", "port_id": port["port_id"]},
                "target": {"scope": "graph_output", "port_id": port["port_id"]},
                "binding": {"kind": "single"},
            }
            for port in outputs
        ],
    }


def input_facts(wave, name, parameters, *, derived_local=False):
    return {
        port: canonical_fact(
            role="primary" if port == "frame" else port,
            fields=fields,
            derived_local=derived_local,
        )
        for port, fields in fields_for(wave, name, parameters).items()
    }


def input_context(facts):
    primary = facts["frame"]
    return canonical_input_bindings(
        owner_id=primary["owner_id"],
        dataset_context_address=primary["dataset_context_address"],
        evaluation_context_address=primary["evaluation_context_address"],
        bindings=facts,
        expected_source_addresses={key: hashing.content_address(value) for key, value in facts.items()},
    )


def compiled_case(wave, name, parameters=None, *, derived_local=False, facts=None):
    parameters = parameters_for(wave, name, parameters)
    facts = input_facts(wave, name, parameters, derived_local=derived_local) if facts is None else facts
    context = input_context(facts)
    source_registry = component_registry(wave, name)
    resolved = resolve_v2(graph_document(wave, name, parameters), source_registry)
    plan = compile_data_requirement_plan(resolved, registry=source_registry, input_bindings=context)
    verify_data_requirement_plan(plan, resolved, registry=source_registry, input_bindings=context)
    receipt = plain(plan.parameter_binding_provenance[0]["node_contract_binding"])
    return source_registry, resolved, context, plan, receipt


def state_snapshot(wave, name, parameters, receipt):
    bound = ResolvedNodeContract(receipt, receipt["bound_contract_address"])
    if wave is core_math:
        state = wave.CoreMathState(name, parameters, bound)
    elif wave is recursive_state:
        state = wave.RecursiveState(name, parameters, bound)
    else:
        state = wave.MultiOutputState(name, parameters, bound)
    row = {
        port: {field.lower(): 10.0 for field in fields}
        for port, fields in fields_for(wave, name, parameters).items()
    }
    state.step(row, event_time="2025-01-02T10:00:00Z")
    return plain(state.snapshot())


def protected_hashes():
    relative = (
        "paper-trader/backend/app/ir/node_contracts.py",
        "paper-trader/backend/app/ir/first_party/analytical_v2/contracts.py",
        "paper-trader/backend/app/market_data/requirements.py",
        "paper-trader/backend/app/ir/first_party/analytical_v2/core_math.py",
        "paper-trader/backend/app/ir/first_party/analytical_v2/recursive_state.py",
        "paper-trader/backend/app/ir/first_party/analytical_v2/multi_output.py",
        "paper-trader/backend/app/ir/first_party/analytical_v2/session_data.py",
    )
    return {item: hashlib.sha256((ROOT / item).read_bytes()).hexdigest() for item in relative}


def capture_before(destination):
    representatives = {}
    for wave, name, parameters in REPRESENTATIVES:
        _, resolved, _, plan, receipt = compiled_case(wave, name, parameters)
        representatives[wave.__name__.rsplit(".", 1)[-1]] = {
            "name": name,
            "parameters": parameters,
            "resolved_graph_address": resolved.resolved_graph_address,
            "plan": plain(vars(plan)),
            "receipt": receipt,
            "state": state_snapshot(wave, name, parameters, receipt),
        }
    catalogue = json.loads(CATALOGUE.read_text())
    assert len(catalogue["records"]) == 125
    payload = {
        "schema": "session-context-binding-pre-mutation/1",
        "registry_source_sha256": hashlib.sha256((ROOT / "paper-trader/backend/app/ir/registry.py").read_bytes()).hexdigest(),
        "data_fields": sorted(registry_module._DATA_FIELDS),
        "identities": combined_identities(),
        "representatives": representatives,
        "default_registry_snapshot_address": DEFAULT_REGISTRY.registry_snapshot_address,
        "legacy_catalogue_sha256": hashlib.sha256(CATALOGUE.read_bytes()).hexdigest(),
        "legacy_count": len(catalogue["records"]),
        "protected_hashes": protected_hashes(),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def before():
    data = json.loads(BEFORE.read_text())
    assert data["schema"] == "session-context-binding-pre-mutation/1"
    assert len(data["identities"]) == 84
    return data


def test_exact_three_field_closed_grammar():
    baseline = before()
    assert set(registry_module._DATA_FIELDS) - set(baseline["data_fields"]) == SESSION_FIELDS
    assert len(registry_module._DATA_FIELDS) == len(baseline["data_fields"]) + 3
    for field in SESSION_FIELDS:
        registry_module._validate_data_direct("field", field)
    for field in (
        "session_id", "Session_ID", "SESSION-ID", "SESSION_OPEN", "SESSION_CLOSE",
        "SESSION_TIMEZONE", "PROVIDER_SESSION_ID", "CAPABILITY_VERIFIED", "SESSION_ID ",
    ):
        with pytest.raises(ValueError):
            registry_module._validate_data_direct("field", field)
    for value in (True, None, {"field": "SESSION_ID"}, ["SESSION_ID"]):
        with pytest.raises((TypeError, ValueError)):
            registry_module._validate_data_direct("field", value)


@pytest.mark.parametrize("name", ["BARS_SINCE_SESSION_OPEN", "TIME_TO_SESSION_CLOSE"])
def test_real_materializer_and_compiler_accept_exact_local_session_context(name):
    _, _, _, plan, receipt = compiled_case(session_data, name, {}, derived_local=True)
    fields = {row["requirement"]["field"] for row in plan.requirements}
    assert fields <= SESSION_FIELDS and "SESSION_ID" in fields
    assert all(row["requirement"]["instrument"] == {"role": "primary", "type": "PHYSICAL"} for row in plan.requirements)
    assert all(row["requirement"]["session"] == "INSTRUMENT_CALENDAR" for row in plan.requirements)
    assert all(row["requirement"]["derived_local"] is True for row in plan.requirements)
    assert receipt["bound_contract_address"] == hashing.content_address({key: value for key, value in receipt.items() if key != "bound_contract_address"})


def session_case_with_facts(name="BARS_SINCE_SESSION_OPEN"):
    parameters = parameters_for(session_data, name, {})
    facts = input_facts(session_data, name, parameters, derived_local=True)
    source_registry, resolved, context, plan, receipt = compiled_case(
        session_data, name, parameters, facts=facts,
    )
    return parameters, facts, source_registry, resolved, context, plan, receipt


@pytest.mark.parametrize("forgery", ["role", "session", "derived_local", "field_case"])
def test_real_compiler_refuses_context_forgery_against_exact_plan(forgery):
    _, facts, source_registry, resolved, _, plan, _ = session_case_with_facts()
    forged = deepcopy(facts)
    if forgery == "role":
        forged["frame"]["instrument"]["role"] = "peer"
    elif forgery == "session":
        forged["frame"]["session"] = "CONTINUOUS"
    elif forgery == "derived_local":
        forged["frame"]["derived_local"] = False
    else:
        forged["frame"]["fields"] = ["SESSION_id" if item == "SESSION_ID" else item for item in forged["frame"]["fields"]]
    with pytest.raises((node_contracts.NodeContractRefusal, DataRequirementRefusal)):
        forged_context = input_context(forged)
        verify_data_requirement_plan(
            plan, resolved, registry=source_registry, input_bindings=forged_context,
        )


def test_real_materializer_refuses_forged_binding_address():
    parameters, _, source_registry, _, _, _, receipt = session_case_with_facts()
    forged = deepcopy(receipt["input_binding"])
    forged["ports"]["frame"]["binding_address"] = address("forged-binding-address")
    key = session_data.component_key("BARS_SINCE_SESSION_OPEN")
    with pytest.raises(node_contracts.NodeContractRefusal):
        materialize_node_contract(
            session_data.NODE_CONTRACTS[key], source_registry.contract_bindings[key], parameters, forged,
        )


def test_benchmark_ema_preserves_explicit_input_lineage_through_compile_and_state_replay():
    parameters = parameters_for(recursive_state, "EMA", {"window": 200})
    fact = canonical_fact(role="benchmark", fields=fields_for(recursive_state, "EMA", parameters)["frame"])
    context = canonical_input_bindings(
        owner_id=fact["owner_id"], dataset_context_address=fact["dataset_context_address"],
        evaluation_context_address=fact["evaluation_context_address"], bindings={"benchmark": fact},
        expected_source_addresses={"benchmark": hashing.content_address(fact)},
    )
    registry = component_registry(recursive_state, "EMA")
    graph = graph_document(recursive_state, "EMA", parameters)
    graph["graph_inputs"][0]["port_id"] = "benchmark"
    graph["edges"][0]["source"]["port_id"] = "benchmark"
    resolved = resolve_v2(graph, registry)
    plan = compile_data_requirement_plan(resolved, registry=registry, input_bindings=context)
    verify_data_requirement_plan(plan, resolved, registry=registry, input_bindings=context)
    receipt = plain(plan.parameter_binding_provenance[0]["node_contract_binding"])
    bound_input = receipt["input_binding"]["ports"]["frame"]
    assert bound_input["source"] == {"scope": "graph_input", "port_id": "benchmark"}
    assert bound_input["binding"] == fact
    assert bound_input["binding_address"] == hashing.content_address(fact)
    assert all(row["requirement"]["instrument"] == {"role": "benchmark", "type": "PHYSICAL"}
               for row in plan.requirements)
    bound = ResolvedNodeContract(receipt, receipt["bound_contract_address"])
    state = recursive_state.RecursiveState("EMA", parameters, bound)
    values = {field.lower(): 10.0 for field in fields_for(recursive_state, "EMA", parameters)["frame"]}
    state.step({"frame": values}, event_time="2025-01-02T10:00:00Z")
    snapshot = state.snapshot()
    restored = recursive_state.RecursiveState.restore("EMA", parameters, bound, snapshot)
    assert plain(restored.snapshot()) == plain(snapshot)


def test_explicit_secondary_role_still_refuses_readdressed_benchmark_input():
    parameters = parameters_for(core_math, "CROSS_ABOVE")
    facts = input_facts(core_math, "CROSS_ABOVE", parameters)
    assert "peer" in facts
    facts["peer"]["instrument"]["role"] = "benchmark"
    facts["peer"]["canonical_instrument_address"] = address("instrument:benchmark")
    with pytest.raises((node_contracts.NodeContractRefusal, DataRequirementRefusal), match="role"):
        compiled_case(core_math, "CROSS_ABOVE", parameters, facts=facts)


@pytest.mark.parametrize("role", ["primary", "benchmark"])
@pytest.mark.parametrize(("wave", "name", "state_type"), [
    (core_math, "SMA", core_math.CoreMathState),
    (multi_output, "MACD", multi_output.MultiOutputState),
    (session_data, "OHLCV", session_data.SessionDataState),
    (session_data, "BARS_SINCE_SESSION_OPEN", session_data.SessionDataState),
    (session_data, "OPENING_RANGE", session_data.SessionDataState),
    (session_data, "PREVIOUS_SESSION_FIELDS", session_data.SessionDataState),
    (session_data, "ANCHORED_VWAP", session_data.SessionDataState),
    (remaining_oracles, "EWMA_VOLATILITY", remaining_oracles.RemainingOracleState),
])
def test_local_resolution_role_replays_across_analytical_families(role, wave, name, state_type):
    parameters = parameters_for(wave, name, {"anchor_at": "2025-01-02T10:15:00+00:00"}
                                if name == "ANCHORED_VWAP" else None)
    ports = fields_for(wave, name, parameters)
    resolution_port = wave.NODE_CONTRACTS[wave.component_key(name)]["required_resolution"]["port"]
    facts = {port: canonical_fact(role=role if port == resolution_port else port, fields=fields,
                                 derived_local=port == "session") for port, fields in ports.items()}
    local = facts[resolution_port]
    context = canonical_input_bindings(owner_id=local["owner_id"],
        dataset_context_address=local["dataset_context_address"],
        evaluation_context_address=local["evaluation_context_address"], bindings=facts,
        expected_source_addresses={port: hashing.content_address(fact) for port, fact in facts.items()})
    registry = component_registry(wave, name)
    resolved = resolve_v2(graph_document(wave, name, parameters), registry)
    plan = compile_data_requirement_plan(resolved, registry=registry, input_bindings=context)
    verify_data_requirement_plan(plan, resolved, registry=registry, input_bindings=context)
    receipt = plain(plan.parameter_binding_provenance[0]["node_contract_binding"])
    assert receipt["input_binding"]["ports"][resolution_port]["binding"] == local
    assert {row["requirement"]["instrument"]["role"] for row in plan.requirements} == {
        fact["instrument"]["role"] for fact in facts.values()}
    bound = ResolvedNodeContract(receipt, receipt["bound_contract_address"])
    state = state_type(name, parameters, bound)
    context_values = {"session_id": "2025-01-02", "session_open_at": "2025-01-02T10:00:00+00:00",
                      "session_close_at": "2025-01-02T16:00:00+00:00"}
    values = {port: {field.lower(): context_values.get(field.lower(), 10.0) for field in fields}
              for port, fields in ports.items()}
    state.step(values, event_time="2025-01-02T10:15:00Z")
    snapshot = state.snapshot()
    restored = state_type.restore(name, parameters, bound, snapshot)
    assert plain(restored.snapshot()) == plain(snapshot)


@pytest.mark.parametrize(("value", "kind", "minimum", "maximum", "values"), [
    (None, "utc_timestamp", None, None, ()),
    ("2025-01-02T10:15:00Z", "utc_timestamp", None, None, ()),
    ("open", "enum", None, None, ("close",)),
    (True, "exact_integer", 1, 240, ()),
    (241, "exact_integer", 1, 240, ()),
])
def test_session_binding_parameter_guards_remain_exact(value, kind, minimum, maximum, values):
    with pytest.raises(ValueError):
        session_data._validate_binding_parameter(value, kind, minimum, maximum, values)


def test_secondary_role_and_fields_cannot_be_rewritten_by_materialization():
    from types import SimpleNamespace
    _, _, _, _, receipt = compiled_case(core_math, "CROSS_ABOVE")
    key = core_math.component_key("CROSS_ABOVE")
    parameters = parameters_for(core_math, "CROSS_ABOVE")
    source = core_math.NODE_CONTRACTS[key]
    registration = core_math.CONTRACT_BINDINGS[key]
    binding = deepcopy(receipt["input_binding"])
    binding["ports"]["peer"]["binding"]["instrument"]["role"] = "benchmark"
    binding["ports"]["peer"]["binding_address"] = hashing.content_address(binding["ports"]["peer"]["binding"])
    with pytest.raises(node_contracts.NodeContractRefusal, match="role"):
        materialize_node_contract(source, registration, parameters, binding)
    result = plain(registration.implementation(parameters, receipt["input_binding"]))
    result["required_market_fields"].append("benchmark.volume")
    wrong = SimpleNamespace(component=registration.component, source_contract_address=registration.source_contract_address,
        implementation_address=registration.implementation_address, implementation=lambda *_args: result)
    with pytest.raises(node_contracts.NodeContractRefusal, match="undeclared"):
        materialize_node_contract(source, wrong, parameters, receipt["input_binding"])


@pytest.mark.parametrize(("wave", "name"), [
    (core_math, "SMA"), (recursive_state, "EMA"), (remaining_oracles, "EWMA_VOLATILITY"),
])
def test_runtime_role_change_preserves_receipt_authority_checks(wave, name):
    parameters = parameters_for(wave, name)
    with pytest.raises(node_contracts.NodeContractRefusal, match="VERIFIED_BINDING_REQUIRED"):
        wave._check_bound(name, parameters, None)
    _, _, _, _, receipt = compiled_case(wave, name, parameters)
    receipt["resolved_contract"]["resource_profile"]["memory_bytes_upper_bound"] += 1
    receipt["bound_contract_address"] = hashing.content_address({key: value for key, value in receipt.items()
                                                                 if key != "bound_contract_address"})
    bound = ResolvedNodeContract(receipt, receipt["bound_contract_address"])
    with pytest.raises(node_contracts.NodeContractRefusal, match="BINDING_REPLAY_MISMATCH"):
        wave._check_bound(name, parameters, bound)


def test_local_clock_role_keeps_secondary_session_authority_and_fields_strict():
    session = canonical_fact(role="session", fields=["SESSION_ID"], derived_local=True)
    frame = canonical_fact(role="benchmark", fields=["CLOSE"])
    inputs = {"ports": {"frame": {"binding": frame}, "session": {"binding": session}}}
    fields = (("frame", ("CLOSE",)), ("session", ("SESSION_ID",)))
    assert session_data._validate_binding_ports(inputs, fields) == "frame"
    session_data._check_bound_port("session", "frame", ("SESSION_ID",), session)
    for changes in ({"instrument": {"role": "benchmark", "type": "PHYSICAL"}}, {"derived_local": False}):
        altered = {"ports": {**inputs["ports"], "session": {"binding": {**session, **changes}}}}
        with pytest.raises(ValueError):
            session_data._validate_binding_ports(altered, fields)
    for changes in ({"instrument": {"role": "benchmark", "type": "PHYSICAL"}}, {"fields": []},
                    {"alignment": {"kind": "ASOF_BACKWARD", "maximum_skew_seconds": 1}},
                    {"session": "CONTINUOUS"}, {"derived_local": False}):
        with pytest.raises(node_contracts.NodeContractRefusal, match="CANONICAL_BINDING_REQUIRED"):
            session_data._check_bound_port("session", "frame", ("SESSION_ID",), {**session, **changes})


def test_all_125_legacy_identities_and_default_snapshot_remain_exact():
    baseline = before()
    catalogue = json.loads(CATALOGUE.read_text())
    assert hashlib.sha256(CATALOGUE.read_bytes()).hexdigest() == baseline["legacy_catalogue_sha256"]
    assert len(catalogue["records"]) == baseline["legacy_count"] == 125
    assert DEFAULT_REGISTRY.registry_snapshot_address == baseline["default_registry_snapshot_address"]
    for row in catalogue["records"]:
        key = (row["component_id"], row["component_version"])
        assert plain(DEFAULT_REGISTRY.v2_components[key]) == row["descriptor"]
        assert plain(DEFAULT_REGISTRY.node_contracts[key]) == row["node_contract"]
        assert plain(DEFAULT_REGISTRY.data_requirement_declarations[key]) == row["data_requirement"]
        assert DEFAULT_REGISTRY.v2_implementation_registrations[key].implementation_address == row["implementation_address"]
        assert DEFAULT_REGISTRY.node_contract_addresses[key] == row["node_contract_address"]
        assert DEFAULT_REGISTRY.data_requirement_declaration_addresses[key] == row["data_requirement_address"]


def test_84_source_contracts_exact_and_transitive_implementations_move():
    baseline = before()["identities"]
    current = combined_identities()
    assert set(current) == set(baseline) and len(current) == 84
    assert all(current[key]["component_address"] == baseline[key]["component_address"] for key in current)
    assert all(current[key]["source_contract_address"] == baseline[key]["source_contract_address"] for key in current)
    assert all(current[key]["binding_source_contract_address"] == current[key]["source_contract_address"] for key in current)
    assert all(current[key]["binding_implementation_address"] == baseline[key]["binding_implementation_address"] for key in current)
    assert all(current[key]["implementation_address"] != baseline[key]["implementation_address"] for key in current)


@pytest.mark.parametrize("wave,name,parameters", REPRESENTATIVES)
def test_old_plan_receipt_and_state_refuse_after_transitive_identity_move(wave, name, parameters):
    baseline = before()["representatives"][wave.__name__.rsplit(".", 1)[-1]]
    _, resolved, context, current_plan, current_receipt = compiled_case(wave, name, parameters)
    old_plan = DataRequirementPlan(**baseline["plan"])
    with pytest.raises(DataRequirementRefusal):
        verify_data_requirement_plan(old_plan, resolved, registry=component_registry(wave, name), input_bindings=context)
    old_receipt = ResolvedNodeContract(baseline["receipt"], baseline["receipt"]["bound_contract_address"])
    assert old_receipt.bound_contract_address == current_receipt["bound_contract_address"]
    creation = address("checkpoint-creation:" + name)
    reset = hashing.content_address(plain(current_receipt["resolved_contract"]["state_reset_policy"]))
    old_authority = _create_research_snapshot_authority(
        strategy_address=address("strategy:" + name),
        resolved_graph_address=baseline["resolved_graph_address"],
        node_contract_address=baseline["receipt"]["source_contract_address"],
        implementation_closure_address=baseline["plan"]["implementation_closure_address"],
        dataset_context_address=baseline["receipt"]["input_binding"]["dataset_context_address"],
        evaluation_context_address=baseline["receipt"]["input_binding"]["evaluation_context_address"],
        reset_policy_address=reset,
        creation_evidence_address=creation,
        initial_state_payload={},
    )
    checkpoint = create_research_checkpoint(
        old_authority,
        closed(baseline["state"]),
        last_event_address=address("old-event:" + name),
        last_event_time="2025-01-02T10:00:00+00:00",
    )
    current_authority = _create_research_snapshot_authority(
        strategy_address=address("strategy:" + name),
        resolved_graph_address=resolved.resolved_graph_address,
        node_contract_address=current_receipt["source_contract_address"],
        implementation_closure_address=current_plan.implementation_closure_address,
        dataset_context_address=current_receipt["input_binding"]["dataset_context_address"],
        evaluation_context_address=current_receipt["input_binding"]["evaluation_context_address"],
        reset_policy_address=reset,
        creation_evidence_address=creation,
        initial_state_payload={},
    )
    with pytest.raises(ResearchSnapshotRefusal):
        restore_research_checkpoint(
            checkpoint,
            current_authority,
            next_event_address=address("next-event:" + name),
            next_event_time="2025-01-02T10:15:00+00:00",
        )
    assert current_plan.plan_address != baseline["plan"]["plan_address"]


def test_protected_inputs_remain_at_sealed_hashes():
    assert protected_hashes() == before()["protected_hashes"]


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--capture-before":
        capture_before(Path(sys.argv[2]).resolve())
    else:
        raise SystemExit("usage: test_indicator_accuracy_session_context_binding_correction.py --capture-before OUTPUT")
