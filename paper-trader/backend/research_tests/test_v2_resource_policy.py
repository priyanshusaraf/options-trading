from dataclasses import replace
from types import MappingProxyType, SimpleNamespace

import pytest

from app.ir.hashing import content_address
from app.ir.resource_plan import ResourcePlan
from research.evaluation.v2_resource_policy import (
    V0_V2_RESEARCH_RESOURCE_POLICY_ADDRESS,
    V0_V2_RESEARCH_RESOURCE_POLICY_DOCUMENT,
    V2ResourceAdmissionRefused,
    admit_v0_v2_research_resource_plan,
)


EXPECTED = "sha256:5469e08625270d71f3c3323905f81b5047eb3511ea29b7793cee675dee79c087"


def _plan(**changes):
    family = {"TYPE_1": 1, "TYPE_2": 1, "TYPE_3": 1, "TYPE_4": 1, "TYPE_5": 1}
    document = {
        "family_counts": family,
        "authored_node_count": 5,
        "lowered_node_count": 5,
        "authored_edge_count": 4,
        "lowered_edge_count": 4,
        "maximum_compound_depth": 1,
        "maximum_single_output_fanout": 1,
        "queue_concurrency_upper_bound": 1,
        "memory_bytes_upper_bound": 10**18,
        "storage_bytes_per_day_upper_bound": 10**18,
        "cache_bytes_upper_bound": 10**18,
        "artifact_bytes_upper_bound": 10**18,
    }
    for key, value in changes.items():
        if key.startswith("TYPE_"):
            family[key] = value
        else:
            document[key] = value
    return SimpleNamespace(document=MappingProxyType(document), plan_address=content_address(document))


def test_fixed_policy_document_has_reviewed_address_and_record_only_dimensions():
    assert V0_V2_RESEARCH_RESOURCE_POLICY_ADDRESS == EXPECTED
    assert content_address(V0_V2_RESEARCH_RESOURCE_POLICY_DOCUMENT) == EXPECTED
    assert V0_V2_RESEARCH_RESOURCE_POLICY_DOCUMENT["record_only_resource_fields"] == [
        "artifact_bytes_upper_bound", "cache_bytes_upper_bound",
        "memory_bytes_upper_bound", "storage_bytes_per_day_upper_bound",
    ]


@pytest.mark.parametrize("dimension,limit", [
    ("TYPE_1", 32), ("TYPE_2", 128), ("TYPE_3", 32), ("TYPE_4", 64),
    ("TYPE_5", 192), ("authored_node_count", 256),
    ("lowered_node_count", 1024), ("authored_edge_count", 1024),
    ("lowered_edge_count", 1024), ("maximum_compound_depth", 16),
    ("maximum_single_output_fanout", 32), ("queue_concurrency_upper_bound", 1),
])
def test_every_structural_bound_accepts_at_limit_and_refuses_first_above(dimension, limit):
    below = dict(
        manifest_count=1, total_rows=1999, total_bytes=8388607,
        maximum_events=1999, items_per_operation=1, plan_bytes=65535,
        running_v2_operations_per_owner=1,
    )
    if dimension == "queue_concurrency_upper_bound":
        with pytest.raises(V2ResourceAdmissionRefused, match=dimension):
            admit_v0_v2_research_resource_plan(
                _plan(**{dimension: limit - 1}), **below,
            )
    else:
        admit_v0_v2_research_resource_plan(
            _plan(**{dimension: limit - 1}), **below,
        )
    admit_v0_v2_research_resource_plan(
        _plan(**{dimension: limit}), manifest_count=1, total_rows=2000,
        total_bytes=8388608, maximum_events=2000, items_per_operation=1,
        plan_bytes=65536, running_v2_operations_per_owner=1,
    )
    with pytest.raises(V2ResourceAdmissionRefused, match=dimension):
        admit_v0_v2_research_resource_plan(
            _plan(**{dimension: limit + 1}), manifest_count=1, total_rows=2000,
            total_bytes=8388608, maximum_events=2000, items_per_operation=1,
            plan_bytes=65536, running_v2_operations_per_owner=1,
        )


@pytest.mark.parametrize("dimension,limit", [
    ("manifest_count", 1), ("total_rows", 2000), ("total_bytes", 8388608),
    ("maximum_events", 2000), ("items_per_operation", 1),
    ("running_v2_operations_per_owner", 1), ("plan_bytes", 65536),
])
def test_dataset_event_and_operation_bounds_accept_at_limit_and_refuse_first_above(dimension, limit):
    values = dict(manifest_count=1, total_rows=2000, total_bytes=8388608,
                  maximum_events=2000, items_per_operation=1, plan_bytes=65536,
                  running_v2_operations_per_owner=1)
    admit_v0_v2_research_resource_plan(_plan(), **values)
    values[dimension] = limit + 1
    with pytest.raises(V2ResourceAdmissionRefused, match=dimension):
        admit_v0_v2_research_resource_plan(_plan(), **values)


@pytest.mark.parametrize("dimension", [
    "manifest_count", "total_rows", "total_bytes", "maximum_events",
    "items_per_operation", "plan_bytes",
])
def test_required_work_dimensions_refuse_vacuous_zero(dimension):
    values = dict(manifest_count=1, total_rows=1, total_bytes=1,
                  maximum_events=1, items_per_operation=1, plan_bytes=1,
                  running_v2_operations_per_owner=0)
    values[dimension] = 0
    with pytest.raises(V2ResourceAdmissionRefused, match=dimension):
        admit_v0_v2_research_resource_plan(_plan(), **values)


@pytest.mark.parametrize("dimension,limit", [("manifest_count", 8), ("total_rows", 2000),
    ("total_bytes", 8388608), ("maximum_events", 2000), ("plan_bytes", 65536)])
def test_input_set_policy_keeps_total_work_bounds(dimension, limit):
    from research.evaluation.v2_resource_policy import (
        V0_V2_INPUT_SET_RESOURCE_POLICY_ADDRESS, V0_V2_INPUT_SET_RESOURCE_POLICY_DOCUMENT,
        admit_v0_v2_input_set_resource_plan,
    )
    values = dict(manifest_count=8, total_rows=2000, total_bytes=8388608, maximum_events=2000,
                  items_per_operation=1, running_v2_operations_per_owner=1, plan_bytes=65536)
    result = admit_v0_v2_input_set_resource_plan(_plan(), **values)
    assert result.resource_policy_address == V0_V2_INPUT_SET_RESOURCE_POLICY_ADDRESS
    assert result.resource_policy_address != EXPECTED
    assert V0_V2_INPUT_SET_RESOURCE_POLICY_DOCUMENT["dataset_limits"] == {
        "manifest_count": 8, "total_rows": 2000, "total_bytes": 8388608, "maximum_events": 2000}
    values[dimension] = limit + 1
    with pytest.raises(V2ResourceAdmissionRefused, match=dimension):
        admit_v0_v2_input_set_resource_plan(_plan(), **values)


@pytest.mark.parametrize("count", [0, 1, True, 2.0])
def test_input_set_resource_policy_does_not_relabel_a_scalar_request(count):
    from research.evaluation.v2_resource_policy import admit_v0_v2_input_set_resource_plan
    with pytest.raises(V2ResourceAdmissionRefused, match="manifest_count"):
        admit_v0_v2_input_set_resource_plan(_plan(), manifest_count=count, total_rows=100,
            total_bytes=100, maximum_events=50, items_per_operation=1,
            running_v2_operations_per_owner=1, plan_bytes=100)
