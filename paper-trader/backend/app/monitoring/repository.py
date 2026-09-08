"""Owner-scoped persistence for V0 monitoring evidence.

This module has no API, worker, provider, broker, execution or money import. The
caller supplies one server-derived owner scope and owns the transaction. Durable
facts are append-only; the two latest-state tables are rebuildable projections.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import datetime as dt
import json
import re
from typing import Any, Generic, Iterable, TypeVar

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.concurrency import caller_owned_savepoint
from app.db.schema_semantics import (
    check_sql_matches as _shared_check_sql_matches,
    conservative_check_sql as _shared_conservative_check_sql,
    normalise_schema_sql as _shared_normalise_schema_sql,
)
from app.db.models import (
    MonitoringAlertAttentionEventRow,
    MonitoringAlertAttentionStateRow,
    MonitoringAlertDeliveryAttemptRow,
    MonitoringAssignmentRow,
    MonitoringLatestStateRow,
    MonitoringSignalAlertRow,
    MonitoringSignalEventRow,
    MonitoringSignalReviewRow,
    MonitoringStateSnapshotRow,
    Project,
)
from app.ir.hashing import canonical_json, content_address
from app.monitoring.contracts import (
    AlertAttentionEvent,
    AlertAttentionProjection,
    AlertDeliveryAttempt,
    EntryReference,
    MonitoringContractError,
    MonitoringSignalEvent,
    ProtectionEvidence,
    SignalAlert,
    StrategyState,
    derive_signal_alert,
    rebuild_attention_projection,
    validate_delivery_attempts,
)
from app.monitoring.state_contracts import (
    MonitoringAssignment,
    MonitoringAssignmentSpec,
    MonitoringStateSnapshot,
)
from app.monitoring.research_state_contracts import ResearchMonitoringStateSnapshot
from app.monitoring.research_event_contracts import (
    ResearchMonitoringSignalEvent, ResearchSignalAlert, derive_research_signal_alert,
)


DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 100
MAX_CANONICAL_BYTES = 16 * 1024
MAX_REVIEW_NOTE_BYTES = 4096

MONITORING_TABLES = (
    "monitoring_assignments",
    "monitoring_state_snapshots",
    "monitoring_signal_events",
    "monitoring_signal_alerts",
    "monitoring_alert_delivery_attempts",
    "monitoring_alert_attention_events",
    "monitoring_latest_state",
    "monitoring_alert_attention_state",
    "monitoring_signal_reviews",
)
IMMUTABLE_TABLES = frozenset(MONITORING_TABLES[1:6] + (MONITORING_TABLES[8],))
FORBIDDEN_AUTHORITY_KEYS = frozenset({
    "deployment_id", "broker_account_id", "execution_connection_id",
    "execution_provider", "execution_lease_id", "execution_intent_id",
    "capital", "allocation", "reservation", "quantity", "order_type",
    "order_id", "fill_id", "position_id", "arm_mode", "live_mode",
    "pnl", "balance",
})

_ADDRESS = re.compile(r"^sha256:[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_CODE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


class MonitoringPersistenceError(RuntimeError):
    pass


class MonitoringNotFound(MonitoringPersistenceError):
    """One absence shape for a missing or foreign-scoped identifier."""

    def __init__(self) -> None:
        super().__init__("monitoring object not found")


class MonitoringConflict(MonitoringPersistenceError):
    pass


class MonitoringCorrupt(MonitoringPersistenceError):
    pass


class MonitoringRefused(MonitoringPersistenceError):
    pass


@dataclass(frozen=True, slots=True)
class SignalReview:
    owner_id: str
    assignment_id: str
    monitoring_event_address: str
    reviewer_user_id: str
    disposition: str
    reason_code: str
    note: str
    created_at: dt.datetime

    schema = "monitoring-signal-review/1"

    def __post_init__(self) -> None:
        for value, label in (
            (self.owner_id, "owner"), (self.assignment_id, "assignment"),
            (self.reviewer_user_id, "reviewer"),
        ):
            _identifier(value, label)
        _address(self.monitoring_event_address, "monitoring event")
        if self.disposition not in {"CONFIRMED", "REJECTED"}:
            raise MonitoringRefused("closed review disposition required")
        if not isinstance(self.reason_code, str) or not _CODE.fullmatch(self.reason_code):
            raise MonitoringRefused("closed review reason required")
        if (not isinstance(self.note, str) or self.note != self.note.strip()
                or any(ord(char) < 32 or ord(char) == 127 for char in self.note)
                or len(self.note.encode("utf-8")) > MAX_REVIEW_NOTE_BYTES):
            raise MonitoringRefused("review note must be trimmed, control-free and bounded")
        _utc(self.created_at, "review created time")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "schema": self.schema, "owner_id": self.owner_id,
            "assignment_id": self.assignment_id,
            "monitoring_event_address": self.monitoring_event_address,
            "reviewer_user_id": self.reviewer_user_id,
            "disposition": self.disposition, "reason_code": self.reason_code,
            "note": self.note, "created_at": _time(self.created_at),
        }

    @property
    def address(self) -> str:
        return content_address(self.canonical_payload())

    def to_dict(self) -> dict[str, Any]:
        return {**self.canonical_payload(), "address": self.address}

    @classmethod
    def from_dict(cls, value: Any) -> "SignalReview":
        expected = {
            "schema", "owner_id", "assignment_id", "monitoring_event_address",
            "reviewer_user_id", "disposition", "reason_code", "note", "created_at",
            "address",
        }
        payload = _closed_payload(value, cls.schema, expected)
        try:
            result = cls(
                owner_id=payload["owner_id"], assignment_id=payload["assignment_id"],
                monitoring_event_address=payload["monitoring_event_address"],
                reviewer_user_id=payload["reviewer_user_id"],
                disposition=payload["disposition"], reason_code=payload["reason_code"],
                note=payload["note"], created_at=_parse_time(payload["created_at"]),
            )
        except (KeyError, TypeError, ValueError, MonitoringPersistenceError) as exc:
            raise MonitoringCorrupt("monitoring signal review is invalid") from exc
        if value["address"] != result.address:
            raise MonitoringCorrupt("monitoring signal review address mismatch")
        return result


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Page(Generic[T]):
    items: tuple[T, ...]
    next_cursor: Any | None


@dataclass(frozen=True, slots=True)
class TimeAddressCursor:
    occurred_at: dt.datetime
    address: str

    def __post_init__(self) -> None:
        _utc(self.occurred_at, "cursor time")
        _address(self.address, "cursor address")


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise MonitoringRefused(f"{label} identifier required")
    return value


def _address(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _ADDRESS.fullmatch(value):
        raise MonitoringRefused(f"{label} content address required")
    return value


def _utc(value: Any, label: str) -> dt.datetime:
    if not isinstance(value, dt.datetime) or value.tzinfo is not dt.timezone.utc:
        raise MonitoringRefused(f"{label} must be UTC")
    return value


def _time(value: dt.datetime) -> str:
    return _utc(value, "time").strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _parse_time(value: Any) -> dt.datetime:
    if not isinstance(value, str):
        raise MonitoringCorrupt("canonical UTC timestamp required")
    try:
        parsed = dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
            tzinfo=dt.timezone.utc)
    except ValueError as exc:
        raise MonitoringCorrupt("canonical UTC timestamp required") from exc
    if _time(parsed) != value:
        raise MonitoringCorrupt("canonical UTC timestamp required")
    return parsed


def _db_time(value: dt.datetime) -> dt.datetime:
    return _utc(value, "database time").replace(tzinfo=None)


def _domain_time(value: dt.datetime | None) -> dt.datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    if value.tzinfo is not dt.timezone.utc:
        raise MonitoringCorrupt("stored timestamp is not UTC")
    return value


def _reject_forbidden_keys(value: Any) -> None:
    if isinstance(value, dict):
        forbidden = FORBIDDEN_AUTHORITY_KEYS & {str(key).lower() for key in value}
        if forbidden:
            raise MonitoringRefused(
                f"monitoring document contains forbidden authority keys: {sorted(forbidden)}")
        for item in value.values():
            _reject_forbidden_keys(item)
    elif isinstance(value, list):
        for item in value:
            _reject_forbidden_keys(item)


def _closed_payload(value: Any, schema: str, expected: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected or value.get("schema") != schema:
        raise MonitoringCorrupt("closed monitoring document schema required")
    _reject_forbidden_keys(value)
    return value


def _canonical_document(value: dict[str, Any]) -> str:
    _reject_forbidden_keys(value)
    encoded = canonical_json(value)
    if len(encoded.encode("utf-8")) > MAX_CANONICAL_BYTES:
        raise MonitoringRefused("monitoring canonical document exceeds 16 KiB")
    return encoded


def _parse_document(raw: str) -> dict[str, Any]:
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > MAX_CANONICAL_BYTES:
        raise MonitoringCorrupt("monitoring canonical document is invalid or oversized")
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError) as exc:
        raise MonitoringCorrupt("monitoring canonical JSON is invalid") from exc
    if canonical_json(value) != raw:
        raise MonitoringCorrupt("monitoring canonical JSON is not canonical")
    try:
        _reject_forbidden_keys(value)
    except MonitoringRefused as exc:
        raise MonitoringCorrupt(str(exc)) from exc
    return value


def _limit(value: int) -> int:
    if type(value) is not int or value < 1 or value > MAX_PAGE_LIMIT:
        raise MonitoringRefused("page limit must be between 1 and 100")
    return value


def _assignment_from_row(row: MonitoringAssignmentRow) -> MonitoringAssignment:
    spec = MonitoringAssignmentSpec(**{
        field: getattr(row, field)
        for field in MonitoringAssignmentSpec.__dataclass_fields__
    })
    current = row.current_state_snapshot_address
    if current is not None:
        _address(current, "current state snapshot")
    return MonitoringAssignment(
        owner_id=row.owner_id, spec=spec,
        optimistic_revision=row.optimistic_revision,
        lifecycle_state=row.lifecycle_state,
        current_state_snapshot_address=current,
        created_at=_domain_time(row.created_at), updated_at=_domain_time(row.updated_at),
        withdrawn_at=_domain_time(row.withdrawn_at),
    )


def _snapshot_from_row(row: MonitoringStateSnapshotRow) -> MonitoringStateSnapshot:
    value = _parse_document(row.canonical_json)
    try:
        snapshot_type = (ResearchMonitoringStateSnapshot
            if value.get("schema") == ResearchMonitoringStateSnapshot.schema else MonitoringStateSnapshot)
        fact = snapshot_type.from_dict(value)
    except MonitoringContractError as exc:
        raise MonitoringCorrupt("monitoring state snapshot is invalid") from exc
    copied = (
        row.owner_id, row.assignment_id, row.canonical_instrument_address,
        row.snapshot_address, row.snapshot_sequence, row.predecessor_snapshot_address,
        row.strategy_state, row.evaluation_event_address, _domain_time(row.effective_at),
    )
    expected = (
        fact.owner_id, fact.assignment_id, fact.canonical_instrument_address,
        fact.address, fact.snapshot_sequence, fact.predecessor_snapshot_address,
        fact.strategy_state.value, fact.evaluation_event_address, fact.effective_at,
    )
    if copied != expected:
        raise MonitoringCorrupt("monitoring state snapshot copied columns mismatch")
    if canonical_json(fact.entry_reference.to_dict()) != row.entry_reference_json:
        raise MonitoringCorrupt("monitoring state entry reference mismatch")
    if canonical_json(fact.stop_loss.to_dict()) != row.stop_loss_json:
        raise MonitoringCorrupt("monitoring state stop loss mismatch")
    if canonical_json(fact.take_profit.to_dict()) != row.take_profit_json:
        raise MonitoringCorrupt("monitoring state take profit mismatch")
    return fact


def _require_research_snapshot_predecessor(session, snapshot):
    if type(snapshot) is not ResearchMonitoringStateSnapshot or snapshot.snapshot_sequence == 0:
        return
    row = session.get(MonitoringStateSnapshotRow, (snapshot.owner_id, snapshot.assignment_id,
        snapshot.canonical_instrument_address, snapshot.predecessor_snapshot_address))
    if row is None:
        raise MonitoringNotFound()
    previous = _snapshot_from_row(row)
    if type(previous) is not ResearchMonitoringStateSnapshot:
        raise MonitoringRefused("research state requires a research predecessor")
    state = snapshot.checkpoint.state
    if (state.consumer_address, state.predecessor_snapshot_address, snapshot.snapshot_sequence) != (
            previous.checkpoint.state.consumer_address, previous.checkpoint.state.address, previous.snapshot_sequence + 1):
        raise MonitoringRefused("research state inner predecessor differs")
    if not _research_history_advances(previous, snapshot):
        raise MonitoringRefused("research state history must advance by one observed bar")


def _research_history_advances(before, after):
    if before.snapshot_sequence == 0:
        return True
    prior, current = before.checkpoint.state, after.checkpoint.state
    return (after.checkpoint.history_bars == before.checkpoint.history_bars + 1
        and current.last_bar_open_at >= prior.last_bar_completed_at
        and current.last_bar_identity != prior.last_bar_identity)


def _require_owned_snapshot(owner_id, snapshot):
    if type(snapshot) not in (MonitoringStateSnapshot, ResearchMonitoringStateSnapshot) or snapshot.owner_id != owner_id:
        raise MonitoringRefused("owner-scoped monitoring snapshot required")
    snapshot.__post_init__()


def _event_from_row(row: MonitoringSignalEventRow) -> MonitoringSignalEvent:
    value = _parse_document(row.canonical_json)
    try:
        event_type = (ResearchMonitoringSignalEvent
            if value.get("schema") == ResearchMonitoringSignalEvent.schema else MonitoringSignalEvent)
        fact = event_type.from_dict(value)
    except MonitoringContractError as exc:
        raise MonitoringCorrupt("monitoring signal event is invalid") from exc
    copied = (
        row.owner_id, row.assignment_id, row.content_address,
        row.canonical_instrument_address, row.evaluation_event_address,
        row.graph_version_address, row.implementation_closure_address,
        row.state_before_address, row.state_after_address,
        _domain_time(row.event_at), _domain_time(row.valid_until),
    )
    expected = (
        fact.owner_id, fact.assignment_id, fact.address,
        fact.canonical_instrument_address, fact.evaluation_event_address,
        fact.graph_version_address, fact.implementation_closure_address,
        fact.state_before_address, fact.state_after_address,
        fact.event_at, fact.valid_until,
    )
    if copied != expected or row.dedupe_address != event_dedupe_address(fact):
        raise MonitoringCorrupt("monitoring signal event copied columns mismatch")
    return fact


def _alert_from_row(row: MonitoringSignalAlertRow) -> SignalAlert:
    value = _parse_document(row.canonical_json)
    try:
        alert_type = ResearchSignalAlert if value.get("schema") == ResearchSignalAlert.schema else SignalAlert
        fact = alert_type.from_dict(value)
    except MonitoringContractError as exc:
        raise MonitoringCorrupt("monitoring signal alert is invalid") from exc
    copied = (
        row.owner_id, row.assignment_id, row.alert_address,
        row.monitoring_event_address, row.canonical_instrument_address,
        _domain_time(row.event_at), _domain_time(row.valid_until),
    )
    expected = (
        fact.owner_id, fact.assignment_id, fact.address,
        fact.monitoring_event_address, fact.canonical_instrument_address,
        fact.event_at, fact.valid_until,
    )
    if copied != expected:
        raise MonitoringCorrupt("monitoring signal alert copied columns mismatch")
    return fact


def derive_monitoring_alert(event):
    if type(event) is ResearchMonitoringSignalEvent:
        return derive_research_signal_alert(event)
    return derive_signal_alert(event)


def _event_snapshot_types(before, after, event, error):
    expected = ResearchMonitoringStateSnapshot if type(event) is ResearchMonitoringSignalEvent else MonitoringStateSnapshot
    if (type(before), type(after)) != (expected, expected):
        raise error("event and monitoring snapshot variants differ")


def _research_event_snapshot_binding(before, after, event, error):
    _event_snapshot_types(before, after, event, error)
    if type(event) is not ResearchMonitoringSignalEvent:
        return
    state = after.checkpoint.state
    pending = state.pending
    expected = (before.checkpoint.state.address, before.checkpoint.state.consumer_address,
        after.effective_at, state.last_bar_identity, state.consumer_address,
        "NONE" if pending is None else pending.kind,
        StrategyState.FLAT if state.position is None else StrategyState(state.position.direction),
        after.entry_reference, after.stop_loss, after.take_profit)
    actual = (state.predecessor_snapshot_address, state.consumer_address,
        event.event_at, event.completed_bar_identity, event.consumer_address,
        event.decision_kind, event.simulated_position_state,
        event.entry_reference, event.stop_loss, event.take_profit)
    if actual != expected:
        raise error("research event differs from its replay checkpoint")
    if not _research_history_advances(before, after):
        raise error("research event history must advance by one observed bar")


def _event_snapshot_binding(before, after, event, error):
    expected = (event.previous_state, event.target_state, before.address,
        before.snapshot_sequence + 1, event.evaluation_event_address)
    actual = (before.strategy_state, after.strategy_state, after.predecessor_snapshot_address,
        after.snapshot_sequence, after.evaluation_event_address)
    if actual != expected:
        raise error("event state transition does not match snapshots")
    _research_event_snapshot_binding(before, after, event, error)


def _delivery_from_row(row: MonitoringAlertDeliveryAttemptRow) -> AlertDeliveryAttempt:
    value = _parse_document(row.canonical_json)
    try:
        fact = AlertDeliveryAttempt.from_dict(value)
    except MonitoringContractError as exc:
        raise MonitoringCorrupt("monitoring delivery attempt is invalid") from exc
    copied = (
        row.owner_id, row.assignment_id, row.attempt_address, row.attempt_id,
        row.alert_address, row.sequence, row.channel, row.outcome,
        _domain_time(row.occurred_at), row.failure_code,
    )
    expected = (
        fact.owner_id, fact.assignment_id, fact.address, fact.attempt_id,
        fact.alert_address, fact.sequence, fact.channel.value, fact.outcome.value,
        fact.occurred_at, fact.failure_code,
    )
    if copied != expected:
        raise MonitoringCorrupt("monitoring delivery copied columns mismatch")
    return fact


def _attention_from_row(row: MonitoringAlertAttentionEventRow) -> AlertAttentionEvent:
    value = _parse_document(row.canonical_json)
    try:
        fact = AlertAttentionEvent.from_dict(value)
    except MonitoringContractError as exc:
        raise MonitoringCorrupt("monitoring attention event is invalid") from exc
    copied = (
        row.owner_id, row.assignment_id, row.attention_event_address,
        row.request_id, row.alert_address, row.sequence, row.action,
        _domain_time(row.occurred_at),
    )
    expected = (
        fact.owner_id, fact.assignment_id, fact.address, fact.request_id,
        fact.alert_address, fact.sequence, fact.action.value, fact.occurred_at,
    )
    if copied != expected:
        raise MonitoringCorrupt("monitoring attention copied columns mismatch")
    return fact


def _review_from_row(row: MonitoringSignalReviewRow) -> SignalReview:
    fact = SignalReview.from_dict(_parse_document(row.canonical_json))
    copied = (
        row.owner_id, row.assignment_id, row.review_address,
        row.monitoring_event_address, row.reviewer_user_id, row.disposition,
        row.reason_code, row.note, _domain_time(row.created_at),
    )
    expected = (
        fact.owner_id, fact.assignment_id, fact.address,
        fact.monitoring_event_address, fact.reviewer_user_id, fact.disposition,
        fact.reason_code, fact.note, fact.created_at,
    )
    if copied != expected:
        raise MonitoringCorrupt("monitoring review copied columns mismatch")
    return fact


def _reconstruct_latest_states(
    session: Session, owner_id: str,
) -> dict[tuple[str, str], tuple[MonitoringStateSnapshot, MonitoringSignalEvent | None, dt.datetime]]:
    snapshots_by_key: dict[tuple[str, str], dict[str, MonitoringStateSnapshot]] = {}
    for row in session.scalars(sa.select(MonitoringStateSnapshotRow).where(
            MonitoringStateSnapshotRow.owner_id == owner_id)):
        fact = _snapshot_from_row(row)
        snapshots_by_key.setdefault(
            (fact.assignment_id, fact.canonical_instrument_address), {})[fact.address] = fact
    events_by_key: dict[tuple[str, str], list[MonitoringSignalEvent]] = {}
    for row in session.scalars(sa.select(MonitoringSignalEventRow).where(
            MonitoringSignalEventRow.owner_id == owner_id)):
        fact = _event_from_row(row)
        events_by_key.setdefault(
            (fact.assignment_id, fact.canonical_instrument_address), []).append(fact)
    if set(events_by_key) - set(snapshots_by_key):
        raise MonitoringCorrupt("monitoring event has no reconstructible snapshot chain")

    return {key: _reconstruct_state_chain(snapshots, events_by_key.get(key, []))
        for key, snapshots in snapshots_by_key.items()}


def _event_successor(snapshots, current, event):
    after = snapshots.get(event.state_after_address)
    if after is None:
        raise MonitoringCorrupt("monitoring event successor snapshot is missing")
    _event_snapshot_binding(current, after, event, MonitoringCorrupt)
    return after


def _reconstruct_state_chain(snapshots, events):
    roots = [snapshot for snapshot in snapshots.values() if snapshot.snapshot_sequence == 0]
    if len(roots) != 1:
        raise MonitoringCorrupt("monitoring snapshot chain requires exactly one root")
    current, current_event = roots[0], None
    updated_at = current.effective_at
    outgoing = {}
    for event in events:
        outgoing.setdefault(event.state_before_address, []).append(event)
    consumed = set()
    while current.address in outgoing:
        candidates = outgoing[current.address]
        if len(candidates) != 1:
            raise MonitoringCorrupt("monitoring event chain branches from one state")
        event = candidates[0]
        current = _event_successor(snapshots, current, event)
        consumed.add(event.address)
        current_event, updated_at = event, event.knowledge_cutoff_at
    if consumed != {event.address for event in events}:
        raise MonitoringCorrupt("monitoring event chain contains an orphan or reorder")
    return current, current_event, updated_at


def _assignment_projection_pointers(
    latest: dict[
        tuple[str, str],
        tuple[MonitoringStateSnapshot, MonitoringSignalEvent | None, dt.datetime],
    ],
) -> dict[str, tuple[str, dt.datetime]]:
    candidates: dict[str, list[tuple[dt.datetime, str, str]]] = {}
    for (assignment_id, instrument), (snapshot, _event, updated_at) in latest.items():
        candidates.setdefault(assignment_id, []).append(
            (updated_at, instrument, snapshot.address))
    return {
        assignment_id: (selected[2], selected[0])
        for assignment_id, values in candidates.items()
        for selected in [max(values)]
    }


def event_dedupe_address(event: MonitoringSignalEvent) -> str:
    if not isinstance(event, MonitoringSignalEvent):
        raise MonitoringRefused("monitoring signal event required")
    return content_address({
        "schema": "monitoring-event-dedupe/1",
        "owner_id": event.owner_id,
        "assignment_id": event.assignment_id,
        "canonical_instrument_address": event.canonical_instrument_address,
        "evaluation_event_address": event.evaluation_event_address,
        "graph_version_address": event.graph_version_address,
        "implementation_closure_address": event.implementation_closure_address,
        "state_before_address": event.state_before_address,
    })


def _normalise_schema_sql(value: Any) -> str | None:
    return _shared_normalise_schema_sql(value)


def _compiled_server_default(column, dialect) -> str | None:
    if column.server_default is None:
        return None
    value = column.server_default.arg
    if hasattr(value, "compile"):
        value = value.compile(
            dialect=dialect, compile_kwargs={"literal_binds": True})
    return _normalise_schema_sql(value)


def _conservative_check_sql(value: Any, **options: Any) -> str:
    return _shared_conservative_check_sql(value, **options)


def _check_sql_matches(
    table: sa.Table, constraint_name: str | None, dialect_name: str,
    expected: Any, actual: Any,
) -> bool:
    return _shared_check_sql_matches(
        table, constraint_name, dialect_name, expected, actual, context="monitoring")

def _foreign_key_options(constraint) -> tuple[Any, ...]:
    return (
        constraint.ondelete, constraint.onupdate,
        bool(constraint.deferrable) if constraint.deferrable is not None else None,
        constraint.initially,
    )


def _expected_relational_manifest(connection: sa.Connection) -> dict[str, Any]:
    metadata = MonitoringAssignmentRow.metadata
    dialect = connection.dialect
    result: dict[str, Any] = {}
    for name in MONITORING_TABLES:
        table = metadata.tables[name]
        result[name] = {
            "columns": [
                (
                    column.name,
                    _normalise_schema_sql(column.type.compile(dialect=dialect)),
                    bool(column.nullable),
                    _compiled_server_default(column, dialect),
                )
                for column in table.columns
            ],
            "primary_key": (
                table.primary_key.name,
                tuple(column.name for column in table.primary_key.columns),
            ),
            "uniques": sorted(
                (constraint.name, tuple(column.name for column in constraint.columns))
                for constraint in table.constraints
                if isinstance(constraint, sa.UniqueConstraint)
            ),
            "foreign_keys": sorted(
                (
                    constraint.name,
                    tuple(element.parent.name for element in constraint.elements),
                    constraint.elements[0].column.table.name,
                    tuple(element.column.name for element in constraint.elements),
                    *_foreign_key_options(constraint),
                )
                for constraint in table.foreign_key_constraints
            ),
            "indexes": sorted(
                (
                    index.name,
                    tuple(column.name for column in index.columns),
                    bool(index.unique),
                )
                for index in table.indexes
            ),
            "checks": sorted(
                (
                    constraint.name,
                    str(constraint.sqltext.compile(
                        dialect=dialect,
                        compile_kwargs={"literal_binds": True},
                    )),
                )
                for constraint in table.constraints
                if isinstance(constraint, sa.CheckConstraint)
            ),
        }
    return result


def _actual_relational_manifest(connection: sa.Connection) -> dict[str, Any]:
    inspector = sa.inspect(connection)
    result: dict[str, Any] = {}
    for name in MONITORING_TABLES:
        uniques = sorted(
            (unique.get("name"), tuple(unique.get("column_names") or ()))
            for unique in inspector.get_unique_constraints(name)
        )
        primary = inspector.get_pk_constraint(name)
        primary_name = primary.get("name")
        if primary_name == f"{name}_pkey":
            primary_name = None
        result[name] = {
            "columns": [
                (
                    column["name"], _normalise_schema_sql(column["type"]),
                    bool(column["nullable"]),
                    _normalise_schema_sql(column.get("default")),
                )
                for column in inspector.get_columns(name)
            ],
            "primary_key": (
                primary_name,
                tuple(primary.get("constrained_columns") or ()),
            ),
            "uniques": uniques,
            "foreign_keys": sorted(
                (
                    foreign_key.get("name"),
                    tuple(foreign_key.get("constrained_columns") or ()),
                    foreign_key.get("referred_table"),
                    tuple(foreign_key.get("referred_columns") or ()),
                    (foreign_key.get("options") or {}).get("ondelete"),
                    (foreign_key.get("options") or {}).get("onupdate"),
                    (foreign_key.get("options") or {}).get("deferrable"),
                    (foreign_key.get("options") or {}).get("initially"),
                )
                for foreign_key in inspector.get_foreign_keys(name)
            ),
            "indexes": sorted(
                (
                    index.get("name"), tuple(index.get("column_names") or ()),
                    bool(index.get("unique")),
                )
                for index in inspector.get_indexes(name)
                if index.get("name") not in {unique[0] for unique in uniques}
            ),
            "checks": sorted(
                (check.get("name"), check.get("sqltext"))
                for check in inspector.get_check_constraints(name)
            ),
        }
    return result


def _assignment_identity_columns() -> tuple[str, ...]:
    mutable = {
        "optimistic_revision", "lifecycle_state", "current_state_snapshot_address",
        "updated_at", "withdrawn_at",
    }
    return tuple(
        column.name for column in MonitoringAssignmentRow.__table__.columns
        if column.name not in mutable
    )


def _expected_sqlite_triggers() -> dict[str, tuple[str, str]]:
    expected: dict[str, tuple[str, str]] = {}
    for table in IMMUTABLE_TABLES:
        for operation in ("UPDATE", "DELETE"):
            name = f"{table}_refuse_{operation.lower()}"
            definition = (
                f"CREATE TRIGGER {name} BEFORE {operation} ON {table} BEGIN "
                f"SELECT RAISE(ABORT, '{table} is immutable'); END"
            )
            expected[name] = (table, _normalise_schema_sql(definition))
    changed = " OR ".join(
        f"NEW.{name} IS NOT OLD.{name}" for name in _assignment_identity_columns())
    identity_name = "monitoring_assignments_refuse_identity_change"
    expected[identity_name] = (
        "monitoring_assignments",
        _normalise_schema_sql(
            f"CREATE TRIGGER {identity_name} BEFORE UPDATE ON monitoring_assignments "
            f"WHEN {changed} BEGIN SELECT RAISE(ABORT, "
            "'monitoring assignment identity is immutable'); END"),
    )
    delete_name = "monitoring_assignments_refuse_delete"
    expected[delete_name] = (
        "monitoring_assignments",
        _normalise_schema_sql(
            f"CREATE TRIGGER {delete_name} BEFORE DELETE ON monitoring_assignments "
            "BEGIN SELECT RAISE(ABORT, 'monitoring assignments are durable'); END"),
    )
    return expected


def _expected_postgresql_triggers() -> dict[str, tuple[Any, ...]]:
    expected: dict[str, tuple[Any, ...]] = {}
    for table in IMMUTABLE_TABLES:
        name = f"{table}_refuse_mutation"
        expected[name] = (
            table, "O", 27, None,
            _normalise_schema_sql(
                f"CREATE TRIGGER {name} BEFORE DELETE OR UPDATE ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION {name}()"),
            name,
            _normalise_schema_sql(
                f"BEGIN RAISE EXCEPTION '{table} is immutable'; END;"),
        )
    identity = "monitoring_assignments_refuse_identity_change"
    function = f"{identity}_fn"
    changed = " OR ".join(
        f"NEW.{name} IS DISTINCT FROM OLD.{name}"
        for name in _assignment_identity_columns())
    expected[identity] = (
        "monitoring_assignments", "O", 19, None,
        _normalise_schema_sql(
            f"CREATE TRIGGER {identity} BEFORE UPDATE ON monitoring_assignments "
            f"FOR EACH ROW EXECUTE FUNCTION {function}()"),
        function,
        _normalise_schema_sql(
            f"BEGIN IF {changed} THEN RAISE EXCEPTION "
            "'monitoring assignment identity is immutable'; "
            "END IF; RETURN NEW; END;"),
    )
    delete = "monitoring_assignments_refuse_delete"
    delete_function = f"{delete}_fn"
    expected[delete] = (
        "monitoring_assignments", "O", 11, None,
        _normalise_schema_sql(
            f"CREATE TRIGGER {delete} BEFORE DELETE ON monitoring_assignments "
            f"FOR EACH ROW EXECUTE FUNCTION {delete_function}()"),
        delete_function,
        _normalise_schema_sql(
            "BEGIN RAISE EXCEPTION 'monitoring assignments are durable'; END;"),
    )
    return expected


def _actual_trigger_manifest(connection: sa.Connection) -> dict[str, tuple[Any, ...]]:
    if connection.dialect.name == "sqlite":
        return {
            row.name: (row.tbl_name, _normalise_schema_sql(row.sql))
            for row in connection.execute(sa.text(
                "SELECT name,tbl_name,sql FROM sqlite_master WHERE type='trigger' "
                "AND tbl_name LIKE 'monitoring_%' ORDER BY name"))
        }
    if connection.dialect.name == "postgresql":
        return {
            row.name: (
                row.table_name, row.tgenabled, int(row.tgtype),
                _normalise_schema_sql(row.when_clause),
                _normalise_schema_sql(row.definition), row.function_name,
                _normalise_schema_sql(row.function_source),
            )
            for row in connection.execute(sa.text("""
                SELECT trigger.tgname AS name, relation.relname AS table_name,
                       trigger.tgenabled, trigger.tgtype,
                       pg_get_expr(trigger.tgqual, trigger.tgrelid) AS when_clause,
                       pg_get_triggerdef(trigger.oid, true) AS definition,
                       procedure.proname AS function_name,
                       procedure.prosrc AS function_source
                FROM pg_trigger AS trigger
                JOIN pg_class AS relation ON relation.oid = trigger.tgrelid
                JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                JOIN pg_proc AS procedure ON procedure.oid = trigger.tgfoid
                WHERE NOT trigger.tgisinternal
                  AND namespace.nspname = current_schema()
                  AND relation.relname LIKE 'monitoring_%'
                ORDER BY trigger.tgname
            """))
        }
    raise MonitoringCorrupt("unsupported monitoring database dialect")


def monitoring_schema_manifest(connection: sa.Connection) -> dict[str, Any]:
    """Return the exact reflected monitoring catalog used by startup/copy/restore."""
    relational = _actual_relational_manifest(connection)
    triggers = _actual_trigger_manifest(connection)
    return {
        "dialect": connection.dialect.name,
        "tables": relational,
        "triggers": triggers,
    }


MONITORING_COMPATIBLE_EXECUTION_HEADS = frozenset({
    "0044", "0045", "0046", "0047", "0048", "0049", "0050", "0051", "0052", "0053", "0054", "0055", "0056",
})


def validate_monitoring_schema(
    connection: sa.Connection, *, require_marker: bool = True,
) -> None:
    inspector = sa.inspect(connection)
    actual_tables = set(inspector.get_table_names())
    missing = set(MONITORING_TABLES) - actual_tables
    unexpected = {
        name for name in actual_tables
        if name.startswith("monitoring_") and name not in MONITORING_TABLES
    }
    if missing or unexpected:
        raise MonitoringCorrupt(
            "monitoring schema table inventory mismatch: "
            f"missing={sorted(missing)} unexpected={sorted(unexpected)}")
    if require_marker:
        if "alembic_version" not in actual_tables:
            raise MonitoringCorrupt("monitoring schema has no migration marker")
        marker = connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalars().all()
        if (len(marker) != 1
                or marker[0] not in MONITORING_COMPATIBLE_EXECUTION_HEADS):
            raise MonitoringCorrupt(
                "monitoring schema marker is not one exact compatible execution head")
    if connection.dialect.name not in {"sqlite", "postgresql"}:
        raise MonitoringCorrupt("unsupported monitoring database dialect")
    actual_relational = _actual_relational_manifest(connection)
    expected_relational = _expected_relational_manifest(connection)
    defects = []
    metadata = MonitoringAssignmentRow.metadata
    for name in MONITORING_TABLES:
        actual_table = actual_relational[name]
        expected_table = expected_relational[name]
        if any(
            actual_table[key] != expected_table[key]
            for key in (
                "columns", "primary_key", "uniques", "foreign_keys", "indexes",
            )
        ):
            defects.append(f"{name}:relational")
            continue
        actual_checks = actual_table["checks"]
        expected_checks = expected_table["checks"]
        if (
            len(actual_checks) != len(expected_checks)
            or any(
                actual_name != expected_name
                or not _check_sql_matches(
                    metadata.tables[name], expected_name,
                    connection.dialect.name, expected_sql, actual_sql)
                for (expected_name, expected_sql), (actual_name, actual_sql)
                in zip(expected_checks, actual_checks, strict=True)
            )
        ):
            defects.append(f"{name}:relational")
    expected_triggers = (
        _expected_sqlite_triggers()
        if connection.dialect.name == "sqlite"
        else _expected_postgresql_triggers()
    )
    if _actual_trigger_manifest(connection) != expected_triggers:
        defects.append("monitoring:triggers")
    if defects:
        raise MonitoringCorrupt(f"monitoring schema contract drift: {sorted(defects)}")


class MonitoringRepository:
    """One transaction-bound repository with one immutable server owner scope."""

    def __init__(self, session: Session, *, owner_id: str) -> None:
        if not isinstance(session, Session):
            raise MonitoringRefused("SQLAlchemy session required")
        self.session = session
        self.owner_id = _identifier(owner_id, "owner")
        validate_monitoring_schema(session.connection())

    def _assignment_row(self, assignment_id: str, *, write: bool = False) -> MonitoringAssignmentRow:
        _identifier(assignment_id, "assignment")
        statement = sa.select(MonitoringAssignmentRow).where(
            MonitoringAssignmentRow.owner_id == self.owner_id,
            MonitoringAssignmentRow.assignment_id == assignment_id,
        )
        if write and self.session.get_bind().dialect.name == "postgresql":
            statement = statement.with_for_update()
        row = self.session.scalar(statement)
        if row is None:
            raise MonitoringNotFound()
        return row

    def create_assignment(self, spec: MonitoringAssignmentSpec, *, now: dt.datetime) -> MonitoringAssignment:
        if not isinstance(spec, MonitoringAssignmentSpec):
            raise MonitoringRefused("closed monitoring assignment spec required")
        now = _utc(now, "assignment creation time")
        project = self.session.scalar(sa.select(Project.project_id).where(
            Project.owner_id == self.owner_id, Project.project_id == spec.project_id))
        if project is None:
            raise MonitoringNotFound()
        existing = self.session.get(MonitoringAssignmentRow, (self.owner_id, spec.assignment_id))
        if existing is not None:
            current = _assignment_from_row(existing)
            if current.spec == spec:
                return current
            raise MonitoringConflict("assignment identity already exists with different bytes")
        row = MonitoringAssignmentRow(
            owner_id=self.owner_id, optimistic_revision=1, lifecycle_state="ACTIVE",
            current_state_snapshot_address=None, created_at=_db_time(now),
            updated_at=_db_time(now), withdrawn_at=None, **asdict(spec),
        )
        try:
            with caller_owned_savepoint(self.session, scope="create-monitoring-assignment"):
                self.session.add(row)
                self.session.flush()
        except IntegrityError as exc:
            existing = self.session.get(MonitoringAssignmentRow, (self.owner_id, spec.assignment_id))
            if existing is not None and _assignment_from_row(existing).spec == spec:
                return _assignment_from_row(existing)
            raise MonitoringConflict("assignment identity conflict") from exc
        return _assignment_from_row(row)

    def get_assignment(self, assignment_id: str) -> MonitoringAssignment:
        return _assignment_from_row(self._assignment_row(assignment_id))

    def list_assignments(
        self, *, limit: int = DEFAULT_PAGE_LIMIT, after: str | None = None,
        lifecycle_state: str | None = None,
    ) -> Page[MonitoringAssignment]:
        limit = _limit(limit)
        statement = sa.select(MonitoringAssignmentRow).where(
            MonitoringAssignmentRow.owner_id == self.owner_id)
        if lifecycle_state is not None:
            if lifecycle_state not in {"ACTIVE", "PAUSED", "WITHDRAWN"}:
                raise MonitoringRefused("closed lifecycle state required")
            statement = statement.where(MonitoringAssignmentRow.lifecycle_state == lifecycle_state)
        if after is not None:
            _identifier(after, "assignment cursor")
            statement = statement.where(MonitoringAssignmentRow.assignment_id > after)
        rows = self.session.scalars(statement.order_by(
            MonitoringAssignmentRow.assignment_id).limit(limit + 1)).all()
        return Page(
            tuple(_assignment_from_row(row) for row in rows[:limit]),
            rows[limit - 1].assignment_id if len(rows) > limit else None,
        )

    def update_assignment(
        self, assignment_id: str, *, expected_revision: int,
        lifecycle_state: str, now: dt.datetime,
    ) -> MonitoringAssignment:
        if type(expected_revision) is not int or expected_revision < 1:
            raise MonitoringRefused("positive expected revision required")
        if lifecycle_state not in {"ACTIVE", "PAUSED"}:
            raise MonitoringRefused("assignment update permits ACTIVE or PAUSED only")
        now = _utc(now, "assignment update time")
        row = self._assignment_row(assignment_id, write=True)
        if row.optimistic_revision != expected_revision or row.lifecycle_state == "WITHDRAWN":
            raise MonitoringConflict("assignment optimistic revision conflict")
        changed = self.session.execute(sa.update(MonitoringAssignmentRow).where(
            MonitoringAssignmentRow.owner_id == self.owner_id,
            MonitoringAssignmentRow.assignment_id == assignment_id,
            MonitoringAssignmentRow.optimistic_revision == expected_revision,
            MonitoringAssignmentRow.lifecycle_state != "WITHDRAWN",
        ).values(
            optimistic_revision=expected_revision + 1,
            lifecycle_state=lifecycle_state, updated_at=_db_time(now), withdrawn_at=None,
        ))
        if changed.rowcount != 1:
            raise MonitoringConflict("assignment optimistic revision conflict")
        self.session.flush()
        return _assignment_from_row(self._assignment_row(assignment_id))

    def withdraw_assignment(
        self, assignment_id: str, *, expected_revision: int, now: dt.datetime,
    ) -> MonitoringAssignment:
        if type(expected_revision) is not int or expected_revision < 1:
            raise MonitoringRefused("positive expected revision required")
        now = _utc(now, "assignment withdrawal time")
        row = self._assignment_row(assignment_id, write=True)
        if row.optimistic_revision != expected_revision or row.lifecycle_state == "WITHDRAWN":
            raise MonitoringConflict("assignment optimistic revision conflict")
        changed = self.session.execute(sa.update(MonitoringAssignmentRow).where(
            MonitoringAssignmentRow.owner_id == self.owner_id,
            MonitoringAssignmentRow.assignment_id == assignment_id,
            MonitoringAssignmentRow.optimistic_revision == expected_revision,
            MonitoringAssignmentRow.lifecycle_state != "WITHDRAWN",
        ).values(
            optimistic_revision=expected_revision + 1, lifecycle_state="WITHDRAWN",
            updated_at=_db_time(now), withdrawn_at=_db_time(now),
        ))
        if changed.rowcount != 1:
            raise MonitoringConflict("assignment optimistic revision conflict")
        self.session.flush()
        return _assignment_from_row(self._assignment_row(assignment_id))

    def append_state_snapshot(
        self, snapshot: MonitoringStateSnapshot, *, created_at: dt.datetime,
    ) -> MonitoringStateSnapshot:
        _require_owned_snapshot(self.owner_id, snapshot)
        _require_research_snapshot_predecessor(self.session, snapshot)
        assignment = self._assignment_row(snapshot.assignment_id, write=snapshot.snapshot_sequence == 0)
        created_at = _utc(created_at, "snapshot created time")
        raw = _canonical_document(snapshot.to_dict())
        existing = self.session.get(MonitoringStateSnapshotRow, (
            self.owner_id, snapshot.assignment_id, snapshot.canonical_instrument_address,
            snapshot.address,
        ))
        if existing is not None:
            if existing.canonical_json != raw:
                raise MonitoringConflict("snapshot address reused with different bytes")
            return _snapshot_from_row(existing)
        row = MonitoringStateSnapshotRow(
            owner_id=self.owner_id, assignment_id=snapshot.assignment_id,
            canonical_instrument_address=snapshot.canonical_instrument_address,
            snapshot_address=snapshot.address, snapshot_sequence=snapshot.snapshot_sequence,
            predecessor_snapshot_address=snapshot.predecessor_snapshot_address,
            strategy_state=snapshot.strategy_state.value,
            entry_reference_json=canonical_json(snapshot.entry_reference.to_dict()),
            stop_loss_json=canonical_json(snapshot.stop_loss.to_dict()),
            take_profit_json=canonical_json(snapshot.take_profit.to_dict()),
            evaluation_event_address=snapshot.evaluation_event_address,
            effective_at=_db_time(snapshot.effective_at), canonical_json=raw,
            created_at=_db_time(created_at),
        )
        try:
            with caller_owned_savepoint(self.session, scope="append-monitoring-snapshot"):
                self.session.add(row)
                self.session.flush()
        except IntegrityError as exc:
            existing = self.session.scalar(sa.select(MonitoringStateSnapshotRow).where(
                MonitoringStateSnapshotRow.owner_id == self.owner_id,
                MonitoringStateSnapshotRow.assignment_id == snapshot.assignment_id,
                MonitoringStateSnapshotRow.canonical_instrument_address == snapshot.canonical_instrument_address,
                MonitoringStateSnapshotRow.snapshot_sequence == snapshot.snapshot_sequence,
            ))
            if existing is not None and existing.canonical_json == raw:
                return _snapshot_from_row(existing)
            raise MonitoringConflict("snapshot sequence or identity conflict") from exc
        if snapshot.snapshot_sequence == 0:
            current = self.session.get(MonitoringLatestStateRow, (
                self.owner_id, snapshot.assignment_id, snapshot.canonical_instrument_address,
            ))
            if current is not None:
                raise MonitoringConflict("initial snapshot projection already exists")
            self.session.add(MonitoringLatestStateRow(
                owner_id=self.owner_id, assignment_id=snapshot.assignment_id,
                canonical_instrument_address=snapshot.canonical_instrument_address,
                snapshot_address=snapshot.address, last_event_address=None,
                snapshot_sequence=0, strategy_state=snapshot.strategy_state.value,
                projection_revision=1, updated_at=_db_time(snapshot.effective_at),
            ))
            assignment.current_state_snapshot_address = snapshot.address
            assignment.optimistic_revision += 1
            assignment.updated_at = _db_time(snapshot.effective_at)
            self.session.flush()
        return _snapshot_from_row(row)

    def _validated_event_assignment(self, event):
        if type(event) not in (MonitoringSignalEvent, ResearchMonitoringSignalEvent) or event.owner_id != self.owner_id:
            raise MonitoringRefused("owner-scoped monitoring event required")
        event.__post_init__()
        assignment = self._assignment_row(event.assignment_id, write=True)
        if assignment.lifecycle_state != "ACTIVE":
            raise MonitoringRefused("only an active assignment may author a monitoring event")
        identity = (
            assignment.strategy_id, assignment.graph_version_address,
            assignment.resolved_graph_address, assignment.implementation_closure_address,
            assignment.research_admission_address,
        )
        if identity != (
            event.strategy_id, event.graph_version_address, event.resolved_graph_address,
            event.implementation_closure_address, event.admission_address,
        ):
            raise MonitoringRefused("event identity does not match assignment")
        return assignment

    def append_event(
        self, event: MonitoringSignalEvent, *, created_at: dt.datetime,
    ) -> MonitoringSignalEvent:
        assignment = self._validated_event_assignment(event)
        before = self.session.get(MonitoringStateSnapshotRow, (
            self.owner_id, event.assignment_id, event.canonical_instrument_address,
            event.state_before_address,
        ))
        after = self.session.get(MonitoringStateSnapshotRow, (
            self.owner_id, event.assignment_id, event.canonical_instrument_address,
            event.state_after_address,
        ))
        if before is None or after is None:
            raise MonitoringNotFound()
        before_fact, after_fact = _snapshot_from_row(before), _snapshot_from_row(after)
        _event_snapshot_binding(before_fact, after_fact, event, MonitoringRefused)
        raw = _canonical_document(event.to_dict())
        dedupe = event_dedupe_address(event)
        current = self._locked_latest_projection(event)
        existing = self.session.get(MonitoringSignalEventRow, (
            self.owner_id, event.assignment_id, event.address,
        ))
        if existing is not None:
            if existing.canonical_json != raw:
                raise MonitoringConflict(
                    "monitoring event identity reused with different bytes")
            fact = _event_from_row(existing)
            self._apply_existing_event_retry(
                assignment, current, after_fact, fact)
            return fact

        self._require_next_event_state(assignment, current, after_fact, event)
        row = MonitoringSignalEventRow(
            owner_id=self.owner_id, assignment_id=event.assignment_id,
            content_address=event.address, dedupe_address=dedupe,
            canonical_instrument_address=event.canonical_instrument_address,
            evaluation_event_address=event.evaluation_event_address,
            graph_version_address=event.graph_version_address,
            implementation_closure_address=event.implementation_closure_address,
            state_before_address=event.state_before_address,
            state_after_address=event.state_after_address,
            event_at=_db_time(event.event_at), valid_until=_db_time(event.valid_until),
            canonical_json=raw, created_at=_db_time(_utc(created_at, "event created time")),
        )
        try:
            with caller_owned_savepoint(self.session, scope="append-monitoring-event"):
                self.session.add(row)
                self.session.flush()
                fact = _event_from_row(row)
                self._advance_latest_projection(
                    assignment, current, after_fact, fact)
        except IntegrityError as exc:
            existing = self.session.scalar(sa.select(MonitoringSignalEventRow).where(
                MonitoringSignalEventRow.owner_id == self.owner_id,
                MonitoringSignalEventRow.dedupe_address == dedupe,
            ))
            if existing is None or existing.canonical_json != raw:
                raise MonitoringConflict("monitoring event dedupe conflict") from exc
            fact = _event_from_row(existing)
            current = self._locked_latest_projection(event)
            self._apply_existing_event_retry(
                assignment, current, after_fact, fact)
            return fact
        return fact

    def _locked_latest_projection(
        self, event: MonitoringSignalEvent,
    ) -> MonitoringLatestStateRow:
        statement = sa.select(MonitoringLatestStateRow).where(
            MonitoringLatestStateRow.owner_id == self.owner_id,
            MonitoringLatestStateRow.assignment_id == event.assignment_id,
            MonitoringLatestStateRow.canonical_instrument_address
            == event.canonical_instrument_address,
        )
        if self.session.get_bind().dialect.name == "postgresql":
            statement = statement.with_for_update()
        current = self.session.scalar(statement)
        if current is None:
            raise MonitoringConflict(
                "ordered event admission requires a current state projection")
        return current

    def _require_next_event_state(
        self, assignment: MonitoringAssignmentRow,
        current: MonitoringLatestStateRow,
        snapshot: MonitoringStateSnapshot,
        event: MonitoringSignalEvent,
    ) -> None:
        if assignment.current_state_snapshot_address != current.snapshot_address:
            raise MonitoringConflict(
                "assignment current state does not match the locked projection")
        if current.snapshot_address != event.state_before_address:
            raise MonitoringConflict(
                "ordered event state_before does not match the current projection")
        if snapshot.snapshot_sequence != current.snapshot_sequence + 1:
            raise MonitoringConflict(
                "ordered event snapshot sequence must advance current state by one")
        if snapshot.predecessor_snapshot_address != current.snapshot_address:
            raise MonitoringConflict(
                "ordered event successor does not reference the current projection")

    def _snapshot_is_descendant(
        self, event: MonitoringSignalEvent, *, descendant_address: str,
        ancestor: MonitoringStateSnapshot,
    ) -> bool:
        address = descendant_address
        seen: set[str] = set()
        while address not in seen:
            if address == ancestor.address:
                return True
            seen.add(address)
            row = self.session.get(MonitoringStateSnapshotRow, (
                self.owner_id, event.assignment_id,
                event.canonical_instrument_address, address,
            ))
            if row is None:
                raise MonitoringCorrupt(
                    "latest projection snapshot chain is incomplete")
            fact = _snapshot_from_row(row)
            if fact.snapshot_sequence <= ancestor.snapshot_sequence:
                return False
            if fact.predecessor_snapshot_address is None:
                return False
            address = fact.predecessor_snapshot_address
        raise MonitoringCorrupt("latest projection snapshot chain contains a cycle")

    def _apply_existing_event_retry(
        self, assignment: MonitoringAssignmentRow,
        current: MonitoringLatestStateRow,
        snapshot: MonitoringStateSnapshot,
        event: MonitoringSignalEvent,
    ) -> None:
        if (current.last_event_address == event.address
                and current.snapshot_address == snapshot.address):
            return
        if (current.snapshot_address == event.state_before_address
                and snapshot.snapshot_sequence == current.snapshot_sequence + 1):
            self._require_next_event_state(
                assignment, current, snapshot, event)
            with caller_owned_savepoint(
                    self.session, scope="repair-monitoring-event-projection"):
                self._advance_latest_projection(
                    assignment, current, snapshot, event)
            return
        if (current.snapshot_sequence > snapshot.snapshot_sequence
                and self._snapshot_is_descendant(
                    event, descendant_address=current.snapshot_address,
                    ancestor=snapshot)):
            return
        raise MonitoringConflict(
            "byte-identical event retry is not current or a proven projection ancestor")

    def _advance_latest_projection(
        self, assignment: MonitoringAssignmentRow,
        current: MonitoringLatestStateRow,
        snapshot: MonitoringStateSnapshot, event: MonitoringSignalEvent,
    ) -> None:
        self._require_next_event_state(assignment, current, snapshot, event)
        now = event.knowledge_cutoff_at
        current.snapshot_address = snapshot.address
        current.last_event_address = event.address
        current.snapshot_sequence = snapshot.snapshot_sequence
        current.strategy_state = snapshot.strategy_state.value
        current.projection_revision += 1
        current.updated_at = _db_time(now)
        assignment.current_state_snapshot_address = snapshot.address
        assignment.optimistic_revision += 1
        assignment.updated_at = _db_time(now)
        self.session.flush()

    def _validate_alert_event(self, alert):
        if type(alert) not in (SignalAlert, ResearchSignalAlert) or alert.owner_id != self.owner_id:
            raise MonitoringRefused("owner-scoped monitoring alert required")
        event_row = self.session.get(MonitoringSignalEventRow, (
            self.owner_id, alert.assignment_id, alert.monitoring_event_address,
        ))
        if event_row is None:
            raise MonitoringNotFound()
        event = _event_from_row(event_row)
        derived = derive_monitoring_alert(event)
        if not hasattr(derived, "alert") or derived.alert != alert:
            raise MonitoringRefused("alert is not the canonical derivation of its event")

    def append_alert(self, alert: SignalAlert, *, created_at: dt.datetime) -> SignalAlert:
        self._validate_alert_event(alert)
        raw = _canonical_document(alert.to_dict())
        row = self.session.get(MonitoringSignalAlertRow, (
            self.owner_id, alert.assignment_id, alert.address,
        ))
        if row is None:
            row = MonitoringSignalAlertRow(
                owner_id=self.owner_id, assignment_id=alert.assignment_id,
                alert_address=alert.address,
                monitoring_event_address=alert.monitoring_event_address,
                canonical_instrument_address=alert.canonical_instrument_address,
                event_at=_db_time(alert.event_at), valid_until=_db_time(alert.valid_until),
                canonical_json=raw, created_at=_db_time(_utc(created_at, "alert created time")),
            )
            try:
                with caller_owned_savepoint(self.session, scope="append-monitoring-alert"):
                    self.session.add(row)
                    self.session.flush()
            except IntegrityError as exc:
                row = self.session.scalar(sa.select(MonitoringSignalAlertRow).where(
                    MonitoringSignalAlertRow.owner_id == self.owner_id,
                    MonitoringSignalAlertRow.assignment_id == alert.assignment_id,
                    MonitoringSignalAlertRow.monitoring_event_address == alert.monitoring_event_address,
                ))
                if row is None or row.canonical_json != raw:
                    raise MonitoringConflict("monitoring alert derivation conflict") from exc
        if row.canonical_json != raw:
            raise MonitoringConflict("monitoring alert identity reused with different bytes")
        fact = _alert_from_row(row)
        self._ensure_alert_attention(fact)
        return fact

    def _ensure_alert_attention(self, fact):
        attention_state = self.session.get(MonitoringAlertAttentionStateRow, (
            self.owner_id, fact.assignment_id, fact.address,
        ))
        if attention_state is None:
            attention_rows = self.session.scalars(sa.select(
                MonitoringAlertAttentionEventRow).where(
                    MonitoringAlertAttentionEventRow.owner_id == self.owner_id,
                    MonitoringAlertAttentionEventRow.assignment_id == fact.assignment_id,
                    MonitoringAlertAttentionEventRow.alert_address == fact.address,
                ).order_by(MonitoringAlertAttentionEventRow.sequence)).all()
            self._write_attention_projection(
                rebuild_attention_projection(
                    fact, tuple(_attention_from_row(row) for row in attention_rows)),
                expected_revision=None,
                updated_at=(_domain_time(attention_rows[-1].occurred_at)
                            if attention_rows else fact.event_at),
            )

    def append_delivery_attempt(
        self, attempt: AlertDeliveryAttempt, *, created_at: dt.datetime,
    ) -> AlertDeliveryAttempt:
        if not isinstance(attempt, AlertDeliveryAttempt) or attempt.owner_id != self.owner_id:
            raise MonitoringRefused("owner-scoped delivery attempt required")
        alert = self._alert(attempt.assignment_id, attempt.alert_address)
        rows = self.session.scalars(sa.select(MonitoringAlertDeliveryAttemptRow).where(
            MonitoringAlertDeliveryAttemptRow.owner_id == self.owner_id,
            MonitoringAlertDeliveryAttemptRow.assignment_id == attempt.assignment_id,
            MonitoringAlertDeliveryAttemptRow.alert_address == attempt.alert_address,
        ).order_by(MonitoringAlertDeliveryAttemptRow.sequence)).all()
        facts = [_delivery_from_row(row) for row in rows]
        validate_delivery_attempts(alert, (*facts, attempt))
        raw = _canonical_document(attempt.to_dict())
        existing = self.session.scalar(sa.select(MonitoringAlertDeliveryAttemptRow).where(
            MonitoringAlertDeliveryAttemptRow.owner_id == self.owner_id,
            MonitoringAlertDeliveryAttemptRow.attempt_id == attempt.attempt_id,
        ))
        if existing is not None:
            if existing.canonical_json != raw:
                raise MonitoringConflict("delivery request reused with different bytes")
            return _delivery_from_row(existing)
        row = MonitoringAlertDeliveryAttemptRow(
            owner_id=self.owner_id, assignment_id=attempt.assignment_id,
            attempt_address=attempt.address, attempt_id=attempt.attempt_id,
            alert_address=attempt.alert_address, sequence=attempt.sequence,
            channel=attempt.channel.value, outcome=attempt.outcome.value,
            occurred_at=_db_time(attempt.occurred_at), failure_code=attempt.failure_code,
            canonical_json=raw, created_at=_db_time(_utc(created_at, "delivery created time")),
        )
        try:
            with caller_owned_savepoint(self.session, scope="append-monitoring-delivery"):
                self.session.add(row)
                self.session.flush()
        except IntegrityError as exc:
            existing = self.session.scalar(sa.select(MonitoringAlertDeliveryAttemptRow).where(
                MonitoringAlertDeliveryAttemptRow.owner_id == self.owner_id,
                MonitoringAlertDeliveryAttemptRow.attempt_id == attempt.attempt_id,
            ))
            if existing is not None and existing.canonical_json == raw:
                return _delivery_from_row(existing)
            raise MonitoringConflict("delivery sequence or request conflict") from exc
        return _delivery_from_row(row)

    def append_attention_event(
        self, event: AlertAttentionEvent, *, created_at: dt.datetime,
        update_projection: bool = True,
    ) -> AlertAttentionEvent:
        if not isinstance(event, AlertAttentionEvent) or event.owner_id != self.owner_id:
            raise MonitoringRefused("owner-scoped attention event required")
        alert = self._alert(event.assignment_id, event.alert_address)
        rows = self.session.scalars(sa.select(MonitoringAlertAttentionEventRow).where(
            MonitoringAlertAttentionEventRow.owner_id == self.owner_id,
            MonitoringAlertAttentionEventRow.assignment_id == event.assignment_id,
            MonitoringAlertAttentionEventRow.alert_address == event.alert_address,
        ).order_by(MonitoringAlertAttentionEventRow.sequence)).all()
        facts = [_attention_from_row(row) for row in rows]
        projection = rebuild_attention_projection(alert, (*facts, event))
        raw = _canonical_document(event.to_dict())
        existing = self.session.scalar(sa.select(MonitoringAlertAttentionEventRow).where(
            MonitoringAlertAttentionEventRow.owner_id == self.owner_id,
            MonitoringAlertAttentionEventRow.request_id == event.request_id,
        ))
        if existing is None:
            row = MonitoringAlertAttentionEventRow(
                owner_id=self.owner_id, assignment_id=event.assignment_id,
                attention_event_address=event.address, request_id=event.request_id,
                alert_address=event.alert_address, sequence=event.sequence,
                action=event.action.value, occurred_at=_db_time(event.occurred_at),
                canonical_json=raw, created_at=_db_time(_utc(created_at, "attention created time")),
            )
            try:
                with caller_owned_savepoint(self.session, scope="append-monitoring-attention"):
                    self.session.add(row)
                    self.session.flush()
                existing = row
            except IntegrityError as exc:
                existing = self.session.scalar(sa.select(MonitoringAlertAttentionEventRow).where(
                    MonitoringAlertAttentionEventRow.owner_id == self.owner_id,
                    MonitoringAlertAttentionEventRow.request_id == event.request_id,
                ))
                if existing is None or existing.canonical_json != raw:
                    raise MonitoringConflict("attention sequence or request conflict") from exc
        if existing.canonical_json != raw:
            raise MonitoringConflict("attention request reused with different bytes")
        fact = _attention_from_row(existing)
        if update_projection:
            current = self.session.get(MonitoringAlertAttentionStateRow, (
                self.owner_id, event.assignment_id, event.alert_address,
            ))
            if current is None or current.projection_address != projection.address:
                self._write_attention_projection(
                    projection,
                    expected_revision=current.projection_revision if current is not None else None,
                    updated_at=event.occurred_at,
                )
        return fact

    def _write_attention_projection(
        self, projection: AlertAttentionProjection, *, expected_revision: int | None,
        updated_at: dt.datetime,
    ) -> None:
        current = self.session.get(MonitoringAlertAttentionStateRow, (
            self.owner_id, projection.assignment_id, projection.alert_address,
        ))
        if current is None:
            if expected_revision is not None:
                raise MonitoringConflict("attention projection revision conflict")
            self.session.add(MonitoringAlertAttentionStateRow(
                owner_id=self.owner_id, assignment_id=projection.assignment_id,
                alert_address=projection.alert_address,
                projection_address=projection.address,
                alert_event_at=_db_time(projection.alert_event_at),
                alert_valid_until=_db_time(projection.alert_valid_until),
                last_sequence=projection.last_sequence, is_unread=projection.is_unread,
                read_at=_db_time(projection.read_at) if projection.read_at else None,
                acknowledged_at=_db_time(projection.acknowledged_at) if projection.acknowledged_at else None,
                dismissed_at=_db_time(projection.dismissed_at) if projection.dismissed_at else None,
                projection_revision=1, updated_at=_db_time(updated_at),
            ))
        else:
            if expected_revision != current.projection_revision:
                raise MonitoringConflict("attention projection revision conflict")
            current.projection_address = projection.address
            current.alert_event_at = _db_time(projection.alert_event_at)
            current.alert_valid_until = _db_time(projection.alert_valid_until)
            current.last_sequence = projection.last_sequence
            current.is_unread = projection.is_unread
            current.read_at = _db_time(projection.read_at) if projection.read_at else None
            current.acknowledged_at = (
                _db_time(projection.acknowledged_at) if projection.acknowledged_at else None)
            current.dismissed_at = _db_time(projection.dismissed_at) if projection.dismissed_at else None
            current.projection_revision += 1
            current.updated_at = _db_time(updated_at)
        self.session.flush()

    def append_review(self, review: SignalReview) -> SignalReview:
        if not isinstance(review, SignalReview) or review.owner_id != self.owner_id:
            raise MonitoringRefused("owner-scoped signal review required")
        if self.session.get(MonitoringSignalEventRow, (
            self.owner_id, review.assignment_id, review.monitoring_event_address,
        )) is None:
            raise MonitoringNotFound()
        raw = _canonical_document(review.to_dict())
        existing = self.session.scalar(sa.select(MonitoringSignalReviewRow).where(
            MonitoringSignalReviewRow.owner_id == self.owner_id,
            MonitoringSignalReviewRow.assignment_id == review.assignment_id,
            MonitoringSignalReviewRow.monitoring_event_address == review.monitoring_event_address,
            MonitoringSignalReviewRow.reviewer_user_id == review.reviewer_user_id,
        ))
        if existing is not None:
            if existing.canonical_json != raw:
                raise MonitoringConflict("review identity reused with different bytes")
            return _review_from_row(existing)
        row = MonitoringSignalReviewRow(
            owner_id=self.owner_id, assignment_id=review.assignment_id,
            review_address=review.address,
            monitoring_event_address=review.monitoring_event_address,
            reviewer_user_id=review.reviewer_user_id,
            disposition=review.disposition, reason_code=review.reason_code,
            note=review.note, created_at=_db_time(review.created_at), canonical_json=raw,
        )
        try:
            with caller_owned_savepoint(self.session, scope="append-monitoring-review"):
                self.session.add(row)
                self.session.flush()
        except IntegrityError as exc:
            existing = self.session.scalar(sa.select(MonitoringSignalReviewRow).where(
                MonitoringSignalReviewRow.owner_id == self.owner_id,
                MonitoringSignalReviewRow.assignment_id == review.assignment_id,
                MonitoringSignalReviewRow.monitoring_event_address == review.monitoring_event_address,
                MonitoringSignalReviewRow.reviewer_user_id == review.reviewer_user_id,
            ))
            if existing is not None and existing.canonical_json == raw:
                return _review_from_row(existing)
            raise MonitoringConflict("review identity conflict") from exc
        return _review_from_row(row)

    def _alert(self, assignment_id: str, alert_address: str) -> SignalAlert:
        _identifier(assignment_id, "assignment")
        _address(alert_address, "alert")
        row = self.session.get(MonitoringSignalAlertRow, (
            self.owner_id, assignment_id, alert_address,
        ))
        if row is None:
            raise MonitoringNotFound()
        return _alert_from_row(row)

    def get_alert(self, assignment_id: str, alert_address: str) -> SignalAlert:
        """Return one exact owner-scoped immutable alert."""
        return self._alert(assignment_id, alert_address)

    def get_delivery_attempt(
        self, assignment_id: str, alert_address: str, sequence: int,
    ) -> AlertDeliveryAttempt:
        """Return one exact owner-scoped in-app delivery attempt."""
        self._alert(assignment_id, alert_address)
        if type(sequence) is not int or sequence < 1:
            raise MonitoringRefused("positive delivery sequence required")
        row = self.session.scalar(sa.select(MonitoringAlertDeliveryAttemptRow).where(
            MonitoringAlertDeliveryAttemptRow.owner_id == self.owner_id,
            MonitoringAlertDeliveryAttemptRow.assignment_id == assignment_id,
            MonitoringAlertDeliveryAttemptRow.alert_address == alert_address,
            MonitoringAlertDeliveryAttemptRow.sequence == sequence,
            MonitoringAlertDeliveryAttemptRow.channel == "IN_APP",
        ))
        if row is None:
            raise MonitoringNotFound()
        fact = _delivery_from_row(row)
        if (
            fact.owner_id != self.owner_id
            or fact.assignment_id != assignment_id
            or fact.alert_address != alert_address
            or fact.sequence != sequence
            or fact.channel.value != "IN_APP"
        ):
            raise MonitoringCorrupt("delivery attempt scope differs")
        return fact

    def get_event(self, assignment_id: str, address: str) -> MonitoringSignalEvent:
        _identifier(assignment_id, "assignment")
        _address(address, "monitoring event")
        row = self.session.get(MonitoringSignalEventRow, (self.owner_id, assignment_id, address))
        if row is None:
            raise MonitoringNotFound()
        return _event_from_row(row)

    def list_events(
        self, assignment_id: str, *, limit: int = DEFAULT_PAGE_LIMIT,
        after: TimeAddressCursor | None = None,
    ) -> Page[MonitoringSignalEvent]:
        self._assignment_row(assignment_id)
        limit = _limit(limit)
        statement = sa.select(MonitoringSignalEventRow).where(
            MonitoringSignalEventRow.owner_id == self.owner_id,
            MonitoringSignalEventRow.assignment_id == assignment_id,
        )
        if after is not None:
            if not isinstance(after, TimeAddressCursor):
                raise MonitoringRefused("closed event cursor required")
            moment = _db_time(after.occurred_at)
            statement = statement.where(sa.or_(
                MonitoringSignalEventRow.event_at > moment,
                sa.and_(MonitoringSignalEventRow.event_at == moment,
                        MonitoringSignalEventRow.content_address > after.address),
            ))
        rows = self.session.scalars(statement.order_by(
            MonitoringSignalEventRow.event_at, MonitoringSignalEventRow.content_address,
        ).limit(limit + 1)).all()
        items = tuple(_event_from_row(row) for row in rows[:limit])
        cursor = (TimeAddressCursor(items[-1].event_at, items[-1].address)
                  if len(rows) > limit else None)
        return Page(items, cursor)

    def list_alerts(
        self, *, assignment_id: str | None = None,
        limit: int = DEFAULT_PAGE_LIMIT, after: TimeAddressCursor | None = None,
    ) -> Page[SignalAlert]:
        limit = _limit(limit)
        statement = sa.select(MonitoringSignalAlertRow).where(
            MonitoringSignalAlertRow.owner_id == self.owner_id)
        if assignment_id is not None:
            self._assignment_row(assignment_id)
            statement = statement.where(MonitoringSignalAlertRow.assignment_id == assignment_id)
        if after is not None:
            moment = _db_time(after.occurred_at)
            statement = statement.where(sa.or_(
                MonitoringSignalAlertRow.event_at > moment,
                sa.and_(MonitoringSignalAlertRow.event_at == moment,
                        MonitoringSignalAlertRow.alert_address > after.address),
            ))
        rows = self.session.scalars(statement.order_by(
            MonitoringSignalAlertRow.event_at, MonitoringSignalAlertRow.alert_address,
        ).limit(limit + 1)).all()
        items = tuple(_alert_from_row(row) for row in rows[:limit])
        cursor = (TimeAddressCursor(items[-1].event_at, items[-1].address)
                  if len(rows) > limit else None)
        return Page(items, cursor)

    def get_latest_state(
        self, assignment_id: str, canonical_instrument_address: str,
    ) -> MonitoringStateSnapshot:
        self._assignment_row(assignment_id)
        _address(canonical_instrument_address, "canonical instrument")
        row = self.session.get(MonitoringLatestStateRow, (
            self.owner_id, assignment_id, canonical_instrument_address,
        ))
        if row is None:
            raise MonitoringNotFound()
        snapshot = self.session.get(MonitoringStateSnapshotRow, (
            self.owner_id, assignment_id, canonical_instrument_address, row.snapshot_address,
        ))
        if snapshot is None:
            raise MonitoringCorrupt("latest state references a missing snapshot")
        fact = _snapshot_from_row(snapshot)
        if (row.snapshot_sequence, row.strategy_state) != (
                fact.snapshot_sequence, fact.strategy_state.value):
            raise MonitoringCorrupt("latest state copied columns mismatch")
        return fact

    def get_attention_state(
        self, assignment_id: str, alert_address: str,
    ) -> AlertAttentionProjection:
        alert = self._alert(assignment_id, alert_address)
        row = self.session.get(MonitoringAlertAttentionStateRow, (
            self.owner_id, assignment_id, alert_address,
        ))
        if row is None:
            raise MonitoringNotFound()
        projection = AlertAttentionProjection(
            owner_id=row.owner_id, assignment_id=row.assignment_id,
            alert_address=row.alert_address, alert_event_at=_domain_time(row.alert_event_at),
            alert_valid_until=_domain_time(row.alert_valid_until),
            last_sequence=row.last_sequence, is_unread=row.is_unread,
            read_at=_domain_time(row.read_at), acknowledged_at=_domain_time(row.acknowledged_at),
            dismissed_at=_domain_time(row.dismissed_at),
        )
        if projection.address != row.projection_address or projection.alert_address != alert.address:
            raise MonitoringCorrupt("attention projection address mismatch")
        return projection

    def get_attention_event(
        self, assignment_id: str, alert_address: str, request_id: str,
    ) -> AlertAttentionEvent:
        """Return one exact owner-scoped attention command fact."""
        self._alert(assignment_id, alert_address)
        _address(request_id, "attention request")
        row = self.session.scalar(sa.select(MonitoringAlertAttentionEventRow).where(
            MonitoringAlertAttentionEventRow.owner_id == self.owner_id,
            MonitoringAlertAttentionEventRow.assignment_id == assignment_id,
            MonitoringAlertAttentionEventRow.alert_address == alert_address,
            MonitoringAlertAttentionEventRow.request_id == request_id,
        ))
        if row is None:
            raise MonitoringNotFound()
        fact = _attention_from_row(row)
        if (
            fact.owner_id != self.owner_id
            or fact.assignment_id != assignment_id
            or fact.alert_address != alert_address
            or fact.request_id != request_id
        ):
            raise MonitoringCorrupt("attention request scope differs")
        return fact

    def get_review(
        self, assignment_id: str, monitoring_event_address: str,
        reviewer_user_id: str,
    ) -> SignalReview:
        """Return one immutable owner/reviewer/event review identity."""
        self._assignment_row(assignment_id)
        _address(monitoring_event_address, "monitoring event")
        _identifier(reviewer_user_id, "reviewer")
        row = self.session.scalar(sa.select(MonitoringSignalReviewRow).where(
            MonitoringSignalReviewRow.owner_id == self.owner_id,
            MonitoringSignalReviewRow.assignment_id == assignment_id,
            MonitoringSignalReviewRow.monitoring_event_address == monitoring_event_address,
            MonitoringSignalReviewRow.reviewer_user_id == reviewer_user_id,
        ))
        if row is None:
            raise MonitoringNotFound()
        fact = _review_from_row(row)
        if (
            fact.owner_id != self.owner_id
            or fact.assignment_id != assignment_id
            or fact.monitoring_event_address != monitoring_event_address
            or fact.reviewer_user_id != reviewer_user_id
        ):
            raise MonitoringCorrupt("signal review scope differs")
        return fact

    def list_reviews(
        self, assignment_id: str, *, limit: int = DEFAULT_PAGE_LIMIT,
        after: TimeAddressCursor | None = None,
    ) -> Page[SignalReview]:
        self._assignment_row(assignment_id)
        limit = _limit(limit)
        statement = sa.select(MonitoringSignalReviewRow).where(
            MonitoringSignalReviewRow.owner_id == self.owner_id,
            MonitoringSignalReviewRow.assignment_id == assignment_id,
        )
        if after is not None:
            moment = _db_time(after.occurred_at)
            statement = statement.where(sa.or_(
                MonitoringSignalReviewRow.created_at > moment,
                sa.and_(MonitoringSignalReviewRow.created_at == moment,
                        MonitoringSignalReviewRow.review_address > after.address),
            ))
        rows = self.session.scalars(statement.order_by(
            MonitoringSignalReviewRow.created_at, MonitoringSignalReviewRow.review_address,
        ).limit(limit + 1)).all()
        items = tuple(_review_from_row(row) for row in rows[:limit])
        cursor = (TimeAddressCursor(items[-1].created_at, items[-1].address)
                  if len(rows) > limit else None)
        return Page(items, cursor)

    def rebuild_projections(self) -> dict[str, int]:
        """Deterministically repair this owner's two rebuildable projections."""
        self.session.execute(sa.delete(MonitoringLatestStateRow).where(
            MonitoringLatestStateRow.owner_id == self.owner_id))
        self.session.execute(sa.delete(MonitoringAlertAttentionStateRow).where(
            MonitoringAlertAttentionStateRow.owner_id == self.owner_id))
        latest = _reconstruct_latest_states(self.session, self.owner_id)
        for (assignment_id, instrument), (snapshot, event, updated_at) in latest.items():
            self.session.add(MonitoringLatestStateRow(
                owner_id=self.owner_id, assignment_id=assignment_id,
                canonical_instrument_address=instrument, snapshot_address=snapshot.address,
                last_event_address=event.address if event is not None else None,
                snapshot_sequence=snapshot.snapshot_sequence,
                strategy_state=snapshot.strategy_state.value, projection_revision=1,
                updated_at=_db_time(updated_at),
            ))
        pointers = _assignment_projection_pointers(latest)
        for assignment in self.session.scalars(sa.select(MonitoringAssignmentRow).where(
                MonitoringAssignmentRow.owner_id == self.owner_id)):
            expected = pointers.get(assignment.assignment_id)
            expected_address = expected[0] if expected is not None else None
            if assignment.current_state_snapshot_address != expected_address:
                assignment.current_state_snapshot_address = expected_address
                assignment.optimistic_revision += 1
                if expected is not None:
                    assignment.updated_at = _db_time(expected[1])
        alert_rows = self.session.scalars(sa.select(MonitoringSignalAlertRow).where(
            MonitoringSignalAlertRow.owner_id == self.owner_id)).all()
        for alert_row in alert_rows:
            alert = _alert_from_row(alert_row)
            attention = self.session.scalars(sa.select(MonitoringAlertAttentionEventRow).where(
                MonitoringAlertAttentionEventRow.owner_id == self.owner_id,
                MonitoringAlertAttentionEventRow.assignment_id == alert.assignment_id,
                MonitoringAlertAttentionEventRow.alert_address == alert.address,
            ).order_by(MonitoringAlertAttentionEventRow.sequence)).all()
            projection = rebuild_attention_projection(
                alert, tuple(_attention_from_row(row) for row in attention))
            self._write_attention_projection(
                projection, expected_revision=None,
                updated_at=(projection.dismissed_at or projection.acknowledged_at
                            or projection.read_at or alert.event_at),
            )
        self.session.flush()
        return {"latest_state": len(latest), "attention_state": len(alert_rows)}


