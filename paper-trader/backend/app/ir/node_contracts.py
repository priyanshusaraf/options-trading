"""Closed Phase 5 node contracts carried by the sole PlatformRegistry."""
from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from app.ir.hashing import content_address
from app.ir.schema import is_content_address


VISIBLE_FAMILIES = ("TYPE_1", "TYPE_2", "TYPE_3", "TYPE_4", "TYPE_5")
EXECUTION_FORMS = ("STATELESS", "ROLLING", "RECURSIVE")
RESET_REASONS = (
    "ELAPSED_WINDOW",
    "EXPIRY_ROLL",
    "EXPLICIT",
    "POSITION_CLOSE",
    "SESSION",
)
NODE_CONTRACT_FIELDS = (
    "stable_node_id",
    "semantic_version",
    "visible_family",
    "input_types",
    "output_types",
    "required_market_fields",
    "required_resolution",
    "warmup_history",
    "execution_form",
    "state_initialization",
    "state_reset_policy",
    "bar_policy",
    "missing_data_policy",
    "numeric_validity_policy",
    "causal_declaration",
    "evaluation_triggers",
    "streaming_support",
    "batch_support",
    "mode_eligibility",
    "provider_requirements",
    "resource_profile",
    "reference_provenance",
)
RESOURCE_PROFILE_FIELDS = (
    "compute_microseconds_per_event",
    "memory_bytes_upper_bound",
    "history_bytes_upper_bound",
    "state_bytes_upper_bound",
    "storage_bytes_per_day_upper_bound",
    "subscription_count_upper_bound",
    "fanout_upper_bound",
)
_ID = re.compile(r"^[a-z][a-z0-9_.-]{0,95}$")


class NodeContractRefusal(ValueError):
    """A typed refusal for a malformed or incomplete node contract."""


@dataclass(frozen=True)
class NodeContract:
    component: tuple[str, int]
    document: Mapping[str, Any]
    contract_address: str


@dataclass(frozen=True)
class StateSnapshot:
    document: Mapping[str, Any]
    snapshot_address: str

    def __post_init__(self) -> None:
        if self.document.get("snapshot_address") != self.snapshot_address:
            raise NodeContractRefusal("state snapshot wrapper identity conflicts")


