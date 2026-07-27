"""Journal service layer — CRUD + stats over journal.db. Every function takes
an explicit Session (no module-level session state) so it's testable against
a throwaway DB and safely callable from FastAPI's request-scoped session.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select

from app.journal.db import DEFAULT_BOOK_NAME
from app.journal.models import (
    JournalBias, JournalBook, JournalDay, JournalInstrument, JournalMissed,
    JournalNote, JournalTag, JournalTrade, JournalView,
)
from app.journal.pnl import net_pnl, unrealized_pnl

CURRENT_VIEW_NAME = "current"
BIAS_HORIZONS = ("6M", "1M")


# ── books (workbooks) ────────────────────────────────────────────────────
def default_book(s) -> JournalBook:
    """The fallback book every un-booked write lands in. Created on demand so a
    session opened against a DB that predates books still resolves one."""
    row = s.execute(select(JournalBook).where(JournalBook.is_default.is_(True))).scalar()
    if row is None:
        row = JournalBook(name=DEFAULT_BOOK_NAME, is_default=True,
                          created_at=dt.datetime.now())
        s.add(row)
        s.commit()
    return row


def resolve_book_id(s, book_id: int | None) -> int:
    """Caller-supplied book, or the default when omitted. Every write path goes
    through this so a row can never be created without a book."""
    if book_id is None:
        return default_book(s).id
    if s.get(JournalBook, book_id) is None:
        raise ValueError(f"unknown journal book {book_id}")
    return book_id


def create_book(s, *, name: str, description: str | None = None) -> JournalBook:
    b = JournalBook(name=name, description=description, created_at=dt.datetime.now())
    s.add(b)
    s.commit()
    return b


def list_books(s, *, include_archived: bool = False) -> list[JournalBook]:
    q = select(JournalBook).order_by(JournalBook.is_default.desc(), JournalBook.name)
    if not include_archived:
        q = q.where(JournalBook.archived_at.is_(None))
    return list(s.execute(q).scalars().all())


def archive_book(s, book_id: int) -> JournalBook:
    """Hide a book without deleting its entries. The default book is refused —
    it is where un-booked writes land, so archiving it would orphan them."""
    b = s.get(JournalBook, book_id)
    if b is None:
        raise ValueError(f"unknown journal book {book_id}")
    if b.is_default:
        raise ValueError("the default journal cannot be archived")
    b.archived_at = dt.datetime.now()
    s.commit()
    return b


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
              notes: str | None = None, view_id: int | None = None,
              book_id: int | None = None) -> JournalTrade:
    vid = view_id if view_id is not None else ensure_current_view(s).id
    t = JournalTrade(book_id=resolve_book_id(s, book_id),
                      instrument_symbol=symbol, direction=direction, lots=lots,
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
               notes: str | None = None,
               book_id: int | None = None) -> JournalMissed:
    m = JournalMissed(book_id=resolve_book_id(s, book_id),
                       instrument_symbol=symbol, direction=direction, seen_at=seen_at,
                       skip_reason=skip_reason, setup_tag=setup_tag,
                       hypothetical_entry=hypothetical_entry,
                       hypothetical_exit=hypothetical_exit, notes=notes)
    s.add(m)
    _upsert_tag(s, setup_tag)
    s.commit()
    return m


def list_trades(s, *, open_only: bool = False,
                book_id: int | None = None) -> list[JournalTrade]:
    """Trades in ONE book. `book_id=None` means the default book, matching the
    write paths — never 'every book', so a caller can't accidentally mix journals."""
    q = (select(JournalTrade).where(JournalTrade.book_id == resolve_book_id(s, book_id))
         .order_by(JournalTrade.entry_time.desc()))
    if open_only:
        q = q.where(JournalTrade.exit_time.is_(None))
    return list(s.execute(q).scalars().all())


def list_missed(s, *, book_id: int | None = None) -> list[JournalMissed]:
    return list(s.execute(
        select(JournalMissed)
        .where(JournalMissed.book_id == resolve_book_id(s, book_id))
        .order_by(JournalMissed.seen_at.desc())).scalars().all())


def trade_unrealized(trade: JournalTrade, inst: JournalInstrument, last_price: float) -> float:
    return unrealized_pnl(trade.direction, trade.entry_price, last_price,
                           lots=trade.lots, lot_size=inst.lot_size, multiplier=inst.multiplier)


def _trade_net(t: JournalTrade, inst: JournalInstrument) -> float | None:
    if t.exit_price is None:
        return None
    return net_pnl(t.direction, t.entry_price, t.exit_price, lots=t.lots,
                    lot_size=inst.lot_size, multiplier=inst.multiplier,
                    manual_net_pnl=t.manual_net_pnl)


def stats(s, *, book_id: int | None = None) -> dict:
    trades = list_trades(s, book_id=book_id)
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

    missed = list_missed(s, book_id=book_id)
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


def upsert_day(s, *, entry_date, market_view=None, result=None,
               book_id: int | None = None) -> JournalDay:
    """Create or update the day row for ONE book. Only non-None fields overwrite,
    so saving the narrative never wipes the result and vice versa. Keyed on
    (book, date): two journals can each hold their own view of the same day."""
    now = dt.datetime.now()
    bid = resolve_book_id(s, book_id)
    row = s.get(JournalDay, (bid, entry_date))
    if row is None:
        row = JournalDay(book_id=bid, entry_date=entry_date, market_view=market_view,
                         result=result, created_at=now, updated_at=now)
        s.add(row)
    else:
        if market_view is not None:
            row.market_view = market_view
        if result is not None:
            row.result = result
        row.updated_at = now
    s.commit()
    return row


