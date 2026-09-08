"""Pure Type 5 logic/state primitives and shared Type 1/3/5 catalogue builder."""
from __future__ import annotations

import math
import datetime as dt
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from app.ir import hashing as hashing_module
from app.ir import node_contracts as node_contracts_module
from app.ir import resource_plan as resource_plan_module
from app.ir import schema as schema_module
from app.ir import validity as validity_module
from app.market_data import capability as capability_module
from app.ir.hashing import content_address
from app.ir.registry import DependencyBoundary, registered_v2_implementation


TYPE_5_NAMES = tuple(sorted(set("""
ABS ADD ALL AND ANY AVERAGE A_THEN_B A_WITHIN_N_BARS_OF_B BARS_SINCE BETWEEN
CLAMP COOLDOWN COUNT COUNTER DATE_RANGE DEBOUNCE DIVIDE DTE_GATE EQ
EXPLICIT_FALLBACK FALLING_N GT GTE HYSTERESIS IF_MISSING IS_MISSING IS_STALE
IS_UNDEFINED IS_VALID LAG_N LATCH LOG LT LTE MAX MIN MINUTES_FROM_OPEN
MINUTES_TO_CLOSE MODULO MULTIPLY NEQ NOT N_CONSECUTIVE N_OF_LAST_M OR POWER
PREVIOUS_VALUE RESETTABLE_LATCH RISING_N ROUND SESSION_GATE SQRT STATE_MACHINE
SUBTRACT SUM TIME_RANGE TIME_SINCE TOGGLE WEEKDAY_GATE XOR
""".split())))
STATEFUL_TYPE_5_NAMES = frozenset({
    "A_THEN_B", "A_WITHIN_N_BARS_OF_B", "BARS_SINCE", "COOLDOWN", "COUNTER",
    "DEBOUNCE", "FALLING_N", "HYSTERESIS", "LAG_N", "LATCH", "N_CONSECUTIVE",
    "N_OF_LAST_M", "PREVIOUS_VALUE", "RESETTABLE_LATCH", "RISING_N",
    "STATE_MACHINE", "TIME_SINCE", "TOGGLE",
})
FROZEN_VALIDITY_STATES = frozenset({
    validity_module.ValidityState.VALID,
    validity_module.ValidityState.MISSING,
    validity_module.ValidityState.STALE,
    validity_module.ValidityState.INSUFFICIENT_HISTORY,
    validity_module.ValidityState.MATHEMATICALLY_UNDEFINED,
    validity_module.ValidityState.PROVIDER_UNAVAILABLE,
    validity_module.ValidityState.NOT_IN_SESSION,
    validity_module.ValidityState.NOT_LISTED,
})
ENTRY_OPERATIONS = frozenset({"BUY", "SELL", "ENTER_LONG", "ENTER_SHORT", "ADD_POSITION"})
RISK_REDUCING_OPERATIONS = frozenset({
    "CLOSE_POSITION", "FLATTEN_ACCOUNT", "FLATTEN_DEPLOYMENT", "EXPIRY_EXIT",
    "PARTIAL_EXIT", "SESSION_EXIT",
})


class FirstPartyCatalogueRefusal(ValueError):
    pass


@dataclass(frozen=True)
class StateSeriesResult:
    """One immutable prefix result plus the exact payload needed for restart."""

    values: tuple[validity_module.NumericValue, ...]
    state_payload: Any
    last_event_time: str

    def __post_init__(self) -> None:
        if not self.values or any(
            not isinstance(item, validity_module.NumericValue)
            or item.state not in FROZEN_VALIDITY_STATES for item in self.values
        ):
            raise FirstPartyCatalogueRefusal("STATE_RESULT_VALIDITY_INVALID")
        _closed_state_payload(self.state_payload)
        _aware_time(self.last_event_time, "last_event_time")


def _context_address(value: Any, label: str) -> str:
    if not isinstance(value, str) or not schema_module.is_content_address(value):
        raise FirstPartyCatalogueRefusal(f"{label} must be a content address")
    return value


@dataclass(frozen=True)
class DerivativeEvaluationContext:
    """Accepted evaluator facts supplied outside authored graph inputs."""

    owner_id: str
    mode: str
    point_in_time_fact_address: str
    source_address: str
    acceptance_evidence_address: str
    rulebook_snapshot_address: str
    selector_policy_address: str
    role_requirement_address: str
    capability_evidence_address: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.owner_id, str) or not self.owner_id \
                or self.mode not in {"RESEARCH", "PAPER", "LIVE"}:
            raise FirstPartyCatalogueRefusal("DERIVATIVE_EVALUATION_SCOPE_INVALID")
        for field in (
            "point_in_time_fact_address", "source_address",
            "acceptance_evidence_address", "rulebook_snapshot_address",
            "selector_policy_address", "role_requirement_address",
        ):
            _context_address(getattr(self, field), field)
        if self.capability_evidence_address is not None:
            _context_address(
                self.capability_evidence_address, "capability_evidence_address",
            )


@dataclass(frozen=True)
class StateRestoreContext:
    """Evaluator-owned restart facts; never a graph input or authored parameter."""

    snapshot_address: str
    strategy_address: str
    resolved_graph_address: str
    node_contract_address: str
    implementation_closure_address: str
    dataset_context_address: str
    evaluation_context_address: str
    reset_policy_address: str
    last_event_address: str
    creation_evidence_address: str
    snapshot_reset_reasons: tuple[str, ...]
    pending_reset_reasons: tuple[str, ...]
    next_event_address: str
    next_event_time: str

    def __post_init__(self) -> None:
        for field in (
            "snapshot_address", "strategy_address", "resolved_graph_address",
            "node_contract_address", "implementation_closure_address",
            "dataset_context_address", "evaluation_context_address",
            "reset_policy_address", "last_event_address",
            "creation_evidence_address", "next_event_address",
        ):
            _context_address(getattr(self, field), field)
        object.__setattr__(self, "snapshot_reset_reasons",
                          node_contracts_module.canonical_reset_schedule(
                              self.snapshot_reset_reasons,
                          ))
        object.__setattr__(self, "pending_reset_reasons",
                          node_contracts_module.canonical_reset_schedule(
                              self.pending_reset_reasons,
                          ))
        _aware_time(self.next_event_time, "next_event_time")


def component_id(family: str, name: str) -> str:
    prefix = {"TYPE_1": "intent", "TYPE_3": "derivative", "TYPE_5": "logic"}[family]
    return f"{prefix}.{name.lower()}"


def _port(port_id: str, *, direction: str) -> dict[str, Any]:
    result = {
        "port_id": port_id, "direction": direction, "semantic_flow": "value",
        "semantic_role": "catalogue_value",
        "type_ref": {"type_id": "phase5.generic", "type_version": 1},
        "shape": "series",
    }
    if direction == "input":
        result["connections"] = {
            "cardinality": "optional", "min": 0, "max": 1, "assembly": "single",
        }
        result["default"] = None
    return result


def _parameter(default: Any, type_name: str) -> dict[str, Any]:
    return {
        "type": type_name, "required": False, "default": default, "enum": None,
        "domain": None, "units": "value", "serialization": "canonical-json",
    }


def _component(family: str, name: str) -> dict[str, Any]:
    if family == "TYPE_1":
        parameters = {"entry_blocked": _parameter(False, "bool")}
    elif family == "TYPE_3":
        parameters = {"maximum_members": _parameter(1, "int")}
    elif name in STATEFUL_TYPE_5_NAMES:
        parameters = {"window": _parameter(1, "int")}
        if name == "N_OF_LAST_M":
            parameters["required_count"] = _parameter(1, "int")
    else:
        parameters = {}
    return {
        "component_id": component_id(family, name), "component_version": 1,
        "domain_family": {
            "TYPE_1": "intent_description", "TYPE_3": "market_data", "TYPE_5": "state",
        }[family],
        "structural_role": {
            "TYPE_1": "sinkless_terminal", "TYPE_3": "selector",
            "TYPE_5": "stateful" if name in STATEFUL_TYPE_5_NAMES else "transform",
        }[family],
        "ports": [_port("input", direction="input"), _port("value", direction="output")],
        "parameters": parameters,
    }


