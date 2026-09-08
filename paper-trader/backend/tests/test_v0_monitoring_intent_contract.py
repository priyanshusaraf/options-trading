"""Owner proof for registered monitoring value contracts; no activation authority."""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
import pandas as pd

from app.ir import hashing, node_contracts, schema, validity
from app.ir.first_party import execution_intent
from app.ir.first_party import monitoring_intent_v2 as subject
from app.ir.library import REGISTRY as DEFAULT_REGISTRY, V2_CONTRIBUTORS
from app.ir.registry import PlatformRegistry
from app.core.release_profile import manifest


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "paper-trader/backend/app/ir/first_party/monitoring_intent_v2.py"
EXPECTED_SCOPE = {
    "BUY", "SELL", "ENTER_LONG", "ENTER_SHORT", "CLOSE_POSITION", "SESSION_EXIT",
    "EXPIRY_EXIT", "FIXED_STOP_PERCENT", "POINT_STOP", "ATR_STOP",
    "TAKE_PROFIT_PERCENT", "RISK_REWARD_TARGET",
}
TARGETS = {
    "BUY": ("LONG", False), "ENTER_LONG": ("LONG", False),
    "SELL": ("SHORT", False), "ENTER_SHORT": ("SHORT", False),
    "CLOSE_POSITION": ("FLAT", True), "SESSION_EXIT": ("FLAT", True),
    "EXPIRY_EXIT": ("FLAT", True),
}
PARAMETERS = {
    "FIXED_STOP_PERCENT": {"rate": "0.125"}, "POINT_STOP": {"distance": "25.5"},
    "ATR_STOP": {"multiplier": "1.5"}, "TAKE_PROFIT_PERCENT": {"rate": "0.25"},
    "RISK_REWARD_TARGET": {"ratio": "3"},
}
PARAMETER_BOUNDS = {
    "FIXED_STOP_PERCENT": ("rate", "0.000001", "0.999999", "1"),
    "POINT_STOP": ("distance", "0.000001", "1000000000000", "1000000000000.000001"),
    "ATR_STOP": ("multiplier", "0.000001", "100", "100.000001"),
    "TAKE_PROFIT_PERCENT": ("rate", "0.000001", "100", "100.000001"),
    "RISK_REWARD_TARGET": ("ratio", "0.000001", "100", "100.000001"),
}
PROTECTION_EXPECTED = {
    "FIXED_STOP_PERCENT": ("STOP_LOSS", "PERCENT_FROM_ENTRY_REFERENCE", "0.125", "RATE"),
    "POINT_STOP": ("STOP_LOSS", "DISTANCE_FROM_ENTRY_REFERENCE", "25.5", "PRICE_POINTS"),
    "ATR_STOP": ("STOP_LOSS", "VERIFIED_INDICATOR_DISTANCE", "3.75", "PRICE_POINTS"),
    "TAKE_PROFIT_PERCENT": ("TAKE_PROFIT", "PERCENT_FROM_ENTRY_REFERENCE", "0.25", "RATE"),
    "RISK_REWARD_TARGET": ("TAKE_PROFIT", "DISTANCE_FROM_ENTRY_REFERENCE", "7.5", "PRICE_POINTS"),
}
FORBIDDEN = {
    "account", "allocation", "armed", "broker", "broker_account", "capital", "deployment",
    "execution", "fill", "lease", "live", "money", "order", "position", "quantity",
    "reservation", "route", "tradingsymbol",
}


def plain(value): return node_contracts._plain(value)
def condition(value=True): return validity.valid(value)


