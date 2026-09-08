"""Cross-lane proof for the V0 schedule and runtime-cache foundation."""
from __future__ import annotations

from dataclasses import replace

import pytest

from app.ir.evaluation_schedule import (
    AcquisitionSupport,
    AuthoredGateOutcome,
    ScheduleRefusal,
    ScheduleRefusalCode,
    admit_authored_acquisition_gate,
    admit_evaluation_event,
)
from app.market_data.runtime_cache_identity import (
    RuntimeCacheRefusal,
    derived_node_cache_identity,
    evaluation_result_cache_identity,
    observation_cache_identity,
)
from tests import test_v0_evaluation_schedule as schedule_fixtures
from tests import test_v0_runtime_cache_identity as cache_fixtures


def _event(schedule, *, recorded_second: int = 2):
    return admit_evaluation_event(
        schedule,
        trigger="completed_bar",
        observation_address=schedule_fixtures._address("observation"),
        event_at=schedule_fixtures._time(0),
        completed_at=schedule_fixtures._time(1),
        available_at=schedule_fixtures._time(1),
        recorded_at=schedule_fixtures._time(recorded_second),
        cutoff_at=schedule_fixtures._time(3),
        unit_contract_address=schedule_fixtures._address("event-unit-seconds"),
    )


def _chain(*, recorded_second: int = 2):
    registry, graph, data, resource, schedule, _conditional = schedule_fixtures._facts()
    event = _event(schedule, recorded_second=recorded_second)
    observation = observation_cache_identity(
        owner_id=schedule.owner_id,
        assignment_id=schedule.assignment_id,
        licence_scope_address=cache_fixtures._address("licence"),
        provider_entity_address=cache_fixtures._address("provider-entity"),
        provider_product_address=cache_fixtures._address("provider-product"),
        provider_contract_address=cache_fixtures._address("provider-contract"),
        provider_conformance_address=cache_fixtures._address("provider-conformance"),
        provider_capability_address=cache_fixtures._address("provider-capability"),
        canonical_instrument_address=cache_fixtures._address("instrument"),
        canonical_contract_address=cache_fixtures._address("contract"),
        fields=("close",),
        depth_levels=0,
        rulebook_address=cache_fixtures._address("rulebook"),
        alias_addresses=(cache_fixtures._address("alias"),),
        correction_addresses=(),
        raw_segment_addresses=(cache_fixtures._address("segment"),),
        event_at=event.event_at,
        completed_at=event.completed_at,
        available_at=event.available_at,
        recorded_at=event.recorded_at,
        knowledge_cutoff=event.cutoff_at,
        timeframe_seconds=60,
        session_policy_address=cache_fixtures._address("session"),
        unit_contract_address=event.unit_contract_address,
        missing_data_policy_address=cache_fixtures._address("missing"),
        alignment_policy_address=cache_fixtures._address("alignment"),
        adjustment_policy_address=cache_fixtures._address("adjustment"),
    )
    derived = derived_node_cache_identity(
        owner_id=schedule.owner_id,
        assignment_id=schedule.assignment_id,
        node_semantic_address=cache_fixtures._address("semantic"),
        node_contract_address=cache_fixtures._address("node-contract"),
        node_implementation_address=cache_fixtures._address("node-implementation"),
        parameters_address=cache_fixtures._address("parameters"),
        input_bindings=(("close", observation.address),),
        resolved_graph_address=schedule.resolved_graph_address,
        implementation_closure_address=schedule.implementation_closure_address,
        registry_snapshot_address=schedule.registry_snapshot_address,
        input_unit_addresses=(event.unit_contract_address,),
        output_unit_address=cache_fixtures._address("signal-unit"),
        missing_data_policy_address=cache_fixtures._address("missing"),
        alignment_policy_address=cache_fixtures._address("alignment"),
        adjustment_policy_address=cache_fixtures._address("adjustment"),
        session_policy_address=cache_fixtures._address("session"),
        event_at=event.event_at,
        knowledge_cutoff=event.cutoff_at,
        state_predecessor_address=None,
        state_reset_address=None,
        output_port="signal",
        evaluation_schedule=schedule,
    )
    result = evaluation_result_cache_identity(
        owner_id=schedule.owner_id,
        assignment_id=schedule.assignment_id,
        resolved_graph_address=schedule.resolved_graph_address,
        implementation_closure_address=schedule.implementation_closure_address,
        registry_snapshot_address=schedule.registry_snapshot_address,
        admission_address=cache_fixtures._address("admission"),
        data_requirement_plan_address=data.plan_address,
        resource_plan_address=resource.plan_address,
        dataset_or_stream_address=cache_fixtures._address("stream"),
        market_truth_address=cache_fixtures._address("market-truth"),
        evaluation_schedule=schedule,
        input_addresses=(derived.address,),
        unit_policy_address=cache_fixtures._address("unit-policy"),
        result_scope="EVALUATION_ONLY",
        fill_policy_address=None,
        charge_schedule_address=None,
        book_epoch_address=None,
        paper_policy_address=None,
        state_predecessor_address=None,
        state_reset_address=None,
        event_at=event.event_at,
        knowledge_cutoff=event.cutoff_at,
    )
    return registry, graph, data, resource, schedule, event, observation, derived, result


