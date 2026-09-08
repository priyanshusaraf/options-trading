"""Registered semantic-v2 monitoring target and protection value contracts.

These components describe alert-only strategy intent. They cannot create a deployment, order, capital reservation,
position, broker request, or exchange protection instruction.
"""
from __future__ import annotations

import collections.abc as abc
import decimal
import re
import pandas as pd

from app.ir import hashing, node_contracts, registry, schema, validity
from app.ir.first_party import execution_intent


class MonitoringIntentRefusal(node_contracts.NodeContractRefusal):
    """Typed refusal at the monitoring-language boundary."""


TARGET_SPECS = node_contracts._freeze({
    "BUY": {"target_state": "LONG", "risk_reducing": False},
    "SELL": {"target_state": "SHORT", "risk_reducing": False},
    "ENTER_LONG": {"target_state": "LONG", "risk_reducing": False},
    "ENTER_SHORT": {"target_state": "SHORT", "risk_reducing": False},
    "CLOSE_POSITION": {"target_state": "FLAT", "risk_reducing": True},
    "SESSION_EXIT": {"target_state": "FLAT", "risk_reducing": True},
    "EXPIRY_EXIT": {"target_state": "FLAT", "risk_reducing": True},
})

PROTECTION_SPECS = node_contracts._freeze({
    "FIXED_STOP_PERCENT": {
        "kind": "STOP_LOSS", "basis": "PERCENT_FROM_ENTRY_REFERENCE",
        "parameter": "rate", "minimum": "0.000001", "maximum": "0.999999",
        "units": "RATE", "input": "condition",
    },
    "POINT_STOP": {
        "kind": "STOP_LOSS", "basis": "DISTANCE_FROM_ENTRY_REFERENCE",
        "parameter": "distance", "minimum": "0.000001", "maximum": "1000000000000",
        "units": "PRICE_POINTS", "input": "condition",
    },
    "ATR_STOP": {
        "kind": "STOP_LOSS", "basis": "VERIFIED_INDICATOR_DISTANCE",
        "parameter": "multiplier", "minimum": "0.000001", "maximum": "100",
        "units": "PRICE_POINTS", "input": "distance",
    },
    "TAKE_PROFIT_PERCENT": {
        "kind": "TAKE_PROFIT", "basis": "PERCENT_FROM_ENTRY_REFERENCE",
        "parameter": "rate", "minimum": "0.000001", "maximum": "100",
        "units": "RATE", "input": "condition",
    },
    "RISK_REWARD_TARGET": {
        "kind": "TAKE_PROFIT", "basis": "DISTANCE_FROM_ENTRY_REFERENCE",
        "parameter": "ratio", "minimum": "0.000001", "maximum": "100",
        "units": "PRICE_POINTS", "input": "distance",
    },
})

NAMES = tuple(sorted((*TARGET_SPECS, *PROTECTION_SPECS)))
UNSUPPORTED_NAMES = tuple(sorted(set(execution_intent.TYPE_1_NAMES) - set(NAMES)))
ALL_TYPE_1_NAMES = tuple(sorted((*NAMES, *UNSUPPORTED_NAMES)))
MAX_PREFIX_EVENTS = 100_000
FINAL_PREFIX_CONDITION = ("monitoring.final_prefix_condition", 1)
_FORBIDDEN_OUTPUT_FIELDS = frozenset({
    "account", "allocation", "armed", "broker", "broker_account", "capital",
    "deployment", "execution", "fill", "lease", "live", "money", "order",
    "position", "quantity", "reservation", "route", "tradingsymbol",
})
_RESOURCE_PROFILE = {
    "compute_microseconds_per_event": 2500,
    "memory_bytes_upper_bound": 524288,
    "history_bytes_upper_bound": 0,
    "state_bytes_upper_bound": 0,
    "storage_bytes_per_day_upper_bound": 0,
    "subscription_count_upper_bound": 0,
    "fanout_upper_bound": 1,
}