def monitoring_series_graph():
    """Real published comparison, authored projection and monitoring terminals."""
    from app.ir.resolve import resolve_v2

    def boundary(name, direction, type_id, version, shape):
        port = plain(subject._port(name, direction, type_id, "value"))
        port.update(type_ref={"type_id": type_id, "type_version": version}, shape=shape)
        return port

    nodes = [("compare", "strategy_math.gt", 1, {}),
             ("project", "monitoring.final_prefix_condition", 1, {}),
             ("buy", "intent.buy", 2, {}),
             ("stop", "intent.fixed_stop_percent", 2, {"rate": "0.01"}),
             ("target", "intent.take_profit_percent", 2, {"rate": "0.02"})]
    edges = []

    def edge(source, target):
        edges.append({"edge_id": f"e{len(edges)}", "source": source,
                      "target": target, "binding": {"kind": "single"}})

    def endpoint(node, port):
        return {"scope": "node", "node_id": node, "port_id": port}

    for name in ("left", "right"):
        edge({"scope": "graph_input", "port_id": name}, endpoint("compare", name))
    edge(endpoint("compare", "value"), endpoint("project", "series"))
    outputs = [boundary("history", "output", "analytical.float64", 2, "series")]
    edge({"scope": "graph_input", "port_id": "left"}, {"scope": "graph_output", "port_id": "history"})
    for node, port, type_id in (("buy", "intent", "monitoring.target_intent"),
                                ("stop", "protection", "monitoring.protection"),
                                ("target", "protection", "monitoring.protection")):
        edge(endpoint("project", "condition"), endpoint(node, "condition"))
        edge(endpoint(node, port), {"scope": "graph_output", "port_id": node})
        outputs.append(boundary(node, "output", type_id, 1, "scalar"))
    document = {"format_version": 2, "strategy_id": "authored-monitoring-prefix", "strategy_version": 1,
                "metadata": {"metadata_version": 1, "name": "Authored condition", "description": None, "tags": []},
                "graph_inputs": [boundary(name, "input", "analytical.float64", 2, "series") for name in ("left", "right")],
                "graph_outputs": outputs,
                "nodes": [{"node_id": name, "component": {"component_id": component, "component_version": version},
                           "parameters": parameters} for name, component, version, parameters in nodes], "edges": edges}
    return resolve_v2(document, DEFAULT_REGISTRY)


def monitoring_series_inputs():
    index = pd.date_range("2026-09-01", periods=3, freq="15min", tz="UTC")
    return {"left": pd.Series([validity.valid(value) for value in (1., 3., 1.)], index=index),
            "right": pd.Series([validity.valid(2.)] * 3, index=index)}


def test_final_prefix_condition_real_graph_mixed_scalar_series_parity():
    from app.ir.runtime import evaluate_v2
    from app.ir.streaming_reference import evaluate_v2_prefix_stream
    from app.ir.incremental_runtime import accept_research_resource_plan, evaluate_incremental_v2
    from app.market_data.requirements import compile_data_requirement_plan

    graph = monitoring_series_graph()
    inputs = monitoring_series_inputs()
    plan = accept_research_resource_plan(graph, compile_data_requirement_plan(graph, registry=DEFAULT_REGISTRY), DEFAULT_REGISTRY)
    for size, expected in enumerate((False, True, False), 1):
        prefix = {name: value.iloc[:size] for name, value in inputs.items()}
        batch = evaluate_v2(graph, prefix, DEFAULT_REGISTRY)
        reference = evaluate_v2_prefix_stream(graph, prefix, DEFAULT_REGISTRY)
        incremental = evaluate_incremental_v2(graph, prefix, DEFAULT_REGISTRY, plan,
                                             event_kind="completed_bar", maximum_events=3)
        for result in (batch, reference, incremental.outputs):
            assert result["buy"]["requested"] is expected
            assert result["stop"]["active"] is expected
            assert result["target"]["active"] is expected
            assert result["history"].equals(batch["history"])
        assert reference["buy"] == incremental.outputs["buy"] == batch["buy"]


def distance(value="2.5", state="VALID"):
    return subject.verified_distance(
        value=value if state == "VALID" else None, units="PRICE_POINTS",
        source_component_id="analytical.atr", source_component_version=2,
        source_component_address=hashing.content_address({"component": "atr-v2"}),
        source_contract_address=hashing.content_address({"contract": "atr-v2"}),
        validity_state=state,
    )


def inputs(name, enabled=True):
    return ({"distance": distance()} if name in {"ATR_STOP", "RISK_REWARD_TARGET"}
            else {"condition": condition(enabled)})


def params(name): return deepcopy(PARAMETERS.get(name, {}))


def assert_no_forbidden_keys(value):
    if isinstance(value, dict):
        assert not FORBIDDEN & set(value)
        for child in value.values(): assert_no_forbidden_keys(child)
    elif isinstance(value, (tuple, list)):
        for child in value: assert_no_forbidden_keys(child)