def _contract(family: str, name: str, gated: bool) -> dict[str, Any]:
    provider = [content_address({"provider-capability": name})] \
        if family == "TYPE_3" and gated else []
    stateful = family == "TYPE_5" and name in STATEFUL_TYPE_5_NAMES
    return {
        "stable_node_id": component_id(family, name), "semantic_version": 1,
        "visible_family": family,
        "input_types": {"input": {
            "TYPE_1": "intent-payload/1", "TYPE_3": "point-in-time-derivative-fact/2",
            "TYPE_5": "numeric-validity-input/1",
        }[family]},
        "output_types": {"value": {
            "TYPE_1": "execution-intent-description/1", "TYPE_3": "derivative-result/1",
            "TYPE_5": "state-series-result/1" if stateful else "numeric-value/1",
        }[family]},
        "required_market_fields": ["close"] if family == "TYPE_3" else [],
        "required_resolution": {"timeframe_seconds": 60, "alignment": "BAR_CLOSE"},
        "warmup_history": 1,
        "execution_form": "RECURSIVE" if stateful else "STATELESS",
        "state_initialization": {
            "schema": "state-initialization/1",
            "initial_state_address": (
                content_address({"type5-initial-state": name, "version": 1})
                if stateful else None
            ),
        },
        "state_reset_policy": {
            "schema": "state-reset-policy/1",
            "reasons": list(node_contracts_module.RESET_REASONS) if stateful else [],
        },
        "bar_policy": "COMPLETED_ONLY", "missing_data_policy": "EXPLICIT_FALLBACK",
        "numeric_validity_policy": "EXPLICIT_VALIDITY",
        "causal_declaration": "COMPLETED_EVENT_PREFIX",
        "evaluation_triggers": ["completed_bar"], "streaming_support": True,
        "batch_support": True,
        "mode_eligibility": {"research": True, "paper": True, "live": False},
        "provider_requirements": provider,
        "resource_profile": {
            "compute_microseconds_per_event": 25, "memory_bytes_upper_bound": 2048,
            "history_bytes_upper_bound": 4096 if stateful else 0,
            "state_bytes_upper_bound": 2048 if stateful else 0,
            "storage_bytes_per_day_upper_bound": 0,
            "subscription_count_upper_bound": 1 if family == "TYPE_3" else 0,
            "fanout_upper_bound": 32,
        },
        "reference_provenance": [content_address({"phase5-reference": family, "name": name})],
    }


def _declaration(family: str, name: str, gated: bool) -> dict[str, Any]:
    if family != "TYPE_3":
        return {"schema": "data-requirement-declaration/1", "classification": "NO_DATA", "requirements": []}
    field = "CLOSE"
    if any(word in name for word in ("BID", "ASK", "DEPTH", "BOOK", "MICROPRICE")):
        field = "BID" if "BID" in name else "ASK" if "ASK" in name else "CLOSE"
    elif any(word in name for word in ("OPEN_INTEREST", "PCR", "OI_")):
        field = "OPEN_INTEREST"
    elif name in {"DELTA", "GAMMA", "VEGA", "THETA"}:
        field = name
    elif name == "IMPLIED_VOLATILITY":
        field = "IMPLIED_VOLATILITY"
    return {
        "schema": "data-requirement-declaration/1", "classification": "REQUIRES_DATA",
        "requirements": [{
            "requirement_id": "primary", "instrument": {"literal": {"role": "primary", "type": "ECONOMIC_SELECTOR"}},
            "field": {"literal": field}, "timeframe": {"literal": 60},
            "history": {"literal": {"minimum_bars": 1, "warmup_bars": 1}},
            "freshness": {"literal": {"maximum_age_seconds": 120}},
            "depth": {"literal": {"kind": "BOOK" if "DEPTH" in name or "BOOK" in name else "NONE", "levels": 5 if "DEPTH" in name or "BOOK" in name else None}},
            "session": {"literal": "INSTRUMENT_CALENDAR"},
            "alignment": {"literal": {"kind": "EXACT", "maximum_skew_seconds": 0}},
            "derived_local": {"literal": not gated},
        }],
    }


def _implementation(
    family: str, name: str, gated: bool, node_contract_address: str,
):
    def implementation(
        parameters: Mapping[str, Any], inputs: Mapping[str, Any],
        *, evaluation_context: DerivativeEvaluationContext | StateRestoreContext | None = None,
        _family: str = family, _name: str = name, _gated: bool = gated,
        _node_contract_address: str = node_contract_address,
    ):
        return {"value": evaluate_catalogue(
            _family, _name, parameters, inputs.get("input"), _gated,
            node_contract_address=_node_contract_address,
            evaluation_context=evaluation_context,
        )}
    return implementation


def make_catalogue(
    names: Sequence[str], family: str, capability_gated: Sequence[str] = (),
) -> tuple[dict, dict, dict, dict, dict]:
    gated = set(capability_gated)
    components = {(component_id(family, name), 1): _component(family, name) for name in names}
    contracts = {(component_id(family, name), 1): _contract(family, name, name in gated) for name in names}
    declarations = {(component_id(family, name), 1): _declaration(family, name, name in gated) for name in names}
    implementations = {
        (component_id(family, name), 1): registered_v2_implementation(
            component=(component_id(family, name), 1),
            implementation=_implementation(
                family, name, name in gated,
                node_contracts_module.canonical_node_contract(
                    (component_id(family, name), 1),
                    contracts[(component_id(family, name), 1)],
                ).contract_address,
            ),
            dependency_boundary=DependencyBoundary(
                "defining_module", (
                    capability_module, dt, hashing_module, math,
                    node_contracts_module, resource_plan_module, schema_module,
                    validity_module,
                ),
            ),
        ) for name in names
    }
    types = {("phase5.generic", 1): {
        "type_id": "phase5.generic", "type_version": 1,
        "shapes": ["series"], "runtime_representation": "closed-json-or-pandas",
    }}
    return types, components, implementations, declarations, contracts


def evaluate_catalogue(
    family: str, name: str, parameters: Mapping[str, Any], value: Any, gated: bool,
    *, node_contract_address: str | None = None,
    evaluation_context: DerivativeEvaluationContext | StateRestoreContext | None = None,
) -> Any:
    window = parameters.get("window", 1)
    if type(window) is not int or window < 1:
        raise FirstPartyCatalogueRefusal("WINDOW_INVALID")
    if family == "TYPE_1":
        entry_blocked = parameters.get("entry_blocked") is True
        risk_reducing = name in RISK_REDUCING_OPERATIONS
        return {
            "schema": "execution-intent-description/1", "operation": name,
            "state": "BLOCKED_ENTRY" if entry_blocked and name in ENTRY_OPERATIONS else "REQUESTED",
            "risk_reducing": risk_reducing, "payload": value,
        }
    if family == "TYPE_3":
        maximum = parameters.get("maximum_members", 1)
        if type(maximum) is not int or maximum < 1:
            raise FirstPartyCatalogueRefusal("DYNAMIC_WINDOW_BOUND")
        fact = _derivative_fact(
            value, name=name, gated=gated, maximum=maximum,
            evaluation_context=evaluation_context,
        )
        return _derivative_result(name, fact, gated=gated)
    return evaluate_logic_state(
        name, parameters, value, node_contract_address=node_contract_address,
        evaluation_context=evaluation_context,
    )


