from __future__ import annotations

import datetime as dt
import importlib
from contextlib import contextmanager
from dataclasses import FrozenInstanceError, replace
from functools import lru_cache
import inspect
from pathlib import Path
import subprocess
import sys
import threading

import pytest

from app.ir import evaluation_schedule as schedule_contract
from app.ir.evaluation_schedule import (
    AuthoredGateOutcome,
    EvaluationScheduleAddress,
    ScheduleRefusal,
    ScheduleRefusalCode,
    admit_authored_acquisition_gate,
    canonical_conditional_requirement_selector,
)
from app.ir.hashing import content_address
import app.market_data.runtime_cache_identity as runtime_cache_module
from app.market_data.runtime_cache_identity import (
    ResourceBound,
    RuntimeCacheIdentity,
    RuntimeCacheRefusal,
    derived_node_cache_identity,
    evaluation_result_cache_identity,
    observation_cache_identity,
    static_window_cache_identity,
)


_SCHEDULE_FIXTURE_SPEC = importlib.util.spec_from_file_location(
    "runtime_cache_schedule_fixtures", Path(__file__).with_name("test_v0_evaluation_schedule.py")
)
assert _SCHEDULE_FIXTURE_SPEC is not None and _SCHEDULE_FIXTURE_SPEC.loader is not None
_SCHEDULE_FIXTURES = importlib.util.module_from_spec(_SCHEDULE_FIXTURE_SPEC)
sys.modules[_SCHEDULE_FIXTURE_SPEC.name] = _SCHEDULE_FIXTURES
_SCHEDULE_FIXTURE_SPEC.loader.exec_module(_SCHEDULE_FIXTURES)
_schedule_facts = _SCHEDULE_FIXTURES._facts
_typed_conditional_authority = _SCHEDULE_FIXTURES._typed_conditional_authority


UTC = dt.timezone.utc


def _address(label: str) -> str:
    return content_address({"fixture": label})


def _time(second: int) -> dt.datetime:
    return dt.datetime(2026, 8, 31, 9, 15, second, tzinfo=UTC)


def _observation(**changes):
    values = {
        "owner_id": "owner-a",
        "assignment_id": "assignment-a",
        "licence_scope_address": _address("licence"),
        "provider_entity_address": _address("provider-entity"),
        "provider_product_address": _address("provider-product"),
        "provider_contract_address": _address("provider-contract"),
        "provider_conformance_address": _address("provider-conformance"),
        "provider_capability_address": _address("provider-capability"),
        "canonical_instrument_address": _address("instrument"),
        "canonical_contract_address": _address("contract"),
        "fields": ("ask", "bid"),
        "depth_levels": 5,
        "rulebook_address": _address("rulebook"),
        "alias_addresses": (_address("alias-a"),),
        "correction_addresses": (_address("correction-a"),),
        "raw_segment_addresses": (_address("segment-a"),),
        "event_at": _time(0),
        "completed_at": _time(1),
        "available_at": _time(2),
        "recorded_at": _time(3),
        "knowledge_cutoff": _time(4),
        "timeframe_seconds": 60,
        "session_policy_address": _address("session-policy"),
        "unit_contract_address": _address("quote-units"),
        "missing_data_policy_address": _address("missing-policy"),
        "alignment_policy_address": _address("alignment-policy"),
        "adjustment_policy_address": _address("adjustment-policy"),
    }
    values.update(changes)
    return observation_cache_identity(**values)


def _bounds(*, subscription_demand=1, subscription_ceiling=2):
    return (
        ResourceBound("subscription_count", _address("count-unit"), subscription_demand, subscription_ceiling),
        ResourceBound("depth_feed_count", _address("count-unit"), 1, 1),
        ResourceBound("cache_bytes", _address("byte-unit"), 1024, 2048),
    )


@lru_cache(maxsize=None)
def _compiled_schedule(owner_id="owner-a", assignment_id="assignment-a"):
    return _schedule_facts(
        owner_id=owner_id, assignment_id=assignment_id
    )


@lru_cache(maxsize=None)
def _current_static_evidence(owner_id="owner-a", assignment_id="assignment-a"):
    registry, graph, data, resource, schedule, _conditional = _compiled_schedule(
        owner_id, assignment_id
    )
    assessment, eligibility, authority = _typed_conditional_authority(
        registry, graph, data, schedule
    )
    not_required = admit_authored_acquisition_gate(
        schedule,
        data_requirement_plan=data,
        outcome=AuthoredGateOutcome.NOT_REQUIRED,
        decision_input_address=_address("gate-input"),
    )
    return data, resource, schedule, not_required, authority, assessment, eligibility


def _current_static_authorities(owner_id="owner-a", assignment_id="assignment-a"):
    return _current_static_evidence(owner_id, assignment_id)[:5]


