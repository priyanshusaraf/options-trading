"""Strategy archive/lifecycle service.

Every strategy that enters the pipeline gets a record and moves through a small state
machine. The transitions are deliberately constrained so the archive stays meaningful
(you can't jump a candidate straight to probation), but RETIREMENT IS NOT THE END:
a retired strategy can be revived to `candidate` (re-test it) or `running` (redeploy it),
because a strategy that failed in one regime or on one universe may earn its keep later
or elsewhere.

    candidate ── running ⇄ probation ⇄ on_hold ── retired ──▶ (revive)
                   └────────────────────────────────┘

Session-injected, like the watchlist service.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.db.models import StrategyLifecycle

STATUSES = ("candidate", "running", "probation", "on_hold", "retired")

# Allowed transitions. Retirement is revivable (retired -> candidate|running).
_TRANSITIONS: dict[str, set] = {
    "candidate": {"running", "retired"},
    "running": {"probation", "on_hold", "retired"},
    "probation": {"running", "on_hold", "retired"},
    "on_hold": {"running", "retired"},
    "retired": {"candidate", "running"},
}


def get(session, strategy_key: str, *, owner_id: str) -> StrategyLifecycle | None:
    return session.scalars(
        select(StrategyLifecycle).where(StrategyLifecycle.owner_id == owner_id,
                                        StrategyLifecycle.strategy_key == strategy_key)
    ).one_or_none()


def record_strategy(session, strategy_key: str, *, owner_id: str, source: str = "builtin",
                    status: str = "candidate", note: str = "") -> StrategyLifecycle:
    """Idempotently enter a strategy into the archive. If it already exists, the existing
    record is returned unchanged (use `set_status` to transition it)."""
    existing = get(session, strategy_key, owner_id=owner_id)
    if existing is not None:
        return existing
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}")
    rec = StrategyLifecycle(owner_id=owner_id, strategy_key=strategy_key, source=source,
                            status=status, note=note)
    session.add(rec)
    session.flush()
    return rec


def set_status(session, strategy_key: str, status: str, *, owner_id: str, note: str | None = None,
               deployed_watchlist_id: int | None = None, last_dsr: float | None = None
               ) -> StrategyLifecycle:
    """Transition a strategy to `status`, rejecting a move the lifecycle does not allow."""
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r}")
    rec = get(session, strategy_key, owner_id=owner_id)
    if rec is None:
        raise ValueError(f"strategy {strategy_key!r} is not in the archive")
    if status != rec.status and status not in _TRANSITIONS[rec.status]:
        raise ValueError(f"illegal transition {rec.status!r} -> {status!r} for {strategy_key!r}")
    rec.status = status
    if note is not None:
        rec.note = note
    if deployed_watchlist_id is not None:
        from app.db.models import Watchlist
        if session.scalars(select(Watchlist).where(Watchlist.owner_id == owner_id,
                                                   Watchlist.id == deployed_watchlist_id)).one_or_none() is None:
            raise ValueError(f"no watchlist with id {deployed_watchlist_id}")
        rec.deployed_watchlist_id = deployed_watchlist_id
    if last_dsr is not None:
        rec.last_dsr = last_dsr
    rec.updated_at = dt.datetime.now()
    session.flush()
    return rec


def by_status(session, status: str, *, owner_id: str) -> list:
    return list(session.scalars(
        select(StrategyLifecycle).where(StrategyLifecycle.owner_id == owner_id,
                                        StrategyLifecycle.status == status)
        .order_by(StrategyLifecycle.strategy_key)))


def list_archive(session, *, owner_id: str) -> list[dict]:
    return [r.to_dict() for r in session.scalars(
        select(StrategyLifecycle).where(StrategyLifecycle.owner_id == owner_id)
        .order_by(StrategyLifecycle.strategy_key))]