def _aware_time(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, str):
        raise FirstPartyCatalogueRefusal(f"{label} must be an aware timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FirstPartyCatalogueRefusal(f"{label} is malformed") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise FirstPartyCatalogueRefusal(f"{label} must be timezone-aware")
    return parsed.astimezone(dt.UTC)


def _derivative_fact(
    value: Any, *, name: str, gated: bool, maximum: int,
    evaluation_context: DerivativeEvaluationContext | StateRestoreContext | None,
) -> Mapping[str, Any]:
    fields = {
        "schema", "fact_address", "acceptance_evidence_address",
        "source_address", "capability_evidence_address",
        "capability_assessment_envelope", "owner_id", "mode",
        "rulebook_snapshot_address", "selector_policy_address",
        "selector_policy", "role_requirement_address", "role_requirement",
        "event_time", "knowledge_time", "evaluation_cutoff", "members", "context",
    }
    if not isinstance(value, dict) or set(value) != fields \
            or value["schema"] != "point-in-time-derivative-fact/2":
        raise FirstPartyCatalogueRefusal("POINT_IN_TIME_FACT_REQUIRED")
    for field in (
        "fact_address", "acceptance_evidence_address", "source_address",
        "rulebook_snapshot_address", "selector_policy_address",
        "role_requirement_address",
    ):
        if not isinstance(value[field], str) or not schema_module.is_content_address(value[field]):
            raise FirstPartyCatalogueRefusal("POINT_IN_TIME_IDENTITY_INVALID")
    expected_fact_address = hashing_module.content_address({
        key: item for key, item in value.items() if key != "fact_address"
    })
    if value["fact_address"] != expected_fact_address:
        raise FirstPartyCatalogueRefusal("POINT_IN_TIME_FACT_ADDRESS_MISMATCH")
    if not isinstance(evaluation_context, DerivativeEvaluationContext):
        raise FirstPartyCatalogueRefusal("DERIVATIVE_EVALUATION_CONTEXT_REQUIRED")
    context_values = (
        value["owner_id"], value["mode"], value["fact_address"],
        value["source_address"], value["acceptance_evidence_address"],
        value["rulebook_snapshot_address"], value["selector_policy_address"],
        value["role_requirement_address"], value["capability_evidence_address"],
    )
    expected_context_values = (
        evaluation_context.owner_id, evaluation_context.mode,
        evaluation_context.point_in_time_fact_address,
        evaluation_context.source_address,
        evaluation_context.acceptance_evidence_address,
        evaluation_context.rulebook_snapshot_address,
        evaluation_context.selector_policy_address,
        evaluation_context.role_requirement_address,
        evaluation_context.capability_evidence_address,
    )
    if context_values != expected_context_values:
        raise FirstPartyCatalogueRefusal("DERIVATIVE_EVALUATION_CONTEXT_MISMATCH")
    try:
        role = resource_plan_module.instrument_role_requirement(value["role_requirement"])
    except resource_plan_module.ResourcePlanRefusal as exc:
        raise FirstPartyCatalogueRefusal("CANONICAL_ROLE_REQUIRED") from exc
    if role.address != value["role_requirement_address"] \
            or role.document["role_kind"] != "DERIVATIVE_SELECTOR" \
            or role.document["instrument_type"] != "ECONOMIC_SELECTOR" \
            or role.document["binding_input_kind"] != "SELECTOR_POLICY_ADDRESS" \
            or role.document["execution_eligible"] \
            or not role.document["research_only"] \
            or role.document["maximum_members"] != maximum:
        raise FirstPartyCatalogueRefusal("CANONICAL_ROLE_MISMATCH")
    policy = value["selector_policy"]
    policy_fields = {
        "schema", "operation", "accepted_source_address",
        "acceptance_evidence_address", "rulebook_snapshot_address",
        "role_requirement_address", "provider_requirement_address",
        "maximum_members", "algorithm_version", "policy_address",
    }
    if not isinstance(policy, dict) or set(policy) != policy_fields \
            or policy["schema"] != "derivative-selector-policy/1" \
            or policy["operation"] != name \
            or policy["accepted_source_address"] != value["source_address"] \
            or policy["acceptance_evidence_address"] != value["acceptance_evidence_address"] \
            or policy["rulebook_snapshot_address"] != value["rulebook_snapshot_address"] \
            or policy["role_requirement_address"] != role.address \
            or policy["maximum_members"] != maximum \
            or policy["algorithm_version"] != "phase5-type3/2":
        raise FirstPartyCatalogueRefusal("SELECTOR_POLICY_MISMATCH")
    expected_policy_address = hashing_module.content_address({
        key: item for key, item in policy.items() if key != "policy_address"
    })
    if policy["policy_address"] != expected_policy_address \
            or value["selector_policy_address"] != expected_policy_address:
        raise FirstPartyCatalogueRefusal("SELECTOR_POLICY_ADDRESS_MISMATCH")
    provider_requirement = hashing_module.content_address({"provider-capability": name})
    role_providers = tuple(role.document["provider_requirement_addresses"])
    capability = value["capability_evidence_address"]
    envelope = value["capability_assessment_envelope"]
    if gated:
        if policy["provider_requirement_address"] != provider_requirement \
                or role_providers != (provider_requirement,):
            raise FirstPartyCatalogueRefusal("PROVIDER_REQUIREMENT_MISMATCH")
        try:
            normalized, authority_address = (
                capability_module.require_capability_assessment_authority_envelope(envelope)
            )
        except capability_module.CapabilityRefusal as exc:
            raise FirstPartyCatalogueRefusal("ACCEPTED_CAPABILITY_REQUIRED") from exc
        capability_fact = normalized["fact"]
        result_rows = capability_fact["requirement_results"]
        if capability != authority_address \
                or capability_fact["owner_id"] != value["owner_id"] \
                or capability_fact["mode"] != value["mode"] \
                or capability_fact["market_truth_snapshot_address"] \
                != value["rulebook_snapshot_address"] \
                or result_rows != [{
                    "selector": provider_requirement,
                    "result": "SATISFIED",
                    "reason": "one declared offer covers the complete requirement",
                }]:
            raise FirstPartyCatalogueRefusal("ACCEPTED_CAPABILITY_REQUIRED")
    elif capability is not None or envelope is not None \
            or policy["provider_requirement_address"] is not None or role_providers:
        raise FirstPartyCatalogueRefusal("LOCAL_DERIVATION_CANNOT_CLAIM_PROVIDER_EVIDENCE")
    if not isinstance(value["owner_id"], str) or not value["owner_id"] \
            or value["mode"] not in {"RESEARCH", "PAPER", "LIVE"}:
        raise FirstPartyCatalogueRefusal("DERIVATIVE_SCOPE_INVALID")
    event = _aware_time(value["event_time"], "event_time")
    knowledge = _aware_time(value["knowledge_time"], "knowledge_time")
    cutoff = _aware_time(value["evaluation_cutoff"], "evaluation_cutoff")
    if not event <= knowledge <= cutoff:
        raise FirstPartyCatalogueRefusal("POINT_IN_TIME_ORDER_INVALID")
    if gated:
        assessed = dt.datetime.fromtimestamp(
            capability_fact["assessed_at"], tz=dt.UTC,
        )
        if not knowledge <= assessed <= cutoff:
            raise FirstPartyCatalogueRefusal("CAPABILITY_TIME_INVALID")
    members = value["members"]
    if not isinstance(members, tuple) or not members or len(members) > maximum:
        raise FirstPartyCatalogueRefusal("DYNAMIC_WINDOW_BOUND")
    cardinality = role.document["cardinality"]
    if cardinality == "EXACT_ONE" and len(members) != 1:
        raise FirstPartyCatalogueRefusal("ROLE_CARDINALITY_MISMATCH")
    normalized = []
    addresses = []
    for member in members:
        if not isinstance(member, dict) or set(member) != {
            "instrument_address", "values", "values_address",
        } or not isinstance(member["instrument_address"], str) \
                or not schema_module.is_content_address(member["instrument_address"]) \
                or not isinstance(member["values"], dict):
            raise FirstPartyCatalogueRefusal("DERIVATIVE_MEMBER_INVALID")
        _closed_derivative_value(member["values"])
        if member["values_address"] != hashing_module.content_address(member["values"]):
            raise FirstPartyCatalogueRefusal("DERIVATIVE_MEMBER_ADDRESS_MISMATCH")
        normalized.append(member)
        addresses.append(member["instrument_address"])
    if tuple(addresses) != tuple(sorted(set(addresses))):
        raise FirstPartyCatalogueRefusal("DERIVATIVE_MEMBERS_NOT_CANONICAL")
    if not isinstance(value["context"], dict):
        raise FirstPartyCatalogueRefusal("DERIVATIVE_CONTEXT_INVALID")
    _closed_derivative_value(value["context"])
    return {**value, "members": tuple(normalized), "event_time": event,
            "knowledge_time": knowledge, "evaluation_cutoff": cutoff}


def _closed_derivative_value(value: Any) -> None:
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if math.isfinite(value):
            return
        raise FirstPartyCatalogueRefusal("DERIVATIVE_VALUE_INVALID")
    if isinstance(value, tuple):
        for item in value:
            _closed_derivative_value(item)
        return
    if isinstance(value, dict) and all(isinstance(key, str) and key for key in value):
        for item in value.values():
            _closed_derivative_value(item)
        return
    raise FirstPartyCatalogueRefusal("DERIVATIVE_VALUE_INVALID")


def _number(mapping: Mapping[str, Any], name: str) -> float:
    value = mapping.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise FirstPartyCatalogueRefusal(f"DERIVATIVE_{name.upper()}_REQUIRED")
    return float(value)


def _derivative_result(name: str, fact: Mapping[str, Any], *, gated: bool) -> Mapping[str, Any]:
    members = fact["members"]
    values = [member["values"] for member in members]
    context = fact["context"]
    result: Any
    if name == "SECONDARY_INSTRUMENT_INPUT":
        result = _member_role(members, "SECONDARY")["instrument_address"]
    elif name == "PEER_BASKET":
        result = tuple(item["instrument_address"] for item in members)
    elif name == "RELATIVE_VALUE_STRUCTURE":
        primary = _member_role(members, "PRIMARY")["values"]
        secondary = _member_role(members, "SECONDARY")["values"]
        result = _number(primary, "price") - _number(secondary, "price")
    elif name in {"STRADDLE_PRICE", "STRADDLE_SELECTOR"}:
        call, put = _call_put_pair(members, _number(context, "spot"))
        result = (_number(call["values"], "price") + _number(put["values"], "price")
                  if name == "STRADDLE_PRICE" else
                  (call["instrument_address"], put["instrument_address"]))
    elif name == "STRANGLE_SELECTOR":
        spot = _number(context, "spot")
        calls = [item for item in members if item["values"].get("right") == "CALL"
                 and _number(item["values"], "strike") > spot]
        puts = [item for item in members if item["values"].get("right") == "PUT"
                and _number(item["values"], "strike") < spot]
        if not calls or not puts:
            raise FirstPartyCatalogueRefusal("STRANGLE_PAIR_REQUIRED")
        call = min(calls, key=lambda item: (_number(item["values"], "strike") - spot,
                                           item["instrument_address"]))
        put = min(puts, key=lambda item: (spot - _number(item["values"], "strike"),
                                          item["instrument_address"]))
        result = (call["instrument_address"], put["instrument_address"])
    elif name in {"PUT_CALL_PARITY_DEVIATION", "SYNTHETIC_FUTURE"}:
        call = next((_number(item, "price") for item in values if item.get("right") == "CALL"), None)
        put = next((_number(item, "price") for item in values if item.get("right") == "PUT"), None)
        if call is None or put is None:
            raise FirstPartyCatalogueRefusal("CALL_PUT_PAIR_REQUIRED")
        strike = _number(context, "strike")
        result = call - put + strike if name == "SYNTHETIC_FUTURE" \
            else call - put - (_number(context, "spot") - strike)
    elif name in {"BASIS", "ANNUALIZED_BASIS"}:
        difference = _number(context, "future") - _number(context, "spot")
        result = difference / _number(context, "year_fraction") \
            if name == "ANNUALIZED_BASIS" else difference
    elif name == "CALENDAR_SPREAD":
        ordered = sorted(members, key=lambda item: (
            _integer_value(item["values"], "contract_rank"), item["instrument_address"]
        ))
        _require_members(ordered, 2, name)
        result = _number(ordered[0]["values"], "price") \
            - _number(ordered[1]["values"], "price")
    elif name == "DAYS_TO_EXPIRY":
        result = min(_number(item, "dte") for item in values)
    elif name == "DTE_SELECTOR":
        target = _number(context, "target_dte")
        selected = min(members, key=lambda item: (
            abs(_number(item["values"], "dte") - target), item["instrument_address"]
        ))
        result = selected["instrument_address"]
    elif name == "ATM":
        spot = _number(context, "spot")
        result = min((_number(item, "strike") for item in values),
                     key=lambda strike: (abs(strike - spot), strike))
    elif name == "ATM_PLUS_MINUS_N":
        spot = _number(context, "spot")
        distance = int(_number(context, "strike_offset_count"))
        strikes = tuple(sorted(set(_number(item, "strike") for item in values)))
        atm_index = min(range(len(strikes)), key=lambda index: (
            abs(strikes[index] - spot), strikes[index]
        ))
        result = strikes[max(0, atm_index-distance):atm_index+distance+1]
    elif name == "MONEYNESS_SELECTOR":
        spot = _number(context, "spot")
        target = _number(context, "target_moneyness_ratio")
        selected = min(members, key=lambda item: (
            abs((_number(item["values"], "strike") / spot) - target),
            item["instrument_address"],
        ))
        result = selected["instrument_address"]
    elif name == "DELTA_TARGET_SELECTOR":
        target = _number(context, "target_delta")
        selected = min(members, key=lambda item: (
            abs(_number(item["values"], "delta") - target), item["instrument_address"]
        ))
        result = selected["instrument_address"]
    elif name == "CALL_PUT_SELECTOR":
        right = context.get("option_right")
        if right not in {"CALL", "PUT"}:
            raise FirstPartyCatalogueRefusal("OPTION_RIGHT_REQUIRED")
        result = tuple(item["instrument_address"] for item in members
                       if item["values"].get("right") == right)
    elif name == "OPTION_CHAIN_SLICE":
        lower = _number(context, "strike_min")
        upper = _number(context, "strike_max")
        if lower > upper:
            raise FirstPartyCatalogueRefusal("STRIKE_RANGE_INVALID")
        expiry = context.get("selected_expiry")
        result = tuple(item["instrument_address"] for item in members
                       if lower <= _number(item["values"], "strike") <= upper
                       and item["values"].get("expiry") == expiry)
    elif name in {"EXPIRY_LIST", "NEAREST_EXPIRY", "NEXT_EXPIRY", "FAR_EXPIRY"}:
        expiries = tuple(sorted(set(_text(item, "expiry") for item in values)))
        if name == "EXPIRY_LIST":
            result = expiries
        else:
            index = {"NEAREST_EXPIRY": 0, "NEXT_EXPIRY": 1, "FAR_EXPIRY": -1}[name]
            if name == "NEXT_EXPIRY" and len(expiries) < 2:
                raise FirstPartyCatalogueRefusal("NEXT_EXPIRY_REQUIRED")
            result = expiries[index]
    elif name in {"FRONT_CONTRACT", "NEXT_CONTRACT", "FAR_CONTRACT"}:
        ordered = sorted(members, key=lambda item: (
            _integer_value(item["values"], "contract_rank"), item["instrument_address"]
        ))
        index = {"FRONT_CONTRACT": 0, "NEXT_CONTRACT": 1, "FAR_CONTRACT": -1}[name]
        if name == "NEXT_CONTRACT" and len(ordered) < 2:
            raise FirstPartyCatalogueRefusal("NEXT_CONTRACT_REQUIRED")
        result = ordered[index]["instrument_address"]
    elif name == "ROLL_SELECTOR":
        minimum = _number(context, "minimum_roll_dte")
        eligible = [item for item in members if _number(item["values"], "dte") >= minimum]
        if not eligible:
            raise FirstPartyCatalogueRefusal("ROLL_CONTRACT_UNAVAILABLE")
        result = min(eligible, key=lambda item: (
            _number(item["values"], "dte"), item["instrument_address"]
        ))["instrument_address"]
    elif name == "CONTINUOUS_RESEARCH_SERIES":
        result = tuple(_number(item["values"], "price") for item in sorted(
            members, key=lambda item: (
                _integer_value(item["values"], "contract_rank"),
                item["instrument_address"],
            )
        ))
    elif name == "TRADABLE_MAPPED_CONTRACT":
        mapped = context.get("mapped_contract_address")
        if mapped not in {item["instrument_address"] for item in members}:
            raise FirstPartyCatalogueRefusal("TRADABLE_MAPPING_REQUIRED")
        result = mapped
    elif name in {"CHAIN_OPEN_INTEREST", "CHANGE_IN_OPEN_INTEREST"}:
        field = "open_interest" if name == "CHAIN_OPEN_INTEREST" else "change_in_open_interest"
        result = sum(_number(item, field) for item in values)
    elif name in {"PCR_OPEN_INTEREST", "PCR_VOLUME"}:
        field = "open_interest" if name == "PCR_OPEN_INTEREST" else "volume"
        calls = sum(_number(item, field) for item in values if item.get("right") == "CALL")
        puts = sum(_number(item, field) for item in values if item.get("right") == "PUT")
        if calls == 0:
            raise FirstPartyCatalogueRefusal("PUT_CALL_RATIO_UNDEFINED")
        result = puts / calls
    elif name == "OPEN_INTEREST_CONCENTRATION":
        amounts = tuple(_number(item, "open_interest") for item in values)
        total = sum(amounts)
        if total == 0:
            raise FirstPartyCatalogueRefusal("OPEN_INTEREST_CONCENTRATION_UNDEFINED")
        result = max(amounts) / total
    elif name == "STRIKE_VOLUME_OI_RATIO":
        result = tuple(_safe_ratio(_number(item, "volume"),
                                   _number(item, "open_interest"), name)
                       for item in values)
    elif name in {"BEST_BID", "BEST_ASK", "SPREAD", "BID_QUANTITY", "ASK_QUANTITY",
                  "DEPTH_LEVEL_N", "CUMULATIVE_N_LEVEL_DEPTH", "DEPTH_IMBALANCE",
                  "WEIGHTED_DEPTH_IMBALANCE", "MICROPRICE", "BOOK_SLOPE",
                  "LIQUIDITY_CONCENTRATION", "DEPTH_WEIGHTED_SPREAD",
                  "PROVIDER_TOTAL_BUY_SELL_QUANTITY"}:
        result = _order_book_result(name, values, context)
    elif name in {"AGGRESSOR_BUY_SELL_FLOW", "VOLUME_DELTA", "TRADE_IMBALANCE",
                  "CUMULATIVE_DELTA"}:
        result = _trade_flow_result(name, values)
    elif gated:
        field = {
            "IMPLIED_VOLATILITY": "implied_volatility", "DELTA": "delta",
            "GAMMA": "gamma", "THETA": "theta", "VEGA": "vega", "RHO": "rho",
            "IV_RANK": "iv_rank", "IV_PERCENTILE": "iv_percentile", "SKEW": "skew",
            "TERM_STRUCTURE": "term_structure",
        }.get(name)
        if field is None:
            raise FirstPartyCatalogueRefusal("PROVIDER_SUPPLIED_OPERATION_UNKNOWN")
        result = tuple(_number(item, field) for item in values)
    else:
        result = tuple(item["instrument_address"] for item in members)
    return {
        "schema": "derivative-result/1", "operation": name,
        "source_address": fact["source_address"],
        "capability_evidence_address": fact["capability_evidence_address"],
        "rulebook_snapshot_address": fact["rulebook_snapshot_address"],
        "selector_policy_address": fact["selector_policy_address"],
        "role_requirement_address": fact["role_requirement_address"],
        "event_time": fact["event_time"].isoformat(),
        "knowledge_time": fact["knowledge_time"].isoformat(),
        "evaluation_cutoff": fact["evaluation_cutoff"].isoformat(),
        "attribution": "PROVIDER_SUPPLIED" if gated else "LOCAL_DERIVED",
        "member_addresses": tuple(item["instrument_address"] for item in members),
        "value": result,
    }


def _require_members(members: Sequence[Mapping[str, Any]], minimum: int, name: str) -> None:
    if len(members) < minimum:
        raise FirstPartyCatalogueRefusal(f"{name}_MEMBERS_REQUIRED")


def _member_role(
    members: Sequence[Mapping[str, Any]], role: str,
) -> Mapping[str, Any]:
    selected = [item for item in members if item["values"].get("structure_role") == role]
    if len(selected) != 1:
        raise FirstPartyCatalogueRefusal(f"{role}_MEMBER_REQUIRED")
    return selected[0]


def _text(mapping: Mapping[str, Any], name: str) -> str:
    value = mapping.get(name)
    if not isinstance(value, str) or not value:
        raise FirstPartyCatalogueRefusal(f"DERIVATIVE_{name.upper()}_REQUIRED")
    return value


def _integer_value(mapping: Mapping[str, Any], name: str) -> int:
    value = mapping.get(name)
    if type(value) is not int:
        raise FirstPartyCatalogueRefusal(f"DERIVATIVE_{name.upper()}_REQUIRED")
    return value


def _safe_ratio(numerator: float, denominator: float, name: str) -> float:
    if denominator == 0:
        raise FirstPartyCatalogueRefusal(f"{name}_UNDEFINED")
    return numerator / denominator


def _call_put_pair(
    members: Sequence[Mapping[str, Any]], spot: float,
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    calls = [item for item in members if item["values"].get("right") == "CALL"]
    puts = [item for item in members if item["values"].get("right") == "PUT"]
    common = sorted(
        {float(item["values"].get("strike")) for item in calls
         if isinstance(item["values"].get("strike"), (int, float))}
        & {float(item["values"].get("strike")) for item in puts
           if isinstance(item["values"].get("strike"), (int, float))},
        key=lambda strike: (abs(strike - spot), strike),
    )
    if not common:
        raise FirstPartyCatalogueRefusal("CALL_PUT_PAIR_REQUIRED")
    strike = common[0]
    call = min((item for item in calls if _number(item["values"], "strike") == strike),
               key=lambda item: item["instrument_address"])
    put = min((item for item in puts if _number(item["values"], "strike") == strike),
              key=lambda item: item["instrument_address"])
    return call, put


def _depth_levels(value: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    levels = value.get("depth_levels")
    if not isinstance(levels, tuple) or not levels:
        raise FirstPartyCatalogueRefusal("DEPTH_LEVELS_REQUIRED")
    expected = {"bid", "ask", "bid_quantity", "ask_quantity"}
    if any(not isinstance(row, dict) or set(row) != expected for row in levels):
        raise FirstPartyCatalogueRefusal("DEPTH_LEVEL_INVALID")
    for row in levels:
        for field in expected:
            _number(row, field)
    return levels


def _order_book_result(
    name: str, values: Sequence[Mapping[str, Any]], context: Mapping[str, Any],
) -> Any:
    primary_rows = [item for item in values if item.get("structure_role") == "PRIMARY"]
    if len(primary_rows) != 1:
        raise FirstPartyCatalogueRefusal("PRIMARY_MEMBER_REQUIRED")
    primary = primary_rows[0]
    bid = _number(primary, "best_bid")
    ask = _number(primary, "best_ask")
    bid_quantity = _number(primary, "bid_quantity")
    ask_quantity = _number(primary, "ask_quantity")
    total_quantity = bid_quantity + ask_quantity
    if name == "BEST_BID": return bid
    if name == "BEST_ASK": return ask
    if name == "SPREAD": return ask - bid
    if name == "BID_QUANTITY": return bid_quantity
    if name == "ASK_QUANTITY": return ask_quantity
    if name == "PROVIDER_TOTAL_BUY_SELL_QUANTITY":
        return (_number(primary, "total_buy_quantity"),
                _number(primary, "total_sell_quantity"))
    if total_quantity <= 0:
        raise FirstPartyCatalogueRefusal("ORDER_BOOK_QUANTITY_INVALID")
    if name == "DEPTH_IMBALANCE": return (bid_quantity-ask_quantity)/total_quantity
    if name == "MICROPRICE": return (ask*bid_quantity + bid*ask_quantity)/total_quantity
    levels = _depth_levels(primary)
    level_count = _integer_value(context, "depth_level_count")
    if not 1 <= level_count <= len(levels):
        raise FirstPartyCatalogueRefusal("DEPTH_LEVEL_BOUND")
    selected = levels[:level_count]
    if name == "DEPTH_LEVEL_N":
        row = selected[-1]
        return tuple(row[field] for field in ("bid", "ask", "bid_quantity", "ask_quantity"))
    if name == "CUMULATIVE_N_LEVEL_DEPTH":
        return (sum(_number(row, "bid_quantity") for row in selected),
                sum(_number(row, "ask_quantity") for row in selected))
    if name == "WEIGHTED_DEPTH_IMBALANCE":
        weighted_bid = sum(_number(row, "bid_quantity")/(index+1)
                           for index, row in enumerate(selected))
        weighted_ask = sum(_number(row, "ask_quantity")/(index+1)
                           for index, row in enumerate(selected))
        return _safe_ratio(weighted_bid-weighted_ask, weighted_bid+weighted_ask, name)
    if name == "BOOK_SLOPE":
        return ((_number(selected[-1], "ask")-_number(selected[0], "ask"))
                + (_number(selected[0], "bid")-_number(selected[-1], "bid"))) / 2
    if name == "LIQUIDITY_CONCENTRATION":
        quantities = tuple(_number(row, side) for row in selected
                           for side in ("bid_quantity", "ask_quantity"))
        return _safe_ratio(max(quantities), sum(quantities), name)
    if name == "DEPTH_WEIGHTED_SPREAD":
        bid_total = sum(_number(row, "bid_quantity") for row in selected)
        ask_total = sum(_number(row, "ask_quantity") for row in selected)
        weighted_bid = _safe_ratio(sum(_number(row, "bid")*_number(row, "bid_quantity")
                                           for row in selected), bid_total, name)
        weighted_ask = _safe_ratio(sum(_number(row, "ask")*_number(row, "ask_quantity")
                                           for row in selected), ask_total, name)
        return weighted_ask-weighted_bid
    raise FirstPartyCatalogueRefusal("ORDER_BOOK_OPERATION_UNKNOWN")


def _trade_flow_result(name: str, values: Sequence[Mapping[str, Any]]) -> Any:
    buys = sum(_number(item, "aggressor_buy_volume") for item in values)
    sells = sum(_number(item, "aggressor_sell_volume") for item in values)
    delta = buys-sells
    if name == "AGGRESSOR_BUY_SELL_FLOW": return (buys, sells)
    if name == "VOLUME_DELTA": return delta
    if name == "TRADE_IMBALANCE": return _safe_ratio(delta, buys+sells, name)
    if name == "CUMULATIVE_DELTA":
        return tuple(_number(item, "cumulative_delta") for item in values)
    raise FirstPartyCatalogueRefusal("TRADE_FLOW_OPERATION_UNKNOWN")


def _value(value: Any, label: str) -> validity_module.NumericValue:
    if not isinstance(value, validity_module.NumericValue):
        raise FirstPartyCatalogueRefusal(f"{label} must use NumericValue")
    if value.state not in FROZEN_VALIDITY_STATES:
        raise FirstPartyCatalogueRefusal(f"{label} uses a non-V1 validity state")
    return value


def _valid_value(value: validity_module.NumericValue, label: str) -> Any:
    if value.state is not validity_module.ValidityState.VALID:
        raise FirstPartyCatalogueRefusal(f"{label} is not VALID")
    return value.value


def _propagate(*values: validity_module.NumericValue) -> validity_module.NumericValue | None:
    invalids = tuple(item for item in values
                     if item.state is not validity_module.ValidityState.VALID)
    if not invalids:
        return None
    priority = {
        validity_module.ValidityState.PROVIDER_UNAVAILABLE: 0,
        validity_module.ValidityState.NOT_LISTED: 1,
        validity_module.ValidityState.NOT_IN_SESSION: 2,
        validity_module.ValidityState.STALE: 3,
        validity_module.ValidityState.MISSING: 4,
        validity_module.ValidityState.INSUFFICIENT_HISTORY: 5,
        validity_module.ValidityState.MATHEMATICALLY_UNDEFINED: 6,
    }
    state = min((item.state for item in invalids), key=priority.__getitem__)
    return validity_module.invalid(state)


def _boolean(value: validity_module.NumericValue, label: str) -> bool:
    raw = _valid_value(value, label)
    if type(raw) is not bool:
        raise FirstPartyCatalogueRefusal(f"{label} must be an exact boolean")
    return raw


def _numeric(value: validity_module.NumericValue, label: str) -> float | int:
    raw = _valid_value(value, label)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw):
        raise FirstPartyCatalogueRefusal(f"{label} must be a finite number")
    return raw


def _numeric_result(operation) -> validity_module.NumericValue:
    try:
        result = operation()
    except (ArithmeticError, OverflowError, ValueError):
        return validity_module.invalid(
            validity_module.ValidityState.MATHEMATICALLY_UNDEFINED,
        )
    if isinstance(result, bool) or not isinstance(result, (int, float)) \
            or not math.isfinite(result):
        return validity_module.invalid(
            validity_module.ValidityState.MATHEMATICALLY_UNDEFINED,
        )
    return validity_module.valid(result)


def _validity_result(name: str, value: validity_module.NumericValue) -> validity_module.NumericValue:
    mapping = {
        "IS_VALID": validity_module.ValidityState.VALID,
        "IS_MISSING": validity_module.ValidityState.MISSING,
        "IS_STALE": validity_module.ValidityState.STALE,
        "IS_UNDEFINED": validity_module.ValidityState.MATHEMATICALLY_UNDEFINED,
    }
    return validity_module.valid(value.state is mapping[name])


def _series(values: Any, label: str) -> tuple[validity_module.NumericValue, ...]:
    if not isinstance(values, (tuple, list)) or not values:
        raise FirstPartyCatalogueRefusal(f"{label} must be a non-empty NumericValue sequence")
    result = tuple(values)
    if any(not isinstance(item, validity_module.NumericValue)
           or item.state not in FROZEN_VALIDITY_STATES for item in result):
        raise FirstPartyCatalogueRefusal(f"{label} must contain NumericValue")
    return result


def _state_scalar(value: Any, *, boolean: bool, label: str) -> bool | float:
    if boolean:
        if type(value) is not bool:
            raise FirstPartyCatalogueRefusal(f"{label} must be an exact boolean")
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)) \
            or not math.isfinite(value):
        raise FirstPartyCatalogueRefusal(f"{label} must be a finite number")
    return float(value)