def _static_attempt(**changes):
    _data, resource, schedule, gate, _authority = _current_static_authorities()
    values = {
        "owner_id": "owner-a",
        "assignment_id": "assignment-a",
        "static_scope_revision_address": _address("static-scope"),
        "evaluation_schedule": schedule,
        "authored_gate": gate,
        "selector_policy_address": _address("selector"),
        "underlying_instrument_address": _address("underlying"),
        "contract_addresses": (_address("option-a"), _address("option-b")),
        "expiry_lower_bound": dt.date(2026, 9, 3),
        "expiry_upper_bound": dt.date(2026, 9, 10),
        "strike_lower_bound": 24000,
        "strike_upper_bound": 24500,
        "strike_unit_address": _address("strike-unit"),
        "buffer_policy_address": _address("buffer"),
        "depth_levels": 5,
        "provider_entity_address": _address("provider-entity"),
        "provider_product_address": _address("provider-product"),
        "provider_contract_address": _address("provider-contract"),
        "provider_conformance_address": _address("provider-conformance"),
        "provider_capability_address": _address("provider-capability"),
        "rulebook_address": _address("rulebook"),
        "alias_addresses": (_address("alias-a"),),
        "as_of": _time(2),
        "knowledge_cutoff": _time(4),
        "freshness_seconds": 2,
        "resource_plan_address": resource.plan_address,
        "resource_bounds": _bounds(),
    }
    values.update(changes)
    return static_window_cache_identity(**values)


def _derived(**changes):
    values = {
        "owner_id": "owner-a",
        "assignment_id": "assignment-a",
        "node_semantic_address": _address("node-semantic"),
        "node_contract_address": _address("node-contract"),
        "node_implementation_address": _address("node-implementation"),
        "parameters_address": _address("parameters"),
        "input_bindings": (("close", _address("close-input")), ("volume", _address("volume-input"))),
        "input_unit_addresses": (_address("price-unit"), _address("volume-unit")),
        "output_unit_address": _address("output-unit"),
        "missing_data_policy_address": _address("missing-policy"),
        "alignment_policy_address": _address("alignment-policy"),
        "adjustment_policy_address": _address("adjustment-policy"),
        "session_policy_address": _address("session-policy"),
        "event_at": _time(1),
        "knowledge_cutoff": _time(4),
        "state_predecessor_address": _address("state-predecessor"),
        "state_reset_address": _address("state-reset"),
        "output_port": "value",
    }
    values.update(changes)
    schedule = values.get("evaluation_schedule")
    if schedule is None:
        schedule = _compiled_schedule(values["owner_id"], values["assignment_id"])[4]
        values["evaluation_schedule"] = schedule
    if "resolved_graph_address" not in values:
        values["resolved_graph_address"] = schedule.resolved_graph_address
    if "implementation_closure_address" not in values:
        values["implementation_closure_address"] = schedule.implementation_closure_address
    if "registry_snapshot_address" not in values:
        values["registry_snapshot_address"] = schedule.registry_snapshot_address
    return derived_node_cache_identity(**values)


def _evaluation(**changes):
    values = {
        "owner_id": "owner-a",
        "assignment_id": "assignment-a",
        "admission_address": _address("admission"),
        "dataset_or_stream_address": _address("stream"),
        "market_truth_address": _address("market-truth"),
        "input_addresses": (_address("node-result-a"), _address("node-result-b")),
        "unit_policy_address": _address("unit-policy"),
        "result_scope": "PAPER_RESULT",
        "fill_policy_address": _address("fill-policy"),
        "charge_schedule_address": _address("charge-schedule"),
        "book_epoch_address": _address("book-epoch"),
        "paper_policy_address": _address("paper-policy"),
        "state_predecessor_address": _address("state-predecessor"),
        "state_reset_address": _address("state-reset"),
        "event_at": _time(1),
        "knowledge_cutoff": _time(4),
    }
    values.update(changes)
    schedule = values.get("evaluation_schedule")
    if schedule is None:
        schedule = _compiled_schedule(values["owner_id"], values["assignment_id"])[4]
        values["evaluation_schedule"] = schedule
    if "resolved_graph_address" not in values:
        values["resolved_graph_address"] = schedule.resolved_graph_address
    if "implementation_closure_address" not in values:
        values["implementation_closure_address"] = schedule.implementation_closure_address
    if "registry_snapshot_address" not in values:
        values["registry_snapshot_address"] = schedule.registry_snapshot_address
    if "data_requirement_plan_address" not in values:
        values["data_requirement_plan_address"] = schedule.data_requirement_plan_address
    if "resource_plan_address" not in values:
        values["resource_plan_address"] = schedule.resource_plan_address
    return evaluation_result_cache_identity(**values)


