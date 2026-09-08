"""Atomically retain every newly consumed research step and its terminal alert."""
from __future__ import annotations

from app.db.concurrency import caller_owned_savepoint
from app.monitoring.contracts import AlertDerived
from app.monitoring.evaluation import MonitoringEvaluationTransition
from app.monitoring.repository import MonitoringRepository
from app.monitoring.research_event_contracts import ResearchMonitoringSignalEvent, derive_research_signal_alert
from app.monitoring.research_state_contracts import ResearchMonitoringStateSnapshot
from app.monitoring.runtime import MonitoringRuntimeRefusal, PersistedMonitoringTransition, _utc


def _research_transition(repository, transition, created_at):
    if type(transition) is not MonitoringEvaluationTransition:
        raise MonitoringRuntimeRefusal("closed research monitoring transition required")
    snapshot, event = transition.next_snapshot, transition.signal_event
    if type(snapshot) is not ResearchMonitoringStateSnapshot or type(event) is not ResearchMonitoringSignalEvent:
        raise MonitoringRuntimeRefusal("research transition variants required")
    snapshot.__post_init__()
    event.__post_init__()
    expected = (repository.owner_id, snapshot.owner_id, snapshot.assignment_id, snapshot.address,
        snapshot.evaluation_event_address)
    actual = (event.owner_id, event.owner_id, event.assignment_id, event.state_after_address,
        event.evaluation_event_address)
    if actual != expected or created_at < event.knowledge_cutoff_at:
        raise MonitoringRuntimeRefusal("research transition owner, state or publication clock differs")
    if transition.alert_result != derive_research_signal_alert(event):
        raise MonitoringRuntimeRefusal("research alert derivation differs")
    if type(transition.alert_result) is AlertDerived and created_at > event.valid_until:
        raise MonitoringRuntimeRefusal("research decision expired before publication")


def _research_sequence(transitions):
    terminal = transitions[-1].signal_event
    if terminal.replay_scope != "CURRENT":
        raise MonitoringRuntimeRefusal("research prefix must include its terminal step")
    previous = None
    fields = ("owner_id", "assignment_id", "canonical_instrument_address", "evaluation_event_address",
        "knowledge_cutoff_at", "prefix_completed_at", "prefix_available_at", "prefix_recorded_at",
        "dataset_address", "provider_evidence_address", "consumer_address")
    expected = tuple(getattr(terminal, name) for name in fields)
    for transition in transitions:
        event = transition.signal_event
        actual = tuple(getattr(event, name) for name in fields)
        if actual != expected:
            raise MonitoringRuntimeRefusal("research steps must belong to the same prefix evaluation")
        if previous is not None and event.state_before_address != previous.next_snapshot.address:
            raise MonitoringRuntimeRefusal("research steps are reordered or disconnected")
        previous = transition


def _persist_research_step(repository, transition, created_at):
    snapshot = repository.append_state_snapshot(transition.next_snapshot, created_at=created_at)
    event = repository.append_event(transition.signal_event, created_at=created_at)
    alert = None
    if type(transition.alert_result) is AlertDerived:
        alert = repository.append_alert(transition.alert_result.alert, created_at=created_at)
        if alert != transition.alert_result.alert:
            raise MonitoringRuntimeRefusal("repository returned a different research alert")
    if (snapshot, event) != (transition.next_snapshot, transition.signal_event):
        raise MonitoringRuntimeRefusal("repository returned different research facts")
    return PersistedMonitoringTransition(snapshot, event, alert)


def persist_research_transitions(repository, transitions, *, created_at):
    """Keep the caller's transaction; failure of any step rolls back the whole tail."""
    if type(repository) is not MonitoringRepository:
        raise MonitoringRuntimeRefusal("exact owner-scoped monitoring repository required")
    if type(transitions) is not tuple or len(transitions) > 2000:
        raise MonitoringRuntimeRefusal("bounded tuple of research transitions required")
    created = _utc(created_at)
    for transition in transitions:
        _research_transition(repository, transition, created)
    if not transitions:
        return ()
    _research_sequence(transitions)
    with caller_owned_savepoint(repository.session, scope="persist-research-monitoring-prefix"):
        return tuple(_persist_research_step(repository, transition, created) for transition in transitions)
