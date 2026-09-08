"""Contract-only fixtures: no corrected analytical implementation or publication."""
from copy import deepcopy
from dataclasses import replace

import pytest

from app.ir.hashing import content_address
from app.ir.node_contracts import NodeContractRefusal
from app.ir.registry import DependencyBoundary, PlatformRegistry, registered_contract_binding
from app.ir.registry import _canonical_registry_node_contract as canonical_node_contract
from app.ir.resolve import ResolutionError, resolve_v2
from app.ir.first_party.analytical_v2.contracts import binding_result, canonical_input_bindings
from app.market_data.requirements import DataRequirementRefusal, compile_data_requirement_plan, verify_data_requirement_plan
from app.ir.incremental_runtime import accept_research_resource_plan


KEY = ("fixture.contract_only", 2)


def address(label):
    return content_address({"contract_test_fixture": label})


def plain(value):
    if hasattr(value, "items"):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    return value


def port(name, direction):
    value = {"port_id": name, "direction": direction, "semantic_flow": "value",
             "semantic_role": "market_frame", "type_ref": {"type_id": "fixture.frame", "type_version": 1}, "shape": "series"}
    if direction == "input":
        value["connections"] = {"cardinality": "single", "min": 1, "max": 1, "assembly": "single"}
    return value


def descriptor():
    def parameter(kind, default, enum, domain):
        return {"type": kind, "default": default, "required": False, "enum": enum,
                "domain": domain, "units": "fixture", "serialization": "canonical-json"}
    return {"component_id": KEY[0], "component_version": KEY[1], "domain_family": "indicator", "structural_role": "transform",
            "ports": [port("frame", "input"), port("value", "output")],
            "parameters": {"source": parameter("str", "CLOSE", ["CLOSE", "OPEN"], {"max_length": 16}),
                           "window": parameter("int", 3, None, {"minimum": 2, "maximum": 4096})}}


def source_contract():
    rule = {"rule_id": "fixture.window_binding", "rule_version": 1}
    return {"schema": "first-party-node-contract/2", "stable_node_id": KEY[0], "semantic_version": 2,
            "visible_family": "TYPE_2", "input_types": {"frame": "fixture.frame/series"},
            "output_types": {"value": "fixture.frame/series"}, "required_market_fields": ["close", "open"],
            "required_resolution": {"source": "canonical_input_binding", "port": "frame", "alignment": "BAR_CLOSE"},
            "warmup_history": rule, "execution_form": "ROLLING",
            "state_initialization": {"schema": "state-initialization/1", "initial_state_address": None},
            "state_reset_policy": {"schema": "state-reset-policy/2", "reasons": ["DATA_GAP", "EXPLICIT", "IDENTITY_CHANGE"]},
            "bar_policy": "COMPLETED_ONLY", "missing_data_policy": "PROPAGATE", "numeric_validity_policy": "EXPLICIT_VALIDITY",
            "causal_declaration": "COMPLETED_EVENT_PREFIX", "evaluation_triggers": ["completed_bar"],
            "streaming_support": False, "batch_support": False,
            "mode_eligibility": {"research": False, "paper": False, "live": False},
            "provider_requirements": [address("provider-requirement")],
            "resource_profile": {"compute_microseconds_per_event": 0, "memory_bytes_upper_bound": 0,
                                 "history_bytes_upper_bound": 0, "state_bytes_upper_bound": 0,
                                 "storage_bytes_per_day_upper_bound": 0, "subscription_count_upper_bound": 0,
                                 "fanout_upper_bound": 0},
            "reference_provenance": [address("contract-only-reference")],
            "parameter_binding": {"scheme": "analytical-contract-binding/1", **rule,
                                  "parameter_names": ["source", "window"], "input_ports": ["frame"]}}


def window_binding(parameters, inputs):
    return binding_result(inputs, fields_by_port={"frame": [parameters["source"]]},
                          warmup_history=parameters["window"] - 1,
                          output_warmup={"value": parameters["window"] - 1})


def not_a_numerical_implementation(parameters, inputs):
    raise ValueError("contract-only test fixture cannot execute numerical work")