@pytest.mark.parametrize(
    "factory,mutations",
    [
        (_observation, {
            "owner_id": "owner-b", "assignment_id": "assignment-b",
            "licence_scope_address": _address("licence-b"),
            "provider_entity_address": _address("provider-entity-b"),
            "provider_product_address": _address("provider-product-b"),
            "provider_contract_address": _address("provider-contract-b"),
            "provider_conformance_address": _address("provider-conformance-b"),
            "provider_capability_address": _address("provider-capability-b"),
            "canonical_instrument_address": _address("instrument-b"),
            "canonical_contract_address": _address("contract-b"),
            "fields": ("ask", "bid", "last"), "depth_levels": 10,
            "rulebook_address": _address("rulebook-b"),
            "alias_addresses": (_address("alias-b"),),
            "correction_addresses": (_address("correction-b"),),
            "raw_segment_addresses": (_address("segment-b"),),
            "event_at": _time(1), "completed_at": _time(2),
            "available_at": _time(3), "recorded_at": _time(4),
            "knowledge_cutoff": _time(5), "timeframe_seconds": 300,
            "session_policy_address": _address("session-b"),
            "unit_contract_address": _address("unit-b"),
            "missing_data_policy_address": _address("missing-b"),
            "alignment_policy_address": _address("alignment-b"),
            "adjustment_policy_address": _address("adjustment-b"),
        }),
        (_derived, {
            "node_semantic_address": _address("semantic-b"),
            "node_contract_address": _address("contract-b"),
            "node_implementation_address": _address("impl-b"),
            "parameters_address": _address("parameters-b"),
            "input_bindings": (("close", _address("close-b")), ("volume", _address("volume-b"))),
            "input_unit_addresses": (_address("input-unit-b"), _address("input-unit-c")),
            "output_unit_address": _address("output-unit-b"),
            "missing_data_policy_address": _address("missing-b"),
            "alignment_policy_address": _address("alignment-b"),
            "adjustment_policy_address": _address("adjustment-b"),
            "session_policy_address": _address("session-b"),
            "event_at": _time(2), "knowledge_cutoff": _time(5),
            "state_predecessor_address": _address("predecessor-b"),
            "state_reset_address": _address("reset-b"), "output_port": "signal",
        }),
        (_evaluation, {
            "admission_address": _address("admission-b"),
            "dataset_or_stream_address": _address("stream-b"),
            "market_truth_address": _address("truth-b"),
            "input_addresses": (_address("result-c"),),
            "unit_policy_address": _address("unit-b"),
            "fill_policy_address": _address("fill-b"),
            "charge_schedule_address": _address("charge-b"),
            "book_epoch_address": _address("epoch-b"),
            "paper_policy_address": _address("paper-b"),
            "state_predecessor_address": _address("predecessor-b"),
            "state_reset_address": _address("reset-b"),
            "event_at": _time(2), "knowledge_cutoff": _time(5),
        }),
    ],
)
def test_every_answer_changing_dimension_changes_identity(factory, mutations):
    baseline = factory()
    for field, changed in mutations.items():
        candidate = factory(**{field: changed})
        assert candidate.address != baseline.address, field


def test_identities_are_immutable_and_cache_loss_reconstructs_exactly():
    first = (_observation(), _derived(), _evaluation())
    reconstructed = (_observation(), _derived(), _evaluation())
    assert [item.address for item in reconstructed] == [item.address for item in first]
    assert [item.document for item in reconstructed] == [item.document for item in first]
    with pytest.raises(FrozenInstanceError):
        first[0].address = _address("forged")
    with pytest.raises(TypeError):
        first[0].document["owner_id"] = "owner-b"
    with pytest.raises(TypeError):
        RuntimeCacheIdentity("observation", first[0].document, _address("forged"))


def test_pure_node_and_evaluation_only_bind_explicit_absence_without_fallback():
    pure = _derived(state_predecessor_address=None, state_reset_address=None)
    evaluation = _evaluation(
        result_scope="EVALUATION_ONLY",
        fill_policy_address=None,
        charge_schedule_address=None,
        book_epoch_address=None,
        paper_policy_address=None,
        state_predecessor_address=None,
        state_reset_address=None,
    )
    assert pure.document["state_predecessor_address"] is None
    assert evaluation.document["book_epoch_address"] is None
    assert evaluation.address != _evaluation().address
    with pytest.raises(RuntimeCacheRefusal, match="both present or both absent"):
        _derived(state_predecessor_address=None)
    with pytest.raises(RuntimeCacheRefusal, match="cannot carry paper"):
        _evaluation(result_scope="EVALUATION_ONLY")


@pytest.mark.parametrize("factory", [_derived, _evaluation])
@pytest.mark.parametrize(
    "scope",
    [
        {"owner_id": "owner-b"},
        {"assignment_id": "assignment-b"},
    ],
)
def test_coherent_typed_schedule_scope_changes_identity(factory, scope):
    assert factory(**scope).address != factory().address


@pytest.mark.parametrize("factory", [_derived, _evaluation])
@pytest.mark.parametrize(
    "scope",
    [
        {"owner_id": "owner-b"},
        {"assignment_id": "assignment-b"},
    ],
)
def test_foreign_owner_or_assignment_schedule_refuses(factory, scope):
    schedule = _compiled_schedule()[4]
    with pytest.raises(RuntimeCacheRefusal, match="owner or assignment"):
        factory(evaluation_schedule=schedule, **scope)


