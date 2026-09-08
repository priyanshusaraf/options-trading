"""Factory-built, unregistered GET-only monitoring Alerts API."""
from __future__ import annotations

import datetime as dt
import re
from typing import Callable, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.api.principal import Principal, get_principal, owner_id_for
from app.monitoring.cursor import AlertCursorCodec, MonitoringCursorRefusal
from app.monitoring.query_service import (
    AlertInboxItem,
    MonitoringQueryRefusal,
    get_alert_inbox_item,
    list_alert_inbox,
)
from app.monitoring.repository import MonitoringNotFound, MonitoringRepository


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_CONTENT_ADDRESS = re.compile(r"^sha256:[0-9a-f]{64}$")
_CURSOR = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")
_MAX_CURSOR_BYTES = 2048


class _ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MonitoringAlertRead(_ClosedModel):
    schema_version: Literal["monitoring-alert-read/1"] = Field(
        default="monitoring-alert-read/1", alias="schema"
    )
    alert_address: str
    assignment_id: str
    action: Literal["BUY", "SELL", "EXIT"]
    display_symbol: str
    previous_state: Literal["FLAT", "LONG", "SHORT"]
    target_state: Literal["FLAT", "LONG", "SHORT"]
    event_at: dt.datetime
    valid_until: dt.datetime
    freshness: Literal["FRESH", "STALE"]
    entry_reference_kind: str
    entry_reference_value: str
    entry_reference_currency: str
    stop_loss_basis: str
    stop_loss_authored_value: str
    stop_loss_units: str
    stop_loss_resolved_value: str
    take_profit_basis: str
    take_profit_authored_value: str
    take_profit_units: str
    take_profit_resolved_value: str
    is_unread: bool
    read_at: dt.datetime | None
    acknowledged_at: dt.datetime | None
    dismissed_at: dt.datetime | None


class MonitoringResearchProtectionRuleRead(_ClosedModel):
    basis: Literal["FRACTION_FROM_SIMULATED_ENTRY", "ATR_RATCHET_STOP"]
    fraction: float | None
    resolved_value: float | None
    definition_address: str


class MonitoringResearchProtectionRead(_ClosedModel):
    status: Literal["DISABLED", "UNRESOLVED", "RESOLVED"]
    rules: list[MonitoringResearchProtectionRuleRead]


class MonitoringResearchAlertRead(_ClosedModel):
    schema_version: Literal["monitoring-research-alert-read/1"] = Field(
        default="monitoring-research-alert-read/1", alias="schema")
    alert_address: str
    assignment_id: str
    monitoring_event_address: str
    strategy_id: str
    graph_version_address: str
    consumer_address: str
    action: Literal["BUY", "SELL", "EXIT"]
    display_symbol: str
    previous_state: Literal["FLAT", "LONG", "SHORT"]
    target_state: Literal["FLAT", "LONG", "SHORT"]
    simulated_position_state: Literal["FLAT", "LONG", "SHORT"]
    decision_kind: Literal["ENTER", "REVERSE", "EXIT"]
    event_at: dt.datetime
    valid_until: dt.datetime
    freshness: Literal["FRESH", "STALE"]
    entry_reference_kind: Literal["COMPLETED_EVENT_CLOSE"]
    entry_reference_value: str
    entry_reference_currency: str
    stop_loss: MonitoringResearchProtectionRead
    take_profit: MonitoringResearchProtectionRead
    is_unread: bool
    read_at: dt.datetime | None
    acknowledged_at: dt.datetime | None
    dismissed_at: dt.datetime | None
    last_sequence: int


class MonitoringAlertPage(_ClosedModel):
    schema_version: Literal["monitoring-alert-page/1"] = Field(
        default="monitoring-alert-page/1", alias="schema"
    )
    items: list[MonitoringAlertRead | MonitoringResearchAlertRead]
    next_cursor: str | None


class MonitoringAttributedAlertRead(MonitoringAlertRead):
    schema_version: Literal["monitoring-alert-read/2"] = Field(default="monitoring-alert-read/2", alias="schema")
    monitoring_event_address: str
    strategy_id: str
    graph_version_address: str
    last_sequence: int


class MonitoringAttributedAlertPage(_ClosedModel):
    schema_version: Literal["monitoring-alert-page/2"] = Field(default="monitoring-alert-page/2", alias="schema")
    items: list[MonitoringAttributedAlertRead | MonitoringResearchAlertRead]
    next_cursor: str | None