def registry(contract=None, registration=None):
    contract = source_contract() if contract is None else contract
    if registration is None:
        registration = registered_contract_binding(component=KEY, source_contract=contract,
            implementation=window_binding, dependency_boundary=DependencyBoundary("declared_objects", (binding_result,)))
    return PlatformRegistry(components={}, bodies={}, registrations={},
        v2_types={("fixture.frame", 1): {"type_id": "fixture.frame", "type_version": 1, "shapes": ["series"], "runtime_representation": "fixture-only"}},
        v2_components={KEY: descriptor()}, node_contracts={KEY: contract},
        contract_bindings={KEY: registration})


def graph(window=3, source="CLOSE"):
    return {"format_version": 2, "strategy_id": "contract-only", "strategy_version": 1,
            "metadata": {"metadata_version": 1, "name": "Contract only", "description": None, "tags": []},
            "graph_inputs": [port("bars", "input")], "graph_outputs": [],
            "nodes": [{"node_id": "probe", "component": {"component_id": KEY[0], "component_version": 2},
                       "parameters": {"window": window, "source": source}}],
            "edges": [{"edge_id": "input", "source": {"scope": "graph_input", "port_id": "bars"},
                       "target": {"scope": "node", "node_id": "probe", "port_id": "frame"}, "binding": {"kind": "single"}}]}