@pytest.mark.parametrize("factory", [_derived, _evaluation])
@pytest.mark.parametrize(
    "changes",
    [
        {"resolved_graph_address": _address("foreign-graph")},
        {"implementation_closure_address": _address("foreign-implementation")},
        {"registry_snapshot_address": _address("foreign-registry")},
    ],
)
def test_schedule_graph_implementation_or_registry_mismatch_refuses(factory, changes):
    with pytest.raises(RuntimeCacheRefusal, match="graph, implementation, or registry"):
        factory(**changes)


@pytest.mark.parametrize(
    "changes,match",
    [
        ({"data_requirement_plan_address": _address("foreign-data-plan")}, "DataRequirementPlan"),
        ({"resource_plan_address": _address("foreign-resource-plan")}, "ResourcePlan"),
    ],
)
def test_evaluation_schedule_plan_mismatch_refuses(changes, match):
    with pytest.raises(RuntimeCacheRefusal, match=match):
        _evaluation(**changes)


@pytest.mark.parametrize("factory", [_derived, _evaluation])
def test_direct_and_forged_schedule_facts_refuse(factory):
    schedule = _compiled_schedule()[4]
    exact = {
        "resolved_graph_address": schedule.resolved_graph_address,
        "implementation_closure_address": schedule.implementation_closure_address,
        "registry_snapshot_address": schedule.registry_snapshot_address,
    }
    if factory is _evaluation:
        exact.update({
            "data_requirement_plan_address": schedule.data_requirement_plan_address,
            "resource_plan_address": schedule.resource_plan_address,
        })
    with pytest.raises(RuntimeCacheRefusal, match="stale or forged"):
        factory(evaluation_schedule=object(), **exact)
    forged = object.__new__(EvaluationScheduleAddress)
    for name in schedule.__dataclass_fields__:
        object.__setattr__(
            forged, name,
            _address("forged-runtime-schedule")
            if name == "schedule_address" else getattr(schedule, name),
        )
    with pytest.raises(RuntimeCacheRefusal, match="stale or forged"):
        factory(evaluation_schedule=forged)
    with pytest.raises(TypeError):
        EvaluationScheduleAddress()


def _self_consistent_schedule_forgery(schedule, **changes):
    forged = object.__new__(EvaluationScheduleAddress)
    for name in schedule.__dataclass_fields__:
        object.__setattr__(forged, name, changes.get(name, getattr(schedule, name)))
    object.__setattr__(
        forged, "schedule_address", content_address(schedule_contract._schedule_payload(forged))
    )
    return forged


@contextmanager
def _mutated_issued_fact(value, *, address_field, payload, changes):
    original = {name: getattr(value, name) for name in (*changes, address_field)}
    try:
        for name, changed in changes.items():
            object.__setattr__(value, name, changed)
        object.__setattr__(value, address_field, content_address(payload(value)))
        yield value
    finally:
        for name, prior in original.items():
            object.__setattr__(value, name, prior)


def _consume_mutated_schedule(cache_class, schedule):
    common = {
        "owner_id": schedule.owner_id,
        "assignment_id": schedule.assignment_id,
        "evaluation_schedule": schedule,
        "resolved_graph_address": schedule.resolved_graph_address,
        "implementation_closure_address": schedule.implementation_closure_address,
        "registry_snapshot_address": schedule.registry_snapshot_address,
    }
    if cache_class == "derived":
        return _derived(**common)
    if cache_class == "evaluation":
        return _evaluation(
            **common,
            data_requirement_plan_address=schedule.data_requirement_plan_address,
            resource_plan_address=schedule.resource_plan_address,
        )
    if cache_class == "static":
        return _static_attempt(
            owner_id=schedule.owner_id,
            assignment_id=schedule.assignment_id,
            evaluation_schedule=schedule,
            resource_plan_address=schedule.resource_plan_address,
        )
    raise AssertionError(f"unknown cache class {cache_class}")


@pytest.mark.parametrize("cache_class", ["derived", "evaluation", "static"])
@pytest.mark.parametrize(
    "changes",
    [
        {"owner_id": "owner-mutated"},
        {"assignment_id": "assignment-mutated"},
        {"declared_triggers": ("completed_bar", "tick")},
        {"event_unit_address": _address("mutated-event-unit")},
        {"maximum_age_seconds": 999},
        {"resolved_graph_address": _address("mutated-resolved-graph")},
        {"implementation_closure_address": _address("mutated-implementation")},
        {"registry_snapshot_address": _address("mutated-registry")},
        {"data_requirement_plan_address": _address("mutated-data-plan")},
        {"resource_plan_address": _address("mutated-resource-plan")},
    ],
)
def test_readdressed_in_place_issued_schedule_mutation_refuses_every_cache_consumer(
    cache_class, changes
):
    schedule = _compiled_schedule()[4]
    with _mutated_issued_fact(
        schedule,
        address_field="schedule_address",
        payload=schedule_contract._schedule_payload,
        changes=changes,
    ):
        with pytest.raises(RuntimeCacheRefusal, match="stale or forged"):
            _consume_mutated_schedule(cache_class, schedule)