def component_key(name):
    if name not in NAMES:
        if name in UNSUPPORTED_NAMES:
            raise MonitoringIntentRefusal("V0_MONITORING_OPERATION_UNAVAILABLE")
        raise MonitoringIntentRefusal("V0_MONITORING_OPERATION_UNKNOWN")
    return ("intent." + name.lower(), 2)


def refusal_for(name):
    if name not in UNSUPPORTED_NAMES:
        raise MonitoringIntentRefusal("V0_MONITORING_REFUSAL_UNKNOWN")
    return node_contracts._freeze({
        "schema": "monitoring-operation-refusal/1",
        "component_id": "intent." + name.lower(),
        "semantic_version": 2,
        "operation": name,
        "code": "V0_MONITORING_OPERATION_UNAVAILABLE",
        "executable": False,
        "authority": "NONE",
    })


REFUSALS = node_contracts._freeze({name: refusal_for(name) for name in UNSUPPORTED_NAMES})


def _canonical_decimal(value, *, minimum, maximum, label):
    if not isinstance(value, str) or not re.fullmatch(
            r"^(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$", value):
        raise MonitoringIntentRefusal(f"{label}_CANONICAL_DECIMAL_REQUIRED")
    try:
        number = decimal.Decimal(value)
        lower = decimal.Decimal(minimum)
        upper = decimal.Decimal(maximum)
    except decimal.DecimalException as exc:
        raise MonitoringIntentRefusal(f"{label}_CANONICAL_DECIMAL_REQUIRED") from exc
    if not number.is_finite() or not lower <= number <= upper:
        raise MonitoringIntentRefusal(f"{label}_OUT_OF_RANGE")
    return number


def parameters_for(name, supplied=None):
    component_key(name)
    supplied = {} if supplied is None else supplied
    if not isinstance(supplied, abc.Mapping):
        raise MonitoringIntentRefusal("MONITORING_PARAMETERS_OBJECT_REQUIRED")
    if name in TARGET_SPECS:
        if supplied:
            raise MonitoringIntentRefusal("MONITORING_PARAMETERS_UNKNOWN")
        return node_contracts._freeze({})
    spec = PROTECTION_SPECS[name]
    parameter = spec["parameter"]
    if set(supplied) != {parameter}:
        raise MonitoringIntentRefusal("MONITORING_PARAMETER_REQUIRED")
    value = _canonical_decimal(
        supplied[parameter], minimum=spec["minimum"], maximum=spec["maximum"],
        label="MONITORING_" + parameter.upper(),
    )
    return node_contracts._freeze({parameter: str(value)})


def first_valid_index(name, parameters=None):
    parameters_for(name, parameters)
    return 0


def _type(type_id, representation):
    return {
        "type_id": type_id, "type_version": 1, "shapes": ["scalar"],
        "runtime_representation": representation,
    }


V2_TYPES = node_contracts._freeze({
    ("analytical.boolean", 2): {"type_id": "analytical.boolean", "type_version": 2,
        "shapes": ["series"], "runtime_representation": "indexed NumericValue boolean cells"},
    ("monitoring.condition", 1): _type("monitoring.condition", "NumericValue boolean"),
    ("monitoring.distance", 1): _type("monitoring.distance", "verified exact decimal distance"),
    ("monitoring.target_intent", 1): _type("monitoring.target_intent", "closed monitoring-target-intent/1"),
    ("monitoring.protection", 1): _type("monitoring.protection", "closed monitoring-protection/1"),
})


def _port(port_id, direction, type_id, semantic_role):
    result = {
        "port_id": port_id, "direction": direction,
        "semantic_flow": "condition" if port_id == "condition" else "value",
        "semantic_role": semantic_role,
        "type_ref": {"type_id": type_id, "type_version": 1},
        "shape": "scalar",
    }
    if direction == "input":
        result["connections"] = {
            "cardinality": "single", "min": 1, "max": 1, "assembly": "single",
        }
    return result


def _parameter_descriptor(spec):
    return {
        "type": "str", "required": True, "default": None, "enum": None,
        "domain": {"minimum": spec["minimum"], "maximum": spec["maximum"]},
        "units": spec["units"], "serialization": "canonical-decimal-string",
    }