def test_exact_scope_and_default_registry_publication():
    assert set(subject.NAMES) == EXPECTED_SCOPE
    assert set(subject.V2_COMPONENTS) == {("intent." + name.lower(), 2) for name in EXPECTED_SCOPE} | {subject.FINAL_PREFIX_CONDITION}
    assert set(subject.NODE_CONTRACTS) == set(subject.DATA_REQUIREMENTS) == set(subject.V2_IMPLEMENTATIONS) == set(subject.V2_COMPONENTS)
    assert V2_CONTRIBUTORS.count(subject) == 1
    for key in subject.V2_COMPONENTS:
        assert plain(DEFAULT_REGISTRY.v2_components[key]) == plain(subject.V2_COMPONENTS[key])
        assert plain(DEFAULT_REGISTRY.node_contracts[key]) == plain(subject.NODE_CONTRACTS[key])
        assert plain(DEFAULT_REGISTRY.data_requirement_declarations[key]) == plain(subject.DATA_REQUIREMENTS[key])
        assert DEFAULT_REGISTRY.v2_implementations[key] is subject.V2_IMPLEMENTATIONS[key].implementation


def test_registry_membership_does_not_enable_public_v0_monitoring():
    capabilities = manifest(
        "v0_research_signal", research_enabled=True,
    )["capabilities"]
    assert capabilities["monitoring"]["state"] == "BLOCKED"
    assert capabilities["signals"]["state"] == "ENABLED_WITH_LIMIT"


def test_isolated_registry_consumes_every_closed_surface():
    isolated = PlatformRegistry(
        components={}, bodies={}, registrations={}, v2_types=subject.V2_TYPES,
        v2_components=subject.V2_COMPONENTS, v2_implementations=subject.V2_IMPLEMENTATIONS,
        data_requirement_declarations=subject.DATA_REQUIREMENTS, node_contracts=subject.NODE_CONTRACTS,
    )
    assert set(isolated.v2_components) == set(subject.V2_COMPONENTS)
    assert isolated.registry_snapshot_address != DEFAULT_REGISTRY.registry_snapshot_address


def test_final_prefix_condition_is_explicit_value_projection():
    source = pd.Series([validity.invalid(validity.ValidityState.MISSING), condition(False), condition(True)],
                       index=pd.date_range("2026-01-01", periods=3, tz="UTC"))
    assert subject.final_prefix_condition({}, {"series": source}) == {"condition": condition(True)}
    assert subject.final_prefix_condition({}, {"series": source.iloc[:2]}) == {"condition": condition(False)}
    assert subject.NODE_CONTRACTS[subject.FINAL_PREFIX_CONDITION]["mode_eligibility"] == {
        "research": True, "paper": False, "live": False}


@pytest.mark.parametrize("parameters", [None, [], {"value": True}])
def test_final_prefix_condition_refuses_parameters_with_valid_series(parameters):
    source = pd.Series([condition(True)], index=pd.date_range("2026-01-01", periods=1, tz="UTC"))
    with pytest.raises(subject.MonitoringIntentRefusal, match="BOUNDARY"):
        subject.final_prefix_condition(parameters, {"series": source})


def test_final_prefix_condition_exact_limit():
    source = pd.Series([condition(True)] * subject.MAX_PREFIX_EVENTS,
                       index=pd.date_range("2026-01-01", periods=subject.MAX_PREFIX_EVENTS, freq="s", tz="UTC"))
    assert subject.final_prefix_condition({}, {"series": source}) == {"condition": condition(True)}


@pytest.mark.parametrize("value", [True, 1, None, float("nan"), validity.valid(1),
    *[validity.invalid(state) for state in validity.ValidityState if state is not validity.ValidityState.VALID]])
def test_final_prefix_condition_invalid_final_cell_refuses(value):
    source = pd.Series([condition(True), value], index=pd.date_range("2026-01-01", periods=2, tz="UTC"))
    with pytest.raises(subject.MonitoringIntentRefusal):
        subject.final_prefix_condition({}, {"series": source})


@pytest.mark.parametrize("index", [pd.RangeIndex(2), pd.date_range("2026-01-01", periods=2),
    pd.DatetimeIndex(["2026-01-01", "2026-01-01"], tz="UTC"),
    pd.DatetimeIndex(["2026-01-02", "2026-01-01"], tz="UTC"),
    pd.DatetimeIndex(["2026-01-01", None], tz="UTC")])
def test_final_prefix_condition_malformed_clock_refuses(index):
    with pytest.raises(subject.MonitoringIntentRefusal, match="PREFIX_CLOCK"):
        subject.final_prefix_condition({}, {"series": pd.Series([condition(True)] * 2, index=index)})


