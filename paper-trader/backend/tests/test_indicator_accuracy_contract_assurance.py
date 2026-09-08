"""Independent consumer assurance; no indicator math or foundation-test imports.

Frozen v1 expected facts come from the accepted replan, not current output.
The synthetic binding is an independently authored protocol fixture, not a
candidate indicator or an oracle for numerical accuracy. Expected histories and
serialized receipt fields below are specified separately from its callable.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path

import pytest

from app.ir.first_party.analytical_v2.common import (
    bound_state_snapshot, required_condition, required_numeric_scalar,
    verify_bound_state_snapshot,
)
from app.ir.first_party.analytical_v2.contracts import (
    ContractInputBindings, ResolvedNodeContract, canonical_input_bindings,
)
from app.ir.node_contracts import NodeContractRefusal, canonical_node_contract
from app.ir.registry import (
    DependencyBoundary, PlatformRegistry, registered_contract_binding,
)
from app.ir.resolve import ResolutionError, resolve_v2
from app.ir.validity import NumericValue, ValidityState
from app.market_data.requirements import (
    DataRequirementRefusal, compile_data_requirement_plan, verify_data_requirement_plan,
)


ROOT = Path(__file__).resolve().parents[3]
CATALOGUE = ROOT / ".agent/runs/post-phase5-indicator-accuracy-correction-replan/current-catalogue.json"
CATALOGUE_SHA = "f0be00e88ca9b1c3799ec98ab14fe16359b0ccf0bd2d1c2a32f422075e17cb6f"
LEGACY_NAMES = """
ACCUMULATION_DISTRIBUTION ADX ALPHA ANCHORED_VWAP ASK ATR BARS_SINCE_SESSION_OPEN
BETA BETA_ADJUSTED_SPREAD BID BOLLINGER_BANDS BOLLINGER_BANDWIDTH BOLLINGER_PERCENT_B
BOOK_DEPTH CCI CHAIKIN_MONEY_FLOW CHAIKIN_OSCILLATOR CLOSE CORRELATION COVARIANCE
CROSS_ABOVE CROSS_BELOW CUMULATIVE_RETURN DISTANCE_FROM_SESSION_HIGH_LOW
DONCHIAN_CHANNELS DTE EMA EWMA_VOLATILITY EXPIRY_CALENDAR FALLING GAP GAP_DOWN GAP_UP
GARMAN_KLASS HIGH HL2 HLC3 ICHIMOKU_COMPONENTS INSIDE_BAR INSTRUMENT_METADATA KAMA
KELTNER_CHANNELS LINEAR_REGRESSION_INTERCEPT LINEAR_REGRESSION_SLOPE LOG_RETURN LOW
LTP MACD MAD MARKET_CLOCK MA_SLOPE MFI MID MIDPOINT MINUS_DI MOMENTUM NATR OBV
OHLC4 OHLCV OPEN OPENING_RANGE OPEN_INTEREST OUTSIDE_BAR PARABOLIC_SAR PARKINSON
PERCENTILE PERCENTILE_RANK PERCENT_RETURN PLUS_DI POINT_CHANGE PPO
PREVIOUS_SESSION_FIELDS PREVIOUS_SESSION_OHLC PRICE_MA_DISTANCE PRICE_VOLUME_TREND
RATIO REALIZED_VOLATILITY RELATIVE_VOLUME RESAMPLING RESIDUAL RISING RMA_WILDER ROC
ROGERS_SATCHELL ROLLING_HEDGE_RATIO ROLLING_HIGH ROLLING_LOW ROLLING_MAX ROLLING_MEAN
ROLLING_MEDIAN ROLLING_MIN ROLLING_RANK ROLLING_REGRESSION ROLLING_RETURN
ROLLING_STDDEV ROLLING_VARIANCE ROLLING_VOLUME_PERCENTILE RSI R_SQUARED
SESSION_CALENDAR SESSION_HIGH SESSION_LOW SESSION_OPEN SESSION_OPEN_HIGH_LOW SMA
SPREAD STOCHASTIC STOCH_RSI SUPERTREND TIMEFRAME TIME_TO_SESSION_CLOSE
TREND_PERSISTENCE TRUE_RANGE TYPICAL_PRICE VOLATILITY_PERCENTILE VOLATILITY_RANK
VOLUME_ZSCORE VWAP VWMA WEIGHTED_CLOSE WILLIAMS_R WMA YANG_ZHANG ZSCORE
""".split()
V1_FIELDS = tuple("""stable_node_id semantic_version visible_family input_types
output_types required_market_fields required_resolution warmup_history
execution_form state_initialization state_reset_policy bar_policy missing_data_policy
numeric_validity_policy causal_declaration evaluation_triggers streaming_support
batch_support mode_eligibility provider_requirements resource_profile reference_provenance""".split())
V2_FIELDS = ("schema", *V1_FIELDS, "parameter_binding")
BOUND_FIELDS = tuple("""schema component source_contract_address binding_implementation_address
parameters input_binding resolved_contract bound_requirements bound_contract_address""".split())
INPUT_FIELDS = tuple("""schema owner_id dataset_context_address evaluation_context_address
dataset_manifest_address market_truth_address provider_product_address provider_contract_address
canonical_instrument_address instrument timeframe fields freshness depth session alignment derived_local""".split())
COMPONENT = ("assurance.contract_pair", 2)


def plain(value):
    if isinstance(value, Mapping):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    return value


def address(value):
    # Independent wire serializer; deliberately does not call product hashing.
    wire = json.dumps(plain(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return "sha256:" + hashlib.sha256(wire.encode("utf-8")).hexdigest()


def mark(name):
    return address({"independent_assurance_fact": name})


def source_contract():
    return {
        "schema": "first-party-node-contract/2", "stable_node_id": COMPONENT[0],
        "semantic_version": 2, "visible_family": "TYPE_2",
        "input_types": {"frame": "market-frame/series", "peer": "market-frame/series"},
        "output_types": {"near": "number/series", "spread": "number/series"},
        "required_market_fields": ["close", "open", "peer.close"],
        "required_resolution": {"source": "canonical_input_binding", "port": "frame", "alignment": "BAR_CLOSE"},
        "warmup_history": {"rule_id": "assurance.pair_history", "rule_version": 1},
        "execution_form": "ROLLING",
        "state_initialization": {"schema": "state-initialization/1", "initial_state_address": None},
        "state_reset_policy": {"schema": "state-reset-policy/2", "reasons": ["DATA_GAP", "EXPLICIT", "IDENTITY_CHANGE"]},
        "bar_policy": "COMPLETED_ONLY", "missing_data_policy": "PROPAGATE",
        "numeric_validity_policy": "EXPLICIT_VALIDITY", "causal_declaration": "COMPLETED_EVENT_PREFIX",
        "evaluation_triggers": ["completed_bar"], "streaming_support": False, "batch_support": True,
        "mode_eligibility": {"research": False, "paper": False, "live": False},
        "provider_requirements": [mark("provider-specification")],
        "resource_profile": {"compute_microseconds_per_event": 100, "memory_bytes_upper_bound": 65536,
                             "history_bytes_upper_bound": 65536, "state_bytes_upper_bound": 64,
                             "storage_bytes_per_day_upper_bound": 0, "subscription_count_upper_bound": 2,
                             "fanout_upper_bound": 2},
        "reference_provenance": [mark("synthetic-protocol-specification")],
        "parameter_binding": {"scheme": "analytical-contract-binding/1", "rule_id": "assurance.pair_history",
                              "rule_version": 1, "parameter_names": ["lag", "price", "window"],
                              "input_ports": ["frame", "peer"]},
    }


def binding_rule(parameters, inputs):
    """Test-only rule; no product helpers supply requirements or expectations."""
    window = parameters["window"]
    history = window + parameters["lag"]
    rows = []
    for port, field in (("frame", parameters["price"]), ("peer", "CLOSE")):
        fact = inputs["ports"][port]["binding"]
        rows.append({"requirement_id": port + "_" + field.lower(), "instrument": dict(fact["instrument"]),
                     "field": field, "timeframe": fact["timeframe"],
                     "history": {"minimum_bars": 1, "warmup_bars": history},
                     "freshness": dict(fact["freshness"]), "depth": dict(fact["depth"]),
                     "session": fact["session"], "alignment": dict(fact["alignment"]),
                     "derived_local": fact["derived_local"]})
    return {"required_market_fields": sorted([parameters["price"].lower(), "peer.close"]),
            "warmup_history": history, "output_warmup": {"near": window, "spread": history},
            "bound_requirements": rows}


def omit_output_rule(parameters, inputs):
    result = binding_rule(parameters, inputs)
    del result["output_warmup"]["near"]
    return result


def underdeclare_history_rule(parameters, inputs):
    result = binding_rule(parameters, inputs)
    result["bound_requirements"][0]["history"]["warmup_bars"] -= 1
    return result


def ambient_rule(parameters, inputs):
    return open("must-never-be-opened").read()


def port(name, direction):
    value = {"port_id": name, "direction": direction, "semantic_flow": "value", "semantic_role": "assurance_value",
             "type_ref": {"type_id": "assurance.frame", "type_version": 1}, "shape": "series"}
    if direction == "input":
        value["connections"] = {"cardinality": "single", "min": 1, "max": 1, "assembly": "single"}
    return value


def descriptor():
    def parameter(kind, default, domain, enum=None):
        return {"type": kind, "required": False, "default": default, "enum": enum,
                "domain": domain, "units": "value", "serialization": "canonical-json"}
    return {"component_id": COMPONENT[0], "component_version": 2, "domain_family": "indicator",
            "structural_role": "transform", "ports": [port("frame", "input"), port("peer", "input"),
                                                         port("near", "output"), port("spread", "output")],
            "parameters": {"lag": parameter("int", 2, {"minimum": 1, "maximum": 8}),
                           "price": parameter("str", "CLOSE", {"max_length": 5}, ["CLOSE", "OPEN"]),
                           "window": parameter("int", 5, {"minimum": 2, "maximum": 4096})}}


def make_registry(source=None, implementation=binding_rule, registration_change=None, component=None, omit=False):
    source = source_contract() if source is None else source
    registration = registered_contract_binding(component=COMPONENT, source_contract=source,
                                               implementation=implementation,
                                               dependency_boundary=DependencyBoundary("declared_objects", (binding_rule,) if implementation in (omit_output_rule, underdeclare_history_rule) else ()))
    if registration_change:
        registration = replace(registration, **registration_change)
    return PlatformRegistry(components={}, bodies={}, registrations={},
                            v2_types={("assurance.frame", 1): {"type_id": "assurance.frame", "type_version": 1,
                                                             "shapes": ["series"], "runtime_representation": "frame"}},
                            v2_components={COMPONENT: component or descriptor()}, node_contracts={COMPONENT: source},
                            contract_bindings={} if omit else {COMPONENT: registration})


def graph(parameters=None):
    return {"format_version": 2, "strategy_id": "independent-contract-assurance", "strategy_version": 1,
            "metadata": {"metadata_version": 1, "name": "Independent assurance", "description": None, "tags": []},
            "graph_inputs": [port("price_feed", "input"), port("peer_feed", "input")], "graph_outputs": [],
            "nodes": [{"node_id": "subject", "component": {"component_id": COMPONENT[0], "component_version": 2},
                       "parameters": {} if parameters is None else parameters}],
            "edges": [{"edge_id": name, "source": {"scope": "graph_input", "port_id": feed},
                       "target": {"scope": "node", "node_id": "subject", "port_id": name}, "binding": {"kind": "single"}}
                      for name, feed in (("frame", "price_feed"), ("peer", "peer_feed"))]}


def input_facts():
    result = {}
    for feed, role in (("price_feed", "primary"), ("peer_feed", "peer")):
        result[feed] = {"schema": "canonical-input-binding/1", "owner_id": "owner-assurance",
                        "dataset_context_address": mark("dataset"), "evaluation_context_address": mark("evaluation"),
                        "dataset_manifest_address": mark("manifest-" + feed), "market_truth_address": mark("market-truth"),
                        "provider_product_address": mark("data-product"), "provider_contract_address": mark("data-contract"),
                        "canonical_instrument_address": mark(role), "instrument": {"role": role, "type": "PHYSICAL"},
                        "timeframe": 300, "fields": ["CLOSE", "OPEN"], "freshness": {"maximum_age_seconds": 600},
                        "depth": {"kind": "NONE", "levels": None}, "session": "INSTRUMENT_CALENDAR",
                        "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0}, "derived_local": True}
    return result


def context(facts=None, *, pins=None, owner="owner-assurance", dataset=None, evaluation=None):
    facts = input_facts() if facts is None else facts
    return canonical_input_bindings(owner_id=owner, dataset_context_address=dataset or mark("dataset"),
                                    evaluation_context_address=evaluation or mark("evaluation"), bindings=facts,
                                    expected_source_addresses=pins or {key: address(value) for key, value in facts.items()})


@pytest.fixture(scope="module")
def canonical_case():
    registry = make_registry()
    resolved = resolve_v2(graph(), registry)
    inputs = context()
    plan = compile_data_requirement_plan(resolved, registry=registry, input_bindings=inputs)
    return registry, resolved, inputs, plan


def receipt(plan):
    value = plain(plan.parameter_binding_provenance[0]["node_contract_binding"])
    return ResolvedNodeContract(value, value["bound_contract_address"])


@pytest.fixture(scope="module")
def legacy():
    from app.ir.library import REGISTRY
    data = CATALOGUE.read_bytes()
    assert hashlib.sha256(data).hexdigest() == CATALOGUE_SHA
    records = json.loads(data)["records"]
    assert len(records) == len(LEGACY_NAMES) == len(set(LEGACY_NAMES)) == 125
    assert {row["name"] for row in records} == set(LEGACY_NAMES)
    return REGISTRY, {row["name"]: row for row in records}


@pytest.mark.parametrize("name", LEGACY_NAMES)
def test_all_125_frozen_v1_identities_and_fields(legacy, name):
    registry, records = legacy
    expected = records[name]
    key = ("analytical." + name.lower(), 1)
    assert (expected["component_id"], expected["component_version"]) == key
    assert set(expected["node_contract"]) == set(V1_FIELDS)
    assert plain(registry.v2_components[key]) == expected["descriptor"]
    assert plain(registry.node_contracts[key]) == expected["node_contract"]
    assert plain(registry.data_requirement_declarations[key]) == expected["data_requirement"]
    assert registry.node_contract_addresses[key] == expected["node_contract_address"] == address(
        {"schema": "first-party-node-contract/1", **expected["node_contract"]})
    assert registry.data_requirement_declaration_addresses[key] == expected["data_requirement_address"] == address(expected["data_requirement"])
    registration = registry.v2_implementation_registrations[key]
    assert registration.implementation_address == expected["implementation_address"]


def test_no_analytical_v2_publication_and_default_registry_is_frozen(legacy):
    registry, _ = legacy
    expected = {("analytical." + name.lower(), 1) for name in LEGACY_NAMES}
    assert {key for key in registry.v2_components if key[0].startswith("analytical.")} == expected
    assert not registry.contract_bindings
    assert address(registry.registry_snapshot_payload) == registry.registry_snapshot_address == "sha256:bef51d976101e495d3666fb89e3a6f0be4ea6dbe87ad7a0d4f2f1c075a9812d0"


@pytest.mark.parametrize("field", V1_FIELDS)
@pytest.mark.parametrize("defect", ["missing", "malformed"])
def test_each_v1_contract_field_is_required_and_typed(legacy, field, defect):
    value = deepcopy(legacy[1]["SMA"]["node_contract"])
    if defect == "missing":
        del value[field]
    else:
        value[field] = None
    with pytest.raises(NodeContractRefusal):
        canonical_node_contract(("analytical.sma", 1), value)


@pytest.mark.parametrize("field", V2_FIELDS)
@pytest.mark.parametrize("defect", ["missing", "malformed"])
def test_each_v2_contract_field_is_required_and_typed(field, defect):
    source = source_contract()
    if defect == "missing":
        del source[field]
    else:
        source[field] = None
    with pytest.raises(NodeContractRefusal):
        make_registry(source=source)


@pytest.mark.parametrize("version", [1, 2])
def test_contracts_reject_extra_top_level_fields(legacy, version):
    if version == 1:
        value = deepcopy(legacy[1]["SMA"]["node_contract"])
        value["schema"] = "first-party-node-contract/1"
        with pytest.raises(NodeContractRefusal):
            canonical_node_contract(("analytical.sma", 1), value)
    else:
        value = source_contract(); value["client_approved"] = True
        with pytest.raises(NodeContractRefusal):
            make_registry(source=value)


@pytest.mark.parametrize("section", ["parameter_binding", "warmup_history", "required_resolution", "state_reset_policy",
                                    "state_initialization", "mode_eligibility", "resource_profile"])
def test_nested_v2_contract_fields_are_closed(section):
    baseline = source_contract()
    for field in baseline[section]:
        source = deepcopy(baseline); del source[section][field]
        with pytest.raises(NodeContractRefusal):
            make_registry(source=source)
    source = deepcopy(baseline); source[section]["extra"] = 1
    with pytest.raises(NodeContractRefusal):
        make_registry(source=source)


@pytest.mark.parametrize("section,field,value", [
    ("parameter_binding", "rule_version", True), ("warmup_history", "rule_id", "different.rule"),
    ("parameter_binding", "parameter_names", ["window", "price", "lag"]),
    ("parameter_binding", "input_ports", ["frame", "frame"]),
    ("required_resolution", "port", "unbound"), ("required_resolution", "source", "client_timeframe"),
    ("state_reset_policy", "reasons", ["FILL"]), ("mode_eligibility", "paper", True),
    ("mode_eligibility", "live", True), ("resource_profile", "fanout_upper_bound", True),
])
def test_v2_contract_semantic_refusals(section, field, value):
    source = source_contract(); source[section][field] = value
    with pytest.raises(NodeContractRefusal):
        make_registry(source=source)


@pytest.mark.parametrize("change", [
    {"rule_id": "other.rule"}, {"rule_version": 2}, {"rule_version": True},
    {"component": ("other.component", 2)}, {"source_contract_address": mark("wrong-source")},
])
def test_registry_refuses_mismatched_registration(change):
    with pytest.raises(ValueError):
        make_registry(registration_change=change)


def test_stale_implementation_address_guard():
    with pytest.raises(ValueError, match="implementation identity is stale or forged"):
        make_registry(registration_change={"implementation_address": mark("stale-implementation")})


def test_registry_refuses_omitted_binding_and_ambient_code():
    with pytest.raises(ValueError, match="missing or extra"):
        make_registry(omit=True)
    with pytest.raises(ValueError):
        make_registry(implementation=ambient_rule)


def test_output_omission_guard():
    registry = make_registry(implementation=omit_output_rule)
    resolved = resolve_v2(graph(), registry)
    with pytest.raises(DataRequirementRefusal, match="every output"):
        compile_data_requirement_plan(resolved, registry=registry, input_bindings=context())


def test_underdeclared_history_guard():
    registry = make_registry(implementation=underdeclare_history_rule)
    resolved = resolve_v2(graph(), registry)
    with pytest.raises(DataRequirementRefusal, match="understates or changes exact warmup"):
        compile_data_requirement_plan(resolved, registry=registry, input_bindings=context())


@pytest.mark.parametrize("parameters,history,near", [
    ({}, 7, 5), ({"window": 2, "lag": 1, "price": "CLOSE"}, 3, 2),
    ({"price": "OPEN", "window": 11, "lag": 4}, 15, 11),
    ({"window": 4096, "lag": 8, "price": "CLOSE"}, 4104, 4096),
])
def test_independent_complete_bound_receipt(canonical_case, parameters, history, near):
    registry = canonical_case[0]
    resolved = resolve_v2(graph(parameters), registry)
    plan = compile_data_requirement_plan(resolved, registry=registry, input_bindings=context())
    bound = plain(receipt(plan).document)
    params = {"lag": 2, "price": "CLOSE", "window": 5, **parameters}
    source = source_contract()
    expected_contract = {key: deepcopy(source[key]) for key in V1_FIELDS}
    expected_contract.update(required_market_fields=sorted([params["price"].lower(), "peer.close"]),
                             required_resolution={"timeframe_seconds": 300, "alignment": "BAR_CLOSE"},
                             warmup_history=history, output_warmup={"near": near, "spread": history})
    expected_inputs = {"schema": "node-input-binding/1", "owner_id": "owner-assurance",
                       "dataset_context_address": mark("dataset"), "evaluation_context_address": mark("evaluation"),
                       "context_address": context().context_address,
                       "ports": {port_name: {"source": {"scope": "graph_input", "port_id": feed},
                                             "binding_address": address(input_facts()[feed]), "binding": input_facts()[feed]}
                                 for port_name, feed in (("frame", "price_feed"), ("peer", "peer_feed"))}}
    expected_rows = []
    for port_name, feed, field in (("frame", "price_feed", params["price"]), ("peer", "peer_feed", "CLOSE")):
        expected_rows.append({"requirement_id": port_name + "_" + field.lower(),
                              "instrument": input_facts()[feed]["instrument"], "field": field, "timeframe": 300,
                              "history": {"minimum_bars": 1, "warmup_bars": history},
                              "freshness": {"maximum_age_seconds": 600}, "depth": {"kind": "NONE", "levels": None},
                              "session": "INSTRUMENT_CALENDAR", "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0},
                              "derived_local": True})
    expected = {"schema": "resolved-node-contract/1", "component": {"component_id": COMPONENT[0], "component_version": 2},
                "source_contract_address": address(source), "binding_implementation_address": registry.contract_bindings[COMPONENT].implementation_address,
                "parameters": params, "input_binding": expected_inputs,
                "resolved_contract": expected_contract, "bound_requirements": expected_rows}
    expected["bound_contract_address"] = address(expected)
    assert set(bound) == set(BOUND_FIELDS)
    assert bound == expected
    assert [plain(row["requirement"]) for row in plan.requirements] == expected_rows
    assert verify_data_requirement_plan(plan, resolved, registry=registry, input_bindings=context()) == plan
    assert plain(registry.registry_snapshot_payload)["contract_bindings"] == [plain(registry.contract_bindings[COMPONENT].document)]
    assert plain(registry.node_contracts[COMPONENT]) == source


@pytest.mark.parametrize("parameters", [
    {"window": 1}, {"window": 4097}, {"window": True}, {"window": 3.0}, {"window": None},
    {"lag": 0}, {"lag": 9}, {"price": "HIGH"}, {"price": None}, {"extra": 2},
])
def test_resolver_refuses_outside_parameter_domain(canonical_case, parameters):
    with pytest.raises(ResolutionError):
        resolve_v2(graph(parameters), canonical_case[0])


def test_parameter_order_is_nonsemantic_and_missing_normalized_parameter_refuses(canonical_case):
    registry, _, _, plan = canonical_case
    one = resolve_v2(graph({"window": 5, "price": "CLOSE", "lag": 2}), registry)
    two = resolve_v2(graph({"lag": 2, "price": "CLOSE", "window": 5}), registry)
    assert one.resolved_graph_address == two.resolved_graph_address
    bound = receipt(plan)
    with pytest.raises(NodeContractRefusal, match="every normalized"):
        registry.bind_node_contract(COMPONENT, {"window": 5, "lag": 2}, bound.document["input_binding"])


@pytest.mark.parametrize("field", INPUT_FIELDS)
def test_each_input_fact_missing_or_stale_refuses(field):
    facts = input_facts(); pins = {key: address(value) for key, value in facts.items()}
    del facts["price_feed"][field]
    with pytest.raises(NodeContractRefusal):
        context(facts, pins=pins)
    facts = input_facts(); facts["price_feed"][field] = None
    with pytest.raises(NodeContractRefusal):
        context(facts, pins=pins)


def test_missing_extra_or_misowned_input_context_refuses(canonical_case):
    registry, resolved, _, _ = canonical_case
    with pytest.raises(DataRequirementRefusal):
        compile_data_requirement_plan(resolved, registry=registry)
    with pytest.raises(DataRequirementRefusal):
        compile_data_requirement_plan(resolved, input_bindings=context())
    for defect in ("extra", "missing", "role", "field"):
        facts = input_facts()
        if defect == "extra": facts["unused"] = deepcopy(facts["price_feed"])
        elif defect == "missing": del facts["peer_feed"]
        elif defect == "role": facts["peer_feed"]["instrument"]["role"] = "primary"
        else: facts["peer_feed"]["fields"] = ["OPEN"]
        with pytest.raises(DataRequirementRefusal):
            compile_data_requirement_plan(resolved, registry=registry, input_bindings=context(facts))
    with pytest.raises(NodeContractRefusal):
        context(owner="different-owner")


@pytest.mark.parametrize("field,value", [
    ("timeframe", 900), ("dataset_manifest_address", mark("other-manifest")),
    ("market_truth_address", mark("other-calendar")), ("provider_product_address", mark("other-data-product")),
    ("provider_contract_address", mark("other-provider-contract")),
    ("canonical_instrument_address", mark("other-instrument")),
    ("freshness", {"maximum_age_seconds": 900}), ("alignment", {"kind": "EXACT", "maximum_skew_seconds": 5}),
    ("derived_local", False),
])
def test_source_context_changes_cannot_reuse_plan(canonical_case, field, value):
    registry, resolved, old_context, old_plan = canonical_case
    facts = input_facts(); facts["price_feed"][field] = value
    with pytest.raises(NodeContractRefusal):
        context(facts, pins={key: address(fact) for key, fact in input_facts().items()})
    new_context = context(facts)
    # Fresh independent pins represent a different producer receipt, not authority.
    new_plan = compile_data_requirement_plan(resolved, registry=registry, input_bindings=new_context)
    assert new_plan.plan_address != old_plan.plan_address
    with pytest.raises(DataRequirementRefusal, match="reconstructed"):
        verify_data_requirement_plan(old_plan, resolved, registry=registry, input_bindings=new_context)
    assert verify_data_requirement_plan(old_plan, resolved, registry=registry, input_bindings=old_context) == old_plan


@pytest.mark.parametrize("kind", ["owner", "dataset", "evaluation"])
def test_cross_context_plan_replay_refuses(canonical_case, kind):
    registry, resolved, _, plan = canonical_case
    facts = input_facts()
    key = {"owner": "owner_id", "dataset": "dataset_context_address", "evaluation": "evaluation_context_address"}[kind]
    value = "different-owner" if kind == "owner" else mark("other-" + kind)
    for fact in facts.values(): fact[key] = value
    new_context = context(facts, **{kind: value})
    with pytest.raises(DataRequirementRefusal, match="reconstructed"):
        verify_data_requirement_plan(plan, resolved, registry=registry, input_bindings=new_context)


def rehash_plan(plan, bound):
    bound["bound_contract_address"] = address({key: value for key, value in bound.items() if key != "bound_contract_address"})
    provenance = plain(plan.parameter_binding_provenance)
    provenance[0]["node_contract_binding"] = bound
    changed = replace(plan, parameter_binding_provenance=tuple(provenance))
    # Rehash the exact plan wire form, including component dictionaries.
    payload = plain(vars(changed)); payload.pop("plan_address")
    for row in payload["requirements"]:
        if isinstance(row["leaf_component"], list):
            row["leaf_component"] = {"component_id": row["leaf_component"][0], "component_version": row["leaf_component"][1]}
    return replace(changed, plan_address=address(payload))


@pytest.mark.parametrize("field", BOUND_FIELDS)
def test_rehashed_omission_is_rejected_by_plan_consumer(canonical_case, field):
    registry, resolved, inputs, plan = canonical_case
    value = plain(receipt(plan).document)
    if field == "bound_contract_address":
        value[field] = mark("stale")
        forged = replace(plan, parameter_binding_provenance=({**plain(plan.parameter_binding_provenance[0]), "node_contract_binding": value},))
    else:
        del value[field]
        forged = rehash_plan(plan, value)
    with pytest.raises(DataRequirementRefusal, match="reconstructed"):
        verify_data_requirement_plan(forged, resolved, registry=registry, input_bindings=inputs)


@pytest.mark.parametrize("field,value", [
    ("schema", "resolved-node-contract/99"), ("component", {"component_id": "other", "component_version": 2}),
    ("source_contract_address", mark("wrong-source")), ("binding_implementation_address", mark("wrong-rule")),
    ("parameters", {"lag": 2, "price": "CLOSE", "window": 2}),
    ("input_binding", {}), ("resolved_contract", {}), ("bound_requirements", []),
])
def test_rehashed_wrong_bound_facts_are_not_authority(canonical_case, field, value):
    registry, resolved, inputs, plan = canonical_case
    document = plain(receipt(plan).document); document[field] = value
    forged = rehash_plan(plan, document)
    with pytest.raises(DataRequirementRefusal, match="reconstructed"):
        verify_data_requirement_plan(forged, resolved, registry=registry, input_bindings=inputs)
    assert verify_data_requirement_plan(plan, resolved, registry=registry, input_bindings=inputs) == plan


def test_rehashed_lower_warmup_extra_field_and_parameter_graph_cannot_replay(canonical_case):
    registry, resolved, inputs, plan = canonical_case
    document = plain(receipt(plan).document)
    document["resolved_contract"]["warmup_history"] = 1
    document["resolved_contract"]["output_warmup"] = {"near": 1, "spread": 1}
    for row in document["bound_requirements"]: row["history"]["warmup_bars"] = 1
    with pytest.raises(DataRequirementRefusal):
        verify_data_requirement_plan(rehash_plan(plan, document), resolved, registry=registry, input_bindings=inputs)
    document = plain(receipt(plan).document); document["client_approved"] = True
    with pytest.raises(DataRequirementRefusal):
        verify_data_requirement_plan(rehash_plan(plan, document), resolved, registry=registry, input_bindings=inputs)
    changed = resolve_v2(graph({"window": 2}), registry)
    with pytest.raises(DataRequirementRefusal):
        verify_data_requirement_plan(plan, changed, registry=registry, input_bindings=inputs)


def state_facts():
    return {"strategy_address": mark("strategy"), "resolved_graph_address": mark("graph"),
            "implementation_closure_address": mark("closure"), "last_event_address": mark("event"),
            "last_event_time": "2026-08-28T04:00:00+00:00", "state_bytes_digest": mark("state-bytes"),
            "validity_state": "INSUFFICIENT_HISTORY", "reset_reasons": ["DATA_GAP"],
            "creation_evidence_address": mark("creation")}


def test_state_binds_exact_contract_context_and_closed_fields(canonical_case):
    bound = receipt(canonical_case[3])
    snapshot = bound_state_snapshot(bound, **state_facts())
    expected = {"schema": "state-snapshot/2", **state_facts(), "bound_contract_address": bound.bound_contract_address,
                "node_contract_address": address(source_contract()),
                "reset_policy_address": address(source_contract()["state_reset_policy"]),
                "dataset_context_address": mark("dataset"), "evaluation_context_address": mark("evaluation")}
    expected["snapshot_address"] = address(expected)
    assert plain(snapshot.document) == expected
    assert verify_bound_state_snapshot(expected, bound) == snapshot
    for field in expected:
        document = deepcopy(expected); del document[field]
        with pytest.raises(NodeContractRefusal): verify_bound_state_snapshot(document, bound)
    document = deepcopy(expected); document["extra"] = True
    with pytest.raises(NodeContractRefusal): verify_bound_state_snapshot(document, bound)
    for field in ("bound_contract_address", "node_contract_address", "dataset_context_address", "evaluation_context_address", "reset_policy_address"):
        document = deepcopy(expected); document[field] = mark("forged-" + field)
        document["snapshot_address"] = address({key: value for key, value in document.items() if key != "snapshot_address"})
        with pytest.raises(NodeContractRefusal, match="stale or mismatched"):
            verify_bound_state_snapshot(document, bound)


@pytest.mark.parametrize("facts", [
    {"reset_reasons": ["SESSION"]}, {"reset_reasons": ["unknown"]}, {"validity_state": "FALSE"},
    {"last_event_time": "2026-08-28T04:00:00"}, {"last_event_time": "2026-08-28T09:30:00+05:30"},
    {"bound_contract_address": mark("override")}, {"node_contract_address": mark("override")},
])
def test_state_refuses_unknown_reset_validity_time_or_owned_fact(canonical_case, facts):
    with pytest.raises(NodeContractRefusal):
        bound_state_snapshot(receipt(canonical_case[3]), **{**state_facts(), **facts})


def test_state_cannot_cross_parameter_owner_timeframe_or_session_identity(canonical_case):
    registry, resolved, _, plan = canonical_case
    old = bound_state_snapshot(receipt(plan), **state_facts())
    changed_graph = resolve_v2(graph({"window": 2}), registry)
    variants = [(changed_graph, context())]
    for field, value in (("owner_id", "different-owner"), ("timeframe", 900), ("market_truth_address", mark("other-session"))):
        facts = input_facts()
        for fact in facts.values(): fact[field] = value
        variants.append((resolved, context(facts, **({"owner": value} if field == "owner_id" else {}))))
    for graph_value, inputs in variants:
        changed = compile_data_requirement_plan(graph_value, registry=registry, input_bindings=inputs)
        with pytest.raises(NodeContractRefusal):
            verify_bound_state_snapshot(old.document, receipt(changed))


@pytest.mark.parametrize("value,state,numeric", [
    (0, "VALID", 0.0), (1.25, "VALID", 1.25), (None, "MISSING", None),
    (float("nan"), "INVALID", None), (float("inf"), "INVALID", None),
    (float("-inf"), "INVALID", None), (True, "INVALID", None), ("not-numeric", "INVALID", None),
    # The existing canonical raw numeric ingress explicitly accepts numeric text.
    ("12", "VALID", 12.0),
])
def test_explicit_numeric_validity_without_fallback(value, state, numeric):
    result = required_numeric_scalar({"close": value}, "close")
    assert result.state.value == state and result.value == numeric
    with pytest.raises(NodeContractRefusal): required_numeric_scalar({"open": 99}, "close")


@pytest.mark.parametrize("value,state,numeric", [
    (False, "VALID", False), (True, "VALID", True), (None, "MISSING", None),
    (0, "INVALID", None), (1, "INVALID", None), ("false", "INVALID", None),
])
def test_false_is_distinct_from_unknown_condition(value, state, numeric):
    result = required_condition({"condition": value}, "condition")
    assert result.state.value == state and result.value is numeric
    with pytest.raises(NodeContractRefusal): required_condition({}, "condition")


@pytest.mark.parametrize("state", [state for state in ValidityState if state is not ValidityState.VALID])
def test_each_nonvalid_state_survives_without_executable_value(state):
    value = NumericValue(state)
    assert required_numeric_scalar({"close": value}, "close") == value
    assert required_condition({"condition": value}, "condition") == value


def test_safe_offline_runtime():
    from app.core.config import Settings
    import numpy
    import pandas
    assert Settings.model_config["env_file"] is None
    assert os.environ["PT_PROVIDER"] == "mock"
    assert os.environ["PT_EXECUTION"] == "paper"
    assert os.environ["PT_LIVE_ACK"] == ""
    for name in ("PT_DB_PATH", "PT_LEDGER_DB_PATH", "PT_RESEARCH_DB_PATH"):
        assert Path(os.environ[name]).is_absolute()
        assert "paper-trader-pytest-" in os.environ[name]
    assert numpy.__version__ == "2.5.2"
    assert pandas.__version__ == "3.0.5"