class MonitoringStoredReviewRead(_ClosedModel):
    review_address: str
    assignment_id: str
    monitoring_event_address: str
    disposition: Literal["CONFIRMED", "REJECTED"]
    reason_code: str
    note: str
    created_at: dt.datetime


class MonitoringReviewRead(_ClosedModel):
    schema_version: Literal["monitoring-review-read/1"] = Field(default="monitoring-review-read/1", alias="schema")
    review: MonitoringStoredReviewRead | None


def _stored_review(repository, assignment_id, alert_address, reviewer):
    alert = repository.get_alert(assignment_id, alert_address)
    try:
        review = repository.get_review(assignment_id, alert.monitoring_event_address, reviewer)
    except MonitoringNotFound:
        return None
    return MonitoringStoredReviewRead(review_address=review.address, assignment_id=review.assignment_id,
        monitoring_event_address=review.monitoring_event_address, disposition=review.disposition,
        reason_code=review.reason_code, note=review.note, created_at=review.created_at)


def _research_protection_read(evidence):
    return MonitoringResearchProtectionRead(status=evidence.status,
        rules=[MonitoringResearchProtectionRuleRead(basis=rule.basis, fraction=rule.fraction,
            resolved_value=rule.resolved_value, definition_address=rule.definition_address)
            for rule in evidence.rules])


def _research_read(item):
    alert, attention = item.alert, item.attention
    return MonitoringResearchAlertRead(alert_address=alert.address, assignment_id=alert.assignment_id,
        monitoring_event_address=alert.monitoring_event_address, strategy_id=alert.strategy_id,
        graph_version_address=alert.graph_version_address, consumer_address=alert.consumer_address,
        action=alert.action.value, display_symbol=alert.display_symbol,
        previous_state=alert.previous_state.value, target_state=alert.target_state.value,
        simulated_position_state=alert.simulated_position_state.value, decision_kind=alert.decision_kind,
        event_at=alert.event_at, valid_until=alert.valid_until, freshness=alert.freshness.value,
        entry_reference_kind=alert.entry_reference.kind.value, entry_reference_value=alert.entry_reference.value,
        entry_reference_currency=alert.entry_reference.currency,
        stop_loss=_research_protection_read(alert.stop_loss), take_profit=_research_protection_read(alert.take_profit),
        is_unread=attention.is_unread, read_at=attention.read_at, acknowledged_at=attention.acknowledged_at,
        dismissed_at=attention.dismissed_at, last_sequence=attention.last_sequence)


def _read(item: AlertInboxItem, *, attributed=False) -> MonitoringAlertRead | MonitoringAttributedAlertRead | MonitoringResearchAlertRead:
    from app.monitoring.research_event_contracts import ResearchSignalAlert
    if type(item.alert) is ResearchSignalAlert:
        return _research_read(item)
    alert, attention = item.alert, item.attention
    result = MonitoringAlertRead(
        alert_address=alert.address,
        assignment_id=alert.assignment_id,
        action=alert.action.value,
        display_symbol=alert.display_symbol,
        previous_state=alert.previous_state.value,
        target_state=alert.target_state.value,
        event_at=alert.event_at,
        valid_until=alert.valid_until,
        freshness=alert.freshness.value,
        entry_reference_kind=alert.entry_reference.kind.value,
        entry_reference_value=alert.entry_reference.value,
        entry_reference_currency=alert.entry_reference.currency,
        stop_loss_basis=alert.stop_loss.basis.value,
        stop_loss_authored_value=alert.stop_loss.authored_value,
        stop_loss_units=alert.stop_loss.units.value,
        stop_loss_resolved_value=alert.stop_loss.resolved_value,
        take_profit_basis=alert.take_profit.basis.value,
        take_profit_authored_value=alert.take_profit.authored_value,
        take_profit_units=alert.take_profit.units.value,
        take_profit_resolved_value=alert.take_profit.resolved_value,
        is_unread=attention.is_unread,
        read_at=attention.read_at,
        acknowledged_at=attention.acknowledged_at,
        dismissed_at=attention.dismissed_at,
    )
    if not attributed:
        return result
    return MonitoringAttributedAlertRead(**result.model_dump(exclude={"schema_version"}),
        monitoring_event_address=alert.monitoring_event_address, strategy_id=alert.strategy_id,
        graph_version_address=alert.graph_version_address, last_sequence=attention.last_sequence)


def _authenticated_owner(principal: Principal) -> str:
    """Accept only a durable authenticated browser/user-session principal."""
    if type(principal) is not Principal or principal.kind != "user" \
            or not principal.authenticated or not principal.user_id \
            or not principal.organization_id or not principal.session_id:
        raise HTTPException(status_code=401, detail="unauthorized")
    return owner_id_for(principal)