@pytest.mark.parametrize("cache_class", ["derived", "evaluation", "static"])
@pytest.mark.parametrize(
    "shape",
    ["declared_triggers", "owner_id", "trigger_rates", "maximum_age_seconds"],
)
def test_same_canonical_bytes_different_schedule_runtime_shape_refuses_cache_consumers(
    cache_class, shape
):
    schedule = _compiled_schedule()[4]
    changed = {
        "declared_triggers": _SCHEDULE_FIXTURES._ChameleonTuple(schedule.declared_triggers),
        "owner_id": _SCHEDULE_FIXTURES._ChameleonStr(schedule.owner_id),
        "trigger_rates": tuple(
            _SCHEDULE_FIXTURES._ChameleonDict(dict(row)) for row in schedule.trigger_rates
        ),
        "maximum_age_seconds": _SCHEDULE_FIXTURES._ChameleonInt(
            schedule.maximum_age_seconds
        ),
    }[shape]
    original_address = schedule.schedule_address
    with _mutated_issued_fact(
        schedule,
        address_field="schedule_address",
        payload=schedule_contract._schedule_payload,
        changes={shape: changed},
    ):
        assert schedule.schedule_address == original_address
        with pytest.raises(RuntimeCacheRefusal, match="stale or forged"):
            _consume_mutated_schedule(cache_class, schedule)


@pytest.mark.parametrize("cache_class", ["derived", "evaluation"])
def test_schedule_cache_consumers_use_detached_original_after_verification_barrier(
    monkeypatch, cache_class
):
    schedule = _compiled_schedule()[4]
    original = {
        "owner_id": schedule.owner_id,
        "assignment_id": schedule.assignment_id,
        "resolved_graph_address": schedule.resolved_graph_address,
        "implementation_closure_address": schedule.implementation_closure_address,
        "registry_snapshot_address": schedule.registry_snapshot_address,
    }
    factory = _derived if cache_class == "derived" else _evaluation
    if cache_class == "evaluation":
        original.update({
            "data_requirement_plan_address": schedule.data_requirement_plan_address,
            "resource_plan_address": schedule.resource_plan_address,
        })
    expected = factory(evaluation_schedule=schedule, **original)
    verified = threading.Barrier(2)
    resume = threading.Barrier(2)
    real_verify = runtime_cache_module.verify_evaluation_schedule

    def paused_verify(value):
        snapshot = real_verify(value)
        verified.wait()
        resume.wait()
        return snapshot

    monkeypatch.setattr(runtime_cache_module, "verify_evaluation_schedule", paused_verify)
    result = {}

    def run():
        try:
            result["identity"] = factory(evaluation_schedule=schedule, **original)
        except Exception as exc:
            result["error"] = exc

    worker = threading.Thread(target=run)
    worker.start()
    verified.wait()
    with _mutated_issued_fact(
        schedule,
        address_field="schedule_address",
        payload=schedule_contract._schedule_payload,
        changes={
            "owner_id": "owner-mutated",
            "assignment_id": "assignment-mutated",
            "resolved_graph_address": _address("mutated-resolved-graph"),
            "implementation_closure_address": _address("mutated-implementation"),
            "registry_snapshot_address": _address("mutated-registry"),
            "data_requirement_plan_address": _address("mutated-data-plan"),
            "resource_plan_address": _address("mutated-resource-plan"),
            "event_unit_address": _address("mutated-event-unit"),
            "maximum_age_seconds": 999,
        },
    ):
        resume.wait()
        worker.join(5)
        assert not worker.is_alive()
    assert "error" not in result
    assert result["identity"].address == expected.address
    assert result["identity"].document["schedule_address"] == expected.document["schedule_address"]


def test_static_cache_uses_detached_schedule_after_verification_barrier(monkeypatch):
    _data, resource, schedule, _gate, authority = _current_static_authorities()
    assert authority.result is _SCHEDULE_FIXTURES.AcquisitionSupport.UNSUPPORTED
    verified = threading.Barrier(2)
    resume = threading.Barrier(2)
    real_verify = runtime_cache_module.verify_evaluation_schedule

    def paused_verify(value):
        snapshot = real_verify(value)
        verified.wait()
        resume.wait()
        return snapshot

    monkeypatch.setattr(runtime_cache_module, "verify_evaluation_schedule", paused_verify)
    result = {}

    def run():
        try:
            _static_attempt(
                owner_id=schedule.owner_id,
                assignment_id=schedule.assignment_id,
                evaluation_schedule=schedule,
                resource_plan_address=resource.plan_address,
            )
        except Exception as exc:
            result["error"] = exc

    worker = threading.Thread(target=run)
    worker.start()
    verified.wait()
    with _mutated_issued_fact(
        schedule,
        address_field="schedule_address",
        payload=schedule_contract._schedule_payload,
        changes={
            "owner_id": "owner-mutated",
            "assignment_id": "assignment-mutated",
            "resolved_graph_address": _address("mutated-resolved-graph"),
            "data_requirement_plan_address": _address("mutated-data-plan"),
            "resource_plan_address": _address("mutated-resource-plan"),
            "event_unit_address": _address("mutated-event-unit"),
            "maximum_age_seconds": 999,
        },
    ):
        resume.wait()
        worker.join(5)
        assert not worker.is_alive()
    assert isinstance(result.get("error"), RuntimeCacheRefusal)
    assert "not REQUIRED" in str(result["error"])