def validate_persisted_monitoring(connection: sa.Connection) -> None:
    """Copy/restore gate for schemas, canonical bytes and rebuildable projections."""
    validate_monitoring_schema(connection, require_marker=False)
    with Session(bind=connection, future=True, expire_on_commit=False) as session:
        for row in session.scalars(sa.select(MonitoringAssignmentRow).execution_options(yield_per=100)):
            _assignment_from_row(row)
        for model, loader in (
            (MonitoringStateSnapshotRow, _snapshot_from_row),
            (MonitoringSignalEventRow, _event_from_row),
            (MonitoringSignalAlertRow, _alert_from_row),
            (MonitoringAlertDeliveryAttemptRow, _delivery_from_row),
            (MonitoringAlertAttentionEventRow, _attention_from_row),
            (MonitoringSignalReviewRow, _review_from_row),
        ):
            for row in session.scalars(sa.select(model).execution_options(yield_per=100)):
                loader(row)
        owners = set(session.scalars(sa.select(MonitoringAssignmentRow.owner_id).distinct()))
        for owner in owners:
            latest_before = {
                (row.assignment_id, row.canonical_instrument_address): (
                    row.snapshot_address, row.last_event_address, row.snapshot_sequence,
                    row.strategy_state,
                )
                for row in session.scalars(sa.select(MonitoringLatestStateRow).where(
                    MonitoringLatestStateRow.owner_id == owner))
            }
            attention_before = {
                (row.assignment_id, row.alert_address): row.projection_address
                for row in session.scalars(sa.select(MonitoringAlertAttentionStateRow).where(
                    MonitoringAlertAttentionStateRow.owner_id == owner))
            }
            reconstructed = _reconstruct_latest_states(session, owner)
            expected_latest = {
                key: (
                    snapshot.address, event.address if event else None,
                    snapshot.snapshot_sequence, snapshot.strategy_state.value,
                )
                for key, (snapshot, event, _updated_at) in reconstructed.items()
            }
            if latest_before != expected_latest:
                raise MonitoringCorrupt("monitoring latest-state projection is not rebuildable")
            expected_pointers = _assignment_projection_pointers(reconstructed)
            for assignment in session.scalars(sa.select(MonitoringAssignmentRow).where(
                    MonitoringAssignmentRow.owner_id == owner)):
                expected = expected_pointers.get(assignment.assignment_id)
                expected_address = expected[0] if expected is not None else None
                if assignment.current_state_snapshot_address != expected_address:
                    raise MonitoringCorrupt(
                        "monitoring assignment current-state pointer disagrees with projections")
            expected_attention: dict[tuple[str, str], str] = {}
            for alert_row in session.scalars(sa.select(MonitoringSignalAlertRow).where(
                    MonitoringSignalAlertRow.owner_id == owner)):
                alert = _alert_from_row(alert_row)
                deliveries = tuple(_delivery_from_row(row) for row in session.scalars(
                    sa.select(MonitoringAlertDeliveryAttemptRow).where(
                        MonitoringAlertDeliveryAttemptRow.owner_id == owner,
                        MonitoringAlertDeliveryAttemptRow.assignment_id == alert.assignment_id,
                        MonitoringAlertDeliveryAttemptRow.alert_address == alert.address,
                    ).order_by(MonitoringAlertDeliveryAttemptRow.sequence)))
                try:
                    validate_delivery_attempts(alert, deliveries)
                except MonitoringContractError as exc:
                    raise MonitoringCorrupt(
                        "monitoring delivery sequence is not reconstructible") from exc
                attention = tuple(_attention_from_row(row) for row in session.scalars(
                    sa.select(MonitoringAlertAttentionEventRow).where(
                        MonitoringAlertAttentionEventRow.owner_id == owner,
                        MonitoringAlertAttentionEventRow.assignment_id == alert.assignment_id,
                        MonitoringAlertAttentionEventRow.alert_address == alert.address,
                    ).order_by(MonitoringAlertAttentionEventRow.sequence)))
                expected_attention[(alert.assignment_id, alert.address)] = (
                    rebuild_attention_projection(alert, attention).address)
            if attention_before != expected_attention:
                raise MonitoringCorrupt("monitoring attention projection is not rebuildable")


__all__ = [
    "DEFAULT_PAGE_LIMIT", "MAX_PAGE_LIMIT", "MAX_CANONICAL_BYTES",
    "MONITORING_TABLES", "MonitoringAssignment", "MonitoringAssignmentSpec",
    "MonitoringConflict", "MonitoringCorrupt", "MonitoringNotFound",
    "MonitoringPersistenceError", "MonitoringRefused", "MonitoringRepository",
    "MonitoringStateSnapshot", "Page", "SignalReview", "TimeAddressCursor",
    "event_dedupe_address", "monitoring_schema_manifest",
    "validate_monitoring_schema", "validate_persisted_monitoring",
]
