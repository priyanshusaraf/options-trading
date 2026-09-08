"""Compile attributed monitoring steps from an issued, completed research prefix.

The worker reloads admission and provider authority. This compiler rechecks their
exact scope, evaluates the original bound graph, and retains every unconsumed step.
"""
from __future__ import annotations

import datetime as dt
import json

from app.ir.hashing import canonical_json, content_address
from app.ir.resolve import ResolvedV2Graph
from app.ir.resource_plan import CanonicalResourceDocument
from app.market_data.requirements import compile_data_requirement_plan
from app.market_truth.identity import CanonicalPhysicalInstrument
from app.monitoring import evaluation
from app.monitoring.input_producer import MonitoringInputPrefix
from app.monitoring.contracts import FactValidity, Freshness, SignalAction, StrategyState
from app.monitoring.research_consumer import SCHEMA, research_consumer_implementation_address
from app.monitoring.research_event_contracts import ResearchMonitoringSignalEvent, derive_research_signal_alert
from app.monitoring.research_prefix import (
    ResearchReplayCheckpoint, _market_bars, advance_research_prefix, evaluate_research_prefix_outputs,
)
from app.monitoring.research_replay_state import ResearchReplayState, _require
from app.monitoring.research_state_contracts import ResearchMonitoringStateSnapshot, compile_research_monitoring_snapshot
from app.monitoring.state_contracts import MonitoringAssignment
from research.data.historical_capture import PURPOSE


def _consumer_assignment(assignment, consumer):
    _require(type(assignment) is MonitoringAssignment and type(consumer) is CanonicalResourceDocument,
        "closed research assignment and consumer required")
    consumer.__post_init__()
    _require(assignment.lifecycle_state == "ACTIVE" and assignment.withdrawn_at is None,
        "research assignment is inactive")
    document, spec = consumer.document, assignment.spec
    _require(consumer.schema == SCHEMA, "research consumer schema differs")
    expected = (assignment.owner_id, spec.assignment_id, spec.project_id, spec.graph_version_address,
        spec.resolved_graph_address, spec.implementation_closure_address, spec.research_admission_address,
        research_consumer_implementation_address())
    actual = tuple(document[key] for key in ("owner_id", "assignment_id", "project_id", "graph_version_address",
        "resolved_graph_address", "graph_implementation_address", "original_admission_address", "consumer_implementation_address"))
    _require(actual == expected, "research consumer differs from assignment or current implementation")


def _previous_research_state(assignment, previous, consumer):
    if previous is None:
        _require(assignment.current_state_snapshot_address is None, "research assignment is already initialized")
        return
    _require(type(previous) is ResearchMonitoringStateSnapshot, "closed preceding research snapshot required")
    previous.__post_init__()
    actual = (previous.owner_id, previous.assignment_id, previous.address, previous.checkpoint.state.consumer_address)
    expected = (assignment.owner_id, assignment.spec.assignment_id, assignment.current_state_snapshot_address, consumer.address)
    _require(actual == expected, "research predecessor differs from current assignment")


def _prefix_event_binding(prefix, schedule, event, graph, registry):
    plan = compile_data_requirement_plan(graph, registry=registry, input_bindings=prefix.projection.input_bindings)
    _require(plan.plan_address == schedule.data_requirement_plan_address, "research prefix differs from scheduled data plan")
    actual = (event.observation_address, event.event_at, event.completed_at, event.available_at,
        event.recorded_at, event.cutoff_at)
    expected = (prefix.observation_address, prefix.event_at, prefix.completed_at, prefix.available_at,
        prefix.recorded_at, prefix.cutoff_at)
    _require(actual == expected, "issued research event differs from canonical prefix receipts")


def _prefix_source_scope(assignment, prefix):
    projection = prefix.projection
    source = json.loads(projection.source_provenance_json)
    _require(canonical_json(source) == projection.source_provenance_json
        and content_address(source) == projection.source_provenance_address, "research source provenance changed")
    connection = source['historical_capture']['connection_id']
    _require(type(connection) is int, "research source connection must be exact")
    actual = (projection.manifest.owner_id, projection.manifest.purpose, connection,
        source['manifest_address'], dt.datetime.fromisoformat(source['as_of']))
    expected = (assignment.owner_id, PURPOSE + assignment.spec.project_id, assignment.spec.data_connection_id,
        prefix.manifest_address, prefix.cutoff_at)
    _require(actual == expected, "research source differs from the assignment's project, connection or cutoff")


def _verified_research_context(assignment, previous, consumer, prefix, graph, registry,
        schedule, event, policy, instrument):
    _consumer_assignment(assignment, consumer)
    _previous_research_state(assignment, previous, consumer)
    _require(type(graph) is ResolvedV2Graph and type(instrument) is CanonicalPhysicalInstrument
        and type(prefix) is MonitoringInputPrefix,
        "closed resolved graph and canonical instrument required")
    _require(prefix.projection.manifest.instrument_addresses == (instrument.address,), "research signal instrument differs")
    _prefix_source_scope(assignment, prefix)
    schedule, event = evaluation._issued_event_schedule(schedule, event)
    _require(schedule.gate_node_id is None, "research prefix requires a completed-bar schedule")
    evaluation._assignment_schedule_binding(assignment, schedule, event, policy)
    verified_registry = evaluation._registry_authority(registry, graph)
    evaluation._graph_schedule_binding(graph, schedule, verified_registry)
    _prefix_event_binding(prefix, schedule, event, graph, verified_registry)
    _require(previous is None or previous.effective_at <= event.completed_at, "research predecessor is from the future")
    return schedule, event