def test_static_cache_uses_detached_not_required_gate_after_verification_barrier(monkeypatch):
    _data, _resource, schedule, gate, authority = _current_static_authorities()
    assert authority.result is _SCHEDULE_FIXTURES.AcquisitionSupport.UNSUPPORTED
    conditional = _compiled_schedule()[5]
    verified = threading.Barrier(2)
    resume = threading.Barrier(2)
    real_verify = runtime_cache_module.verify_authored_acquisition_gate

    def paused_verify(value):
        snapshot = real_verify(value)
        verified.wait()
        resume.wait()
        return snapshot

    monkeypatch.setattr(
        runtime_cache_module, "verify_authored_acquisition_gate", paused_verify,
    )
    result = {}

    def run():
        try:
            _static_attempt(evaluation_schedule=schedule, authored_gate=gate)
        except Exception as exc:
            result["error"] = exc

    worker = threading.Thread(target=run)
    worker.start()
    verified.wait()
    with _mutated_issued_fact(
        gate,
        address_field="gate_address",
        payload=schedule_contract._gate_payload,
        changes={
            "outcome": AuthoredGateOutcome.REQUIRED,
            "authority_address": _address("fabricated-authority"),
            "conditional_requirement_selector": (
                canonical_conditional_requirement_selector(conditional)
            ),
            "conditional_requirement": conditional,
        },
    ):
        resume.wait()
        worker.join(5)
        assert not worker.is_alive()
    assert isinstance(result.get("error"), RuntimeCacheRefusal)
    assert "not REQUIRED" in str(result["error"])


def test_resource_ceiling_integer_subclass_refuses_before_schedule_or_cache_identity():
    with pytest.raises(ScheduleRefusal):
        _SCHEDULE_FIXTURES.compile_schedule_resource_ceiling(
            history_bytes_upper_bound=256,
            memory_bytes_upper_bound=_SCHEDULE_FIXTURES._ChameleonInt(400),
            cache_bytes_upper_bound=128,
            queue_concurrency_upper_bound=2,
            event_rate_events=1,
            event_rate_per_seconds=1,
            policy_address=_address("resource-ceiling-shape"),
        )


@pytest.mark.parametrize(
    "changes,scope",
    [
        ({"owner_id": "owner-b"}, {"owner_id": "owner-b"}),
        ({"assignment_id": "assignment-b"}, {"assignment_id": "assignment-b"}),
        ({"declared_triggers": ("completed_bar", "tick")}, {}),
        ({"event_unit_address": _address("forged-event-unit")}, {}),
        ({"maximum_age_seconds": 999}, {}),
    ],
)
@pytest.mark.parametrize("factory", [_derived, _evaluation])
def test_self_consistent_owner_trigger_unit_or_freshness_schedule_forgery_refuses(
    factory, changes, scope
):
    forged = _self_consistent_schedule_forgery(_compiled_schedule()[4], **changes)
    with pytest.raises(RuntimeCacheRefusal, match="stale or forged"):
        factory(evaluation_schedule=forged, **scope)


@pytest.mark.parametrize("factory,public_factory", [
    (_derived, derived_node_cache_identity),
    (_evaluation, evaluation_result_cache_identity),
])
def test_arbitrary_schedule_address_is_not_a_public_cache_input(factory, public_factory):
    assert "schedule_address" not in inspect.signature(public_factory).parameters
    with pytest.raises(TypeError, match="schedule_address"):
        factory(schedule_address=_address("arbitrary-schedule"))


def test_appending_future_observation_cannot_rewrite_prior_identity():
    admitted = _observation()
    _observation(
        event_at=_time(5), completed_at=_time(6), available_at=_time(7),
        recorded_at=_time(8), knowledge_cutoff=_time(9),
        raw_segment_addresses=(_address("future-segment"),),
    )
    assert _observation().address == admitted.address


@pytest.mark.parametrize("demand,ceiling", [(1, 2), (2, 2)])
def test_resource_demand_below_or_at_ceiling_is_addressed(demand, ceiling):
    bounds = _bounds(subscription_demand=demand, subscription_ceiling=ceiling)
    assert bounds[0].document()["demand"] == demand


def test_resource_demand_above_ceiling_refuses():
    with pytest.raises(RuntimeCacheRefusal, match="exceeds"):
        _bounds(subscription_demand=3, subscription_ceiling=2)


