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

import dataclasses
import json
from collections import defaultdict

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


@dataclasses.dataclass
class Proposal:
    """A new watchlist's bid to run its strategy on `instrument_key`. `score` is the
    instrument's validated performance under that strategy (e.g. its DSR) — the tie-
    breaker when two new watchlists want the same instrument."""
    watchlist_id: int
    instrument_key: str
    score: float


@dataclasses.dataclass
class Resolution:
    assign: dict          # instrument_key -> winning watchlist_id (to write)
    rejected: list        # [{instrument, watchlist_id, reason}]


def resolve_conflicts(current_membership: dict, proposals: list) -> Resolution:
    """Decide which proposals win, given the instruments already spoken for.

    `current_membership` maps instrument_key -> its current watchlist_id (the
    incumbents). Incumbency is absolute: an instrument already in a watchlist is never
    reassigned by a proposal (it keeps running its existing strategy), however well the
    newcomer scores. Among competing NON-incumbent proposals for the same instrument,
    the highest `score` wins; ties break to the lower watchlist id for determinism."""
    assign: dict = {}
    rejected: list = []
    by_inst: dict = defaultdict(list)
    for p in proposals:
        by_inst[p.instrument_key].append(p)

    for inst, props in by_inst.items():
        if inst in current_membership:
            for p in props:                                  # incumbent untouched
                rejected.append({"instrument": inst, "watchlist_id": p.watchlist_id,
                                 "reason": "incumbent"})
            continue
        winner = max(props, key=lambda p: (p.score, -p.watchlist_id))
        assign[inst] = winner.watchlist_id
        for p in props:
            if p is not winner:
                rejected.append({"instrument": inst, "watchlist_id": p.watchlist_id,
                                 "reason": "lost dispute"})
    return Resolution(assign, rejected)


def apply_resolution(session, resolution: Resolution) -> None:
    """Write the winning assignments. Only the `assign` set is touched — incumbents and
    losers are never moved, so applying a resolution is safe to replay."""
    for instrument_key, watchlist_id in resolution.assign.items():
        assign_instrument(session, instrument_key, watchlist_id)


def membership_map(session) -> dict:
    """`{instrument_key: watchlist_id}` for every assigned instrument — the incumbency
    map the deploy bridge feeds to conflict resolution."""
    return {m.instrument_key: m.watchlist_id
            for m in session.scalars(select(WatchlistMembership))}


def in_watchlist_keys(session) -> set:
    """Every instrument committed to a watchlist (any status). The research plane treats
    these as blacklisted for strategy development (bar the always-allowed sandbox)."""
    return set(session.scalars(select(WatchlistMembership.instrument_key)))


def write_research_snapshot(session, path: str) -> dict:
    """Export a read-only snapshot of watchlist membership for the research plane to
    read. Deliberately a plain file: the research process must never open this DB, so it
    consumes the export instead of importing the execution session."""
    snap = {"in_watchlists": sorted(in_watchlist_keys(session))}
    with open(path, "w") as f:
        json.dump(snap, f)
    return snap


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