def _closed_state_payload(value: Any) -> None:
    if value is None or type(value) in {bool, str, int}:
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise FirstPartyCatalogueRefusal("STATE_PAYLOAD_INVALID")
        return
    if isinstance(value, tuple):
        for item in value:
            _closed_state_payload(item)
        return
    raise FirstPartyCatalogueRefusal("STATE_PAYLOAD_INVALID")


def _restore_state_payload(
    values: Mapping[str, Any], *, initial_state: Any,
    node_contract_address: str | None,
    evaluation_context: DerivativeEvaluationContext | StateRestoreContext | None,
) -> Any:
    _closed_state_payload(initial_state)
    reset = node_contracts_module.canonical_reset_schedule(values.get("reset_reasons", ()))
    snapshot = values.get("snapshot")
    if snapshot is None:
        if "state_payload" in values:
            raise FirstPartyCatalogueRefusal("STATE_PAYLOAD_REQUIRES_SNAPSHOT")
        if evaluation_context is not None:
            raise FirstPartyCatalogueRefusal("STATE_CONTEXT_REQUIRES_SNAPSHOT")
        return initial_state
    if type(snapshot) is not node_contracts_module.StateSnapshot:
        raise FirstPartyCatalogueRefusal("CANONICAL_STATE_SNAPSHOT_REQUIRED")
    try:
        canonical = node_contracts_module.canonical_state_snapshot(snapshot.document)
    except node_contracts_module.NodeContractRefusal as exc:
        raise FirstPartyCatalogueRefusal("CANONICAL_STATE_SNAPSHOT_REQUIRED") from exc
    if canonical != snapshot:
        raise FirstPartyCatalogueRefusal("CANONICAL_STATE_SNAPSHOT_REQUIRED")
    if "expected_snapshot_identity" in values:
        raise FirstPartyCatalogueRefusal("CALLER_SNAPSHOT_IDENTITY_FORBIDDEN")
    if not isinstance(evaluation_context, StateRestoreContext):
        raise FirstPartyCatalogueRefusal("STATE_RESTORE_CONTEXT_REQUIRED")
    document = canonical.document
    if node_contract_address is None \
            or document["node_contract_address"] != node_contract_address:
        raise FirstPartyCatalogueRefusal("STATE_SNAPSHOT_NODE_CONTRACT_MISMATCH")
    expected_reset_policy = hashing_module.content_address({
        "schema": "state-reset-policy/1",
        "reasons": list(node_contracts_module.RESET_REASONS),
    })
    if document["reset_policy_address"] != expected_reset_policy:
        raise FirstPartyCatalogueRefusal("STATE_SNAPSHOT_RESET_POLICY_MISMATCH")
    context_values = (
        document["snapshot_address"], document["strategy_address"],
        document["resolved_graph_address"], document["node_contract_address"],
        document["implementation_closure_address"],
        document["dataset_context_address"], document["evaluation_context_address"],
        document["reset_policy_address"], document["last_event_address"],
        document["creation_evidence_address"], tuple(document["reset_reasons"]),
        reset, values.get("next_event_address"), values.get("next_event_time"),
    )
    expected_context_values = (
        evaluation_context.snapshot_address, evaluation_context.strategy_address,
        evaluation_context.resolved_graph_address,
        evaluation_context.node_contract_address,
        evaluation_context.implementation_closure_address,
        evaluation_context.dataset_context_address,
        evaluation_context.evaluation_context_address,
        evaluation_context.reset_policy_address,
        evaluation_context.last_event_address,
        evaluation_context.creation_evidence_address,
        evaluation_context.snapshot_reset_reasons,
        evaluation_context.pending_reset_reasons,
        evaluation_context.next_event_address,
        evaluation_context.next_event_time,
    )
    if context_values != expected_context_values:
        raise FirstPartyCatalogueRefusal("STATE_RESTORE_CONTEXT_MISMATCH")
    if document["validity_state"] != "VALID":
        raise FirstPartyCatalogueRefusal("STATE_SNAPSHOT_VALIDITY_INVALID")
    next_time = _aware_time(values.get("next_event_time"), "next_event_time")
    if _aware_time(document["last_event_time"], "snapshot.last_event_time") >= next_time:
        raise FirstPartyCatalogueRefusal("STATE_SNAPSHOT_EVENT_ORDER")
    restored = values.get("state_payload")
    _closed_state_payload(restored)
    if document["state_bytes_digest"] != hashing_module.content_address({"state": restored}):
        raise FirstPartyCatalogueRefusal("STATE_SNAPSHOT_BYTES_MISMATCH")
    return initial_state if reset else restored


