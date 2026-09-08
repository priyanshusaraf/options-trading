"""Evaluate one current watchlist binding using reloaded research authority.

The caller owns data acquisition, the transaction, and its trusted publication
clock. This worker accepts retained input addresses and never opens a broker.
"""
from __future__ import annotations

import datetime as dt

from app.db.concurrency import begin_reservation, caller_owned_savepoint
from app.ir.hashing import content_address
from app.ir.library import REGISTRY
from app.ir.resource_plan import _plain
from app.market_truth.identity import load_canonical_instrument
from app.monitoring.evaluation_policy import compile_monitoring_evaluation_policy, load_monitoring_evaluation_policy
from app.monitoring.input_producer import _dataset_source, load_monitoring_input_prefix
from app.monitoring.repository import MonitoringRepository
from app.monitoring.research_consumer import load_research_monitoring_context
from app.monitoring.research_evaluation import compile_initial_research_monitoring_state, compile_research_monitoring_prefix
from app.monitoring.research_replay_state import _require
from app.monitoring.research_runtime import persist_research_transitions
from app.monitoring.research_schedule import compile_research_monitoring_schedule
from app.monitoring.state_contracts import MonitoringAssignmentSpec, _utc
from app.monitoring.watchlist_config import TIMEFRAMES, WatchlistConfiguration
from app.monitoring.watchlist_store import bind_watchlist_monitoring, latest_configurations, scope_members, verified_scope
from research.orchestrator.v2_operation import _graph_input_fields


def _current_research_row(session, owner_id, requested, *, bound=True):
    _require(type(requested) is WatchlistConfiguration and requested.owner_id == owner_id,
        'closed owner-scoped watchlist row required')
    begin_reservation(session, scope=f'static-scope:{owner_id}:{requested.project_id}')
    scope = verified_scope(session, owner_id, requested.context, write=True)
    current = latest_configurations(session, owner_id, requested.context,
        (requested.member_key,)).get(requested.member_key)
    _require(current == requested and requested.member_key in scope_members(scope),
        'watchlist row changed before evaluation')
    _require(requested.monitoring_intent == 'MONITOR' and (requested.assignment_id is not None) == bound,
        'watchlist monitoring intent or binding differs')
    return MonitoringRepository(session, owner_id=owner_id)


def _research_row_assignment(repository, requested):
    assignment = repository.get_assignment(requested.assignment_id)
    spec = assignment.spec
    _require(assignment.lifecycle_state == 'ACTIVE' and assignment.withdrawn_at is None,
        'monitoring assignment is inactive')
    actual = (assignment.owner_id, spec.project_id, spec.strategy_id, spec.graph_version_address,
        spec.static_scope_revision_address)
    expected = (requested.owner_id, requested.project_id, requested.graph.graph_id,
        requested.graph.graph_version_address, requested.context.scope_address)
    _require(actual == expected, 'assignment differs from current watchlist strategy or membership')
    return assignment


def evaluate_research_watchlist_row(execution_session, research_session, *, owner_id, requested,
        operation_id, input_manifest_address, display_symbol, cutoff_at, publication_clock=None):
    """Persist every new observed step; only the terminal fresh decision may alert."""
    cutoff = _utc(cutoff_at, 'research worker cutoff')
    clock = publication_clock or (lambda: dt.datetime.now(dt.timezone.utc))
    _require(callable(clock), 'trusted worker clock required')
    started = _utc(clock(), 'research worker start')
    _require(cutoff <= started, 'research worker cutoff is in the future')
    repository = _current_research_row(execution_session, owner_id, requested)
    assignment = _research_row_assignment(repository, requested)
    context = load_research_monitoring_context(execution_session, research_session, owner_id=owner_id,
        project_id=requested.project_id, graph_id=requested.graph.graph_id,
        graph_version=requested.graph.graph_version, admission_address=assignment.spec.research_admission_address,
        operation_id=operation_id, assignment_id=requested.assignment_id)
    _require(assignment.spec.role_binding_address == context.consumer.address,
        'monitoring assignment differs from its retained research consumer')
    policy = load_monitoring_evaluation_policy(requested.evaluation_policy)
    instrument = load_canonical_instrument(execution_session, requested.canonical_instrument_address)
    seconds = TIMEFRAMES[requested.timeframe][0]
    prefix = load_monitoring_input_prefix(research_session, execution_session, owner_id=owner_id,
        manifest_address=input_manifest_address, instrument_address=instrument.address,
        timeframe_seconds=seconds, minimum_bars=1, maximum_age_seconds=policy.document['maximum_age_seconds'],
        cutoff_at=cutoff, graph_input_fields=_graph_input_fields(_plain(context.graph_document), REGISTRY), now=started)
    _require(dt.timedelta(0) <= started - prefix.completed_at
        <= dt.timedelta(seconds=policy.document['maximum_age_seconds']),
        'research input expired before the worker started')
    schedule, event = compile_research_monitoring_schedule(prefix=prefix, graph=context.graph, registry=REGISTRY,
        evaluation_policy=policy, canonical_instrument=instrument, timeframe_seconds=seconds)
    previous = repository.get_latest_state(requested.assignment_id, instrument.address)
    transitions = compile_research_monitoring_prefix(assignment=assignment, previous_snapshot=previous,
        consumer=context.consumer, prefix=prefix, graph=context.graph, graph_document=_plain(context.graph_document),
        registry=REGISTRY, schedule=schedule, evaluation_event=event, evaluation_policy=policy,
        canonical_instrument=instrument, timeframe_seconds=seconds, display_symbol=display_symbol)
    published = _utc(clock(), 'research worker publication')
    _require(published >= started, 'research worker clock moved backwards')
    return persist_research_transitions(repository, transitions, created_at=published)


