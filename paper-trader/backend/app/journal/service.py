"""Journal service layer — CRUD + stats over journal.db. Every function takes
an explicit Session (no module-level session state) so it's testable against
a throwaway DB and safely callable from FastAPI's request-scoped session.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.journal.models import JournalInstrument, JournalMissed, JournalTag, JournalTrade, JournalView
from app.journal.pnl import net_pnl, unrealized_pnl

CURRENT_VIEW_NAME = "current"


def ensure_current_view(s) -> JournalView:
    """The live (non-retired) view trades bind to when the caller doesn't pick
    one explicitly. Auto-creates a 'current' view on first use; idempotent."""
    row = s.execute(
        select(JournalView).where(JournalView.retired_at.is_(None))
        .order_by(JournalView.created_at.desc())
    ).scalars().first()
    if row is not None:
        return row
    name = CURRENT_VIEW_NAME
    suffix = 2
    while s.execute(select(JournalView).where(JournalView.name == name)).scalars().first() is not None:
        name = f"{CURRENT_VIEW_NAME}-{suffix}"
        suffix += 1
    row = JournalView(name=name, created_at=dt.datetime.now())
    s.add(row)
    s.commit()
    return row


def _upsert_tag(s, tag: str | None) -> None:
    if not tag:
        return
    if s.get(JournalTag, tag) is None:
        s.add(JournalTag(name=tag))
        s.commit()


def add_trade(s, *, symbol: str, direction: str, lots: int, entry_price: float,
              entry_time: dt.datetime, setup_tag: str | None = None,
              notes: str | None = None, view_id: int | None = None) -> JournalTrade:
    vid = view_id if view_id is not None else ensure_current_view(s).id
    t = JournalTrade(instrument_symbol=symbol, direction=direction, lots=lots,
                      entry_price=entry_price, entry_time=entry_time, view_id=vid,
                      setup_tag=setup_tag, notes=notes)
    s.add(t)
    _upsert_tag(s, setup_tag)
    s.commit()
    return t


def close_trade(s, trade_id: int, *, exit_price: float, exit_time: dt.datetime,
                 manual_net_pnl: float | None = None) -> JournalTrade:
    t = s.get(JournalTrade, trade_id)
    if t is None:
        raise ValueError(f"no journal trade with id {trade_id}")
    t.exit_price, t.exit_time = exit_price, exit_time
    t.manual_net_pnl = manual_net_pnl
    s.commit()
    return t


def add_missed(s, *, symbol: str, direction: str, seen_at: dt.datetime,
               skip_reason: str, setup_tag: str | None = None,
               hypothetical_entry: float | None = None,
               hypothetical_exit: float | None = None,
               notes: str | None = None) -> JournalMissed:
    m = JournalMissed(instrument_symbol=symbol, direction=direction, seen_at=seen_at,
                       skip_reason=skip_reason, setup_tag=setup_tag,
                       hypothetical_entry=hypothetical_entry,
                       hypothetical_exit=hypothetical_exit, notes=notes)
    s.add(m)
    _upsert_tag(s, setup_tag)
    s.commit()
    return m


def list_trades(s, *, open_only: bool = False) -> list[JournalTrade]:
    q = select(JournalTrade).order_by(JournalTrade.entry_time.desc())
    if open_only:
        q = q.where(JournalTrade.exit_time.is_(None))
    return list(s.execute(q).scalars().all())


def list_missed(s) -> list[JournalMissed]:
    return list(s.execute(select(JournalMissed).order_by(JournalMissed.seen_at.desc())).scalars().all())


def trade_unrealized(trade: JournalTrade, inst: JournalInstrument, last_price: float) -> float:
    return unrealized_pnl(trade.direction, trade.entry_price, last_price,
                           lots=trade.lots, lot_size=inst.lot_size, multiplier=inst.multiplier)


def _trade_net(t: JournalTrade, inst: JournalInstrument) -> float | None:
    if t.exit_price is None:
        return None
    return net_pnl(t.direction, t.entry_price, t.exit_price, lots=t.lots,
                    lot_size=inst.lot_size, multiplier=inst.multiplier,
                    manual_net_pnl=t.manual_net_pnl)


def stats(s) -> dict:
    trades = list_trades(s)
    insts = {r.symbol: r for r in s.execute(select(JournalInstrument)).scalars().all()}
    views = {r.id: r.name for r in s.execute(select(JournalView)).scalars().all()}

    by_tag: dict[str, dict] = {}
    by_view: dict[str, dict] = {}
    for t in trades:
        inst = insts.get(t.instrument_symbol)
        net = _trade_net(t, inst) if inst else None
        if net is None:
            continue  # still open — excluded from realized stats
        tag = t.setup_tag or "untagged"
        row = by_tag.setdefault(tag, {"trades": 0, "wins": 0, "net_pnl": 0.0})
        row["trades"] += 1
        row["wins"] += 1 if net > 0 else 0
        row["net_pnl"] += net
        vname = views.get(t.view_id, "unknown")
        vrow = by_view.setdefault(vname, {"trades": 0, "net_pnl": 0.0})
        vrow["trades"] += 1
        vrow["net_pnl"] += net

    missed = list_missed(s)
    hyp_total = 0.0
    for m in missed:
        if m.hypothetical_entry is None or m.hypothetical_exit is None:
            continue
        inst = insts.get(m.instrument_symbol)
        if inst is None:
            continue
        hyp_total += net_pnl(m.direction, m.hypothetical_entry, m.hypothetical_exit,
                              lots=1, lot_size=inst.lot_size, multiplier=inst.multiplier)

    return {
        "by_tag": by_tag,
        "by_view": by_view,
        "missed_summary": {"count": len(missed), "hypothetical_net_pnl": round(hyp_total, 2)},
    }