@pytest.mark.parametrize("parameters,inputs", [(None, {}), ([], {}), ({"value": True}, {}), ({}, None), ({}, {}),
    ({}, {"series": [condition(True)]}), ({}, {"series": pd.Series([], dtype=object)}),
    ({}, {"series": pd.Series([condition(True)] * (subject.MAX_PREFIX_EVENTS + 1))})])
def test_final_prefix_condition_unbounded_or_open_boundary_refuses(parameters, inputs):
    with pytest.raises(subject.MonitoringIntentRefusal):
        subject.final_prefix_condition(parameters, inputs)


@pytest.mark.parametrize("name", sorted(EXPECTED_SCOPE))
def test_descriptor_contract_data_and_resource_closure(name):
    key = subject.component_key(name); descriptor = plain(subject.V2_COMPONENTS[key])
    contract = plain(subject.NODE_CONTRACTS[key]); declaration = plain(subject.DATA_REQUIREMENTS[key])
    assert descriptor["component_id"] == key[0] and descriptor["component_version"] == 2
    assert descriptor["domain_family"] == ("intent_description" if name in TARGETS else "risk")
    assert len([p for p in descriptor["ports"] if p["direction"] == "input"]) == 1
    assert len([p for p in descriptor["ports"] if p["direction"] == "output"]) == 1
    assert contract["visible_family"] == "TYPE_1" and contract["semantic_version"] == 2
    assert contract["bar_policy"] == "COMPLETED_ONLY" and contract["missing_data_policy"] == "REFUSE"
    assert contract["numeric_validity_policy"] == "EXPLICIT_VALIDITY"
    assert contract["mode_eligibility"] == {"research": True, "paper": False, "live": False}
    assert contract["provider_requirements"] == [] and contract["required_market_fields"] == []
    assert contract["resource_profile"] == {
        "compute_microseconds_per_event": 2500, "memory_bytes_upper_bound": 524288,
        "history_bytes_upper_bound": 0, "state_bytes_upper_bound": 0,
        "storage_bytes_per_day_upper_bound": 0, "subscription_count_upper_bound": 0,
        "fanout_upper_bound": 1,
    }
    assert declaration == {"schema": "data-requirement-declaration/1", "classification": "NO_DATA", "requirements": []}
    assert node_contracts.canonical_node_contract(key, contract).contract_address == subject.NODE_CONTRACT_ADDRESSES[key]
    assert schema.is_content_address(subject.V2_IMPLEMENTATIONS[key].implementation_address)


@pytest.mark.parametrize("name", sorted(TARGETS))
@pytest.mark.parametrize("requested", (False, True))
def test_complete_target_table(name, requested):
    target, reducing = TARGETS[name]
    result = plain(subject.evaluate(name, {}, {"condition": condition(requested)}))["intent"]
    assert result == {"schema": "monitoring-target-intent/1", "operation": name,
        "target_state": target, "risk_reducing": reducing, "requested": requested,
        "authored": result["authored"], "validity": "VALID"}
    assert result["authored"]["component_id"] == "intent." + name.lower()
    assert result["authored"]["semantic_version"] == 2
    assert all(schema.is_content_address(result["authored"][field]) for field in (
        "component_address", "node_contract_address", "parameters_address"))
    assert_no_forbidden_keys(result)


@pytest.mark.parametrize("name", sorted(PARAMETERS))
def test_complete_protection_table(name):
    kind, basis, value, units = PROTECTION_EXPECTED[name]
    result = plain(subject.evaluate(name, params(name), inputs(name)))["protection"]
    assert (result["kind"], result["basis"], result["value"], result["units"]) == (kind, basis, value, units)
    assert result["schema"] == "monitoring-protection/1" and result["active"] is True
    assert result["validity"] == "VALID" and result["authority"] == "MONITORING_ONLY"
    assert result["authored_value"] == next(iter(params(name).values()))
    if name in {"ATR_STOP", "RISK_REWARD_TARGET"}:
        assert all(schema.is_content_address(result["input_identity"][field]) for field in (
            "source_component_address", "source_contract_address"))
    else: assert result["input_identity"] is None
    assert_no_forbidden_keys(result)


@pytest.mark.parametrize("name", ("FIXED_STOP_PERCENT", "POINT_STOP", "TAKE_PROFIT_PERCENT"))
def test_false_protection_condition_is_valid_but_inactive(name):
    result = subject.evaluate(name, params(name), inputs(name, enabled=False))["protection"]
    assert result["active"] is False and result["validity"] == "VALID"


