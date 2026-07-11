"""Watchlist service — the portfolio-organising layer over the tradable universe.

A watchlist binds one strategy to a set of instruments. The engine asks
`effective_strategy_map` for the per-instrument strategy an *active* watchlist
dictates; an instrument in no (active) watchlist falls through to its per-instrument
default, so a system with no watchlists behaves exactly as before.

Every function takes an explicit `session` (no module-level engine binding) so the
layer is trivially testable and never opens a second connection to the live ledger.
Membership is keyed by `instrument_key`, so assigning an instrument that already
belongs elsewhere MOVES it — an instrument is always in at most one watchlist.
"""
from __future__ import annotations

from sqlalchemy import select

from app.db.models import Watchlist, WatchlistMembership


def create_watchlist(session, name: str, strategy_key: str, *, status: str = "active",
                     interval: str | None = None, notes: str = "") -> Watchlist:
    w = Watchlist(name=name, strategy_key=strategy_key, status=status,
                  interval=interval, notes=notes)
    session.add(w)
    session.flush()   # populate w.id without forcing the caller's commit
    return w


def get_watchlist(session, name: str) -> Watchlist | None:
    return session.scalars(select(Watchlist).where(Watchlist.name == name)).one_or_none()


def assign_instrument(session, instrument_key: str, watchlist_id: int) -> WatchlistMembership:
    """Assign (or MOVE) an instrument into `watchlist_id`. Idempotent per instrument:
    the membership PK is the instrument, so a re-assign updates in place."""
    m = session.get(WatchlistMembership, instrument_key)
    if m is None:
        m = WatchlistMembership(instrument_key=instrument_key, watchlist_id=watchlist_id)
        session.add(m)
    else:
        m.watchlist_id = watchlist_id
    session.flush()
    return m


def unassign_instrument(session, instrument_key: str) -> bool:
    m = session.get(WatchlistMembership, instrument_key)
    if m is None:
        return False
    session.delete(m)
    session.flush()
    return True


def watchlist_of(session, instrument_key: str) -> Watchlist | None:
    m = session.get(WatchlistMembership, instrument_key)
    return session.get(Watchlist, m.watchlist_id) if m else None


def effective_strategy_map(session) -> dict[str, str]:
    """`{instrument_key: strategy_key}` for every instrument in an ACTIVE watchlist.
    This is what the engine overlays onto its per-instrument strategy resolution;
    paused/archived watchlists contribute nothing (they do not trade)."""
    rows = session.execute(
        select(WatchlistMembership.instrument_key, Watchlist.strategy_key)
        .join(Watchlist, WatchlistMembership.watchlist_id == Watchlist.id)
        .where(Watchlist.status == "active")
    ).all()
    return {key: strat for key, strat in rows}


def list_watchlists(session) -> list[dict]:
    """Every watchlist with its members — the read model for the UI."""
    members: dict[int, list[str]] = {}
    for m in session.scalars(select(WatchlistMembership)):
        members.setdefault(m.watchlist_id, []).append(m.instrument_key)
    out = []
    for w in session.scalars(select(Watchlist).order_by(Watchlist.id)):
        d = w.to_dict()
        d["instruments"] = sorted(members.get(w.id, []))
        out.append(d)
    return out
