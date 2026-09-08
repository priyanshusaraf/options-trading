"""Seed a flat monitoring state from authored protection, without inventing prices."""
from __future__ import annotations

from app.ir.first_party import monitoring_intent_v2 as intent
from app.ir.hashing import content_address
from app.ir.resolve import ResolvedV2Graph
from app.market_truth.identity import CanonicalPhysicalInstrument
from app.monitoring import evaluation
from app.monitoring.contracts import (
    EntryReference, EntryReferenceKind, FactValidity, ProtectionBasis,
    ProtectionEvidence, ProtectionKind, ProtectionUnits, StrategyState,
)
from app.monitoring.state_contracts import MonitoringAssignment, MonitoringStateSnapshot


def _require(condition, detail):
    if not condition:
        raise evaluation.MonitoringEvaluationRefusal(evaluation.MonitoringEvaluationCode.STATE_INVALID, detail)


def _context(assignment, graph, registry, schedule, event, policy):
    _require(type(assignment) is MonitoringAssignment and type(graph) is ResolvedV2Graph,
        'initial state requires a closed assignment and resolved graph')
    _require(assignment.lifecycle_state == 'ACTIVE' and assignment.withdrawn_at is None
        and assignment.current_state_snapshot_address is None, 'initial state requires an active uninitialized assignment')
    schedule, event = evaluation._issued_event_schedule(schedule, event)
    evaluation._assignment_schedule_binding(assignment, schedule, event, policy)
    evaluation._graph_schedule_binding(graph, schedule, registry)
    evaluation._registry_authority(registry, graph)
    return schedule, event


def _authored_protections(graph):
    _require(len(graph.outputs) <= evaluation.MAX_GRAPH_OUTPUTS, 'monitoring output boundary is unbounded')
    nodes = {node.node_id: node for node in graph.nodes}
    names = {intent.component_key(name): name for name in intent.PROTECTION_SPECS}
    protections, targets = {}, 0
    for output in graph.outputs.values():
        _require(output.source.get('scope') == 'node', 'monitoring outputs require authored intent nodes')
        node = nodes[output.source['node_id']]
        if node.component in names:
            name = names[node.component]
            kind = intent.PROTECTION_SPECS[name]['kind']
            _require(kind not in protections, 'initial protection has multiple authored outputs of one kind')
            protections[kind] = (node, name)
        else:
            _require(node.component in {intent.component_key(name) for name in intent.TARGET_SPECS},
                'monitoring outputs must explicitly author target and protection intent')
            targets += 1
    _require(targets > 0 and set(protections) == {'STOP_LOSS', 'TAKE_PROFIT'},
        'initial monitoring state requires authored target, stop and target protection')
    return protections


def _missing_protection(node, name, assignment, graph, event, instrument_address):
    parameters = intent.parameters_for(name, node.parameters)
    authored = evaluation._expected_authored(name, parameters)
    spec = intent.PROTECTION_SPECS[name]
    resolution = content_address({'schema':'monitoring-unresolved-initial-protection/1',
        'owner_id':assignment.owner_id, 'assignment_id':assignment.spec.assignment_id,
        'graph_address':graph.resolved_graph_address, 'node_id':node.node_id,
        'instrument_address':instrument_address, 'evaluation_event_address':event.event_address,
        'state_reset_policy_address':assignment.spec.state_reset_policy_address,
        'authored_parameters_address':authored['parameters_address'], 'state':'FLAT', 'reason':'NO_ENTRY_REFERENCE'})
    return ProtectionEvidence(kind=ProtectionKind(spec['kind']), basis=ProtectionBasis(spec['basis']),
        authored_component_id=authored['component_id'], authored_component_version=authored['semantic_version'],
        authored_component_address=authored['component_address'], authored_contract_address=authored['node_contract_address'],
        authored_parameters_address=authored['parameters_address'], authored_value=parameters[spec['parameter']],
        units=ProtectionUnits(spec['units']), resolved_value=None, resolution_address=resolution, validity=FactValidity.MISSING)


def compile_initial_monitoring_state(*, assignment, graph, registry, schedule, evaluation_event,
        instrument, source_truth_address, evaluation_policy=None):
    """Compile sequence zero; callers supply the verified instrument and source truth."""
    schedule, event = _context(assignment, graph, registry, schedule, evaluation_event, evaluation_policy)
    _require(type(instrument) is CanonicalPhysicalInstrument, 'initial state requires the verified canonical instrument')
    protections = _authored_protections(graph)
    effective = evaluation._monitoring_instant(schedule, event)
    entry = EntryReference(EntryReferenceKind.COMPLETED_EVENT_CLOSE, instrument.address, None,
        instrument.currency, effective, source_truth_address, FactValidity.MISSING)
    evidence = {kind:_missing_protection(node, name, assignment, graph, event, instrument.address)
        for kind,(node,name) in protections.items()}
    return MonitoringStateSnapshot(assignment.owner_id, assignment.spec.assignment_id, instrument.address,
        0, None, StrategyState.FLAT, entry, evidence['STOP_LOSS'], evidence['TAKE_PROFIT'], event.event_address, effective)