def descriptor(name):
    component = component_key(name)
    if name in TARGET_SPECS:
        ports = [
            _port("condition", "input", "monitoring.condition", "target_condition"),
            _port("intent", "output", "monitoring.target_intent", "monitoring_target_intent"),
        ]
        parameters = {}
        family = "intent_description"
        role = "sinkless_terminal"
    else:
        spec = PROTECTION_SPECS[name]
        input_id = spec["input"]
        input_type = "monitoring.distance" if input_id == "distance" else "monitoring.condition"
        ports = [
            _port(input_id, "input", input_type, "verified_distance" if input_id == "distance" else "protection_condition"),
            _port("protection", "output", "monitoring.protection", "monitoring_protection"),
        ]
        parameters = {spec["parameter"]: _parameter_descriptor(spec)}
        family = "risk"
        role = "transform"
    return node_contracts._freeze({
        "component_id": component[0], "component_version": component[1],
        "domain_family": family, "structural_role": role,
        "ports": ports, "parameters": parameters,
    })


def source_contract(name):
    component = component_key(name)
    target = name in TARGET_SPECS
    input_port = "condition" if target else PROTECTION_SPECS[name]["input"]
    output_port = "intent" if target else "protection"
    document = {
        "stable_node_id": component[0], "semantic_version": 2,
        "visible_family": "TYPE_1",
        "input_types": {input_port: (
            "numeric-validity-bool/1" if input_port == "condition"
            else "verified-monitoring-distance/1"
        )},
        "output_types": {output_port: (
            "monitoring-target-intent/1" if target else "monitoring-protection/1"
        )},
        "required_market_fields": [],
        "required_resolution": {"timeframe_seconds": 1, "alignment": "EVENT_TIME"},
        "warmup_history": 0, "execution_form": "STATELESS",
        "state_initialization": {"schema": "state-initialization/1", "initial_state_address": None},
        "state_reset_policy": {"schema": "state-reset-policy/1", "reasons": []},
        "bar_policy": "COMPLETED_ONLY", "missing_data_policy": "REFUSE",
        "numeric_validity_policy": "EXPLICIT_VALIDITY",
        "causal_declaration": "COMPLETED_EVENT_PREFIX",
        "evaluation_triggers": ["completed_bar"],
        "streaming_support": True, "batch_support": True,
        "mode_eligibility": {"research": True, "paper": False, "live": False},
        "provider_requirements": [], "resource_profile": dict(_RESOURCE_PROFILE),
        "reference_provenance": [hashing.content_address({
            "monitoring-intent-semantic-v2": name,
            "specification": node_contracts._plain(
                TARGET_SPECS[name] if target else PROTECTION_SPECS[name]
            ),
        })],
    }
    return node_contracts.canonical_node_contract(component, document).document


V2_COMPONENTS = node_contracts._freeze({component_key(name): descriptor(name) for name in NAMES})
NODE_CONTRACTS = node_contracts._freeze({component_key(name): source_contract(name) for name in NAMES})
NODE_CONTRACT_ADDRESSES = node_contracts._freeze({
    key: node_contracts.canonical_node_contract(key, contract).contract_address
    for key, contract in NODE_CONTRACTS.items()
})
DATA_REQUIREMENTS = node_contracts._freeze({
    component_key(name): {
        "schema": "data-requirement-declaration/1",
        "classification": "NO_DATA", "requirements": [],
    }
    for name in NAMES
})


def _condition(value):
    if not isinstance(value, validity.NumericValue):
        raise MonitoringIntentRefusal("MONITORING_CONDITION_NUMERIC_VALUE_REQUIRED")
    if value.state is not validity.ValidityState.VALID:
        raise MonitoringIntentRefusal("MONITORING_CONDITION_" + value.state.value)
    if type(value.value) is not bool:
        raise MonitoringIntentRefusal("MONITORING_CONDITION_BOOLEAN_REQUIRED")
    return value.value


