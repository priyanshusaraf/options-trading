"""Stable alert-only bounds for separately verified per-dataset schedules.

A policy describes limits. Owner-scoped assignment persistence grants its use;
the policy alone grants neither source access nor evaluation authority.
"""
from __future__ import annotations

from app.ir.evaluation_schedule import (
    _exact_nonnegative_int,
    compile_schedule_resource_ceiling,
    verify_evaluation_schedule,
)
from app.ir.resource_plan import CanonicalResourceDocument, _canonical, _plain
from app.monitoring.state_contracts import MonitoringAssignment, _address, _identifier


SCHEMA = "monitoring-evaluation-policy/1"
RESOURCE_FIELDS = (
    "history_bytes_upper_bound", "memory_bytes_upper_bound", "cache_bytes_upper_bound",
    "queue_concurrency_upper_bound", "event_rate_events", "event_rate_per_seconds",
)
POSITIVE_FIELDS = frozenset(RESOURCE_FIELDS[3:])
POLICY_FIELDS = frozenset((*RESOURCE_FIELDS, "owner_id", "assignment_id",
    "initial_resource_plan_address", "maximum_age_seconds", "trigger"))


class MonitoringPolicyRefusal(ValueError):
    """The retained monitoring limits or their assignment binding differ."""


def _require(condition, detail):
    if not condition:
        raise MonitoringPolicyRefusal(detail)


def _policy_document(policy):
    _require(type(policy) is CanonicalResourceDocument and policy.schema == SCHEMA,
        "monitoring evaluation policy type differs")
    policy.__post_init__()
    document = _plain(policy.document)
    _require(set(document) == POLICY_FIELDS, "monitoring policy fields are not closed")
    _identifier(document["owner_id"], "owner")
    _identifier(document["assignment_id"], "assignment")
    _address(document["initial_resource_plan_address"], "initial resource plan")
    _require(document["trigger"] == "completed_bar", "monitoring policy trigger is unavailable")
    for field in (*RESOURCE_FIELDS, "maximum_age_seconds"):
        _exact_nonnegative_int(document[field], field, positive=field in POSITIVE_FIELDS)
    return document


def compile_monitoring_evaluation_policy(
    *, owner_id, assignment_id, initial_resource_plan_address, maximum_age_seconds,
    history_bytes_upper_bound, memory_bytes_upper_bound, cache_bytes_upper_bound,
    queue_concurrency_upper_bound, event_rate_events, event_rate_per_seconds,
):
    """Address explicit bounds without embedding the derived ceiling's address."""
    policy = _canonical(SCHEMA, {
        "owner_id": owner_id, "assignment_id": assignment_id,
        "initial_resource_plan_address": initial_resource_plan_address,
        "maximum_age_seconds": maximum_age_seconds, "trigger": "completed_bar",
        "history_bytes_upper_bound": history_bytes_upper_bound,
        "memory_bytes_upper_bound": memory_bytes_upper_bound,
        "cache_bytes_upper_bound": cache_bytes_upper_bound,
        "queue_concurrency_upper_bound": queue_concurrency_upper_bound,
        "event_rate_events": event_rate_events, "event_rate_per_seconds": event_rate_per_seconds,
    })
    _policy_document(policy)
    return policy


def monitoring_policy_payload(policy):
    return {"schema": SCHEMA, **_policy_document(policy), "address": policy.address}


def load_monitoring_evaluation_policy(payload):
    _require(type(payload) is dict and set(payload) == POLICY_FIELDS | {"schema", "address"},
        "retained monitoring policy is not closed")
    _require(payload["schema"] == SCHEMA, "retained monitoring policy schema differs")
    policy = _canonical(SCHEMA, {key: payload[key] for key in POLICY_FIELDS})
    _policy_document(policy)
    _require(policy.address == payload["address"], "retained monitoring policy address differs")
    return policy


def monitoring_resource_ceiling(policy):
    document = _policy_document(policy)
    return compile_schedule_resource_ceiling(policy_address=policy.address,
        **{field: document[field] for field in RESOURCE_FIELDS})


def _assignment_policy_binding(document, policy, assignment):
    _require(type(assignment) is MonitoringAssignment, "monitoring assignment type differs")
    actual = (assignment.owner_id, assignment.spec.assignment_id,
        assignment.spec.resource_plan_address, assignment.spec.evaluation_trigger_address)
    expected = (document["owner_id"], document["assignment_id"],
        document["initial_resource_plan_address"], policy.address)
    _require(actual == expected, "monitoring assignment policy binding differs")


def _policy_schedule_binding(policy, assignment, schedule):
    """Compare bounds after the consumer has detached its verified schedule."""
    document = _policy_document(policy)
    _assignment_policy_binding(document, policy, assignment)
    actual = (schedule.owner_id, schedule.assignment_id, schedule.mode,
        schedule.gate_node_id, schedule.declared_triggers, schedule.resource_ceiling_address)
    expected = (assignment.owner_id, assignment.spec.assignment_id, "research", None,
        ("completed_bar",), monitoring_resource_ceiling(policy).ceiling_address)
    _require(actual == expected, "monitoring schedule differs from its retained policy")
    rates = [{"trigger": "completed_bar", "events": document["event_rate_events"],
        "per_seconds": document["event_rate_per_seconds"]}]
    _require(_plain(schedule.trigger_rates) == rates, "monitoring trigger rate differs from its policy")
    _require(schedule.maximum_age_seconds <= document["maximum_age_seconds"],
        "monitoring schedule exceeds its freshness policy")


def verify_monitoring_policy_schedule(policy, assignment, schedule):
    """Verify issuance once, then check the resulting immutable snapshot."""
    _policy_schedule_binding(policy, assignment, verify_evaluation_schedule(schedule))
