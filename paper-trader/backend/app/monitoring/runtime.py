"""Transaction-bound persistence for already-compiled monitoring transitions."""
from __future__ import annotations

from dataclasses import dataclass
import datetime as dt

from app.db.concurrency import caller_owned_savepoint
from app.monitoring.contracts import (
    AlertDerived,
    MonitoringSignalEvent,
    NoAlert,
    SignalAlert,
    derive_signal_alert,
)
from app.monitoring.evaluation import MonitoringEvaluationTransition
from app.monitoring.repository import MonitoringRepository
from app.monitoring.state_contracts import MonitoringStateSnapshot


class MonitoringRuntimeRefusal(ValueError):
    """The compiled transition cannot cross the persistence boundary."""


@dataclass(frozen=True, slots=True)
class PersistedMonitoringTransition:
    snapshot: MonitoringStateSnapshot
    event: MonitoringSignalEvent
    alert: SignalAlert | None


def _utc(value: object) -> dt.datetime:
    if type(value) is not dt.datetime or value.tzinfo is not dt.timezone.utc:
        raise MonitoringRuntimeRefusal("created_at must use exact UTC")
    return value


def persist_monitoring_transition(
    repository: MonitoringRepository,
    transition: MonitoringEvaluationTransition,
    *,
    created_at: dt.datetime,
) -> PersistedMonitoringTransition:
    """Persist one exact transition without committing the caller transaction."""
    if type(repository) is not MonitoringRepository:
        raise MonitoringRuntimeRefusal("exact owner-scoped monitoring repository required")
    if type(transition) is not MonitoringEvaluationTransition:
        raise MonitoringRuntimeRefusal("exact compiled monitoring transition required")
    created = _utc(created_at)
    snapshot = transition.next_snapshot
    event = transition.signal_event
    alert_result = transition.alert_result
    if (
        snapshot.owner_id != repository.owner_id
        or event.owner_id != repository.owner_id
        or snapshot.assignment_id != event.assignment_id
        or event.state_after_address != snapshot.address
        or snapshot.evaluation_event_address != event.evaluation_event_address
    ):
        raise MonitoringRuntimeRefusal("transition owner, assignment or state identity differs")
    canonical_alert_result = derive_signal_alert(event)
    if alert_result != canonical_alert_result:
        raise MonitoringRuntimeRefusal("compiled alert derivation is not canonical")
    if type(alert_result) is AlertDerived:
        if alert_result.alert.monitoring_event_address != event.address:
            raise MonitoringRuntimeRefusal("compiled alert differs from monitoring event")
    elif type(alert_result) is NoAlert:
        if alert_result.monitoring_event_address != event.address:
            raise MonitoringRuntimeRefusal("no-alert receipt differs from monitoring event")
    else:
        raise MonitoringRuntimeRefusal("closed alert derivation required")

    with caller_owned_savepoint(
        repository.session,
        scope="persist-compiled-monitoring-transition",
    ):
        persisted_snapshot = repository.append_state_snapshot(
            snapshot, created_at=created,
        )
        persisted_event = repository.append_event(event, created_at=created)
        persisted_alert = (
            repository.append_alert(alert_result.alert, created_at=created)
            if type(alert_result) is AlertDerived
            else None
        )
    if (
        persisted_snapshot != snapshot
        or persisted_event != event
        or (
            type(alert_result) is AlertDerived
            and persisted_alert != alert_result.alert
        )
    ):
        raise MonitoringRuntimeRefusal("repository returned different monitoring facts")
    return PersistedMonitoringTransition(
        snapshot=persisted_snapshot,
        event=persisted_event,
        alert=persisted_alert,
    )


__all__ = [
    "MonitoringRuntimeRefusal",
    "PersistedMonitoringTransition",
    "persist_monitoring_transition",
]
