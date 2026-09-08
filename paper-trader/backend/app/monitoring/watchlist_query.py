"""Read current watchlist rows from exact settings and attributable monitoring facts."""
from __future__ import annotations

from sqlalchemy import select

from app.db.models import MonitoringSignalEventRow, Project
from app.monitoring.contracts import SignalAction
from app.monitoring.repository import MonitoringRepository, _event_from_row
from app.monitoring.state_contracts import _time
from app.monitoring.watchlist_config import TIMEFRAMES, WatchlistValues
from app.monitoring.watchlist_store import (
    WatchlistMonitoringUnavailable, _assignment_for_configuration, read_watchlist_configurations,
)


def _empty_result(reason=None):
    return dict(kind="NOT_EVALUATED", label="Not evaluated", evaluated_at=None,
        assignment_id=None, graph_version_address=None, reason=reason, warmup=None)


def _latest_event(session, repository, assignment, configuration):
    row = session.scalar(select(MonitoringSignalEventRow).where(
        MonitoringSignalEventRow.owner_id == repository.owner_id,
        MonitoringSignalEventRow.assignment_id == assignment.spec.assignment_id,
        MonitoringSignalEventRow.state_after_address == assignment.current_state_snapshot_address)
        .order_by(MonitoringSignalEventRow.event_at.desc()).limit(1))
    if row is None:
        return None
    event = _event_from_row(row)
    if (event.strategy_id, event.graph_version_address, event.canonical_instrument_address) != (
            assignment.spec.strategy_id, assignment.spec.graph_version_address,
            configuration.canonical_instrument_address):
        raise WatchlistMonitoringUnavailable("The latest result does not match this row's saved strategy and instrument.")
    state = repository.get_latest_state(assignment.spec.assignment_id, event.canonical_instrument_address)
    if state.address != event.state_after_address:
        raise WatchlistMonitoringUnavailable("The latest result and monitoring state do not agree.")
    return event


def _event_result(event, now):
    stale = now > event.valid_until
    kind = "STALE" if stale else "HOLD" if event.action is SignalAction.HOLD else "SIGNAL"
    label = "Stale result" if stale else "No signal" if kind == "HOLD" else event.action.value.title()
    return dict(kind=kind, label=label, evaluated_at=_time(event.event_at),
        assignment_id=event.assignment_id, graph_version_address=event.graph_version_address,
        reason="Waiting for a fresh completed bar." if stale else None, warmup=None)


def _monitoring_result(session, configuration, now):
    if configuration is None:
        return "OFF", _empty_result(), None
    if configuration.assignment_id is None:
        pending = configuration.monitoring_intent == "MONITOR"
        reason = "Waiting for data and strategy checks before monitoring can start." if pending else None
        return "STARTING" if pending else "OFF", _empty_result(reason), reason
    repository = MonitoringRepository(session, owner_id=configuration.owner_id)
    assignment = _assignment_for_configuration(repository, configuration)
    event = _latest_event(session, repository, assignment, configuration)
    result = _event_result(event, now) if event is not None else _empty_result()
    state = {"ACTIVE": "ON", "PAUSED": "PAUSED", "WITHDRAWN": "BLOCKED"}[assignment.lifecycle_state]
    reason = "This monitoring assignment was withdrawn. Save a new configuration to restart." if state == "BLOCKED" else None
    return state, result, reason


def watchlist_row(session, key, configuration, *, editable, now):
    values = configuration.row_values() if configuration is not None else WatchlistValues()
    state, result, reason = _monitoring_result(session, configuration, now)
    if values.graph is None:
        reason = "Choose a saved strategy and timeframe."
    if not editable:
        reason = "This watchlist is archived and is read only."
    return dict(member_key=key, configuration_revision=configuration.revision if configuration else 0,
        pinned=values.pinned, graph=values.graph.model_dump() if values.graph else None,
        timeframe=values.timeframe, supported_timeframes=[dict(value=key, label=value[1])
            for key, value in TIMEFRAMES.items()], assignment_id=values.assignment_id,
        monitoring=state, can_configure=editable, can_pin=editable,
        can_set_monitoring=editable and values.graph is not None and state != "BLOCKED",
        reason=reason, result=result)


def read_watchlist_rows(session, *, owner_id, context, now):
    scope, members, configurations = read_watchlist_configurations(session, owner_id=owner_id, context=context)
    project_status = session.scalar(select(Project.status).where(
        Project.owner_id == owner_id, Project.project_id == context.project_id))
    editable = scope["status"] == "active" and project_status == "active"
    return {"schema": "watchlist-monitoring-rows/1", "context": context.model_dump(),
        "rows": [watchlist_row(session, key, configurations.get(key), editable=editable, now=now)
            for key in members]}