def _event_sequence(values: Mapping[str, Any], length: int) -> tuple[dt.datetime, ...]:
    raw = values.get("event_times")
    if not isinstance(raw, tuple) or len(raw) != length:
        raise FirstPartyCatalogueRefusal("STATE_EVENT_TIMES_REQUIRED")
    parsed = tuple(_aware_time(item, "event_time") for item in raw)
    if any(right <= left for left, right in zip(parsed, parsed[1:])):
        raise FirstPartyCatalogueRefusal("STATE_EVENT_ORDER_INVALID")
    if values.get("snapshot") is not None:
        next_time = _aware_time(values.get("next_event_time"), "next_event_time")
        if parsed[0] != next_time:
            raise FirstPartyCatalogueRefusal("STATE_NEXT_EVENT_MISMATCH")
    return parsed


def _state_result(
    output: Sequence[validity_module.NumericValue], state_payload: Any,
    times: Sequence[dt.datetime],
) -> StateSeriesResult:
    return StateSeriesResult(
        tuple(output), state_payload, times[-1].astimezone(dt.UTC).isoformat(),
    )


def _initial_state(name: str) -> Any:
    if name in {"A_THEN_B", "LATCH", "RESETTABLE_LATCH", "TOGGLE",
                "STATE_MACHINE", "HYSTERESIS"}:
        return False
    if name in {"A_WITHIN_N_BARS_OF_B", "LAG_N", "PREVIOUS_VALUE", "N_OF_LAST_M"}:
        return ()
    if name in {"RISING_N", "FALLING_N"}:
        return (None, 0)
    if name == "TIME_SINCE":
        return None
    if name == "BARS_SINCE":
        return -1
    if name == "COUNTER":
        return 0.0
    if name in {"DEBOUNCE", "COOLDOWN", "N_CONSECUTIVE"}:
        return 0
    raise FirstPartyCatalogueRefusal(f"unknown state initialization for {name}")