def canonical_node_contract(
    component: tuple[str, int], document: Mapping[str, Any],
) -> NodeContract:
    """Validate and freeze one exact ``first-party-node-contract/1`` document."""
    if (
        not isinstance(component, tuple)
        or len(component) != 2
        or not isinstance(component[0], str)
        or type(component[1]) is not int
        or component[1] < 1
    ):
        raise NodeContractRefusal("invalid component identity")
    if not isinstance(document, Mapping) or set(document) != set(NODE_CONTRACT_FIELDS):
        raise NodeContractRefusal("node contract must use the exact 22-field schema")
    if document["stable_node_id"] != component[0] or not _ID.fullmatch(
        document["stable_node_id"]
    ):
        raise NodeContractRefusal("stable node identity conflicts with component")
    if type(document["semantic_version"]) is not int or document["semantic_version"] < 1:
        raise NodeContractRefusal("semantic version must be a positive exact integer")
    if document["visible_family"] not in VISIBLE_FAMILIES:
        raise NodeContractRefusal("unknown visible family")
    _typed_ports(document["input_types"], "input")
    _typed_ports(document["output_types"], "output")
    _sorted_identifiers(document["required_market_fields"], "market fields")
    resolution = document["required_resolution"]
    if not isinstance(resolution, Mapping) or set(resolution) != {
        "timeframe_seconds", "alignment"
    }:
        raise NodeContractRefusal("required resolution is malformed")
    _nonnegative_int(resolution["timeframe_seconds"], "timeframe seconds", positive=True)
    if resolution["alignment"] not in {"BAR_CLOSE", "EVENT_TIME", "SESSION"}:
        raise NodeContractRefusal("unknown resolution alignment")
    _nonnegative_int(document["warmup_history"], "warmup history")
    if document["execution_form"] not in EXECUTION_FORMS:
        raise NodeContractRefusal("unknown execution form")
    initialization = document["state_initialization"]
    if not isinstance(initialization, Mapping) or set(initialization) != {
        "schema", "initial_state_address"
    } or initialization["schema"] != "state-initialization/1":
        raise NodeContractRefusal("state initialization is malformed")
    _optional_address(initialization["initial_state_address"], "initial state")
    reset = document["state_reset_policy"]
    if not isinstance(reset, Mapping) or set(reset) != {"schema", "reasons"} \
            or reset["schema"] != "state-reset-policy/1":
        raise NodeContractRefusal("state reset policy is malformed")
    reasons = _sorted_values(reset["reasons"], "reset reasons")
    if any(reason not in RESET_REASONS for reason in reasons):
        raise NodeContractRefusal("unknown reset reason")
    if document["bar_policy"] not in {"COMPLETED_ONLY", "PARTIAL_ALLOWED"}:
        raise NodeContractRefusal("unknown bar policy")
    if document["missing_data_policy"] not in {"PROPAGATE", "REFUSE", "EXPLICIT_FALLBACK"}:
        raise NodeContractRefusal("unknown missing-data policy")
    if document["numeric_validity_policy"] not in {"FINITE_ONLY", "EXPLICIT_VALIDITY"}:
        raise NodeContractRefusal("unknown numeric-validity policy")
    if document["causal_declaration"] not in {"COMPLETED_EVENT_PREFIX", "EVENT_PREFIX"}:
        raise NodeContractRefusal("unknown causal declaration")
    _sorted_identifiers(document["evaluation_triggers"], "evaluation triggers")
    _exact_bool(document["streaming_support"], "streaming support")
    _exact_bool(document["batch_support"], "batch support")
    modes = document["mode_eligibility"]
    if not isinstance(modes, Mapping) or set(modes) != {"research", "paper", "live"}:
        raise NodeContractRefusal("mode eligibility is malformed")
    for name, value in modes.items():
        _exact_bool(value, f"{name} eligibility")
    providers = _sorted_values(document["provider_requirements"], "provider requirements")
    if any(not isinstance(value, str) or not is_content_address(value) for value in providers):
        raise NodeContractRefusal("provider requirement must be a content address")
    profile = document["resource_profile"]
    if not isinstance(profile, Mapping) or set(profile) != set(RESOURCE_PROFILE_FIELDS):
        raise NodeContractRefusal("resource profile is incomplete or open-ended")
    for field in RESOURCE_PROFILE_FIELDS:
        _nonnegative_int(profile[field], field)
    provenance = _sorted_values(document["reference_provenance"], "reference provenance")
    if not provenance or any(
        not isinstance(value, str) or not is_content_address(value)
        for value in provenance
    ):
        raise NodeContractRefusal("reference provenance must be non-empty content addresses")
    payload = {"schema": "first-party-node-contract/1", **_plain(document)}
    frozen = _freeze(document)
    return NodeContract(component, frozen, content_address(payload))


def validate_node_contract_closure(
    components: Mapping[tuple[str, int], Mapping[str, Any]],
    contracts: Mapping[tuple[str, int], Mapping[str, Any]],
) -> tuple[dict[tuple[str, int], Mapping[str, Any]], dict[tuple[str, int], str]]:
    copied: dict[tuple[str, int], Mapping[str, Any]] = {}
    addresses: dict[tuple[str, int], str] = {}
    for component, raw in contracts.items():
        descriptor = components.get(component)
        if descriptor is None or descriptor.get("compound") is not None:
            raise NodeContractRefusal("node contract must belong to an exact registered leaf")
        contract = canonical_node_contract(component, raw)
        copied[component] = contract.document
        addresses[component] = contract.contract_address
    return copied, addresses


