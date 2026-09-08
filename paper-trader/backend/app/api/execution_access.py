"""The HTTP boundary for the one local execution cell.

The process still hosts one runner during Phase 1.  That runner is not an
implicit default account: a request may use it only after the authenticated
organization owns its active broker account in SQL.  Every failure is the same
closed response so a foreign account cannot be distinguished from no local
cell.
"""
from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy import select

from app.api.principal import Principal, owner_id_for
from app.db.models import AccountExecutionLease, BrokerAccount
from app.db.session import SessionLocal
from app.execution.leases import LeaseRepository


def _refuse_v0_execution() -> None:
    from app.core.config import get_settings
    from app.core.release_profile import is_v0_profile
    if is_v0_profile(get_settings().release_profile):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "V0_CAPABILITY_UNAVAILABLE",
                "release_profile": "v0_research_signal",
                "capability": "execution",
                "message": "execution is unavailable in the V0 research/signal profile",
            },
        )


def durable_execution_account(principal: Principal, requested: str | None = None) -> str:
    """Resolve an owner-scoped account without consulting process-local runner state."""
    _refuse_v0_execution()
    owner_id = owner_id_for(principal)
    with SessionLocal() as session:
        statement = select(BrokerAccount.broker_account_id).where(
            BrokerAccount.owner_id == owner_id, BrokerAccount.status == "active")
        if requested:
            statement = statement.where(BrokerAccount.broker_account_id == requested)
        rows = list(session.scalars(statement.order_by(BrokerAccount.broker_account_id).limit(2)))
    if len(rows) != 1:
        raise HTTPException(status_code=404, detail="execution unavailable")
    return rows[0]


def durable_execution_status(principal: Principal, requested: str | None = None) -> dict:
    _refuse_v0_execution()
    account_id = durable_execution_account(principal, requested)
    status = LeaseRepository(SessionLocal).status(
        owner_id=owner_id_for(principal), broker_account_id=account_id)
    if status is None:
        raise HTTPException(status_code=404, detail="execution unavailable")
    return status


def local_execution_cell(request: Request, principal: Principal, *, mutation: bool = False):
    """Return the local runner only for its owning active account.

    `runner` is inspected solely to name the one process-local cell.  It never
    supplies an owner or account identity to a request: the SQL predicate is
    bound to the authenticated principal before the runner is returned.
    """
    _refuse_v0_execution()
    if not principal.is_owner and mutation:
        raise HTTPException(status_code=403, detail="forbidden")
    if not principal.is_owner and principal.role not in {"viewer", "member", "admin"}:
        raise HTTPException(status_code=403, detail="forbidden")

    runner = getattr(request.app.state, "runner", None)
    if runner is None:
        raise HTTPException(status_code=404, detail="execution unavailable")
    owner_id = owner_id_for(principal)
    with SessionLocal() as session:
        account = session.scalar(select(BrokerAccount.broker_account_id).where(
            BrokerAccount.owner_id == owner_id,
            BrokerAccount.broker_account_id == runner.broker_account_id,
            BrokerAccount.status == "active",
        ))
    if account is None or runner.owner_id != owner_id:
        raise HTTPException(status_code=404, detail="execution unavailable")
    token = (getattr(runner, "execution_lease_token", None)
             or getattr(getattr(runner, "broker", None), "execution_lease_token", None))
    with SessionLocal() as session:
        durable = session.get(AccountExecutionLease, (owner_id, runner.broker_account_id))
        if durable is not None and (token is None
                or token.fence_epoch != durable.fence_epoch
                or token.cell_id != durable.cell_id
                or token.worker_id != durable.worker_id
                or durable.state != "active"):
            # A replica may host an old local runner, but it never becomes shared authority,
            # including reads which would prime private process state or a WebSocket.
            raise HTTPException(status_code=404, detail="execution unavailable")
    return runner