@pytest.mark.parametrize("name", sorted(PARAMETER_BOUNDS))
def test_parameter_minimum_maximum_and_first_above(name):
    parameter, minimum, maximum, first_above = PARAMETER_BOUNDS[name]
    assert subject.parameters_for(name, {parameter: minimum})[parameter] == minimum
    assert subject.parameters_for(name, {parameter: maximum})[parameter] == maximum
    with pytest.raises(subject.MonitoringIntentRefusal, match="OUT_OF_RANGE"):
        subject.parameters_for(name, {parameter: first_above})
    for value in (0, 1, 1.0, True, None, "NaN", "Infinity", "01", "+1", "1e-2", "0"):
        with pytest.raises(subject.MonitoringIntentRefusal): subject.parameters_for(name, {parameter: value})
    for supplied in ({}, {parameter: minimum, "extra": "1"}):
        with pytest.raises(subject.MonitoringIntentRefusal): subject.parameters_for(name, supplied)


@pytest.mark.parametrize("name", sorted(TARGETS))
def test_targets_reject_parameters_and_open_input_shapes(name):
    with pytest.raises(subject.MonitoringIntentRefusal): subject.parameters_for(name, {"extra": "1"})
    for value in ({}, {"condition": condition(), "extra": condition()}, {"condition": True}):
        with pytest.raises(subject.MonitoringIntentRefusal): subject.evaluate(name, {}, value)


@pytest.mark.parametrize("state", [s for s in validity.ValidityState if s is not validity.ValidityState.VALID])
def test_invalid_condition_states_refuse_and_never_become_hold(state):
    with pytest.raises(subject.MonitoringIntentRefusal, match=state.value):
        subject.evaluate("BUY", {}, {"condition": validity.invalid(state)})


@pytest.mark.parametrize("state", [s.value for s in validity.ValidityState if s is not validity.ValidityState.VALID])
def test_invalid_verified_distance_states_refuse(state):
    with pytest.raises(subject.MonitoringIntentRefusal, match=state):
        subject.evaluate("ATR_STOP", {"multiplier": "1.5"}, {"distance": distance(state=state)})


def test_verified_distance_requires_exact_decimal_units_and_identity():
    valid = plain(distance())
    mutations = (("value", 2.5), ("value", "0"), ("value", "NaN"), ("units", "RUPEES"),
        ("source_component_id", ""), ("source_component_version", True),
        ("source_component_address", "sha256:bad"), ("source_contract_address", ""))
    for field, value in mutations:
        with pytest.raises(subject.MonitoringIntentRefusal):
            subject.evaluate("ATR_STOP", {"multiplier": "1.5"}, {"distance": {**valid, field: value}})
    with pytest.raises(subject.MonitoringIntentRefusal, match="RESULT_OUT_OF_RANGE"):
        subject.evaluate("ATR_STOP", {"multiplier": "100"}, {"distance": distance(value="1000000000000")})


@pytest.mark.parametrize("direction,entry,stop,target", (("LONG", "100", "90", "125"), ("SHORT", "100", "110", "75")))
def test_long_short_resolved_geometry(direction, entry, stop, target):
    assert plain(subject.validate_resolved_geometry(direction=direction, entry_reference=entry,
        stop_loss=stop, take_profit=target)) == {"schema": "monitoring-protection-geometry/1",
        "direction": direction, "entry_reference": entry, "stop_loss": stop,
        "take_profit": target, "validity": "VALID"}


@pytest.mark.parametrize("direction,entry,stop,target", (
    ("LONG", "100", "100", "125"), ("LONG", "100", "110", "125"),
    ("SHORT", "100", "90", "75"), ("SHORT", "100", "110", "110"),
    ("FLAT", "100", "90", "125"), ("LONG", "NaN", "90", "125")))
def test_invalid_or_equal_geometry_refuses(direction, entry, stop, target):
    with pytest.raises(subject.MonitoringIntentRefusal):
        subject.validate_resolved_geometry(direction=direction, entry_reference=entry,
            stop_loss=stop, take_profit=target)