def final_prefix_condition(parameters, inputs):
    """Project a caller-selected causal prefix; this does not certify its data.

    Completion, availability, source binding and freshness belong to the verified
    caller. The explicit node selects only the final value of that prefix and
    never turns an invalid final cell into False or a prior valid condition.
    """
    if (not isinstance(parameters, abc.Mapping) or parameters
            or not isinstance(inputs, abc.Mapping) or set(inputs) != {"series"}):
        raise MonitoringIntentRefusal("MONITORING_PREFIX_BOUNDARY_REQUIRED")
    source = inputs["series"]
    if type(source) is not pd.Series or not 0 < len(source) <= MAX_PREFIX_EVENTS:
        raise MonitoringIntentRefusal("MONITORING_PREFIX_SERIES_REQUIRED")
    _prefix_clock(source.index)
    return {"condition": validity.valid(_condition(source.iloc[-1]))}


def _prefix_clock(index):
    if (type(index) is not pd.DatetimeIndex or index.tz is None or index.hasnans
            or not index.is_monotonic_increasing or not index.is_unique):
        raise MonitoringIntentRefusal("MONITORING_PREFIX_CLOCK_REQUIRED")


def _prefix_descriptor():
    source = _port("series", "input", "analytical.boolean", "causal_prefix")
    source.update(type_ref={"type_id": "analytical.boolean", "type_version": 2}, shape="series")
    return {"component_id": FINAL_PREFIX_CONDITION[0], "component_version": 1,
            "domain_family": "condition", "structural_role": "transform",
            "ports": [source, _port("condition", "output", "monitoring.condition", "final_prefix_condition")],
            "parameters": {}}


def _prefix_contract():
    document = node_contracts._plain(source_contract("BUY"))
    document.update(stable_node_id=FINAL_PREFIX_CONDITION[0], semantic_version=1,
                    visible_family="TYPE_2", input_types={"series": "analytical.boolean/series"},
                    output_types={"condition": "numeric-validity-bool/1"},
                    resource_profile={**_RESOURCE_PROFILE, "fanout_upper_bound": 3},
                    reference_provenance=[hashing.content_address({
                        "schema": "monitoring-final-prefix-condition/1", "selection": "FINAL_PREFIX_CELL",
                        "source_authority": "VERIFIED_CALLER", "invalid_final_cell": "REFUSE"})])
    return node_contracts.canonical_node_contract(FINAL_PREFIX_CONDITION, document).document


def verified_distance(*, value, units, source_component_id, source_component_version,
                      source_component_address, source_contract_address,
                      validity_state="VALID"):
    fields = {
        "schema", "validity", "value", "units", "source_component_id",
        "source_component_version", "source_component_address", "source_contract_address",
    }
    document = {
        "schema": "verified-monitoring-distance/1", "validity": validity_state,
        "value": value, "units": units, "source_component_id": source_component_id,
        "source_component_version": source_component_version,
        "source_component_address": source_component_address,
        "source_contract_address": source_contract_address,
    }
    if set(document) != fields or validity_state not in {state.value for state in validity.ValidityState}:
        raise MonitoringIntentRefusal("MONITORING_DISTANCE_SCHEMA")
    if validity_state != "VALID":
        if value is not None:
            raise MonitoringIntentRefusal("MONITORING_DISTANCE_INVALID_HAS_VALUE")
        return node_contracts._freeze(document)
    _canonical_decimal(value, minimum="0.000001", maximum="1000000000000",
                       label="MONITORING_DISTANCE")
    if units != "PRICE_POINTS" or not isinstance(source_component_id, str) \
            or not source_component_id or type(source_component_version) is not int \
            or source_component_version < 1:
        raise MonitoringIntentRefusal("MONITORING_DISTANCE_IDENTITY")
    for address in (source_component_address, source_contract_address):
        if not isinstance(address, str) or not schema.is_content_address(address):
            raise MonitoringIntentRefusal("MONITORING_DISTANCE_IDENTITY")
    return node_contracts._freeze(document)