def _stateful_evaluation(
    name: str, values: Mapping[str, Any], window: int, required: int,
    node_contract_address: str | None,
    evaluation_context: DerivativeEvaluationContext | StateRestoreContext | None,
) -> StateSeriesResult:
    initial = _initial_state(name)
    state = _restore_state_payload(
        values, initial_state=initial,
        node_contract_address=node_contract_address,
        evaluation_context=evaluation_context,
    )
    series_names = {
        "A_THEN_B", "A_WITHIN_N_BARS_OF_B", "BARS_SINCE", "TIME_SINCE",
        "DEBOUNCE", "COOLDOWN",
    }
    if name in series_names:
        a_values = _series(values.get("a_series"), "a_series")
        b_values = _series(values.get("b_series"), "b_series")
        if len(a_values) != len(b_values):
            raise FirstPartyCatalogueRefusal("TEMPORAL_LENGTH_MISMATCH")
        items = a_values
        invalid_result = _propagate(*a_values, *b_values)
    else:
        items = _series(values.get("series"), "series")
        invalid_result = _propagate(*items)
    times = _event_sequence(values, len(items))
    if invalid_result is not None:
        return _state_result(
            tuple(invalid_result for _item in items), state, times,
        )
    output: list[validity_module.NumericValue] = []
    if name == "A_THEN_B":
        if type(state) is not bool:
            raise FirstPartyCatalogueRefusal("STATE_PAYLOAD_SHAPE_MISMATCH")
        for left, right in zip(a_values, b_values, strict=True):
            a = _boolean(left, "a_series"); b = _boolean(right, "b_series")
            output.append(validity_module.valid(bool(b and state)))
            state = state or a
    elif name == "A_WITHIN_N_BARS_OF_B":
        if not isinstance(state, tuple) or any(type(item) is not bool for item in state) \
                or len(state) > window:
            raise FirstPartyCatalogueRefusal("STATE_PAYLOAD_SHAPE_MISMATCH")
        history = state
        for left, right in zip(a_values, b_values, strict=True):
            a = _boolean(left, "a_series"); b = _boolean(right, "b_series")
            output.append(validity_module.valid(bool(b and any(history[-window:]))))
            history = (*history, a)[-window:]
        state = history
    elif name == "BARS_SINCE":
        if type(state) is not int or state < -1:
            raise FirstPartyCatalogueRefusal("STATE_PAYLOAD_SHAPE_MISMATCH")
        for item in a_values:
            trigger = _boolean(item, "a_series")
            state = 0 if trigger else (-1 if state == -1 else state+1)
            output.append(validity_module.valid(state))
    elif name == "TIME_SINCE":
        if state is not None:
            last = _aware_time(state, "state_payload")
        else:
            last = None
        for time, item in zip(times, a_values, strict=True):
            if _boolean(item, "a_series"):
                last = time
            output.append(validity_module.valid(
                -1.0 if last is None else (time-last).total_seconds()
            ))
        state = None if last is None else last.astimezone(dt.UTC).isoformat()
    elif name in {"DEBOUNCE", "N_CONSECUTIVE"}:
        if type(state) is not int or state < 0:
            raise FirstPartyCatalogueRefusal("STATE_PAYLOAD_SHAPE_MISMATCH")
        source = a_values if name == "DEBOUNCE" else items
        for item in source:
            state = state+1 if _boolean(item, "state event") else 0
            output.append(validity_module.valid(state >= window))
    elif name == "COOLDOWN":
        if type(state) is not int or state < 0:
            raise FirstPartyCatalogueRefusal("STATE_PAYLOAD_SHAPE_MISMATCH")
        for item in a_values:
            trigger = _boolean(item, "a_series")
            allowed = bool(trigger and state == 0)
            output.append(validity_module.valid(allowed))
            state = window if allowed else max(0, state-1)
    elif name == "HYSTERESIS":
        if type(state) is not bool:
            raise FirstPartyCatalogueRefusal("STATE_PAYLOAD_SHAPE_MISMATCH")
        lower = _numeric(_value(values.get("lower"), "lower"), "lower")
        upper = _numeric(_value(values.get("upper"), "upper"), "upper")
        if lower >= upper:
            invalid_result = validity_module.invalid(
                validity_module.ValidityState.MATHEMATICALLY_UNDEFINED,
            )
            return _state_result(tuple(invalid_result for _item in items), state, times)
        for item in items:
            raw = _numeric(item, "hysteresis")
            if raw >= upper: state = True
            elif raw <= lower: state = False
            output.append(validity_module.valid(state))
    elif name in {"LAG_N", "PREVIOUS_VALUE"}:
        if not isinstance(state, tuple) or len(state) > window:
            raise FirstPartyCatalogueRefusal("STATE_PAYLOAD_SHAPE_MISMATCH")
        distance = 1 if name == "PREVIOUS_VALUE" else window
        history = state
        for item in items:
            output.append(
                validity_module.valid(history[-distance]) if len(history) >= distance
                else validity_module.invalid(validity_module.ValidityState.INSUFFICIENT_HISTORY)
            )
            history = (*history, _numeric(item, "series"))[-window:]
        state = history
    elif name in {"RISING_N", "FALLING_N"}:
        if not isinstance(state, tuple) or len(state) != 2 \
                or state[0] is not None and (
                    isinstance(state[0], bool) or not isinstance(state[0], (int, float))
                ) or type(state[1]) is not int or state[1] < 0:
            raise FirstPartyCatalogueRefusal("STATE_PAYLOAD_SHAPE_MISMATCH")
        previous, run = state
        for item in items:
            raw = _numeric(item, "series")
            if previous is None:
                output.append(validity_module.invalid(
                    validity_module.ValidityState.INSUFFICIENT_HISTORY,
                ))
            else:
                comparison = raw > previous if name == "RISING_N" else raw < previous
                run = run+1 if comparison else 0
                output.append(validity_module.valid(run >= window))
            previous = raw
        state = (previous, run)
    elif name == "N_OF_LAST_M":
        if not isinstance(state, tuple) or any(type(item) is not bool for item in state) \
                or len(state) > window:
            raise FirstPartyCatalogueRefusal("STATE_PAYLOAD_SHAPE_MISMATCH")
        history = state
        for item in items:
            history = (*history, _boolean(item, "series"))[-window:]
            output.append(
                validity_module.valid(sum(history) >= required) if len(history) == window
                else validity_module.invalid(validity_module.ValidityState.INSUFFICIENT_HISTORY)
            )
        state = history
    elif name in {"COUNTER", "LATCH", "RESETTABLE_LATCH", "TOGGLE", "STATE_MACHINE"}:
        if name == "COUNTER":
            state = _state_scalar(state, boolean=False, label="state_payload")
            for item in items:
                state += _numeric(item, "counter")
                output.append(validity_module.valid(state))
        else:
            state = _state_scalar(state, boolean=True, label="state_payload")
            reset_items = None
            if name == "RESETTABLE_LATCH":
                reset_items = _series(values.get("reset_series"), "reset_series")
                if len(reset_items) != len(items):
                    raise FirstPartyCatalogueRefusal("RESET_SERIES_LENGTH_MISMATCH")
                reset_invalid = _propagate(*reset_items)
                if reset_invalid is not None:
                    return _state_result(
                        tuple(reset_invalid for _item in items), state, times,
                    )
            transitions = values.get("transition")
            for index, item in enumerate(items):
                event = _boolean(item, "state event")
                if name == "LATCH": state = state or event
                elif name == "RESETTABLE_LATCH":
                    state = (False if _boolean(reset_items[index], "reset event")
                             else state or event)
                elif name == "TOGGLE" and event: state = not state
                elif name == "STATE_MACHINE":
                    key = f"{state}:{event}"
                    if not isinstance(transitions, dict) or set(transitions) != {
                        "False:False", "False:True", "True:False", "True:True",
                    } or type(transitions.get(key)) is not bool:
                        raise FirstPartyCatalogueRefusal("STATE_TRANSITION_TABLE_INVALID")
                    state = transitions[key]
                output.append(validity_module.valid(state))
    else:
        raise FirstPartyCatalogueRefusal(f"unimplemented stateful Type 5 node {name}")
    return _state_result(output, state, times)


