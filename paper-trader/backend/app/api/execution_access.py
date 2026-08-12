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
from app.db.models import BrokerAccount
from app.db.session import SessionLocal


def local_execution_cell(request: Request, principal: Principal, *, mutation: bool = False):
    """Return the local runner only for its owning active account.

    `runner` is inspected solely to name the one process-local cell.  It never
    supplies an owner or account identity to a request: the SQL predicate is
    bound to the authenticated principal before the runner is returned.
    """
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
    return runner