def _distance(value):
    if not isinstance(value, abc.Mapping) or set(value) != {
        "schema", "validity", "value", "units", "source_component_id",
        "source_component_version", "source_component_address", "source_contract_address",
    } or value["schema"] != "verified-monitoring-distance/1":
        raise MonitoringIntentRefusal("MONITORING_DISTANCE_SCHEMA")
    if value["validity"] != "VALID":
        if value["validity"] not in {state.value for state in validity.ValidityState}:
            raise MonitoringIntentRefusal("MONITORING_DISTANCE_VALIDITY")
        raise MonitoringIntentRefusal("MONITORING_DISTANCE_" + value["validity"])
    return verified_distance(**{
        "value": value["value"], "units": value["units"],
        "source_component_id": value["source_component_id"],
        "source_component_version": value["source_component_version"],
        "source_component_address": value["source_component_address"],
        "source_contract_address": value["source_contract_address"],
        "validity_state": value["validity"],
    })


def _authored(name, parameters):
    key = component_key(name)
    return {
        "component_id": key[0], "semantic_version": key[1],
        "component_address": hashing.content_address(node_contracts._plain(descriptor(name))),
        "node_contract_address": node_contracts.canonical_node_contract(
            key, source_contract(name),
        ).contract_address,
        "parameters_address": hashing.content_address(node_contracts._plain(parameters)),
    }


def _target(name, parameters, inputs):
    if not isinstance(inputs, abc.Mapping) or set(inputs) != {"condition"}:
        raise MonitoringIntentRefusal("MONITORING_TARGET_INPUTS")
    requested = _condition(inputs["condition"])
    spec = TARGET_SPECS[name]
    return {"intent": {
        "schema": "monitoring-target-intent/1", "operation": name,
        "target_state": spec["target_state"],
        "risk_reducing": spec["risk_reducing"], "requested": requested,
        "authored": _authored(name, parameters), "validity": "VALID",
    }}


def _protection(name, parameters, inputs):
    spec = PROTECTION_SPECS[name]
    input_port = spec["input"]
    if not isinstance(inputs, abc.Mapping) or set(inputs) != {input_port}:
        raise MonitoringIntentRefusal("MONITORING_PROTECTION_INPUTS")
    authored_value = decimal.Decimal(parameters[spec["parameter"]])
    input_identity = None
    if input_port == "condition":
        active = _condition(inputs["condition"])
        resolved_value = authored_value
    else:
        source = _distance(inputs["distance"])
        active = True
        input_identity = {
            key: source[key] for key in (
                "source_component_id", "source_component_version",
                "source_component_address", "source_contract_address",
            )
        }
        resolved_value = decimal.Decimal(source["value"]) * authored_value
        if not resolved_value.is_finite() or resolved_value <= 0 \
                or resolved_value > decimal.Decimal("1000000000000"):
            raise MonitoringIntentRefusal("MONITORING_PROTECTION_RESULT_OUT_OF_RANGE")
    return {"protection": {
        "schema": "monitoring-protection/1", "kind": spec["kind"],
        "basis": spec["basis"], "value": str(resolved_value),
        "units": spec["units"], "active": active,
        "authored_value": str(authored_value),
        "authored": _authored(name, parameters),
        "input_identity": input_identity, "validity": "VALID",
        "authority": "MONITORING_ONLY",
    }}


def _evaluate_known(name, parameters, inputs):
    canonical = parameters_for(name, parameters)
    result = (_target(name, canonical, inputs) if name in TARGET_SPECS
              else _protection(name, canonical, inputs))
    output = next(iter(result.values()))
    if _FORBIDDEN_OUTPUT_FIELDS & set(output):
        raise MonitoringIntentRefusal("MONITORING_AUTHORITY_FIELD_FORBIDDEN")
    return result


def implementation_for(name):
    component_key(name)

    def implementation(parameters, inputs, *, _name=name):
        return _evaluate_known(_name, parameters, inputs)

    return implementation


V2_IMPLEMENTATIONS = node_contracts._freeze({
    component_key(name): registry.registered_v2_implementation(
        component=component_key(name), implementation=implementation_for(name),
        dependency_boundary=registry.DependencyBoundary(
            "defining_module", (abc, decimal, re, hashing, node_contracts, schema, validity),
        ),
    )
    for name in NAMES
})