def test_admitted_event_flows_into_exact_observation_node_and_result_identities():
    first = _chain()
    reconstructed = _chain()
    assert [item.address for item in first[6:]] == [item.address for item in reconstructed[6:]]
    schedule, event, observation, derived, result = first[4:]
    assert observation.document["owner_id"] == schedule.owner_id
    assert derived.document["schedule_address"] == schedule.schedule_address
    assert derived.document["input_bindings"][0]["address"] == observation.address
    assert result.document["input_addresses"] == (derived.address,)
    assert event.schedule_address == schedule.schedule_address


def test_recording_time_change_propagates_without_rewriting_prior_prefix():
    prior = _chain(recorded_second=2)
    later_recording = _chain(recorded_second=3)
    assert prior[4].schedule_address == later_recording[4].schedule_address
    assert prior[5].event_address != later_recording[5].event_address
    assert [item.address for item in prior[6:]] != [item.address for item in later_recording[6:]]
    assert [item.address for item in _chain(recorded_second=2)[6:]] == [
        item.address for item in prior[6:]
    ]


def test_cross_assignment_schedule_and_cache_scope_cannot_be_mixed():
    prior = _chain()
    foreign_schedule = schedule_fixtures._facts(assignment_id="assignment-b")[4]
    with pytest.raises(RuntimeCacheRefusal, match="assignment"):
        cache_fixtures._derived(
            owner_id=prior[4].owner_id,
            assignment_id=foreign_schedule.assignment_id,
            input_bindings=(("close", prior[6].address),),
            input_unit_addresses=(prior[5].unit_contract_address,),
            event_at=prior[5].event_at,
            knowledge_cutoff=prior[5].cutoff_at,
            evaluation_schedule=prior[4],
        )


def test_current_typed_option_depth_authority_cannot_create_gate_or_static_cache():
    registry, graph, data, resource, schedule, _conditional = schedule_fixtures._facts()
    assessment, eligibility, authority = schedule_fixtures._typed_conditional_authority(
        registry, graph, data, schedule,
    )
    assert authority.result is AcquisitionSupport.UNSUPPORTED
    with pytest.raises(ScheduleRefusal) as caught:
        admit_authored_acquisition_gate(
            schedule,
            data_requirement_plan=data,
            outcome=AuthoredGateOutcome.REQUIRED,
            decision_input_address=cache_fixtures._address("required"),
            authority=authority,
            capability_assessment=assessment,
            eligibility_result=eligibility,
        )
    assert caught.value.code is ScheduleRefusalCode.CAPABILITY_UNSUPPORTED

    not_required = admit_authored_acquisition_gate(
        schedule,
        data_requirement_plan=data,
        outcome=AuthoredGateOutcome.NOT_REQUIRED,
        decision_input_address=cache_fixtures._address("not-required"),
    )
    with pytest.raises(RuntimeCacheRefusal, match="not REQUIRED"):
        cache_fixtures._static_attempt(
            evaluation_schedule=schedule,
            authored_gate=not_required,
            resource_plan_address=resource.plan_address,
        )


def test_fact_copy_cannot_upgrade_not_required_to_required():
    data, _resource, schedule, not_required, _authority = \
        cache_fixtures._current_static_authorities()
    with pytest.raises(TypeError):
        replace(not_required, outcome=AuthoredGateOutcome.REQUIRED)
    assert not_required.outcome is AuthoredGateOutcome.NOT_REQUIRED
    assert data.plan_address == schedule.data_requirement_plan_address
