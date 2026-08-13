"""Bounded durable projection reloads for replica-local event delivery."""
from __future__ import annotations

from sqlalchemy import select

from app.events.outbox import PrincipalScope


_INVALIDATION_ONLY = frozenset({
    "backtest_runs",
    "connections",
    "execution_lifecycle",
    "money_book",
    "published_graphs",
    "research_findings",
    "research_promotions",
    "research_runs",
    "research_specs",
    "runtime_config",
    "universe_preferences",
    "ledger_artifact",
    "manual_fill",
})


def reload_durable_projection(
    scope: PrincipalScope | None,
    projection: str,
    *,
    execution_sessionmaker,
    research_sessionmaker=None,
    ledger_sessionmaker=None,
) -> dict:
    """Reload a scoped read model, or return an explicit typed invalidation.

    An invalidation tells the eventual frontend which durable endpoint to fetch.  It
    never substitutes lease state for an unrelated projection.
    """
    if scope is None:
        return {"projection": projection, "kind": "durable_invalidation"}
    if projection == "execution_status":
        if scope.broker_account_id is None:
            return {"projection": projection, "kind": "durable_invalidation"}
        from app.execution.leases import LeaseRepository
        return LeaseRepository(execution_sessionmaker).status(
            owner_id=scope.owner_id,
            broker_account_id=scope.broker_account_id,
        ) or {"projection": projection, "kind": "durable_invalidation"}
    if projection == "deployments":
        if scope.broker_account_id is None:
            return {"projection": projection, "kind": "durable_invalidation"}
        from app.db.models import Deployment
        with execution_sessionmaker() as session:
            rows = list(session.scalars(select(Deployment).where(
                Deployment.owner_id == scope.owner_id,
                Deployment.broker_account_id == scope.broker_account_id,
            ).order_by(Deployment.id).limit(200)))
        return {"projection": projection, "deployments": [
            {"id": row.id, "name": row.name, "status": row.status, "armed": row.armed}
            for row in rows
        ]}
    if projection == "research_operation" and research_sessionmaker is not None:
        from research.domain.models import ResearchOperation
        with research_sessionmaker() as session:
            rows = list(session.execute(select(
                ResearchOperation.operation_id, ResearchOperation.status,
                ResearchOperation.stage,
            ).where(ResearchOperation.owner_id == scope.owner_id)
                .order_by(ResearchOperation.created_at.desc()).limit(32)))
        return {"projection": projection, "operations": [
            {"operation_id": row[0], "status": row[1], "stage": row[2]}
            for row in rows
        ]}
    if projection == "ledger_snapshot" and ledger_sessionmaker is not None:
        if scope.broker_account_id is None:
            return {"projection": projection, "kind": "durable_invalidation"}
        from app.ledger.service import read_snapshot
        got = read_snapshot(
            ledger_sessionmaker, owner_id=scope.owner_id,
            broker_account_id=scope.broker_account_id,
        )
        return ({"projection": projection, "version": got[0]} if got else
                {"projection": projection, "kind": "durable_invalidation"})
    if projection in _INVALIDATION_ONLY:
        return {"projection": projection, "kind": "durable_invalidation"}
    return {"projection": projection, "kind": "durable_invalidation"}