# This explicit projection leaves the published Type 1 operation set unchanged.
V2_COMPONENTS = node_contracts._freeze({**V2_COMPONENTS, FINAL_PREFIX_CONDITION: _prefix_descriptor()})
NODE_CONTRACTS = node_contracts._freeze({**NODE_CONTRACTS, FINAL_PREFIX_CONDITION: _prefix_contract()})
NODE_CONTRACT_ADDRESSES = node_contracts._freeze({**NODE_CONTRACT_ADDRESSES, FINAL_PREFIX_CONDITION:
    node_contracts.canonical_node_contract(FINAL_PREFIX_CONDITION, NODE_CONTRACTS[FINAL_PREFIX_CONDITION]).contract_address})
DATA_REQUIREMENTS = node_contracts._freeze({**DATA_REQUIREMENTS, FINAL_PREFIX_CONDITION:
    {"schema": "data-requirement-declaration/1", "classification": "NO_DATA", "requirements": []}})
V2_IMPLEMENTATIONS = node_contracts._freeze({**V2_IMPLEMENTATIONS, FINAL_PREFIX_CONDITION:
    registry.registered_v2_implementation(component=FINAL_PREFIX_CONDITION, implementation=final_prefix_condition,
        dependency_boundary=registry.DependencyBoundary("defining_module", (abc, pd, validity)))})


def evaluate(name, parameters, inputs):
    if name in UNSUPPORTED_NAMES:
        raise MonitoringIntentRefusal("V0_MONITORING_OPERATION_UNAVAILABLE")
    return V2_IMPLEMENTATIONS[component_key(name)].implementation(parameters, inputs)


def evaluate_prefix(name, parameters, events):
    if not isinstance(events, (tuple, list)) or not events:
        raise MonitoringIntentRefusal("MONITORING_PREFIX_REQUIRED")
    if len(events) > MAX_PREFIX_EVENTS:
        raise MonitoringIntentRefusal("MONITORING_PREFIX_LIMIT")
    canonical = parameters_for(name, parameters)
    return tuple(_evaluate_known(name, canonical, event) for event in events)


def validate_resolved_geometry(*, direction, entry_reference, stop_loss, take_profit):
    if direction not in {"LONG", "SHORT"}:
        raise MonitoringIntentRefusal("MONITORING_GEOMETRY_DIRECTION")
    entry = _canonical_decimal(
        entry_reference, minimum="0.000001", maximum="1000000000000",
        label="MONITORING_ENTRY_REFERENCE",
    )
    stop = _canonical_decimal(
        stop_loss, minimum="0.000001", maximum="1000000000000",
        label="MONITORING_STOP_LOSS",
    )
    target = _canonical_decimal(
        take_profit, minimum="0.000001", maximum="1000000000000",
        label="MONITORING_TAKE_PROFIT",
    )
    valid_geometry = stop < entry < target if direction == "LONG" else target < entry < stop
    if not valid_geometry:
        raise MonitoringIntentRefusal("MONITORING_PROTECTION_GEOMETRY")
    return node_contracts._freeze({
        "schema": "monitoring-protection-geometry/1", "direction": direction,
        "entry_reference": str(entry), "stop_loss": str(stop),
        "take_profit": str(target), "validity": "VALID",
    })


__all__ = [
    "FINAL_PREFIX_CONDITION", "final_prefix_condition",
    "ALL_TYPE_1_NAMES", "DATA_REQUIREMENTS", "MAX_PREFIX_EVENTS", "MonitoringIntentRefusal",
    "NAMES", "NODE_CONTRACTS", "NODE_CONTRACT_ADDRESSES", "PROTECTION_SPECS", "REFUSALS",
    "TARGET_SPECS", "UNSUPPORTED_NAMES", "V2_COMPONENTS", "V2_IMPLEMENTATIONS", "V2_TYPES",
    "component_key", "descriptor", "evaluate", "evaluate_prefix", "first_valid_index",
    "implementation_for", "parameters_for", "refusal_for", "source_contract",
    "validate_resolved_geometry", "verified_distance",
]
