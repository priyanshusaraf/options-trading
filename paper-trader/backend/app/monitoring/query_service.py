"""Unregistered owner-scoped read model for the monitoring Alerts Inbox."""
from __future__ import annotations

from dataclasses import dataclass

import sqlalchemy as sa

from app.db.models import MonitoringAlertAttentionStateRow, MonitoringSignalAlertRow
from app.monitoring.contracts import AlertAttentionProjection, SignalAlert
from app.monitoring.cursor import AlertCursorCodec, MonitoringCursorRefusal
from app.monitoring.repository import (
    MonitoringNotFound,
    MonitoringRepository,
    _alert_from_row,
    _db_time,
)


DEFAULT_LIMIT = 50
MAX_LIMIT = 100


class MonitoringQueryRefusal(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AlertInboxItem:
    alert: SignalAlert
    attention: AlertAttentionProjection


@dataclass(frozen=True, slots=True)
class AlertInboxPage:
    items: tuple[AlertInboxItem, ...]
    next_cursor: str | None


def _before_cursor(position):
    moment = _db_time(position.event_at)
    return sa.or_(
        MonitoringSignalAlertRow.event_at < moment,
        sa.and_(
            MonitoringSignalAlertRow.event_at == moment,
            MonitoringSignalAlertRow.alert_address < position.alert_address,
        ),
    )


def _boundary(
    repository: object, codec: object, limit: object,
    assignment_id: object, unread_only: object,
) -> tuple[MonitoringRepository, AlertCursorCodec | None, int, str | None, bool | None]:
    if type(repository) is not MonitoringRepository \
            or (codec is not None and type(codec) is not AlertCursorCodec):
        raise MonitoringQueryRefusal("exact repository and cursor codec required")
    if type(limit) is not int or limit < 1 or limit > MAX_LIMIT:
        raise MonitoringQueryRefusal("limit must be between 1 and 100")
    if assignment_id is not None and type(assignment_id) is not str:
        raise MonitoringQueryRefusal("assignment filter is invalid")
    if unread_only is not None and type(unread_only) is not bool:
        raise MonitoringQueryRefusal("unread filter is invalid")
    if repository.session.new or repository.session.dirty or repository.session.deleted:
        raise MonitoringQueryRefusal("read service refuses pending writes")
    if assignment_id is not None:
        repository.get_assignment(assignment_id)
    return repository, codec, limit, assignment_id, unread_only


def list_alert_inbox(
    repository: MonitoringRepository,
    codec: AlertCursorCodec,
    *,
    assignment_id: str | None = None,
    unread_only: bool | None = None,
    limit: int = DEFAULT_LIMIT,
    cursor: str | None = None,
) -> AlertInboxPage:
    repository, codec, limit, assignment_id, unread_only = _boundary(
        repository, codec, limit, assignment_id, unread_only,
    )
    position = None
    if cursor is not None:
        try:
            position = codec.decode(
                cursor, owner_id=repository.owner_id,
                assignment_id=assignment_id, unread_only=unread_only,
            )
        except MonitoringCursorRefusal as exc:
            raise MonitoringQueryRefusal("cursor is invalid") from exc
    statement = sa.select(MonitoringSignalAlertRow).join(
        MonitoringAlertAttentionStateRow,
        sa.and_(
            MonitoringAlertAttentionStateRow.owner_id == MonitoringSignalAlertRow.owner_id,
            MonitoringAlertAttentionStateRow.assignment_id == MonitoringSignalAlertRow.assignment_id,
            MonitoringAlertAttentionStateRow.alert_address == MonitoringSignalAlertRow.alert_address,
        ),
    ).where(MonitoringSignalAlertRow.owner_id == repository.owner_id)
    if assignment_id is not None:
        statement = statement.where(MonitoringSignalAlertRow.assignment_id == assignment_id)
    if unread_only is not None:
        statement = statement.where(MonitoringAlertAttentionStateRow.is_unread == unread_only)
    if position is not None:
        statement = statement.where(_before_cursor(position))
    statement = statement.order_by(
        MonitoringSignalAlertRow.event_at.desc(),
        MonitoringSignalAlertRow.alert_address.desc(),
    ).limit(limit + 1)
    with repository.session.no_autoflush:
        rows = repository.session.scalars(statement).all()
        alerts = tuple(_alert_from_row(row) for row in rows[:limit])
        items = tuple(AlertInboxItem(
            alert=alert,
            attention=repository.get_attention_state(alert.assignment_id, alert.address),
        ) for alert in alerts)
    next_cursor = None
    if len(rows) > limit and items:
        last = items[-1].alert
        next_cursor = codec.encode(
            owner_id=repository.owner_id,
            assignment_id=assignment_id,
            unread_only=unread_only,
            event_at=last.event_at,
            alert_address=last.address,
        )
    if repository.session.new or repository.session.dirty or repository.session.deleted:
        raise MonitoringQueryRefusal("read service changed session state")
    return AlertInboxPage(items, next_cursor)


def get_alert_inbox_item(
    repository: MonitoringRepository,
    *,
    assignment_id: str,
    alert_address: str,
) -> AlertInboxItem:
    repository, _codec, _limit, assignment_id, _unread = _boundary(
        repository, None,
        1, assignment_id, None,
    )
    try:
        alert = repository._alert(assignment_id, alert_address)
        attention = repository.get_attention_state(assignment_id, alert_address)
    except MonitoringNotFound:
        raise
    if repository.session.new or repository.session.dirty or repository.session.deleted:
        raise MonitoringQueryRefusal("read service changed session state")
    return AlertInboxItem(alert, attention)


__all__ = [
    "AlertInboxItem", "AlertInboxPage", "MonitoringQueryRefusal",
    "get_alert_inbox_item", "list_alert_inbox",
]