def _activation_input(execution_session, research_session, requested, context, manifest, cutoff, limits):
    _, data = _dataset_source(research_session, execution_session, requested.owner_id, manifest, cutoff)
    instrument = load_canonical_instrument(execution_session, data.binding['instrument_address'])
    prefix = load_monitoring_input_prefix(research_session, execution_session, owner_id=requested.owner_id,
        manifest_address=manifest, instrument_address=instrument.address, timeframe_seconds=TIMEFRAMES[requested.timeframe][0],
        minimum_bars=1, maximum_age_seconds=limits['maximum_age_seconds'], cutoff_at=cutoff,
        graph_input_fields=_graph_input_fields(_plain(context.graph_document), REGISTRY), now=cutoff)
    return prefix, instrument, data.binding['historical_capture']['connection_id']


def _activation_policy(requested, context, prefix, assignment_id, limits):
    from app.ir.resource_plan import compile_resource_plan
    from app.market_data.requirements import compile_data_requirement_plan
    data = compile_data_requirement_plan(context.graph, registry=REGISTRY, input_bindings=prefix.projection.input_bindings)
    resource = compile_resource_plan(context.graph, data, REGISTRY,
        cache_bytes_upper_bound=limits['cache_bytes_upper_bound'], artifact_bytes_upper_bound=0,
        queue_concurrency_upper_bound=limits['queue_concurrency_upper_bound'])
    return compile_monitoring_evaluation_policy(owner_id=requested.owner_id, assignment_id=assignment_id,
        initial_resource_plan_address=resource.plan_address, **limits)


def _activation_spec(requested, context, prefix, connection_id, policy):
    graph, consumer = context.graph, context.consumer
    return MonitoringAssignmentSpec(assignment_id=consumer.document['assignment_id'], project_id=requested.project_id,
        strategy_id=requested.graph.graph_id, graph_version_address=graph.authored_ir_address,
        resolved_graph_address=graph.resolved_graph_address, registry_address=REGISTRY.registry_snapshot_address,
        implementation_closure_address=graph.implementation_closure_address,
        research_admission_address=context.original_admission.admission_address,
        static_scope_revision_address=requested.context.scope_address, role_binding_address=consumer.address,
        data_connection_id=connection_id, capability_profile_address=prefix.projection.manifest.capability_profile_address,
        resource_plan_address=policy.document['initial_resource_plan_address'], evaluation_trigger_address=policy.address,
        state_reset_policy_address=content_address({'schema': 'research-monitoring-activation-reset/1',
            'consumer_address': consumer.address, 'initial_state': consumer.document['initial_state'],
            'history': consumer.document['history']}))


def activate_research_watchlist_row(execution_session, research_session, *, owner_id, created_by, requested,
        operation_id, admission_address, input_manifest_address, evaluation_limits, request_id, now):
    """Bind real research evidence and input within caller-supplied trusted limits."""
    cutoff = _utc(now, 'research activation time')
    repository = _current_research_row(execution_session, owner_id, requested, bound=False)
    identity = content_address({'schema': 'research-watchlist-assignment/1', 'owner_id': owner_id,
        'requested_address': requested.address, 'operation_id': operation_id, 'admission_address': admission_address})
    assignment_id = 'monitoring.' + identity.removeprefix('sha256:')
    context = load_research_monitoring_context(execution_session, research_session, owner_id=owner_id,
        project_id=requested.project_id, graph_id=requested.graph.graph_id, graph_version=requested.graph.graph_version,
        admission_address=admission_address, operation_id=operation_id, assignment_id=assignment_id)
    prefix, instrument, connection = _activation_input(execution_session, research_session, requested, context,
        input_manifest_address, cutoff, evaluation_limits)
    policy = _activation_policy(requested, context, prefix, assignment_id, evaluation_limits)
    spec = _activation_spec(requested, context, prefix, connection, policy)
    schedule, event = compile_research_monitoring_schedule(prefix=prefix, graph=context.graph, registry=REGISTRY,
        evaluation_policy=policy, canonical_instrument=instrument, timeframe_seconds=TIMEFRAMES[requested.timeframe][0])
    with caller_owned_savepoint(execution_session, scope='activate-research-watchlist'):
        assignment = repository.create_assignment(spec, now=cutoff)
        initial = compile_initial_research_monitoring_state(assignment=assignment, consumer=context.consumer,
            prefix=prefix, graph=context.graph, registry=REGISTRY, schedule=schedule, evaluation_event=event,
            evaluation_policy=policy, canonical_instrument=instrument, timeframe_seconds=TIMEFRAMES[requested.timeframe][0])
        return bind_watchlist_monitoring(execution_session, owner_id=owner_id, created_by=created_by, requested=requested,
            assignment_spec=spec, evaluation_policy=policy, initial_snapshot=initial, request_id=request_id, now=cutoff,
            research_session=research_session, input_manifest_address=input_manifest_address)