def _assignment(value: str | None) -> str | None:
    if value is not None and (
        type(value) is not str or not _IDENTIFIER.fullmatch(value)
    ):
        raise HTTPException(status_code=400, detail="invalid monitoring query")
    return value


def _alert_address(value: str) -> str:
    if type(value) is not str or not _CONTENT_ADDRESS.fullmatch(value):
        raise HTTPException(status_code=400, detail="invalid monitoring query")
    return value


def _cursor(value: str | None) -> str | None:
    if value is not None and (
        type(value) is not str
        or len(value.encode("utf-8")) > _MAX_CURSOR_BYTES
        or not _CURSOR.fullmatch(value)
    ):
        raise HTTPException(status_code=400, detail="invalid monitoring query")
    return value


def build_monitoring_read_router(
    *, sessionmaker: Callable, cursor_secret: bytes, attributed: bool = False,
) -> APIRouter:
    """Build dedicated routes without registering or defaulting shared state."""
    if not callable(sessionmaker) or type(attributed) is not bool:
        raise TypeError("monitoring sessionmaker must be callable")
    codec = AlertCursorCodec(cursor_secret)
    router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring-alerts"])

    @router.get("/alerts", response_model=MonitoringAlertPage | MonitoringAttributedAlertPage)
    def get_alerts(
        principal: Principal = Depends(get_principal),
        assignment_id: str | None = Query(default=None),
        unread_only: bool | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=100),
        cursor: str | None = Query(default=None),
    ) -> MonitoringAlertPage | MonitoringAttributedAlertPage:
        owner_id = _authenticated_owner(principal)
        assignment_id = _assignment(assignment_id)
        cursor = _cursor(cursor)
        try:
            with sessionmaker() as session:
                page = list_alert_inbox(
                    MonitoringRepository(session, owner_id=owner_id), codec,
                    assignment_id=assignment_id, unread_only=unread_only,
                    limit=limit, cursor=cursor,
                )
        except MonitoringNotFound as exc:
            raise HTTPException(status_code=404, detail="monitoring object not found") from exc
        except (MonitoringCursorRefusal, MonitoringQueryRefusal) as exc:
            raise HTTPException(status_code=400, detail="invalid monitoring query") from exc
        model = MonitoringAttributedAlertPage if attributed else MonitoringAlertPage
        return model(
            items=[_read(item, attributed=attributed) for item in page.items],
            next_cursor=page.next_cursor,
        )

    @router.get(
        "/assignments/{assignment_id}/alerts/{alert_address}",
        response_model=MonitoringAlertRead | MonitoringAttributedAlertRead | MonitoringResearchAlertRead,
    )
    def get_alert(
        assignment_id: str,
        alert_address: str,
        principal: Principal = Depends(get_principal),
    ) -> MonitoringAlertRead | MonitoringAttributedAlertRead | MonitoringResearchAlertRead:
        owner_id = _authenticated_owner(principal)
        assignment_id = _assignment(assignment_id)
        alert_address = _alert_address(alert_address)
        try:
            with sessionmaker() as session:
                item = get_alert_inbox_item(
                    MonitoringRepository(session, owner_id=owner_id),
                    assignment_id=assignment_id,
                    alert_address=alert_address,
                )
        except MonitoringNotFound as exc:
            raise HTTPException(status_code=404, detail="monitoring object not found") from exc
        except MonitoringQueryRefusal as exc:
            raise HTTPException(status_code=400, detail="invalid monitoring query") from exc
        return _read(item, attributed=attributed)

    @router.get("/assignments/{assignment_id}/alerts/{alert_address}/review", response_model=MonitoringReviewRead)
    def get_review(assignment_id: str, alert_address: str, principal: Principal = Depends(get_principal)) -> MonitoringReviewRead:
        owner_id = _authenticated_owner(principal)
        assignment_id, alert_address = _assignment(assignment_id), _alert_address(alert_address)
        try:
            with sessionmaker() as session:
                review = _stored_review(MonitoringRepository(session, owner_id=owner_id),
                                        assignment_id, alert_address, principal.user_id)
        except MonitoringNotFound as exc:
            raise HTTPException(status_code=404, detail="monitoring object not found") from exc
        return MonitoringReviewRead(review=review)

    return router


__all__ = [
    "MonitoringAlertPage", "MonitoringAlertRead", "build_monitoring_read_router",
]