def input_fact():
    return {"schema": "canonical-input-binding/1", "owner_id": "org.fixture-a",
            "dataset_context_address": address("dataset-context"), "evaluation_context_address": address("evaluation-context"),
            "dataset_manifest_address": address("manifest"), "market_truth_address": address("market-truth"),
            "provider_product_address": address("provider-product"), "provider_contract_address": address("provider-contract"),
            "canonical_instrument_address": address("instrument"), "instrument": {"role": "primary", "type": "PHYSICAL"},
            "timeframe": 900, "fields": ["CLOSE", "OPEN"], "freshness": {"maximum_age_seconds": 60},
            "depth": {"kind": "NONE", "levels": None}, "session": "INSTRUMENT_CALENDAR",
            "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0}, "derived_local": False}


def inputs(fact=None, pinned_address=None):
    fact = input_fact() if fact is None else fact
    return canonical_input_bindings(owner_id="org.fixture-a", dataset_context_address=address("dataset-context"),
        evaluation_context_address=address("evaluation-context"), bindings={"bars": fact},
        expected_source_addresses={"bars": pinned_address or content_address(fact)})


def test_source_contract_v2_is_closed_immutable_and_does_not_reinterpret_v1():
    raw = source_contract(); accepted = canonical_node_contract(KEY, raw)
    raw["warmup_history"]["rule_version"] = 9
    assert accepted.document["warmup_history"]["rule_version"] == 1
    assert accepted.contract_address == content_address(plain(accepted.document))
    with pytest.raises(TypeError):
        accepted.document["parameter_binding"]["scheme"] = "forged"
    for key in source_contract():
        missing = source_contract(); missing.pop(key)
        with pytest.raises(NodeContractRefusal):
            canonical_node_contract(KEY, missing)
    with pytest.raises(NodeContractRefusal):
        canonical_node_contract((KEY[0], 1), source_contract())


def test_binding_registration_is_registry_owned_and_requires_exact_source_identity():
    current = registry()
    registration = current.contract_bindings[KEY]
    assert registration.source_contract_address == current.node_contract_addresses[KEY]
    assert current.data_requirement_declaration_addresses[KEY] == current.node_contract_addresses[KEY]
    forged = replace(registration, implementation_address=address("forged-implementation"))
    with pytest.raises(ValueError, match="binding"):
        registry(registration=forged)
    forged = replace(registration, source_contract_address=address("forged-source"))
    with pytest.raises(ValueError, match="binding"):
        registry(registration=forged)


def test_resolution_remains_pure_and_compilation_requires_explicit_pinned_context():
    current = registry(); resolved = resolve_v2(graph(), current)
    assert resolved.resolved_graph_address == resolve_v2(graph(), current).resolved_graph_address
    assert resolved.nodes[0].bound_requirements is None
    assert resolved.nodes[0].binding_implementation_address == current.contract_bindings[KEY].implementation_address
    with pytest.raises(DataRequirementRefusal, match="binding"):
        compile_data_requirement_plan(resolved)
    plan = compile_data_requirement_plan(resolved, registry=current, input_bindings=inputs())
    row = plan.requirements[0]["requirement"]
    assert row["field"] == "CLOSE" and row["timeframe"] == 900
    assert row["history"] == {"minimum_bars": 1, "warmup_bars": 2}
    receipt = plan.parameter_binding_provenance[0]["node_contract_binding"]
    assert receipt["resolved_contract"]["warmup_history"] == 2
    assert receipt["resolved_contract"]["output_warmup"] == {"value": 2}
    assert receipt["input_binding"]["owner_id"] == "org.fixture-a"
    assert receipt["bound_contract_address"] == content_address({key: plain(value) for key, value in receipt.items() if key != "bound_contract_address"})


def test_research_resource_plan_retains_and_reconstructs_exact_dynamic_binding_inputs():
    contract = source_contract()
    contract["mode_eligibility"]["research"] = True
    contract["batch_support"] = True
    contract["streaming_support"] = True
    registration = registered_contract_binding(
        component=KEY, source_contract=contract, implementation=window_binding,
        dependency_boundary=DependencyBoundary("declared_objects", (binding_result,)),
    )
    current = registry(contract=contract, registration=registration)
    resolved = resolve_v2(graph(), current); context = inputs()
    data_plan = compile_data_requirement_plan(
        resolved, registry=current, input_bindings=context,
    )
    accepted = accept_research_resource_plan(
        resolved, data_plan, current, input_bindings=context,
    )
    assert accepted.input_bindings == context
    assert accepted.registry_snapshot_address == current.registry_snapshot_address
    from research.evaluation.phase5_runtime import (
        NODE_CONTEXT_RESOLVER_ADDRESS, _node_context_resolver,
    )
    resolver = _node_context_resolver(
        type("Policy", (), {"document": {
            "node_context_resolver_address": NODE_CONTEXT_RESOLVER_ADDRESS,
        }})(), type("Dataset", (), {})(), current, accepted,
    )
    resolved_context = resolver(resolved.nodes[0], {"frame": {}})
    assert resolved_context["bound_contract"].bound_contract_address \
        == data_plan.parameter_binding_provenance[0]["node_contract_binding"]["bound_contract_address"]


def test_selected_field_window_and_input_context_change_exact_bound_plan_identity():
    current = registry()
    close = compile_data_requirement_plan(resolve_v2(graph(), current), registry=current, input_bindings=inputs())
    opened = compile_data_requirement_plan(resolve_v2(graph(4, "OPEN"), current), registry=current, input_bindings=inputs())
    assert opened.requirements[0]["requirement"]["field"] == "OPEN"
    assert opened.requirements[0]["requirement"]["history"]["warmup_bars"] == 3
    assert close.plan_address != opened.plan_address
    changed = input_fact(); changed["timeframe"] = 1800
    other_timeframe = compile_data_requirement_plan(resolve_v2(graph(), current), registry=current, input_bindings=inputs(changed))
    assert close.resolved_graph_address == other_timeframe.resolved_graph_address
    assert close.plan_address != other_timeframe.plan_address


@pytest.mark.parametrize("value", [True, 0, 1, 4097, 3.0, "3", None])
def test_bound_parameters_refuse_wrong_type_missing_or_outside_domain(value):
    with pytest.raises((ResolutionError, NodeContractRefusal)):
        resolve_v2(graph(value), registry())


@pytest.mark.parametrize("field,value", [("owner_id", "org.fixture-b"),
    ("provider_contract_address", address("other-provider")), ("dataset_manifest_address", address("other-manifest"))])
def test_owner_provider_and_dataset_swaps_cannot_reuse_independently_pinned_source(field, value):
    original = input_fact(); changed = deepcopy(original); changed[field] = value
    with pytest.raises(NodeContractRefusal):
        inputs(changed, pinned_address=content_address(original))


@pytest.mark.parametrize("mutate", [
    lambda c: c["parameter_binding"]["parameter_names"].reverse(),
    lambda c: c["parameter_binding"]["input_ports"].append("other"),
    lambda c: c["warmup_history"].__setitem__("rule_version", True),
    lambda c: c["warmup_history"].__setitem__("rule_id", "other.rule"),
    lambda c: c["required_resolution"].__setitem__("port", "missing"),
    lambda c: c["state_reset_policy"]["reasons"].append("UNKNOWN"),
    lambda c: c["mode_eligibility"].__setitem__("paper", True),
    lambda c: c.__setitem__("missing_data_policy", "EXPLICIT_FALLBACK"),
    lambda c: c.__setitem__("bar_policy", "PARTIAL_ALLOWED"),
    lambda c: c.__setitem__("extra", "not allowed"),
])
def test_source_schema_rejects_wrong_rule_ports_order_policy_and_authority(mutate):
    value = source_contract(); mutate(value)
    with pytest.raises(NodeContractRefusal):
        canonical_node_contract(KEY, value)


def test_context_fields_and_binding_source_sets_are_closed():
    original = input_fact()
    for field in original:
        missing = deepcopy(original); missing.pop(field)
        with pytest.raises(NodeContractRefusal):
            inputs(missing)
    changed = deepcopy(original); changed["extra"] = True
    with pytest.raises(NodeContractRefusal):
        inputs(changed)
    changed = deepcopy(original); changed["fields"].reverse()
    with pytest.raises(NodeContractRefusal):
        inputs(changed)
    with pytest.raises(NodeContractRefusal):
        canonical_input_bindings(owner_id="org.fixture-a", dataset_context_address=address("dataset-context"),
            evaluation_context_address=address("evaluation-context"), bindings={"bars": original}, expected_source_addresses={})


@pytest.mark.parametrize("field,value", [("instrument", {"role": "not a role", "type": "PHYSICAL"}), ("fields", ["OPEN"])])
def test_even_correctly_addressed_wrong_roles_or_missing_selected_fields_refuse(field, value):
    changed = input_fact(); changed[field] = value
    current = registry()
    with pytest.raises((NodeContractRefusal, DataRequirementRefusal), match="binding"):
        compile_data_requirement_plan(resolve_v2(graph(), current), registry=current, input_bindings=inputs(changed))


def test_unused_canonical_inputs_and_missing_registry_refuse():
    current = registry(); resolved = resolve_v2(graph(), current); fact = input_fact()
    context = canonical_input_bindings(owner_id="org.fixture-a", dataset_context_address=address("dataset-context"),
        evaluation_context_address=address("evaluation-context"), bindings={"bars": fact, "unused": fact},
        expected_source_addresses={"bars": content_address(fact), "unused": content_address(fact)})
    with pytest.raises(DataRequirementRefusal, match="unused"):
        compile_data_requirement_plan(resolved, registry=current, input_bindings=context)
    with pytest.raises(DataRequirementRefusal, match="registry"):
        compile_data_requirement_plan(resolved, input_bindings=inputs())


def plan_address(plan):
    """Independent adversarial serializer, used to forge internally consistent bad facts."""
    rows = [{**plain(row), "leaf_component": {"component_id": row["leaf_component"][0],
                                              "component_version": row["leaf_component"][1]}} for row in plan.requirements]
    return content_address({"authored_ir_address": plan.authored_ir_address,
        "resolved_graph_address": plan.resolved_graph_address, "implementation_closure_address": plan.implementation_closure_address,
        "registry_snapshot_address": plan.registry_snapshot_address, "declaration_addresses": list(plan.declaration_addresses),
        "requirements": rows, "parameter_binding_provenance": plain(plan.parameter_binding_provenance)})


def test_rehashed_underdeclared_warmup_cannot_replace_replayed_registry_binding():
    current = registry(); resolved = resolve_v2(graph(), current); context = inputs()
    plan = compile_data_requirement_plan(resolved, registry=current, input_bindings=context)
    assert plan_address(plan) == plan.plan_address
    assert verify_data_requirement_plan(plan, resolved, registry=current, input_bindings=context) == plan
    provenance = plain(plan.parameter_binding_provenance)
    receipt = provenance[0]["node_contract_binding"]
    receipt["resolved_contract"]["warmup_history"] = 0
    receipt["resolved_contract"]["output_warmup"]["value"] = 0
    receipt["bound_requirements"][0]["history"]["warmup_bars"] = 0
    receipt["bound_contract_address"] = content_address({key: value for key, value in receipt.items() if key != "bound_contract_address"})
    requirements = plain(plan.requirements); requirements[0]["requirement"]["history"]["warmup_bars"] = 0
    forged = replace(plan, requirements=tuple(requirements), parameter_binding_provenance=tuple(provenance))
    forged = replace(forged, plan_address=plan_address(forged))
    assert plan_address(forged) == forged.plan_address
    with pytest.raises(DataRequirementRefusal, match="reconstructed"):
        verify_data_requirement_plan(forged, resolved, registry=current, input_bindings=context)


def test_changed_binding_implementation_is_rejected_before_compilation(monkeypatch):
    current = registry(); resolved = resolve_v2(graph(), current)
    def changed(parameters, inputs):
        return {}
    monkeypatch.setattr(current.contract_bindings[KEY].implementation, "__code__", changed.__code__)
    with pytest.raises(DataRequirementRefusal, match="binding"):
        compile_data_requirement_plan(resolved, registry=current, input_bindings=inputs())


@pytest.mark.parametrize("change", ["owner", "endpoint", "role"])
def test_direct_registry_binding_cannot_skip_canonical_input_checks(change):
    current = registry(); resolved = resolve_v2(graph(), current)
    plan = compile_data_requirement_plan(resolved, registry=current, input_bindings=inputs())
    binding = plain(plan.parameter_binding_provenance[0]["node_contract_binding"]["input_binding"])
    if change == "owner":
        binding["owner_id"] = ""
        binding["ports"]["frame"]["binding"]["owner_id"] = ""
    elif change == "endpoint":
        binding["ports"]["frame"]["source"]["scope"] = "node"
    else:
        binding["ports"]["frame"]["binding"]["instrument"]["role"] = "not a role"
    entry = binding["ports"]["frame"]
    entry["binding_address"] = content_address(entry["binding"])
    with pytest.raises(NodeContractRefusal):
        current.bind_node_contract(KEY, {"source": "CLOSE", "window": 3}, binding)


def test_undeclared_binding_dependency_and_runtime_import_are_rejected():
    from app.ir.implementation_identity import ImplementationUnidentified
    with pytest.raises(ImplementationUnidentified):
        registered_contract_binding(component=KEY, source_contract=source_contract(), implementation=window_binding,
            dependency_boundary=DependencyBoundary("declared_objects", ()))
    def runtime_import(parameters, bindings):
        import time
        return time.time()
    with pytest.raises(ImplementationUnidentified, match="runtime import"):
        registered_contract_binding(component=KEY, source_contract=source_contract(), implementation=runtime_import,
            dependency_boundary=DependencyBoundary("declared_objects", ()))


def test_ambient_io_clock_and_mutable_state_refuse_without_executing_rule():
    from datetime import datetime
    from app.ir.implementation_identity import ImplementationUnidentified
    captured = {"calls": 0}

    def file_reader(parameters, bindings):
        return open("must-not-be-read", "rb").read()

    def clock_reader(parameters, bindings):
        return datetime.now()

    def mutable_closure(parameters, bindings):
        captured["calls"] += 1
        return captured

    def mutable_default(parameters, bindings, state={}):
        state["calls"] = 1
        return state

    for rule in (file_reader, clock_reader, mutable_closure, mutable_default):
        with pytest.raises(ImplementationUnidentified, match="ambient|mutable"):
            registered_contract_binding(component=KEY, source_contract=source_contract(), implementation=rule,
                dependency_boundary=DependencyBoundary("declared_objects", ()))
    assert captured == {"calls": 0}
    assert mutable_default.__defaults__ == ({},)


def test_legacy_contract_reader_and_default_registry_are_not_mutated_by_new_registration():
    from app.ir.node_contracts import canonical_node_contract as frozen_legacy_reader
    from app.ir.library import REGISTRY
    from app.ir.registry import registered_v2_implementation
    before = (
        REGISTRY.registry_snapshot_address,
        dict(REGISTRY.node_contract_addresses),
        dict(REGISTRY.v2_implementation_identities),
        dict(REGISTRY.contract_bindings),
    )
    with pytest.raises(NodeContractRefusal):
        frozen_legacy_reader(KEY, source_contract())
    extra = registry()
    mixed = PlatformRegistry(components=REGISTRY.library.components, bodies=REGISTRY.library.bodies,
        registrations=REGISTRY.registrations,
        v2_types={**REGISTRY.v2_types, **extra.v2_types}, v2_components={**REGISTRY.v2_components, **extra.v2_components},
        v2_implementations={**REGISTRY.v2_implementation_registrations, KEY: registered_v2_implementation(
            component=KEY, implementation=not_a_numerical_implementation,
            dependency_boundary=DependencyBoundary("declared_objects", ()))},
        data_requirement_declarations={**REGISTRY.data_requirement_declarations, **extra.data_requirement_declarations},
        node_contracts={**REGISTRY.node_contracts, **extra.node_contracts},
        contract_bindings={**REGISTRY.contract_bindings, **extra.contract_bindings})
    assert mixed.registry_snapshot_address != REGISTRY.registry_snapshot_address
    assert {key: mixed.node_contract_addresses[key] for key in REGISTRY.node_contract_addresses} == before[1]
    assert {key: mixed.v2_implementation_identities[key] for key in REGISTRY.v2_implementation_identities} == before[2]
    assert {key: mixed.contract_bindings[key] for key in REGISTRY.contract_bindings} == before[3]
    assert (
        REGISTRY.registry_snapshot_address,
        dict(REGISTRY.node_contract_addresses),
        dict(REGISTRY.v2_implementation_identities),
        dict(REGISTRY.contract_bindings),
    ) == before


def test_shared_scalar_helpers_preserve_invalid_unknown_false_and_zero():
    from app.ir.first_party.analytical_v2.common import required_condition, required_numeric_scalar
    from app.ir.validity import ValidityState, invalid, valid
    import numpy as np
    assert required_numeric_scalar({"x": 0}, "x") == valid(0.0)
    for value in [True, False, np.bool_(True), float("nan"), float("inf"), valid(True)]:
        assert required_numeric_scalar({"x": value}, "x").state is ValidityState.INVALID
    assert required_numeric_scalar({"x": None}, "x").state is ValidityState.MISSING
    missing = invalid(ValidityState.INSUFFICIENT_HISTORY)
    assert required_numeric_scalar({"x": missing}, "x") is missing
    assert required_condition({"x": False}, "x") == valid(False)
    assert required_condition({"x": None}, "x").state is ValidityState.MISSING
    assert required_condition({"x": 0}, "x").state is ValidityState.INVALID
    for helper in (required_condition, required_numeric_scalar):
        with pytest.raises(NodeContractRefusal):
            helper({"close": 123}, "missing")


def test_bound_state_restore_rejects_different_parameters_and_undeclared_resets():
    from app.ir.first_party.analytical_v2.contracts import ResolvedNodeContract
    from app.ir.first_party.analytical_v2.common import bound_state_snapshot, verify_bound_state_snapshot
    current = registry(); context = inputs()
    def bound(window):
        plan = compile_data_requirement_plan(resolve_v2(graph(window), current), registry=current, input_bindings=context)
        document = plan.parameter_binding_provenance[0]["node_contract_binding"]
        return ResolvedNodeContract(document, document["bound_contract_address"])
    expected = bound(3)
    facts = {"strategy_address": address("strategy"), "resolved_graph_address": address("graph"),
             "implementation_closure_address": address("closure"), "last_event_address": address("event"),
             "last_event_time": "2026-08-28T00:00:00+00:00", "state_bytes_digest": address("state-bytes"),
             "validity_state": "INSUFFICIENT_HISTORY", "reset_reasons": ["DATA_GAP"],
             "creation_evidence_address": address("evidence")}
    snapshot = bound_state_snapshot(expected, **facts)
    assert snapshot.document["schema"] == "state-snapshot/2"
    assert verify_bound_state_snapshot(snapshot.document, expected) == snapshot
    with pytest.raises(NodeContractRefusal, match="mismatched"):
        verify_bound_state_snapshot(snapshot.document, bound(4))
    with pytest.raises(NodeContractRefusal, match="not declared"):
        bound_state_snapshot(expected, **{**facts, "reset_reasons": ["SESSION"]})
    with pytest.raises(NodeContractRefusal, match="overrides"):
        bound_state_snapshot(expected, **facts, bound_contract_address=address("fake"))
    with pytest.raises(NodeContractRefusal, match="explicit reset"):
        bound_state_snapshot(expected, **{key: value for key, value in facts.items() if key != "reset_reasons"})
    for field in snapshot.document:
        missing = plain(snapshot.document); missing.pop(field)
        with pytest.raises(NodeContractRefusal):
            verify_bound_state_snapshot(missing, expected)
