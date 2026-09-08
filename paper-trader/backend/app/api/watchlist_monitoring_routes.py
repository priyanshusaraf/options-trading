"""Authenticated row settings and result reads for the instrument watchlist."""
from __future__ import annotations

import datetime as dt

from fastapi import Depends, HTTPException, Query

from app.api.principal import Principal, get_principal, owner_id_for
from app.api.static_scope_routes import TypedMember, require_static_scopes
from app.core.static_scopes import ScopeConflict, ScopeInvalid, ScopeNotFound
from app.db.session import SessionLocal
from app.monitoring.repository import MonitoringPersistenceError
from app.monitoring.watchlist_config import ClosedModel, WatchlistCommand, WatchlistContext
from app.monitoring.watchlist_query import read_watchlist_rows, watchlist_row
from app.monitoring.watchlist_store import (
    WatchlistMonitoringConflict, WatchlistMonitoringUnavailable, write_watchlist_configuration,
)
from pydantic import Field, ValidationError


class RowWrite(ClosedModel):
    context: WatchlistContext
    member: TypedMember
    command: WatchlistCommand
    request_id: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")


def _owner(principal):
    if type(principal) is not Principal or principal.kind != "user" or not principal.authenticated:
        raise HTTPException(401, detail="unauthorized")
    if not principal.user_id or not principal.session_id or not principal.organization_id:
        raise HTTPException(401, detail="unauthorized")
    return owner_id_for(principal)


def _failure(exc):
    if isinstance(exc, ScopeNotFound):
        return HTTPException(404, detail={"code": "WATCHLIST_MONITORING_NOT_FOUND", "message": "Watchlist not found."})
    if isinstance(exc, (ScopeConflict, WatchlistMonitoringConflict)):
        return HTTPException(409, detail={"code": "WATCHLIST_MONITORING_CONFLICT", "message": str(exc)})
    if isinstance(exc, WatchlistMonitoringUnavailable):
        return HTTPException(422, detail={"code": "WATCHLIST_MONITORING_UNAVAILABLE", "message": str(exc)})
    return HTTPException(422, detail={"code": "WATCHLIST_MONITORING_UNAVAILABLE",
        "message": "Check the saved strategy, instrument and timeframe, then refresh this row."})


def get_watchlist_rows(project_id: str, scope_id: str,
        scope_revision: int = Query(ge=1), scope_address: str = Query(), membership_address: str = Query(),
        principal: Principal = Depends(get_principal)):
    owner = _owner(principal)
    try:
        context = WatchlistContext(project_id=project_id, scope_id=scope_id, scope_revision=scope_revision,
            scope_address=scope_address, membership_address=membership_address)
        with SessionLocal() as session:
            return read_watchlist_rows(session, owner_id=owner, context=context, now=dt.datetime.now(dt.UTC))
    except (ScopeNotFound, ScopeConflict, ScopeInvalid, WatchlistMonitoringConflict,
            WatchlistMonitoringUnavailable, MonitoringPersistenceError, ValidationError) as exc:
        raise _failure(exc) from exc


def post_watchlist_row(project_id: str, scope_id: str, body: RowWrite,
        principal: Principal = Depends(get_principal)):
    owner = _owner(principal)
    if (project_id, scope_id) != (body.context.project_id, body.context.scope_id):
        raise HTTPException(422, detail={"code": "WATCHLIST_MONITORING_INVALID", "message": "Watchlist context differs."})
    now = dt.datetime.now(dt.UTC)
    try:
        with SessionLocal.begin() as session:
            configuration = write_watchlist_configuration(session, owner_id=owner,
                created_by=principal.user_id, context=body.context, member=body.member.model_dump(),
                command=body.command, request_id=body.request_id, now=now)
            return {"schema": "watchlist-monitoring-row/1", "context": body.context.model_dump(),
                "row": watchlist_row(session, configuration.member_key, configuration, editable=True, now=now)}
    except (ScopeNotFound, ScopeConflict, ScopeInvalid, WatchlistMonitoringConflict,
            WatchlistMonitoringUnavailable, MonitoringPersistenceError, ValidationError) as exc:
        raise _failure(exc) from exc


def install_routes(router):
    path = "/projects/{project_id}/static-scopes/{scope_id}/monitoring-rows"
    for method, endpoint in (("GET", get_watchlist_rows), ("POST", post_watchlist_row)):
        router.add_api_route(path, endpoint, methods=[method], dependencies=[Depends(require_static_scopes)])
