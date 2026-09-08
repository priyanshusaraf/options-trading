"""Canonical Phase 5 ResourcePlan and separate policy/calibration identities."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from app.ir.hashing import content_address
from app.ir.node_contracts import VISIBLE_FAMILIES
from app.ir.schema import is_content_address


ROLE_KINDS = (
    "BASKET",
    "CONTINUOUS_RESEARCH",
    "DERIVATIVE_SELECTOR",
    "EXECUTION_TARGET",
    "OBSERVATION",
    "REFERENCE",
)
INSTRUMENT_TYPES = ("PHYSICAL", "ECONOMIC_SELECTOR", "CONTINUOUS_FUTURE")
CARDINALITIES = ("EXACT_ONE", "BOUNDED_MANY", "DYNAMIC_WINDOW")
BINDING_INPUT_KINDS = (
    "CANONICAL_PHYSICAL_ADDRESS",
    "CONTINUOUS_SERIES_POLICY_ADDRESS",
    "SELECTOR_POLICY_ADDRESS",
)
RESOURCE_PLAN_FIELDS = (
    "schema", "algorithm_version", "authored_ir_address",
    "resolved_graph_address", "implementation_closure_address",
    "registry_snapshot_address", "data_requirement_plan_address",
    "node_contract_addresses", "provider_requirement_addresses",
    "family_counts", "authored_node_count", "lowered_node_count",
    "authored_edge_count", "lowered_edge_count", "maximum_compound_depth",
    "maximum_single_output_fanout", "instrument_role_requirements",
    "trigger_requirements", "state_requirements", "history_requirements",
    "subscription_requirements", "compute_requirements",
    "dynamic_window_requirements", "memory_bytes_upper_bound",
    "storage_bytes_per_day_upper_bound", "cache_bytes_upper_bound",
    "artifact_bytes_upper_bound", "queue_concurrency_upper_bound",
    "mode_support", "assumption_addresses", "plan_address",
)
TIER_DIMENSIONS = (
    "TYPE_1", "TYPE_2", "TYPE_3", "TYPE_4", "TYPE_5",
    "authored_node_count", "lowered_node_count", "authored_edge_count",
    "maximum_compound_depth", "maximum_single_output_fanout",
)
DEFAULT_TIER_LIMITS: Mapping[str, Mapping[str, int]] = MappingProxyType({
    "Standard": MappingProxyType(dict(zip(TIER_DIMENSIONS, (
        32, 128, 32, 64, 192, 256, 1024, 1024, 16, 32,
    )))),
    "Pro": MappingProxyType(dict(zip(TIER_DIMENSIONS, (
        96, 384, 128, 192, 576, 768, 4096, 4096, 32, 64,
    )))),
    "Desk": MappingProxyType(dict(zip(TIER_DIMENSIONS, (
        256, 1024, 384, 512, 1536, 2048, 12288, 16384, 48, 128,
    )))),
})
_ID = re.compile(r"^[a-z][a-z0-9_.-]{0,95}$")


class ResourcePlanRefusal(ValueError):
    """A closed refusal for resource, provider, role, or tier facts."""


@dataclass(frozen=True)
class CanonicalResourceDocument:
    document: Mapping[str, Any]
    address: str
    schema: str

    def __post_init__(self) -> None:
        if not isinstance(self.schema, str) or not self.schema:
            raise ResourcePlanRefusal("canonical document schema is missing")
        expected = content_address({"schema": self.schema, **_plain(self.document)})
        if self.address != expected:
            raise ResourcePlanRefusal("canonical document address is stale or forged")


@dataclass(frozen=True)
class ResourcePlan:
    document: Mapping[str, Any]
    plan_address: str

    def __post_init__(self) -> None:
        _validate_resource_plan(self.document)
        if self.plan_address != self.document["plan_address"]:
            raise ResourcePlanRefusal("resource plan wrapper identity conflicts")


def bounded_rate(events: int, per_seconds: int) -> Mapping[str, int]:
    _integer(events, "events", positive=True)
    _integer(per_seconds, "per seconds", positive=True)
    divisor = math.gcd(events, per_seconds)
    return MappingProxyType({
        "events": events // divisor,
        "per_seconds": per_seconds // divisor,
    })


def provider_requirement(document: Mapping[str, Any]) -> CanonicalResourceDocument:
    fields = {
        "capability_classes", "fields", "timeframe_seconds", "history_bars",
        "freshness_seconds", "depth_levels", "session", "alignment",
        "product_classes", "contract_classes", "supply",
    }
    if not isinstance(document, Mapping) or set(document) != fields:
        raise ResourcePlanRefusal("provider requirement uses an open or incomplete schema")
    for name in ("capability_classes", "fields", "product_classes", "contract_classes"):
        _sorted_strings(document[name], name)
    for name in ("timeframe_seconds", "history_bars", "freshness_seconds", "depth_levels"):
        _integer(document[name], name)
    if document["supply"] not in {"PROVIDER_REQUIRED", "LOCAL_DERIVATION_ALLOWED"}:
        raise ResourcePlanRefusal("unknown provider supply policy")
    if not isinstance(document["session"], str) or not document["session"] \
            or document["alignment"] not in {"BAR_CLOSE", "EVENT_TIME", "SESSION"}:
        raise ResourcePlanRefusal("provider session/alignment is invalid")
    return _canonical("provider-requirement/1", document)


def instrument_role_requirement(document: Mapping[str, Any]) -> CanonicalResourceDocument:
    fields = {
        "role_id", "role_kind", "instrument_type", "cardinality",
        "maximum_members", "source_requirement_addresses",
        "provider_requirement_addresses", "binding_input_kind",
        "execution_eligible", "research_only",
    }
    if not isinstance(document, Mapping) or set(document) != fields:
        raise ResourcePlanRefusal("instrument role uses an open or incomplete schema")
    if not isinstance(document["role_id"], str) or not _ID.fullmatch(document["role_id"]):
        raise ResourcePlanRefusal("role identity is invalid")
    if document["role_kind"] not in ROLE_KINDS or document["instrument_type"] not in INSTRUMENT_TYPES \
            or document["cardinality"] not in CARDINALITIES \
            or document["binding_input_kind"] not in BINDING_INPUT_KINDS:
        raise ResourcePlanRefusal("role vocabulary is invalid")
    _integer(document["maximum_members"], "maximum members", positive=True)
    if document["cardinality"] == "EXACT_ONE" and document["maximum_members"] != 1:
        raise ResourcePlanRefusal("EXACT_ONE requires one member")
    for name in ("source_requirement_addresses", "provider_requirement_addresses"):
        values = _sorted_strings(document[name], name)
        if any(not is_content_address(value) for value in values):
            raise ResourcePlanRefusal(f"{name} must contain content addresses")
    _boolean(document["execution_eligible"], "execution eligibility")
    _boolean(document["research_only"], "research-only")
    if document["execution_eligible"] and document["research_only"]:
        raise ResourcePlanRefusal("a role cannot be execution-eligible and research-only")
    if document["role_kind"] in {"OBSERVATION", "REFERENCE", "BASKET", "CONTINUOUS_RESEARCH"} \
            and document["execution_eligible"]:
        raise ResourcePlanRefusal("non-execution role cannot gain order authority")
    expected_binding = {
        "PHYSICAL": "CANONICAL_PHYSICAL_ADDRESS",
        "ECONOMIC_SELECTOR": "SELECTOR_POLICY_ADDRESS",
        "CONTINUOUS_FUTURE": "CONTINUOUS_SERIES_POLICY_ADDRESS",
    }[document["instrument_type"]]
    if document["binding_input_kind"] != expected_binding:
        raise ResourcePlanRefusal("instrument type and binding input kind conflict")
    return _canonical("instrument-role-requirement/1", document)


def binding_input_requirement(role: CanonicalResourceDocument) -> CanonicalResourceDocument:
    document = {
        "role_requirement_address": role.address,
        "binding_input_kind": role.document["binding_input_kind"],
        "maximum_members": role.document["maximum_members"],
    }
    return _canonical("binding-input-requirement/1", document)


def compile_resource_plan(
    resolved_graph: Any,
    data_requirement_plan: Any,
    registry: Any,
    *,
    instrument_roles: Sequence[CanonicalResourceDocument] = (),
    provider_requirements: Sequence[CanonicalResourceDocument] = (),
    assumption_addresses: Sequence[str] = (),
    cache_bytes_upper_bound: int = 0,
    artifact_bytes_upper_bound: int = 0,
    queue_concurrency_upper_bound: int = 1,
) -> ResourcePlan:
    identities = {
        "authored_ir_address": getattr(resolved_graph, "authored_ir_address", None),
        "resolved_graph_address": getattr(resolved_graph, "resolved_graph_address", None),
        "implementation_closure_address": getattr(
            resolved_graph, "implementation_closure_address", None
        ),
        "registry_snapshot_address": getattr(resolved_graph, "registry_snapshot_address", None),
        "data_requirement_plan_address": getattr(data_requirement_plan, "plan_address", None),
    }
    if any(not isinstance(value, str) or not is_content_address(value) for value in identities.values()):
        raise ResourcePlanRefusal("resource plan lacks canonical graph/data identities")
    contracts = getattr(registry, "node_contracts", {})
    addresses = getattr(registry, "node_contract_addresses", {})
    nodes = tuple(getattr(resolved_graph, "nodes", ()))
    if not nodes:
        raise ResourcePlanRefusal("resource plan requires at least one lowered node")
    family_counts = {family: 0 for family in VISIBLE_FAMILIES}
    contract_addresses: set[str] = set()
    authored_ids: set[str] = set()
    memory = storage = 0
    trigger_rows: list[dict[str, Any]] = []
    state_rows: list[dict[str, Any]] = []
    history_rows: list[dict[str, Any]] = []
    subscription_rows: list[dict[str, Any]] = []
    compute_rows: list[dict[str, Any]] = []
    maximum_depth = 0
    modes = {"research": True, "paper": True, "live": True}
    node_profiles: dict[str, Mapping[str, Any]] = {}
    for node in nodes:
        contract = contracts.get(node.component)
        address = addresses.get(node.component)
        if contract is None or not isinstance(address, str) or not is_content_address(address):
            raise ResourcePlanRefusal(f"lowered node {node.node_id!r} hides undeclared demand")
        family_counts[contract["visible_family"]] += 1
        contract_addresses.add(address)
        if not isinstance(node.authored_node_id, str) or not node.authored_node_id \
                or not isinstance(node.lowered_path, tuple) or not node.lowered_path:
            raise ResourcePlanRefusal("lowered node lacks originating authored family")
        authored_ids.add(node.authored_node_id)
        maximum_depth = max(maximum_depth, len(node.lowered_path) - 1)
        profile = contract["resource_profile"]
        node_profiles[node.node_id] = profile
        memory += profile["memory_bytes_upper_bound"] + profile["state_bytes_upper_bound"] \
            + profile["history_bytes_upper_bound"]
        storage += profile["storage_bytes_per_day_upper_bound"]
        base = {"node_id": node.node_id, "node_contract_address": address}
        compute_rows.append({**base, "microseconds_per_event": profile["compute_microseconds_per_event"]})
        history_rows.append({**base, "bytes_upper_bound": profile["history_bytes_upper_bound"]})
        state_rows.append({**base, "bytes_upper_bound": profile["state_bytes_upper_bound"],
                           "reset_reasons": list(contract["state_reset_policy"]["reasons"])})
        subscription_rows.append({**base, "count_upper_bound": profile["subscription_count_upper_bound"]})
        for trigger in contract["evaluation_triggers"]:
            trigger_rows.append({**base, "trigger": trigger})
        for mode in modes:
            modes[mode] = modes[mode] and contract["mode_eligibility"][mode]
    topology = getattr(resolved_graph, "topology_document", None) or {}
    edge_rows = topology.get("edges", ()) if isinstance(topology, Mapping) else ()
    authored_edges = len(edge_rows)
    fanout: dict[tuple[str, str], int] = {}
    for edge in edge_rows:
        source = edge.get("source", {}) if isinstance(edge, Mapping) else {}
        key = (str(source.get("node_id", "")), str(source.get("port_id", "")))
        fanout[key] = fanout.get(key, 0) + 1
    maximum_fanout = max(fanout.values(), default=0)
    for (node_id, _port_id), count in fanout.items():
        source = next(
            (edge.get("source", {}) for edge in edge_rows
             if isinstance(edge, Mapping)
             and str(edge.get("source", {}).get("node_id", "")) == node_id
             and str(edge.get("source", {}).get("port_id", "")) == _port_id),
            {},
        )
        if source.get("scope") == "graph_input":
            continue
        profile = node_profiles.get(node_id)
        if profile is None or count > profile["fanout_upper_bound"]:
            raise ResourcePlanRefusal(
                f"actual fanout for {node_id!r} exceeds its declared bound"
            )
    roles = sorted((dict(item.document) for item in instrument_roles), key=lambda row: row["role_id"])
    if len({row["role_id"] for row in roles}) != len(roles):
        raise ResourcePlanRefusal("duplicate instrument role")
    provider_addresses = sorted({item.address for item in provider_requirements})
    for row in roles:
        provider_addresses.extend(row["provider_requirement_addresses"])
    provider_addresses = sorted(set(provider_addresses))
    assumptions = tuple(assumption_addresses)
    if assumptions != tuple(sorted(set(assumptions))) or any(
        not isinstance(value, str) or not is_content_address(value) for value in assumptions
    ):
        raise ResourcePlanRefusal("assumption addresses must be sorted unique content addresses")
    for name, value in (
        ("cache bytes", cache_bytes_upper_bound),
        ("artifact bytes", artifact_bytes_upper_bound),
        ("queue concurrency", queue_concurrency_upper_bound),
    ):
        _integer(value, name, positive=name == "queue concurrency")
    payload: dict[str, Any] = {
        "schema": "resource-plan/1",
        "algorithm_version": 1,
        **identities,
        "node_contract_addresses": sorted(contract_addresses),
        "provider_requirement_addresses": provider_addresses,
        "family_counts": family_counts,
        "authored_node_count": len(authored_ids),
        "lowered_node_count": len(nodes),
        "authored_edge_count": authored_edges,
        "lowered_edge_count": authored_edges,
        "maximum_compound_depth": maximum_depth,
        "maximum_single_output_fanout": maximum_fanout,
        "instrument_role_requirements": roles,
        "trigger_requirements": sorted(trigger_rows, key=_row_key),
        "state_requirements": sorted(state_rows, key=_row_key),
        "history_requirements": sorted(history_rows, key=_row_key),
        "subscription_requirements": sorted(subscription_rows, key=_row_key),
        "compute_requirements": sorted(compute_rows, key=_row_key),
        "dynamic_window_requirements": [
            {"role_id": row["role_id"], "maximum_members": row["maximum_members"]}
            for row in roles if row["cardinality"] == "DYNAMIC_WINDOW"
        ],
        "memory_bytes_upper_bound": memory,
        "storage_bytes_per_day_upper_bound": storage,
        "cache_bytes_upper_bound": cache_bytes_upper_bound,
        "artifact_bytes_upper_bound": artifact_bytes_upper_bound,
        "queue_concurrency_upper_bound": queue_concurrency_upper_bound,
        "mode_support": modes,
        "assumption_addresses": list(assumptions),
    }
    plan_address = content_address(payload)
    complete = {**payload, "plan_address": plan_address}
    _validate_resource_plan(complete)
    return ResourcePlan(_freeze(complete), plan_address)


def resource_calibration(document: Mapping[str, Any]) -> CanonicalResourceDocument:
    if not isinstance(document, Mapping) or set(document) != {
        "workload_address", "measurement_evidence_addresses", "measured_at"
    }:
        raise ResourcePlanRefusal("resource calibration schema is malformed")
    if not is_content_address(document["workload_address"]):
        raise ResourcePlanRefusal("calibration workload identity is invalid")
    values = _sorted_strings(document["measurement_evidence_addresses"], "measurement evidence")
    if not values or any(not is_content_address(value) for value in values) \
            or not isinstance(document["measured_at"], str) or not document["measured_at"]:
        raise ResourcePlanRefusal("calibration evidence is invalid")
    return _canonical("resource-calibration/1", document)


def resource_tier_policy(
    tier: str, *, evidence_addresses: Sequence[str], provisional: bool = True,
) -> CanonicalResourceDocument:
    if tier not in DEFAULT_TIER_LIMITS:
        raise ResourcePlanRefusal("unknown resource tier")
    evidence = tuple(evidence_addresses)
    if evidence != tuple(sorted(set(evidence))) or any(not is_content_address(value) for value in evidence):
        raise ResourcePlanRefusal("tier evidence must be sorted unique addresses")
    document = {
        "tier": tier,
        "status": "PROVISIONAL" if provisional else "ACCEPTED",
        "limits": dict(DEFAULT_TIER_LIMITS[tier]),
        "measurement_evidence_addresses": list(evidence),
    }
    return _canonical("resource-tier-policy/1", document)


def resource_tier_decision(
    plan: ResourcePlan, policy: CanonicalResourceDocument,
    calibration: CanonicalResourceDocument, *, owner_id: str,
) -> CanonicalResourceDocument:
    if not isinstance(owner_id, str) or not _ID.fullmatch(owner_id):
        raise ResourcePlanRefusal("tier owner identity is invalid")
    limits = policy.document["limits"]
    observed = {
        **dict(plan.document["family_counts"]),
        **{key: plan.document[key] for key in TIER_DIMENSIONS if key not in VISIBLE_FAMILIES},
    }
    exceeded = sorted(key for key in TIER_DIMENSIONS if observed[key] > limits[key])
    document = {
        "resource_plan_address": plan.plan_address,
        "policy_address": policy.address,
        "calibration_address": calibration.address,
        "owner_id": owner_id,
        "tier": policy.document["tier"],
        "accepted": not exceeded,
        "reason_code": "WITHIN_LIMITS" if not exceeded else "RESOURCE_LIMIT_EXCEEDED",
        "binding_dimensions": exceeded,
    }
    return _canonical("resource-tier-decision/1", document)


def _validate_resource_plan(document: Mapping[str, Any]) -> None:
    if set(document) != set(RESOURCE_PLAN_FIELDS) or document["schema"] != "resource-plan/1":
        raise ResourcePlanRefusal("resource plan uses an open or incomplete schema")
    for key in (
        "algorithm_version", "authored_node_count", "lowered_node_count",
        "authored_edge_count", "lowered_edge_count", "maximum_compound_depth",
        "maximum_single_output_fanout", "memory_bytes_upper_bound",
        "storage_bytes_per_day_upper_bound", "cache_bytes_upper_bound",
        "artifact_bytes_upper_bound", "queue_concurrency_upper_bound",
    ):
        _integer(document[key], key, positive=key in {"algorithm_version", "queue_concurrency_upper_bound"})
    if set(document["family_counts"]) != set(VISIBLE_FAMILIES):
        raise ResourcePlanRefusal("family counts are incomplete")
    for value in document["family_counts"].values():
        _integer(value, "family count")
    for name in (
        "authored_ir_address", "resolved_graph_address",
        "implementation_closure_address", "registry_snapshot_address",
        "data_requirement_plan_address", "plan_address",
    ):
        if not isinstance(document[name], str) or not is_content_address(document[name]):
            raise ResourcePlanRefusal(f"{name} must be a content address")
    for name in (
        "node_contract_addresses", "provider_requirement_addresses",
        "assumption_addresses",
    ):
        values = _sorted_strings(document[name], name)
        if any(not is_content_address(value) for value in values):
            raise ResourcePlanRefusal(f"{name} must contain content addresses")
    roles = document["instrument_role_requirements"]
    if not isinstance(roles, (tuple, list)):
        raise ResourcePlanRefusal("instrument roles must be an array")
    role_ids: list[str] = []
    for role in roles:
        canonical = instrument_role_requirement(role)
        role_ids.append(canonical.document["role_id"])
    if role_ids != sorted(set(role_ids)):
        raise ResourcePlanRefusal("instrument roles must be sorted and unique")
    row_schemas = {
        "trigger_requirements": {"node_id", "node_contract_address", "trigger"},
        "state_requirements": {
            "node_id", "node_contract_address", "bytes_upper_bound", "reset_reasons",
        },
        "history_requirements": {
            "node_id", "node_contract_address", "bytes_upper_bound",
        },
        "subscription_requirements": {
            "node_id", "node_contract_address", "count_upper_bound",
        },
        "compute_requirements": {
            "node_id", "node_contract_address", "microseconds_per_event",
        },
    }
    for name, fields in row_schemas.items():
        rows = document[name]
        if not isinstance(rows, (tuple, list)) or any(
            not isinstance(row, Mapping) or set(row) != fields for row in rows
        ):
            raise ResourcePlanRefusal(f"{name} must use its exact row schema")
        keys: list[tuple[str, str, str]] = []
        for row in rows:
            if not isinstance(row["node_id"], str) or not row["node_id"] \
                    or not isinstance(row["node_contract_address"], str) \
                    or not is_content_address(row["node_contract_address"]):
                raise ResourcePlanRefusal(f"{name} has invalid node identity")
            numeric = next((field for field in (
                "bytes_upper_bound", "count_upper_bound", "microseconds_per_event"
            ) if field in row), None)
            if numeric is not None:
                _integer(row[numeric], numeric)
            if "trigger" in row and (not isinstance(row["trigger"], str) or not row["trigger"]):
                raise ResourcePlanRefusal("trigger requirement is invalid")
            if "reset_reasons" in row:
                _sorted_strings(row["reset_reasons"], "reset reasons")
            keys.append(_row_key(row))
        if keys != sorted(keys) or len(keys) != len(set(keys)):
            raise ResourcePlanRefusal(f"{name} must be sorted and unique")
    windows = document["dynamic_window_requirements"]
    if not isinstance(windows, (tuple, list)) or any(
        not isinstance(row, Mapping) or set(row) != {"role_id", "maximum_members"}
        for row in windows
    ):
        raise ResourcePlanRefusal("dynamic window requirements are malformed")
    window_ids: list[str] = []
    for row in windows:
        if not isinstance(row["role_id"], str) or not _ID.fullmatch(row["role_id"]):
            raise ResourcePlanRefusal("dynamic window role is invalid")
        _integer(row["maximum_members"], "dynamic window maximum", positive=True)
        window_ids.append(row["role_id"])
    if window_ids != sorted(set(window_ids)):
        raise ResourcePlanRefusal("dynamic windows must be sorted and unique")
    modes = document["mode_support"]
    if not isinstance(modes, Mapping) or set(modes) != {"research", "paper", "live"}:
        raise ResourcePlanRefusal("mode support is incomplete")
    for name, value in modes.items():
        _boolean(value, f"{name} mode support")
    expected = content_address({key: _plain(value) for key, value in document.items() if key != "plan_address"})
    if document["plan_address"] != expected:
        raise ResourcePlanRefusal("resource plan address is stale or forged")


def _canonical(schema: str, document: Mapping[str, Any]) -> CanonicalResourceDocument:
    payload = {"schema": schema, **_plain(document)}
    return CanonicalResourceDocument(_freeze(document), content_address(payload), schema)


def _row_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("node_id", "")),
        str(row.get("node_contract_address", "")),
        str(row.get("trigger", "")),
    )


def _sorted_strings(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)):
        raise ResourcePlanRefusal(f"{label} must be an array")
    values = tuple(value)
    if values != tuple(sorted(set(values))) or any(not isinstance(item, str) or not item for item in values):
        raise ResourcePlanRefusal(f"{label} must be sorted unique strings")
    return values


def _integer(value: Any, label: str, *, positive: bool = False) -> None:
    if type(value) is not int or value < (1 if positive else 0):
        raise ResourcePlanRefusal(f"{label} must be an exact non-negative integer")


def _boolean(value: Any, label: str) -> None:
    if type(value) is not bool:
        raise ResourcePlanRefusal(f"{label} must be an exact boolean")


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    return value


__all__ = [
    "BINDING_INPUT_KINDS", "CARDINALITIES", "CanonicalResourceDocument",
    "DEFAULT_TIER_LIMITS", "INSTRUMENT_TYPES", "RESOURCE_PLAN_FIELDS",
    "ROLE_KINDS", "ResourcePlan", "ResourcePlanRefusal", "TIER_DIMENSIONS",
    "binding_input_requirement", "bounded_rate", "compile_resource_plan",
    "instrument_role_requirement", "provider_requirement", "resource_calibration",
    "resource_tier_decision", "resource_tier_policy",
]
