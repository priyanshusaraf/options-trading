"""REST surface for the trade journal — fully isolated from the execution
engine's routes/DB. Every handler opens its own journal.db session and closes
it; there is no shared session with app.db.session.
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.journal import service
from app.journal.config import journal_db_path
from app.journal.db import init_journal_db, make_engine, make_sessionmaker
from app.journal.models import JournalInstrument, JournalTrade, JournalView
from app.journal.schemas import (
    AddMissedRequest, AddNoteRequest, AddTradeRequest, AddViewRequest,
    CloseTradeRequest, UpsertBiasRequest, UpsertDayRequest,
)

router = APIRouter(prefix="/api/journal", tags=["journal"])

# Own MINI-contract specs — deliberately separate from app.core.instruments
# (the bot's universe carries full-size CRUDEOIL/NATURALGAS, wrong multipliers
# for the owner's manual minis). Verify lot sizes against the current Kite
# instrument dump before trusting P&L on a newly-added symbol.
SEED_INSTRUMENTS = [
    dict(symbol="GOLDM", exchange="MCX", lot_size=10, tick_size=1.0, multiplier=1.0),
    dict(symbol="SILVERM", exchange="MCX", lot_size=5, tick_size=1.0, multiplier=1.0),
    dict(symbol="CRUDEOILM", exchange="MCX", lot_size=10, tick_size=1.0, multiplier=1.0),
    dict(symbol="NATGASM", exchange="MCX", lot_size=250, tick_size=0.1, multiplier=1.0),
]

_engine = None
_SessionLocal = None


def _get_sessionmaker():
    """Lazy singleton so importing this module (e.g. at FastAPI startup
    collection time) never opens the DB file before the app actually runs —
    matters for tests, which set PT_JOURNAL_DB_PATH before import."""
    global _engine, _SessionLocal
    if _SessionLocal is None:
        _engine = make_engine(journal_db_path())
        init_journal_db(_engine)
        _seed_instruments(_engine)
        _seed_bias(_engine)
        _SessionLocal = make_sessionmaker(_engine)
    return _SessionLocal


def _seed_instruments(engine) -> None:
    Session = make_sessionmaker(engine)
    with Session() as s:
        for row in SEED_INSTRUMENTS:
            if s.get(JournalInstrument, row["symbol"]) is None:
                s.add(JournalInstrument(active=True, **row))
        s.commit()


def _seed_bias(engine) -> None:
    Session = make_sessionmaker(engine)
    with Session() as s:
        service.seed_bias(s)


def _session():
    return _get_sessionmaker()()


def _trade_dict(t: JournalTrade) -> dict:
    return {
        "id": t.id, "instrument_symbol": t.instrument_symbol, "direction": t.direction,
        "lots": t.lots, "entry_price": t.entry_price,
        "entry_time": t.entry_time.isoformat(), "exit_price": t.exit_price,
        "exit_time": t.exit_time.isoformat() if t.exit_time else None,
        "view_id": t.view_id, "setup_tag": t.setup_tag, "notes": t.notes,
        "manual_net_pnl": t.manual_net_pnl,
    }


@router.get("/instruments")
def list_instruments():
    with _session() as s:
        rows = s.execute(select(JournalInstrument)).scalars().all()
        return {"instruments": [
            {"symbol": r.symbol, "exchange": r.exchange, "lot_size": r.lot_size,
             "tick_size": r.tick_size, "multiplier": r.multiplier, "active": r.active}
            for r in rows]}


@router.post("/trades")
def add_trade(req: AddTradeRequest):
    with _session() as s:
        if s.get(JournalInstrument, req.symbol) is None:
            raise HTTPException(400, f"unknown journal instrument {req.symbol}")
        t = service.add_trade(
            s, symbol=req.symbol, direction=req.direction, lots=req.lots,
            entry_price=req.entry_price, entry_time=req.entry_time or dt.datetime.now(),
            setup_tag=req.setup_tag, notes=req.notes, view_id=req.view_id)
        return _trade_dict(t)


@router.get("/trades")
def list_trades(open_only: bool = False):
    with _session() as s:
        return {"trades": [_trade_dict(t) for t in service.list_trades(s, open_only=open_only)]}


@router.post("/trades/{trade_id}/close")
def close_trade(trade_id: int, req: CloseTradeRequest):
    with _session() as s:
        if s.get(JournalTrade, trade_id) is None:
            raise HTTPException(404, "trade not found")
        t = service.close_trade(
            s, trade_id, exit_price=req.exit_price,
            exit_time=req.exit_time or dt.datetime.now(), manual_net_pnl=req.manual_net_pnl)
        return _trade_dict(t)


@router.get("/trades/open-mtm")
def open_trades_with_mtm():
    """Open trades with live unrealized P&L via the shared market-data provider
    (read-only quote lookup). A quote failure degrades that row's `unrealized`
    to null rather than failing the whole list."""
    from app.core.instruments import Instrument
    from app.providers.factory import get_provider
    provider = get_provider()
    with _session() as s:
        insts = {r.symbol: r for r in s.execute(select(JournalInstrument)).scalars().all()}
        out = []
        for t in service.list_trades(s, open_only=True):
            inst = insts.get(t.instrument_symbol)
            row = _trade_dict(t)
            row["unrealized"] = None
            if inst is not None:
                probe = Instrument(
                    key=inst.symbol, name=inst.symbol, segment=inst.exchange,
                    spot_exchange=inst.exchange, spot_symbol=inst.symbol,
                    option_name=inst.symbol, lot_size=inst.lot_size, strike_step=0,
                    priority=99, mock_spot=0.0, mock_vol=0.0, has_options=False)
                try:
                    last = provider.get_ltp(probe)
                except Exception:
                    last = None
                if last is not None:
                    row["unrealized"] = service.trade_unrealized(t, inst, last)
            out.append(row)
        return {"trades": out}


@router.post("/missed")
def add_missed(req: AddMissedRequest):
    with _session() as s:
        if s.get(JournalInstrument, req.symbol) is None:
            raise HTTPException(400, f"unknown journal instrument {req.symbol}")
        m = service.add_missed(
            s, symbol=req.symbol, direction=req.direction,
            seen_at=req.seen_at or dt.datetime.now(), skip_reason=req.skip_reason,
            setup_tag=req.setup_tag, hypothetical_entry=req.hypothetical_entry,
            hypothetical_exit=req.hypothetical_exit, notes=req.notes)
        return {"id": m.id}


@router.get("/missed")
def list_missed():
    with _session() as s:
        rows = service.list_missed(s)
        return {"missed": [
            {"id": m.id, "instrument_symbol": m.instrument_symbol, "direction": m.direction,
             "seen_at": m.seen_at.isoformat(), "setup_tag": m.setup_tag,
             "skip_reason": m.skip_reason, "hypothetical_entry": m.hypothetical_entry,
             "hypothetical_exit": m.hypothetical_exit, "notes": m.notes}
            for m in rows]}


@router.get("/stats")
def get_stats():
    with _session() as s:
        return service.stats(s)


@router.post("/views")
def add_view(req: AddViewRequest):
    with _session() as s:
        v = JournalView(name=req.name, thesis=req.thesis, created_at=dt.datetime.now())
        s.add(v)
        s.commit()
        return {"id": v.id, "name": v.name}


@router.get("/views")
def list_views():
    with _session() as s:
        rows = s.execute(select(JournalView)).scalars().all()
        return {"views": [
            {"id": v.id, "name": v.name, "thesis": v.thesis,
             "created_at": v.created_at.isoformat(),
             "retired_at": v.retired_at.isoformat() if v.retired_at else None}
            for v in rows]}


@router.get("/feed")
def get_feed(limit: int = 60):
    with _session() as s:
        return service.feed(s, limit=limit)


@router.post("/days")
def upsert_day(req: UpsertDayRequest):
    with _session() as s:
        d = service.upsert_day(s, entry_date=req.entry_date,
                               market_view=req.market_view, result=req.result)
        return {"entry_date": d.entry_date.isoformat(),
                "market_view": d.market_view, "result": d.result}


@router.post("/notes")
def add_note(req: AddNoteRequest):
    with _session() as s:
        if req.instrument_symbol and s.get(JournalInstrument, req.instrument_symbol) is None:
            raise HTTPException(400, f"unknown journal instrument {req.instrument_symbol}")
        note = service.add_note(s, body=req.body,
                                noted_at=req.noted_at or dt.datetime.now(),
                                instrument_symbol=req.instrument_symbol)
        return {"id": note.id, "noted_at": note.noted_at.isoformat(),
                "body": note.body, "instrument_symbol": note.instrument_symbol}


@router.delete("/notes/{note_id}")
def delete_note(note_id: int):
    with _session() as s:
        if not service.delete_note(s, note_id):
            raise HTTPException(404, "note not found")
        return {"ok": True}


@router.get("/bias")
def get_bias():
    with _session() as s:
        return {"bias": [{"horizon": b.horizon, "stance": b.stance, "note": b.note,
                          "updated_at": b.updated_at.isoformat()} for b in service.list_bias(s)]}


@router.put("/bias/{horizon}")
def put_bias(horizon: str, req: UpsertBiasRequest):
    with _session() as s:
        try:
            b = service.upsert_bias(s, horizon=horizon, stance=req.stance, note=req.note)
        except ValueError as e:
            raise HTTPException(400, str(e))
        return {"horizon": b.horizon, "stance": b.stance, "note": b.note,
                "updated_at": b.updated_at.isoformat()}
