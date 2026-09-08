"""Issue bounded completed-bar schedules from verified research input contracts.

Unit identity retains the registered types, parameter units and implementation
that define each node's numerical semantics. It never substitutes signal prices
for a graph's declared values or grants execution authority.
"""
from __future__ import annotations

import json

from app.ir.evaluation_schedule import admit_evaluation_event, compile_completed_bar_evaluation_schedule
from app.ir.hashing import canonical_json, content_address
from app.ir.resource_plan import _plain, compile_resource_plan
from app.market_data.requirements import compile_data_requirement_plan
from app.market_truth.identity import CanonicalPhysicalInstrument
from app.monitoring import evaluation
from app.monitoring.evaluation_policy import monitoring_policy_payload, monitoring_resource_ceiling
from app.monitoring.input_producer import MonitoringInputPrefix
from app.monitoring.research_replay_state import _require


def _registered_unit_contract(node, graph, registry, data_plan, instrument):
    component = registry.v2_components[node.component]
    ports = _plain(component['ports'])
    types = {port['type_ref']['type_id'] + ':' + str(port['type_ref']['type_version']):
        _plain(registry.v2_types[(port['type_ref']['type_id'], port['type_ref']['type_version'])])
        for port in ports}
    return content_address({'schema': 'monitoring-registered-node-units/1',
        'resolved_graph_address': graph.resolved_graph_address, 'node_id': node.node_id,
        'registry_snapshot_address': registry.registry_snapshot_address,
        'implementation_address': registry.v2_implementation_identities[node.component],
        'node_contract_address': registry.node_contract_addresses[node.component],
        'ports': ports, 'types': types, 'parameters': _plain(node.parameters),
        'parameter_definitions': _plain(component['parameters']),
        'data_requirement_plan_address': data_plan.plan_address,
        'canonical_instrument_address': instrument.address, 'price_currency': instrument.currency,
        'numeric_semantics': 'REGISTERED_IMPLEMENTATION'})


def _prefix_schedule_scope(prefix, instrument, seconds):
    from app.monitoring.research_prefix import _prefix_projection
    projection = _prefix_projection(prefix)
    source = json.loads(projection.source_provenance_json)
    _require(canonical_json(source) == projection.source_provenance_json
        and content_address(source) == projection.source_provenance_address,
        'schedule source provenance changed')
    _require((projection.manifest.instrument_addresses, source['time_interpretation']['resolution_seconds'])
        == ((instrument.address,), seconds), 'schedule instrument or timeframe differs from verified prefix')


def compile_research_monitoring_schedule(*, prefix, graph, registry, evaluation_policy,
        canonical_instrument, timeframe_seconds):
    """Recompile each fresh prefix within the assignment's retained policy limits."""
    _require(type(prefix) is MonitoringInputPrefix and type(canonical_instrument) is CanonicalPhysicalInstrument,
        'closed research prefix and instrument required')
    _require(type(timeframe_seconds) is int and timeframe_seconds in (900, 1800, 3600, 86400),
        'supported completed-bar timeframe required')
    _prefix_schedule_scope(prefix, canonical_instrument, timeframe_seconds)
    registry = evaluation._registry_authority(registry, graph)
    policy = monitoring_policy_payload(evaluation_policy)
    data = compile_data_requirement_plan(graph, registry=registry, input_bindings=prefix.projection.input_bindings)
    resource = compile_resource_plan(graph, data, registry,
        cache_bytes_upper_bound=policy['cache_bytes_upper_bound'], artifact_bytes_upper_bound=0,
        queue_concurrency_upper_bound=policy['queue_concurrency_upper_bound'])
    units = {node.node_id: _registered_unit_contract(node, graph, registry, data, canonical_instrument)
        for node in graph.nodes}
    event_unit = content_address({'schema': 'monitoring-completed-bar-clock-units/1',
        'timezone': 'UTC', 'duration_unit': 'SECOND', 'precision': 'MICROSECOND',
        'timeframe_seconds': timeframe_seconds, 'completion': 'VERIFIED_DATASET_COMPLETION',
        'data_requirement_plan_address': data.plan_address})
    schedule = compile_completed_bar_evaluation_schedule(owner_id=policy['owner_id'],
        assignment_id=policy['assignment_id'], resolved_graph=graph, data_requirement_plan=data,
        resource_plan=resource, registry=registry, unit_contract_addresses=units,
        event_unit_address=event_unit, mode='research',
        trigger_rates={'completed_bar': {'events': policy['event_rate_events'],
            'per_seconds': policy['event_rate_per_seconds']}},
        resource_ceiling=monitoring_resource_ceiling(evaluation_policy),
        freshness_ceiling_seconds=policy['maximum_age_seconds'])
    event = admit_evaluation_event(schedule, trigger='completed_bar', observation_address=prefix.observation_address,
        event_at=prefix.event_at, completed_at=prefix.completed_at, available_at=prefix.available_at,
        recorded_at=prefix.recorded_at, cutoff_at=prefix.cutoff_at, unit_contract_address=event_unit)
    return schedule, event