@pytest.mark.parametrize(
    "factory,changes,match",
    [
        (_observation, {"owner_id": ""}, "owner"),
        (_observation, {"assignment_id": ""}, "assignment"),
        (_observation, {"provider_capability_address": "unknown"}, "content address"),
        (_observation, {"unit_contract_address": "UNKNOWN"}, "content address"),
        (_observation, {"knowledge_cutoff": None}, "knowledge cutoff"),
        (lambda **_changes: ResourceBound("UNKNOWN", _address("unit"), 1, 1), {}, "unknown"),
        (_evaluation, {"unit_policy_address": "UNKNOWN"}, "content address"),
    ],
)
def test_unknown_owner_assignment_capability_unit_demand_or_cutoff_refuses(factory, changes, match):
    with pytest.raises(RuntimeCacheRefusal, match=match):
        factory(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"event_at": dt.datetime(2026, 8, 31, 9, 15)},
        {"event_at": dt.datetime(2026, 8, 31, 9, 15, tzinfo=dt.timezone(dt.timedelta(hours=5, minutes=30)))},
        {"event_at": dt.datetime(2026, 8, 31, 9, 15, 0, 1, tzinfo=UTC)},
        {"completed_at": _time(0), "event_at": _time(1)},
        {"available_at": _time(0), "completed_at": _time(1)},
        {"recorded_at": _time(1), "available_at": _time(2)},
        {"knowledge_cutoff": _time(2), "recorded_at": _time(3)},
    ],
)
def test_observation_time_must_be_whole_second_utc_and_causal(changes):
    with pytest.raises(RuntimeCacheRefusal):
        _observation(**changes)


@pytest.mark.parametrize(
    "constructor",
    [
        lambda: ResourceBound("cache_bytes", _address("bytes"), -0.0, 1),
    ],
)
def test_negative_zero_numeric_fact_refuses(constructor):
    with pytest.raises(RuntimeCacheRefusal, match="negative zero"):
        constructor()


def test_exact_addresses_and_closed_collections_refuse_ambiguity():
    with pytest.raises(RuntimeCacheRefusal, match="content address"):
        _derived(input_bindings=(("close", "sha256:" + "A" * 64),))
    with pytest.raises(RuntimeCacheRefusal, match="canonical"):
        _observation(fields=("bid", "ask"))


def test_static_window_requires_typed_required_supported_schedule_gate_authority():
    data, resource, schedule, not_required, unsupported, assessment, eligibility = \
        _current_static_evidence()
    with pytest.raises(RuntimeCacheRefusal, match="not REQUIRED") as refused:
        _static_attempt()
    assert type(refused.value) is RuntimeCacheRefusal
    with pytest.raises(ScheduleRefusal) as caught:
        admit_authored_acquisition_gate(
            schedule,
            data_requirement_plan=data,
            outcome=AuthoredGateOutcome.REQUIRED,
            decision_input_address=_address("required-gate-input"),
            authority=unsupported,
            capability_assessment=assessment,
            eligibility_result=eligibility,
        )
    assert caught.value.code is ScheduleRefusalCode.CAPABILITY_UNSUPPORTED
    assert resource.plan_address == schedule.resource_plan_address


def test_canonical_selector_matches_schedule_and_self_consistent_gate_authority_forgery_refuses():
    data, _resource, schedule, gate, _authority, _assessment, _eligibility = \
        _current_static_evidence()
    conditional = next(
        record for record in data.requirements
        if canonical_conditional_requirement_selector(record)
        == schedule.conditional_requirement_selector
    )
    assert canonical_conditional_requirement_selector(conditional) \
        == schedule.conditional_requirement_selector
    forged = object.__new__(type(gate))
    changes = {
        "outcome": AuthoredGateOutcome.REQUIRED,
        "authority_address": _address("forged-supported-authority"),
        "conditional_requirement_selector": schedule.conditional_requirement_selector,
        "conditional_requirement": conditional,
    }
    for name in gate.__dataclass_fields__:
        object.__setattr__(forged, name, changes.get(name, getattr(gate, name)))
    object.__setattr__(
        forged, "gate_address", content_address(schedule_contract._gate_payload(forged))
    )
    with pytest.raises(RuntimeCacheRefusal, match="stale or forged") as refused:
        _static_attempt(authored_gate=forged)
    assert type(refused.value) is RuntimeCacheRefusal


def test_readdressed_in_place_issued_not_required_gate_cannot_create_static_identity():
    data, _resource, schedule, gate, authority, _assessment, eligibility = \
        _current_static_evidence()
    conditional = next(
        record for record in data.requirements
        if canonical_conditional_requirement_selector(record)
        == schedule.conditional_requirement_selector
    )
    assert authority.result.value == "UNSUPPORTED"
    assert eligibility.status == "REFUSED"
    with _mutated_issued_fact(
        gate,
        address_field="gate_address",
        payload=schedule_contract._gate_payload,
        changes={
            "outcome": AuthoredGateOutcome.REQUIRED,
            "authority_address": _address("inserted-false-authority"),
            "conditional_requirement_selector": schedule.conditional_requirement_selector,
            "conditional_requirement": conditional,
        },
    ):
        with pytest.raises(RuntimeCacheRefusal, match="stale or forged") as refused:
            _static_attempt(authored_gate=gate)
        assert type(refused.value) is RuntimeCacheRefusal