def evaluate_logic_state(
    name: str, parameters: Mapping[str, Any], value: Any,
    *, node_contract_address: str | None = None,
    evaluation_context: DerivativeEvaluationContext | StateRestoreContext | None = None,
) -> Any:
    if not isinstance(value, dict):
        raise FirstPartyCatalogueRefusal("TYPE5_INPUT_MUST_BE_CLOSED")
    values = value
    left, right = _value(values.get("left", validity_module.invalid(validity_module.ValidityState.MISSING)), "left"), _value(values.get("right", validity_module.invalid(validity_module.ValidityState.MISSING)), "right")
    window = parameters.get("window", 1)
    if type(window) is not int or window < 1: raise FirstPartyCatalogueRefusal("WINDOW_INVALID")
    if name in STATEFUL_TYPE_5_NAMES:
        required = parameters.get("required_count", window)
        if type(required) is not int or not 1 <= required <= window:
            raise FirstPartyCatalogueRefusal("REQUIRED_COUNT_INVALID")
        return _stateful_evaluation(
            name, values, window, required, node_contract_address,
            evaluation_context,
        )
    if name in {"IS_VALID", "IS_MISSING", "IS_STALE", "IS_UNDEFINED"}:
        return _validity_result(name, left)
    if name == "IF_MISSING":
        replacement = _value(values.get("fallback"), "fallback")
        return validity_module.fallback(left, replacement, (validity_module.ValidityState.MISSING,))
    if name == "EXPLICIT_FALLBACK":
        replacement = _value(values.get("fallback"), "fallback")
        raw_states = values.get("fallback_states")
        if not isinstance(raw_states, tuple) or not raw_states \
                or raw_states != tuple(sorted(set(raw_states))):
            raise FirstPartyCatalogueRefusal("FALLBACK_STATES_NOT_CANONICAL")
        try:
            states = tuple(validity_module.ValidityState(item) for item in raw_states)
        except ValueError as exc:
            raise FirstPartyCatalogueRefusal("FALLBACK_STATE_UNKNOWN") from exc
        if any(item not in FROZEN_VALIDITY_STATES
               or item is validity_module.ValidityState.VALID for item in states):
            raise FirstPartyCatalogueRefusal("FALLBACK_STATE_UNKNOWN")
        return validity_module.fallback(left, replacement, states)
    propagated = _propagate(left, right) if name not in {"NOT", "ABS", "LOG", "SQRT", "ROUND"} else _propagate(left)
    if propagated is not None and name not in {"COUNTER", "LATCH", "RESETTABLE_LATCH", "TOGGLE", "STATE_MACHINE", "A_THEN_B", "A_WITHIN_N_BARS_OF_B", "BARS_SINCE", "TIME_SINCE", "DEBOUNCE", "COOLDOWN", "HYSTERESIS", "WEEKDAY_GATE", "SESSION_GATE", "DATE_RANGE", "TIME_RANGE", "DTE_GATE", "MINUTES_FROM_OPEN", "MINUTES_TO_CLOSE", "SUM", "AVERAGE", "COUNT", "MIN", "MAX", "ANY", "ALL", "LAG_N", "PREVIOUS_VALUE", "RISING_N", "FALLING_N", "N_CONSECUTIVE", "N_OF_LAST_M"}:
        return propagated
    if name == "AND": return validity_module.valid(_boolean(left, "left") and _boolean(right, "right"))
    if name == "OR": return validity_module.valid(_boolean(left, "left") or _boolean(right, "right"))
    if name == "XOR": return validity_module.valid(_boolean(left, "left") ^ _boolean(right, "right"))
    if name == "NOT": return validity_module.valid(not _boolean(left, "left"))
    if name in {"GT", "GTE", "LT", "LTE", "EQ", "NEQ"}:
        lraw, rraw = _numeric(left, "left"), _numeric(right, "right")
        return validity_module.valid({"GT": lraw > rraw, "GTE": lraw >= rraw, "LT": lraw < rraw,
                "LTE": lraw <= rraw, "EQ": lraw == rraw, "NEQ": lraw != rraw}[name])
    if name == "BETWEEN":
        lower, upper = _numeric(_value(values.get("lower"), "lower"), "lower"), _numeric(_value(values.get("upper"), "upper"), "upper")
        if lower > upper: return validity_module.invalid(validity_module.ValidityState.MATHEMATICALLY_UNDEFINED)
        return validity_module.valid(lower <= _numeric(left, "left") <= upper)
    if name in {"ADD", "SUBTRACT", "MULTIPLY", "DIVIDE", "MODULO", "POWER"}:
        lraw, rraw = _numeric(left, "left"), _numeric(right, "right")
        if name in {"DIVIDE", "MODULO"} and rraw == 0: return validity_module.invalid(validity_module.ValidityState.MATHEMATICALLY_UNDEFINED)
        if name == "POWER" and lraw < 0 and not float(rraw).is_integer(): return validity_module.invalid(validity_module.ValidityState.MATHEMATICALLY_UNDEFINED)
        operations = {
            "ADD": lambda: lraw+rraw, "SUBTRACT": lambda: lraw-rraw,
            "MULTIPLY": lambda: lraw*rraw, "DIVIDE": lambda: lraw/rraw,
            "MODULO": lambda: lraw % rraw, "POWER": lambda: lraw**rraw,
        }
        return _numeric_result(operations[name])
    if name in {"ABS", "LOG", "SQRT", "ROUND"}:
        raw = _numeric(left, "left")
        if (name == "LOG" and raw <= 0) or (name == "SQRT" and raw < 0): return validity_module.invalid(validity_module.ValidityState.MATHEMATICALLY_UNDEFINED)
        operations = {
            "ABS": lambda: abs(raw), "LOG": lambda: math.log(raw),
            "SQRT": lambda: math.sqrt(raw), "ROUND": lambda: round(raw),
        }
        return _numeric_result(operations[name])
    if name == "CLAMP":
        raw = _numeric(left, "left"); lower = _numeric(_value(values.get("lower"), "lower"), "lower"); upper = _numeric(_value(values.get("upper"), "upper"), "upper")
        if lower > upper: return validity_module.invalid(validity_module.ValidityState.MATHEMATICALLY_UNDEFINED)
        return validity_module.valid(lower if raw < lower else upper if raw > upper else raw)
    if name in {"SUM", "AVERAGE", "COUNT", "MIN", "MAX", "ANY", "ALL"}:
        items = _series(values.get("series"), "series")
        invalid_result = _propagate(*items)
        if invalid_result is not None: return invalid_result
        if name in {"ANY", "ALL"}: raw = tuple(_boolean(item, "series") for item in items)
        else: raw = tuple(_numeric(item, "series") for item in items)
        return validity_module.valid({"SUM": sum(raw), "AVERAGE": sum(raw)/len(raw), "COUNT": len(raw),
                      "MIN": min(raw), "MAX": max(raw), "ANY": any(raw), "ALL": all(raw)}[name])
    if name == "WEEKDAY_GATE":
        instant = _aware_time(values.get("evaluation_time"), "evaluation_time")
        weekdays = values.get("allowed_weekdays")
        if not isinstance(weekdays, tuple) or not weekdays \
                or weekdays != tuple(sorted(set(weekdays))) \
                or any(type(day) is not int or not 0 <= day <= 6 for day in weekdays):
            raise FirstPartyCatalogueRefusal("WEEKDAY_SET_INVALID")
        return validity_module.valid(instant.weekday() in weekdays)
    if name in {"SESSION_GATE", "TIME_RANGE"}:
        instant = _aware_time(values.get("evaluation_time"), "evaluation_time")
        start = _clock_time(values.get(
            "session_open" if name == "SESSION_GATE" else "time_start"
        ), "range start")
        end = _clock_time(values.get(
            "session_close" if name == "SESSION_GATE" else "time_end"
        ), "range end")
        current = instant.timetz().replace(tzinfo=None)
        allowed = start <= current <= end if start <= end else current >= start or current <= end
        return validity_module.valid(allowed)
    if name == "DATE_RANGE":
        instant = _aware_time(values.get("evaluation_time"), "evaluation_time").date()
        start = _calendar_date(values.get("date_start"), "date_start")
        end = _calendar_date(values.get("date_end"), "date_end")
        if start > end:
            return validity_module.invalid(
                validity_module.ValidityState.MATHEMATICALLY_UNDEFINED,
            )
        return validity_module.valid(start <= instant <= end)
    if name == "DTE_GATE":
        dte = _numeric(_value(values.get("dte"), "dte"), "dte")
        lower = _numeric(_value(values.get("minimum_dte"), "minimum_dte"), "minimum_dte")
        upper = _numeric(_value(values.get("maximum_dte"), "maximum_dte"), "maximum_dte")
        if lower > upper:
            return validity_module.invalid(
                validity_module.ValidityState.MATHEMATICALLY_UNDEFINED,
            )
        return validity_module.valid(lower <= dte <= upper)
    if name in {"MINUTES_FROM_OPEN", "MINUTES_TO_CLOSE"}:
        instant = _aware_time(values.get("evaluation_time"), "evaluation_time")
        boundary = _aware_time(values.get(
            "session_open_time" if name == "MINUTES_FROM_OPEN" else "session_close_time"
        ), "session boundary")
        seconds = ((instant-boundary).total_seconds() if name == "MINUTES_FROM_OPEN"
                   else (boundary-instant).total_seconds())
        if seconds < 0:
            return validity_module.invalid(validity_module.ValidityState.NOT_IN_SESSION)
        return validity_module.valid(seconds/60.0)
    raise FirstPartyCatalogueRefusal(f"unimplemented Type 5 node {name}")