def test_all_unsupported_type1_operations_have_typed_nonexecuting_refusals():
    assert set(subject.ALL_TYPE_1_NAMES) == set(execution_intent.TYPE_1_NAMES)
    assert set(subject.UNSUPPORTED_NAMES) == set(execution_intent.TYPE_1_NAMES) - EXPECTED_SCOPE
    for name in subject.UNSUPPORTED_NAMES:
        assert plain(subject.refusal_for(name)) == {"schema": "monitoring-operation-refusal/1",
            "component_id": "intent." + name.lower(), "semantic_version": 2,
            "operation": name, "code": "V0_MONITORING_OPERATION_UNAVAILABLE",
            "executable": False, "authority": "NONE"}
        assert ("intent." + name.lower(), 2) not in subject.V2_COMPONENTS
        with pytest.raises(subject.MonitoringIntentRefusal, match="V0_MONITORING_OPERATION_UNAVAILABLE"):
            subject.evaluate(name, {}, {"condition": condition()})


@pytest.mark.parametrize("name", sorted(EXPECTED_SCOPE))
def test_prefix_is_deterministic_serializable_and_future_invariant(name):
    event = inputs(name); events = [event for _ in range(32)]
    first = subject.evaluate_prefix(name, params(name), events)
    second = subject.evaluate_prefix(name, params(name), events)
    extended = subject.evaluate_prefix(name, params(name), [*events, event])
    assert first == second == extended[:-1]
    encoded = hashing.canonical_json(plain(first))
    assert json.loads(encoded) == json.loads(hashing.canonical_json(plain(second)))
    assert len(encoded) < 131072


def test_prefix_first_above_limit_refuses_before_evaluation():
    event = {"condition": condition()}
    with pytest.raises(subject.MonitoringIntentRefusal, match="PREFIX_LIMIT"):
        subject.evaluate_prefix("BUY", {}, [event] * (subject.MAX_PREFIX_EVENTS + 1))


def test_implementations_are_deterministic_content_addressed_and_distinct():
    addresses = [r.implementation_address for r in subject.V2_IMPLEMENTATIONS.values()]
    assert len(addresses) == len(set(addresses)) == 13
    assert all(schema.is_content_address(address) for address in addresses)
    for name in subject.NAMES:
        implementation = subject.implementation_for(name)
        assert implementation(params(name), inputs(name)) == implementation(params(name), inputs(name))


def test_outputs_are_closed_plain_data_with_no_authority_fields_or_effects():
    for name in subject.NAMES:
        result = plain(subject.evaluate(name, params(name), inputs(name)))
        assert_no_forbidden_keys(result)
        assert json.loads(json.dumps(result, sort_keys=True)) == result
        assert hashing.content_address(result) == hashing.content_address(deepcopy(result))


def test_source_has_no_authority_import_or_runtime_side_effect_surface():
    tree = ast.parse(SOURCE.read_text())
    imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    forbidden = ("app.engine", "app.execution", "app.providers", "app.db", "app.ledger",
        "app.notify", "app.api", "app.core.credential", "app.core.deploy")
    assert not any(name.startswith(prefix) for name in imports for prefix in forbidden)
    for token in ("place_order", "open_position", "broker_account_id", "capital_reservation", "ExecutionIntent"):
        assert token not in SOURCE.read_text()


def test_protected_v1_and_shared_module_hashes_are_exact():
    expected = {
        "paper-trader/backend/app/ir/first_party/execution_intent.py": "ea9c9f87ba48a5ef9ca7e33c6fca0dfb1060e931dc330c1f2086dcfecea848be",
        "paper-trader/backend/app/ir/first_party/logic_state.py": "31ea8e62e1d07cce07a53ccef21bf1411ca7727d3f584c73ed4644c815250463",
        "paper-trader/backend/app/ir/registry.py": "4c1d83e9f8714d9e8a11e571426cde6b7a896fe47aec3d3fe1a44b4f58bf120f",
        "paper-trader/backend/app/ir/node_contracts.py": "a1e16b735cd8decfcad4356aa82c10a20d65c5129f25d78ae7931ad9596af284",
        "paper-trader/backend/app/ir/runtime.py": "9febb25ee02c1d390ce8a287901f3119146c1d672267c31f582d22a2801141fd"}
    for relative, wanted in expected.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() == wanted


def test_mutation_guard_buy_target_is_long():
    assert subject.evaluate("BUY", {}, {"condition": condition()})["intent"]["target_state"] == "LONG"


def test_mutation_guard_fixed_stop_basis_is_percent():
    assert subject.evaluate(
        "FIXED_STOP_PERCENT", {"rate": "0.125"}, {"condition": condition()},
    )["protection"]["basis"] == "PERCENT_FROM_ENTRY_REFERENCE"