@pytest.mark.parametrize(
    "changes,match",
    [
        ({"owner_id": "owner-b"}, "owner or assignment"),
        ({"assignment_id": "assignment-b"}, "owner or assignment"),
        ({"resource_plan_address": _address("other-resource")}, "resource plan differs"),
        ({"evaluation_schedule": object()}, "stale or forged"),
        ({"authored_gate": object()}, "stale or forged"),
    ],
)
def test_static_window_refuses_cross_scope_resource_and_direct_facts(changes, match):
    with pytest.raises(RuntimeCacheRefusal, match=match):
        _static_attempt(**changes)


def test_static_window_refuses_cross_schedule_and_stale_forged_schedule():
    _data, _resource, schedule, _gate, _authority, _assessment, _eligibility = \
        _current_static_evidence()
    (_other_data, _other_resource, _other_schedule, other_gate, _other_authority,
     _other_assessment, _other_eligibility) = \
        _current_static_evidence(assignment_id="assignment-b")
    with pytest.raises(RuntimeCacheRefusal, match="gate differs"):
        _static_attempt(authored_gate=other_gate)
    forged = object.__new__(EvaluationScheduleAddress)
    for name in schedule.__dataclass_fields__:
        object.__setattr__(
            forged, name,
            _address("forged-schedule") if name == "schedule_address" else getattr(schedule, name),
        )
    with pytest.raises(RuntimeCacheRefusal, match="stale or forged"):
        _static_attempt(evaluation_schedule=forged)


def test_arbitrary_gate_address_is_not_part_of_the_public_factory():
    assert "authored_gate_address" not in inspect.signature(static_window_cache_identity).parameters
    with pytest.raises(TypeError, match="authored_gate_address"):
        _static_attempt(authored_gate_address=_address("arbitrary-gate"))


def test_fresh_module_recompile_accepts_equal_schedule_without_parent_identity_leak():
    module_name = "app.market_data.runtime_cache_identity"
    original_cache_module = sys.modules[module_name]
    original_schedule_module = sys.modules["app.ir.evaluation_schedule"]
    original_refusal = RuntimeCacheRefusal
    original_schedule_type = EvaluationScheduleAddress
    expected_schedule_address = _compiled_schedule()[4].schedule_address
    script = f"""
import importlib.util
from pathlib import Path
import sys

path = Path({str(Path(__file__).resolve())!r})
spec = importlib.util.spec_from_file_location("fresh_cache_consumer_fixtures", path)
fixtures = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = fixtures
spec.loader.exec_module(fixtures)
schedule = fixtures._compiled_schedule()[4]
assert schedule.schedule_address == {expected_schedule_address!r}
assert fixtures._derived().document["schedule_address"] == schedule.schedule_address
assert fixtures._evaluation().document["schedule_address"] == schedule.schedule_address
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).parents[1],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert sys.modules[module_name] is original_cache_module
    assert sys.modules["app.ir.evaluation_schedule"] is original_schedule_module
    assert RuntimeCacheRefusal is original_refusal
    assert EvaluationScheduleAddress is original_schedule_type


def test_no_provider_persistence_monitoring_evaluator_or_execution_imports():
    blocked = (
        "app.providers", "app.db", "app.monitoring", "app.api", "app.engine",
        "app.execution", "app.ledger", "app.backtest", "app.ir.runtime",
        "app.ir.incremental_runtime",
    )
    module_name = "app.market_data.runtime_cache_identity"
    original_module = sys.modules[module_name]
    original_refusal = RuntimeCacheRefusal
    original_schedule_type = EvaluationScheduleAddress
    script = f"""
import builtins
import importlib

blocked = {blocked!r}
# The cache's accepted typed boundary is loaded before poisoning.  Its existing
# dependency cone is owned by the schedule lane; the cache import must not widen it.
importlib.import_module("app.ir.evaluation_schedule")
real_import = builtins.__import__

def poison(name, *args, **kwargs):
    if name.startswith(blocked):
        raise AssertionError(f\"forbidden runtime import: {{name}}\")
    return real_import(name, *args, **kwargs)

builtins.__import__ = poison
importlib.import_module({module_name!r})
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).parents[1],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert sys.modules[module_name] is original_module
    assert RuntimeCacheRefusal is original_refusal
    assert EvaluationScheduleAddress is original_schedule_type


def test_cache_consumers_remain_usable_after_isolated_fresh_module_checks():
    schedule = _compiled_schedule()[4]
    derived = _derived()
    evaluation = _evaluation()
    assert type(derived) is RuntimeCacheIdentity
    assert type(evaluation) is RuntimeCacheIdentity
    assert derived.document["schedule_address"] == schedule.schedule_address
    assert evaluation.document["schedule_address"] == schedule.schedule_address
