"""Fixed V0 admission policy for the bounded V2 research runtime.

This policy is a deterministic structural admission bound.  The four byte
estimates named as record-only remain lineage facts, not capacity evidence.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from app.ir.hashing import content_address


V0_V2_RESEARCH_RESOURCE_POLICY_DOCUMENT = {
    "schema": "v0-v2-research-runtime-policy/1",
    "algorithm_version": 1,
    "resource_plan_limits": {
        "TYPE_1": 32, "TYPE_2": 128, "TYPE_3": 32, "TYPE_4": 64,
        "TYPE_5": 192, "authored_node_count": 256,
        "lowered_node_count": 1024, "authored_edge_count": 1024,
        "lowered_edge_count": 1024, "maximum_compound_depth": 16,
        "maximum_single_output_fanout": 32,
        "queue_concurrency_upper_bound": 1,
    },
    "dataset_limits": {
        "manifest_count": 1, "total_rows": 2000,
        "total_bytes": 8388608, "maximum_events": 2000,
    },
    "operation_limits": {
        "items_per_operation": 1, "running_v2_operations_per_owner": 1,
        "plan_bytes": 65536,
    },
    "record_only_resource_fields": [
        "artifact_bytes_upper_bound", "cache_bytes_upper_bound",
        "memory_bytes_upper_bound", "storage_bytes_per_day_upper_bound",
    ],
    "release_capacity_gate": "strategy-os-v0-security-operations-deployability",
}
V0_V2_RESEARCH_RESOURCE_POLICY_ADDRESS = content_address(
    V0_V2_RESEARCH_RESOURCE_POLICY_DOCUMENT
)
_REVIEWED_ADDRESS = "sha256:5469e08625270d71f3c3323905f81b5047eb3511ea29b7793cee675dee79c087"
if V0_V2_RESEARCH_RESOURCE_POLICY_ADDRESS != _REVIEWED_ADDRESS:
    raise RuntimeError("V0 V2 research resource policy identity differs from review")

V0_V2_INPUT_SET_RESOURCE_POLICY_DOCUMENT = {
    **deepcopy(V0_V2_RESEARCH_RESOURCE_POLICY_DOCUMENT),
    "schema": "v0-v2-research-runtime-policy/2", "algorithm_version": 2,
    "dataset_limits": {**V0_V2_RESEARCH_RESOURCE_POLICY_DOCUMENT["dataset_limits"],
                       "manifest_count": 8},
}
V0_V2_INPUT_SET_RESOURCE_POLICY_ADDRESS = content_address(V0_V2_INPUT_SET_RESOURCE_POLICY_DOCUMENT)


class V2ResourceAdmissionRefused(ValueError):
    """Stable refusal for a closed V2 research resource dimension."""


@dataclass(frozen=True)
class AcceptedV2ResearchResourceAdmission:
    resource_plan_address: str
    resource_policy_address: str
    observed_dimensions: Mapping[str, int]
    admission_address: str


def _exact_nonnegative(name: str, value: Any) -> int:
    if type(value) is not int or value < 0:
        raise V2ResourceAdmissionRefused(f"{name} is not an exact non-negative integer")
    return value


def admit_v0_v2_research_resource_plan(
    resource_plan: Any, *, manifest_count: int, total_rows: int,
    total_bytes: int, maximum_events: int, items_per_operation: int,
    running_v2_operations_per_owner: int, plan_bytes: int,
) -> AcceptedV2ResearchResourceAdmission:
    return _admit_resource_policy(resource_plan, V0_V2_RESEARCH_RESOURCE_POLICY_DOCUMENT,
        V0_V2_RESEARCH_RESOURCE_POLICY_ADDRESS, manifest_count=manifest_count,
        total_rows=total_rows, total_bytes=total_bytes, maximum_events=maximum_events,
        items_per_operation=items_per_operation,
        running_v2_operations_per_owner=running_v2_operations_per_owner, plan_bytes=plan_bytes)


def admit_v0_v2_input_set_resource_plan(
    resource_plan: Any, *, manifest_count: int, total_rows: int,
    total_bytes: int, maximum_events: int, items_per_operation: int,
    running_v2_operations_per_owner: int, plan_bytes: int,
) -> AcceptedV2ResearchResourceAdmission:
    if type(manifest_count) is not int or manifest_count < 2:
        raise V2ResourceAdmissionRefused("manifest_count requires at least two selected sources")
    return _admit_resource_policy(resource_plan, V0_V2_INPUT_SET_RESOURCE_POLICY_DOCUMENT,
        V0_V2_INPUT_SET_RESOURCE_POLICY_ADDRESS, manifest_count=manifest_count,
        total_rows=total_rows, total_bytes=total_bytes, maximum_events=maximum_events,
        items_per_operation=items_per_operation,
        running_v2_operations_per_owner=running_v2_operations_per_owner, plan_bytes=plan_bytes)


def _admit_resource_policy(resource_plan, policy, policy_address, *, manifest_count,
        total_rows, total_bytes, maximum_events, items_per_operation,
        running_v2_operations_per_owner, plan_bytes):
    plan_address, structural = _resource_dimensions(resource_plan)
    observed = {
        **structural, "manifest_count": manifest_count, "total_rows": total_rows,
        "total_bytes": total_bytes, "maximum_events": maximum_events,
        "items_per_operation": items_per_operation,
        "running_v2_operations_per_owner": running_v2_operations_per_owner,
        "plan_bytes": plan_bytes,
    }
    limits = {**policy["resource_plan_limits"], **policy["dataset_limits"], **policy["operation_limits"]}
    _verify_dimensions(observed, limits)
    frozen = MappingProxyType({name: observed[name] for name in sorted(observed)})
    admission_address = content_address({
        "schema": "accepted-v0-v2-research-resource-admission/1",
        "resource_plan_address": plan_address,
        "resource_policy_address": policy_address,
        "observed_dimensions": dict(frozen),
    })
    return AcceptedV2ResearchResourceAdmission(plan_address, policy_address, frozen, admission_address)


def _resource_dimensions(resource_plan):
    document = getattr(resource_plan, "document", None)
    plan_address = getattr(resource_plan, "plan_address", None)
    if not isinstance(document, Mapping) or not isinstance(plan_address, str):
        raise V2ResourceAdmissionRefused("canonical ResourcePlan is required")
    family = document.get("family_counts")
    if not isinstance(family, Mapping):
        raise V2ResourceAdmissionRefused("ResourcePlan family counts are absent")
    structural = {
        **{name: family.get(name) for name in ("TYPE_1", "TYPE_2", "TYPE_3", "TYPE_4", "TYPE_5")},
        **{name: document.get(name) for name in (
            "authored_node_count", "lowered_node_count", "authored_edge_count",
            "lowered_edge_count", "maximum_compound_depth",
            "maximum_single_output_fanout", "queue_concurrency_upper_bound",
        )},
    }
    return plan_address, structural


def _verify_dimensions(observed, limits):
    for name in sorted(limits):
        value = _exact_nonnegative(name, observed.get(name))
        if name in {
            "manifest_count", "total_rows", "total_bytes", "maximum_events",
            "items_per_operation", "plan_bytes", "queue_concurrency_upper_bound",
        } and value == 0:
            raise V2ResourceAdmissionRefused(f"{name} must be present")
        if value > limits[name]:
            raise V2ResourceAdmissionRefused(f"{name} exceeds the V0 V2 research bound")


__all__ = [
    "AcceptedV2ResearchResourceAdmission", "V0_V2_RESEARCH_RESOURCE_POLICY_ADDRESS",
    "V0_V2_RESEARCH_RESOURCE_POLICY_DOCUMENT", "V2ResourceAdmissionRefused",
    "admit_v0_v2_research_resource_plan",
    "V0_V2_INPUT_SET_RESOURCE_POLICY_ADDRESS", "V0_V2_INPUT_SET_RESOURCE_POLICY_DOCUMENT",
    "admit_v0_v2_input_set_resource_plan",
]