def canonical_state_snapshot(document: Mapping[str, Any]) -> StateSnapshot:
    """Freeze one post-completed-event state snapshot with exact reset facts."""
    fields = {
        "schema", "strategy_address", "resolved_graph_address",
        "node_contract_address", "implementation_closure_address",
        "dataset_context_address", "evaluation_context_address",
        "last_event_address", "last_event_time", "state_bytes_digest",
        "validity_state", "reset_policy_address", "reset_reasons",
        "creation_evidence_address", "snapshot_address",
    }
    if not isinstance(document, Mapping) or set(document) != fields \
            or document["schema"] != "state-snapshot/1":
        raise NodeContractRefusal("state snapshot uses an open or incomplete schema")
    for field in (
        "strategy_address", "resolved_graph_address", "node_contract_address",
        "implementation_closure_address", "dataset_context_address",
        "evaluation_context_address", "last_event_address", "state_bytes_digest",
        "reset_policy_address", "creation_evidence_address",
    ):
        value = document[field]
        if not isinstance(value, str) or not is_content_address(value):
            raise NodeContractRefusal(f"{field} must be a content address")
    if not isinstance(document["last_event_time"], str) or not document["last_event_time"] \
            or document["validity_state"] not in {"VALID", "MISSING", "STALE", "INVALID"}:
        raise NodeContractRefusal("state snapshot event/validity fact is invalid")
    reasons = _sorted_values(document["reset_reasons"], "snapshot reset reasons")
    if any(reason not in RESET_REASONS for reason in reasons):
        raise NodeContractRefusal("state snapshot has an unknown reset reason")
    expected = content_address({
        key: _plain(value) for key, value in document.items()
        if key != "snapshot_address"
    })
    if document["snapshot_address"] != expected:
        raise NodeContractRefusal("state snapshot address is stale or forged")
    return StateSnapshot(_freeze(document), expected)


def state_snapshot_document(**facts: Any) -> Mapping[str, Any]:
    """Create canonical snapshot bytes; callers cannot supply the final address."""
    payload = {"schema": "state-snapshot/1", **facts}
    if "snapshot_address" in facts:
        raise NodeContractRefusal("snapshot address is derived, never caller input")
    address = content_address(_plain(payload))
    return canonical_state_snapshot({**payload, "snapshot_address": address}).document


def canonical_reset_schedule(reasons: Any) -> tuple[str, ...]:
    """V1 resets commute: collect, deduplicate, sort, and apply once."""
    if not isinstance(reasons, (tuple, list, set, frozenset)):
        raise NodeContractRefusal("reset schedule must be a finite collection")
    values = tuple(sorted(set(reasons)))
    if any(not isinstance(reason, str) or reason not in RESET_REASONS for reason in values):
        raise NodeContractRefusal("reset schedule contains an unknown reason")
    return values


def _typed_ports(value: Any, label: str) -> None:
    if not isinstance(value, Mapping) or not value:
        raise NodeContractRefusal(f"{label} types must be a non-empty mapping")
    keys = list(value)
    if keys != sorted(keys) or any(not isinstance(key, str) or not _ID.fullmatch(key) for key in keys):
        raise NodeContractRefusal(f"{label} types are noncanonical")
    if any(not isinstance(item, str) or not item for item in value.values()):
        raise NodeContractRefusal(f"{label} type is invalid")


def _sorted_identifiers(value: Any, label: str) -> tuple[str, ...]:
    values = _sorted_values(value, label)
    if any(not isinstance(item, str) or not _ID.fullmatch(item) for item in values):
        raise NodeContractRefusal(f"{label} contain an invalid identifier")
    return values


def _sorted_values(value: Any, label: str) -> tuple[Any, ...]:
    if not isinstance(value, (tuple, list)):
        raise NodeContractRefusal(f"{label} must be an array")
    values = tuple(value)
    if values != tuple(sorted(values)) or len(values) != len(set(values)):
        raise NodeContractRefusal(f"{label} must be sorted and unique")
    return values


def _nonnegative_int(value: Any, label: str, *, positive: bool = False) -> None:
    if type(value) is not int or value < (1 if positive else 0):
        raise NodeContractRefusal(f"{label} must be an exact bounded integer")


def _exact_bool(value: Any, label: str) -> None:
    if type(value) is not bool:
        raise NodeContractRefusal(f"{label} must be an exact boolean")


def _optional_address(value: Any, label: str) -> None:
    if value is not None and (not isinstance(value, str) or not is_content_address(value)):
        raise NodeContractRefusal(f"{label} must be absent or a content address")


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
    "EXECUTION_FORMS",
    "NODE_CONTRACT_FIELDS",
    "NodeContract",
    "NodeContractRefusal",
    "StateSnapshot",
    "RESET_REASONS",
    "RESOURCE_PROFILE_FIELDS",
    "VISIBLE_FAMILIES",
    "canonical_node_contract",
    "canonical_reset_schedule",
    "canonical_state_snapshot",
    "state_snapshot_document",
    "validate_node_contract_closure",
]