def _snapshot_arguments(prefix, consumer, instrument, event):
    return dict(consumer=consumer, instrument=prefix.instrument, canonical_instrument=instrument,
        source_truth_address=prefix.projection.manifest.truth_snapshot_addresses[0],
        evaluation_event_address=event.event_address)


def compile_initial_research_monitoring_state(*, assignment, consumer, prefix, graph, registry,
        schedule, evaluation_event, evaluation_policy, canonical_instrument, timeframe_seconds):
    """Seed honest FLAT state at activation; earlier rows are indicator warmup."""
    _, event = _verified_research_context(assignment, None, consumer, prefix, graph, registry,
        schedule, evaluation_event, evaluation_policy, canonical_instrument)
    checkpoint = ResearchReplayCheckpoint(ResearchReplayState(assignment.owner_id, assignment.spec.assignment_id,
        canonical_instrument.address, consumer.address, 0))
    terminal = _market_bars(prefix, checkpoint, consumer, timeframe_seconds)[-1]
    return compile_research_monitoring_snapshot(checkpoint, bar=terminal, previous=None,
        **_snapshot_arguments(prefix, consumer, canonical_instrument, event))


def _research_decision_details(previous, state):
    pending = state.pending
    if pending is None:
        prior = previous.pending
        failed = prior is not None and prior.kind in ("ENTER", "REVERSE") and state.position is None
        return "NONE", SignalAction.HOLD, "ENTRY_NOT_FILLED" if failed else "NO_NEW_DECISION"
    if pending.kind == "EXIT":
        return "EXIT", SignalAction.EXIT, "RESEARCH_EXIT_PENDING"
    action = SignalAction.BUY if pending.argument == "LONG" else SignalAction.SELL
    reason = "RESEARCH_REVERSAL_PENDING" if pending.kind == "REVERSE" else "RESEARCH_ENTRY_PENDING"
    return pending.kind, action, reason


def _research_step_event(assignment, previous, snapshot, prefix, event, maximum_age_seconds, display_symbol):
    state, spec = snapshot.checkpoint.state, assignment.spec
    decision, action, reason = _research_decision_details(previous.checkpoint.state, state)
    held = StrategyState.FLAT if state.position is None else StrategyState(state.position.direction)
    deadline = snapshot.effective_at + dt.timedelta(seconds=maximum_age_seconds)
    explanation = content_address({"schema": "monitoring-research-decision-evidence/1",
        "consumer_address": state.consumer_address, "before": previous.checkpoint.address,
        "after": snapshot.checkpoint.address, "dataset_address": prefix.manifest_address,
        "completed_bar_identity": state.last_bar_identity, "decision_kind": decision, "reason": reason})
    return ResearchMonitoringSignalEvent(owner_id=assignment.owner_id, assignment_id=spec.assignment_id,
        strategy_id=spec.strategy_id, graph_version_address=spec.graph_version_address,
        resolved_graph_address=spec.resolved_graph_address, implementation_closure_address=spec.implementation_closure_address,
        admission_address=spec.research_admission_address, canonical_instrument_address=snapshot.canonical_instrument_address,
        display_symbol=display_symbol, previous_state=previous.strategy_state, target_state=snapshot.strategy_state,
        action=action, evaluation_event_address=event.event_address, event_at=snapshot.effective_at,
        latest_data_at=snapshot.effective_at, knowledge_cutoff_at=event.cutoff_at, valid_until=deadline,
        evaluation_validity=FactValidity.VALID, freshness=Freshness.FRESH if event.cutoff_at <= deadline else Freshness.STALE,
        repeated_target_state=previous.strategy_state is snapshot.strategy_state,
        entry_reference=snapshot.entry_reference, stop_loss=snapshot.stop_loss, take_profit=snapshot.take_profit,
        state_before_address=previous.address, state_after_address=snapshot.address,
        provider_evidence_address=prefix.observation_address, dataset_address=prefix.manifest_address,
        reason_code=reason, reason_evidence_address=explanation, consumer_address=state.consumer_address,
        completed_bar_identity=state.last_bar_identity, prefix_completed_at=prefix.completed_at,
        prefix_available_at=prefix.available_at, prefix_recorded_at=prefix.recorded_at,
        replay_scope="CURRENT" if snapshot.effective_at == prefix.completed_at else "CATCH_UP",
        decision_kind=decision, simulated_position_state=held)


def compile_research_monitoring_prefix(*, assignment, previous_snapshot, consumer, prefix, graph,
        graph_document, registry, schedule, evaluation_event, evaluation_policy, canonical_instrument,
        timeframe_seconds, display_symbol):
    """Return the full unconsumed tail; an unchanged completed bar produces nothing."""
    schedule, event = _verified_research_context(assignment, previous_snapshot, consumer, prefix, graph,
        registry, schedule, evaluation_event, evaluation_policy, canonical_instrument)
    _require(previous_snapshot is not None, "research prefix requires its persisted initial state")
    outputs = evaluate_research_prefix_outputs(prefix, consumer=consumer, graph_document=graph_document, registry=registry)
    steps = advance_research_prefix(previous_snapshot.checkpoint, prefix=prefix, consumer=consumer,
        graph_document=graph_document, outputs=outputs, timeframe_seconds=timeframe_seconds)
    transitions, previous = [], previous_snapshot
    for step in steps:
        snapshot = compile_research_monitoring_snapshot(step.checkpoint, bar=step.bar, previous=previous,
            **_snapshot_arguments(prefix, consumer, canonical_instrument, event))
        source = _research_step_event(assignment, previous, snapshot, prefix, event,
            schedule.maximum_age_seconds, display_symbol)
        transitions.append(evaluation.MonitoringEvaluationTransition(snapshot, source, derive_research_signal_alert(source)))
        previous = snapshot
    return tuple(transitions)