def add_note(s, *, body, noted_at, instrument_symbol=None,
             book_id: int | None = None) -> JournalNote:
    note = JournalNote(book_id=resolve_book_id(s, book_id), body=body,
                       noted_at=noted_at, instrument_symbol=instrument_symbol)
    s.add(note)
    s.commit()
    return note


def delete_note(s, note_id) -> bool:
    row = s.get(JournalNote, note_id)
    if row is None:
        return False
    s.delete(row)
    s.commit()
    return True


def list_notes(s, *, book_id: int | None = None) -> list[JournalNote]:
    return list(s.execute(
        select(JournalNote).where(JournalNote.book_id == resolve_book_id(s, book_id))
        .order_by(JournalNote.noted_at.desc())).scalars().all())


def seed_bias(s) -> None:
    changed = False
    for h in BIAS_HORIZONS:
        if s.get(JournalBias, h) is None:
            s.add(JournalBias(horizon=h, stance=None, note=None, updated_at=dt.datetime.now()))
            changed = True
    if changed:
        s.commit()


def list_bias(s) -> list[JournalBias]:
    return list(s.execute(
        select(JournalBias).order_by(JournalBias.horizon.desc())).scalars().all())


def upsert_bias(s, *, horizon, stance=None, note=None) -> JournalBias:
    row = s.get(JournalBias, horizon)
    if row is None:
        raise ValueError(f"unknown bias horizon {horizon}")
    row.stance = stance
    row.note = note
    row.updated_at = dt.datetime.now()
    s.commit()
    return row


def _note_row(nrow: JournalNote) -> dict:
    return {"id": nrow.id, "noted_at": nrow.noted_at.isoformat(),
            "body": nrow.body, "instrument_symbol": nrow.instrument_symbol}


def _trade_row(t: JournalTrade, inst: JournalInstrument | None) -> dict:
    return {"id": t.id, "instrument_symbol": t.instrument_symbol,
            "direction": t.direction, "lots": t.lots, "entry_price": t.entry_price,
            "entry_time": t.entry_time.isoformat(), "exit_price": t.exit_price,
            "exit_time": t.exit_time.isoformat() if t.exit_time else None,
            "setup_tag": t.setup_tag,
            "net_pnl": _trade_net(t, inst) if inst else None}


def _missed_row(m: JournalMissed) -> dict:
    return {"id": m.id, "instrument_symbol": m.instrument_symbol,
            "direction": m.direction, "seen_at": m.seen_at.isoformat(),
            "setup_tag": m.setup_tag, "skip_reason": m.skip_reason}


def feed(s, *, limit: int = 60, book_id: int | None = None) -> dict:
    """The day-grouped feed for ONE book (default book when unspecified)."""
    bid = resolve_book_id(s, book_id)
    insts = {r.symbol: r for r in s.execute(select(JournalInstrument)).scalars().all()}
    trades = list_trades(s, book_id=bid)
    notes = list_notes(s, book_id=bid)
    missed = list_missed(s, book_id=bid)
    day_rows = {d.entry_date: d for d in s.execute(
        select(JournalDay).where(JournalDay.book_id == bid)).scalars().all()}

    dates = set(day_rows)
    dates.update(t.entry_time.date() for t in trades)
    dates.update(nrow.noted_at.date() for nrow in notes)
    dates.update(m.seen_at.date() for m in missed)

    out_days = []
    for d in sorted(dates, reverse=True)[:limit]:
        drow = day_rows.get(d)
        d_trades = [t for t in trades if t.entry_time.date() == d]
        net = 0.0
        for t in d_trades:
            tn = _trade_net(t, insts.get(t.instrument_symbol)) if insts.get(t.instrument_symbol) else None
            if tn is not None:
                net += tn
        out_days.append({
            "date": d.isoformat(),
            "market_view": drow.market_view if drow else None,
            "result": drow.result if drow else None,
            "net_pnl": round(net, 2),
            "notes": [_note_row(nr) for nr in notes if nr.noted_at.date() == d],
            "trades": [_trade_row(t, insts.get(t.instrument_symbol)) for t in d_trades],
            "missed": [_missed_row(m) for m in missed if m.seen_at.date() == d],
        })

    closed = [t for t in trades if t.exit_price is not None]
    net_total, wins = 0.0, 0
    for t in closed:
        tn = _trade_net(t, insts.get(t.instrument_symbol)) if insts.get(t.instrument_symbol) else None
        if tn is not None:
            net_total += tn
            wins += 1 if tn > 0 else 0
    stats_row = {
        "net_pnl": round(net_total, 2),
        "win_rate": round(wins / len(closed), 3) if closed else None,
        "days_journaled": len(day_rows),
        "trades": len(closed),
    }

    bias_rows = [{"horizon": b.horizon, "stance": b.stance, "note": b.note,
                  "updated_at": b.updated_at.isoformat()} for b in list_bias(s)]
    return {"bias": bias_rows, "stats": stats_row, "days": out_days}