def _clock_time(value: Any, label: str) -> dt.time:
    if not isinstance(value, str):
        raise FirstPartyCatalogueRefusal(f"{label} must be HH:MM:SS")
    try:
        parsed = dt.time.fromisoformat(value)
    except ValueError as exc:
        raise FirstPartyCatalogueRefusal(f"{label} must be HH:MM:SS") from exc
    if parsed.tzinfo is not None:
        raise FirstPartyCatalogueRefusal(f"{label} must be a local clock time")
    return parsed


def _calendar_date(value: Any, label: str) -> dt.date:
    if not isinstance(value, str):
        raise FirstPartyCatalogueRefusal(f"{label} must be an ISO date")
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise FirstPartyCatalogueRefusal(f"{label} must be an ISO date") from exc


V2_TYPES, V2_COMPONENTS, V2_IMPLEMENTATIONS, DATA_REQUIREMENTS, NODE_CONTRACTS = make_catalogue(
    TYPE_5_NAMES, "TYPE_5",
)


__all__ = [
    "DATA_REQUIREMENTS", "DerivativeEvaluationContext", "ENTRY_OPERATIONS",
    "FROZEN_VALIDITY_STATES", "FirstPartyCatalogueRefusal",
    "NODE_CONTRACTS", "RISK_REDUCING_OPERATIONS", "TYPE_5_NAMES", "V2_COMPONENTS",
    "STATEFUL_TYPE_5_NAMES", "StateRestoreContext", "StateSeriesResult",
    "V2_IMPLEMENTATIONS", "V2_TYPES", "component_id", "evaluate_catalogue",
    "evaluate_logic_state", "make_catalogue",
]
