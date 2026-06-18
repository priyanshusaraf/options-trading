"""
SQLAlchemy models — the persistent paper-trading ledger.

Capital and history survive restarts (the owner runs this live over time), so
realized P&L compounds. The reconciliation invariant the dry-run checks:

    cash == initial_capital + realized_pnl - Σ(open position entry_cost)

i.e. every open position has removed its full entry cost (premium×qty + entry
charges) from cash, and every closed trade has folded its net P&L back in.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CapitalState(Base):
    __tablename__ = "capital_state"
    id: Mapped[int] = mapped_column(primary_key=True)
    initial_capital: Mapped[float] = mapped_column(Float)
    cash: Mapped[float] = mapped_column(Float)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)


class InstrumentState(Base):
    __tablename__ = "instrument_state"
    instrument_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Position(Base):
    __tablename__ = "positions"
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_key: Mapped[str] = mapped_column(String(32), index=True)
    direction: Mapped[str] = mapped_column(String(8))       # LONG | SHORT
    option_type: Mapped[str] = mapped_column(String(4))     # CE | PE
    tradingsymbol: Mapped[str] = mapped_column(String(64))
    exchange: Mapped[str] = mapped_column(String(8))        # NFO/BFO/MCX/NCDEX
    strike: Mapped[float] = mapped_column(Float)
    expiry: Mapped[dt.date] = mapped_column(Date)
    lot_size: Mapped[int] = mapped_column(Integer)
    qty: Mapped[int] = mapped_column(Integer)

    entry_premium: Mapped[float] = mapped_column(Float)
    entry_charges: Mapped[float] = mapped_column(Float)
    entry_cost: Mapped[float] = mapped_column(Float)        # premium*qty + entry charges
    entry_spot: Mapped[float] = mapped_column(Float)
    entry_time: Mapped[dt.datetime] = mapped_column(DateTime)
    entry_reason: Mapped[str] = mapped_column(String(400), default="")

    stop_price: Mapped[float] = mapped_column(Float)        # premium floor (SL)
    target_price: Mapped[float] = mapped_column(Float)      # premium ceiling (TP)

    last_premium: Mapped[float] = mapped_column(Float, default=0.0)  # live mark
    last_spot: Mapped[float] = mapped_column(Float, default=0.0)

    def to_dict(self) -> dict:
        mtm = (self.last_premium or self.entry_premium) * self.qty
        unrealized = mtm - self.entry_premium * self.qty
        return {
            "id": self.id,
            "instrument_key": self.instrument_key,
            "direction": self.direction,
            "option_type": self.option_type,
            "tradingsymbol": self.tradingsymbol,
            "strike": self.strike,
            "expiry": self.expiry.isoformat(),
            "lot_size": self.lot_size,
            "qty": self.qty,
            "entry_premium": round(self.entry_premium, 2),
            "entry_cost": round(self.entry_cost, 2),
            "entry_time": self.entry_time.isoformat(),
            "entry_reason": self.entry_reason,
            "stop_price": round(self.stop_price, 2),
            "target_price": round(self.target_price, 2),
            "last_premium": round(self.last_premium or self.entry_premium, 2),
            "last_spot": round(self.last_spot, 2),
            "unrealized_pnl": round(unrealized, 2),
        }


class Trade(Base):
    __tablename__ = "trades"
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_key: Mapped[str] = mapped_column(String(32), index=True)
    direction: Mapped[str] = mapped_column(String(8))
    option_type: Mapped[str] = mapped_column(String(4))
    tradingsymbol: Mapped[str] = mapped_column(String(64))
    exchange: Mapped[str] = mapped_column(String(8))
    strike: Mapped[float] = mapped_column(Float)
    expiry: Mapped[dt.date] = mapped_column(Date)
    qty: Mapped[int] = mapped_column(Integer)

    entry_premium: Mapped[float] = mapped_column(Float)
    entry_cost: Mapped[float] = mapped_column(Float)
    entry_spot: Mapped[float] = mapped_column(Float)
    entry_time: Mapped[dt.datetime] = mapped_column(DateTime)

    exit_premium: Mapped[float] = mapped_column(Float)
    exit_charges: Mapped[float] = mapped_column(Float)
    exit_spot: Mapped[float] = mapped_column(Float)
    exit_time: Mapped[dt.datetime] = mapped_column(DateTime, index=True)
    exit_reason: Mapped[str] = mapped_column(String(32))    # STOP_LOSS|TARGET|STRATEGY_EXIT

    gross_pnl: Mapped[float] = mapped_column(Float)
    charges_total: Mapped[float] = mapped_column(Float)
    net_pnl: Mapped[float] = mapped_column(Float)
    return_pct: Mapped[float] = mapped_column(Float)
    holding_minutes: Mapped[float] = mapped_column(Float)
    win: Mapped[bool] = mapped_column(Boolean)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "instrument_key": self.instrument_key,
            "direction": self.direction,
            "option_type": self.option_type,
            "tradingsymbol": self.tradingsymbol,
            "strike": self.strike,
            "qty": self.qty,
            "entry_premium": round(self.entry_premium, 2),
            "exit_premium": round(self.exit_premium, 2),
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat(),
            "exit_reason": self.exit_reason,
            "gross_pnl": round(self.gross_pnl, 2),
            "charges_total": round(self.charges_total, 2),
            "net_pnl": round(self.net_pnl, 2),
            "return_pct": round(self.return_pct, 2),
            "holding_minutes": round(self.holding_minutes, 1),
            "win": self.win,
        }


class EquitySnapshot(Base):
    __tablename__ = "equity_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    time: Mapped[dt.datetime] = mapped_column(DateTime, index=True)
    equity: Mapped[float] = mapped_column(Float)
    cash: Mapped[float] = mapped_column(Float)
    invested: Mapped[float] = mapped_column(Float)
    realized_pnl: Mapped[float] = mapped_column(Float)
    open_count: Mapped[int] = mapped_column(Integer)

    def to_dict(self) -> dict:
        return {
            "time": int(self.time.timestamp()),
            "equity": round(self.equity, 2),
            "cash": round(self.cash, 2),
            "invested": round(self.invested, 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "open_count": self.open_count,
        }


class SignalEvent(Base):
    __tablename__ = "signal_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    time: Mapped[dt.datetime] = mapped_column(DateTime, index=True)
    instrument_key: Mapped[str] = mapped_column(String(32), index=True)
    signal: Mapped[str] = mapped_column(String(16))        # LONG_ENTRY | SHORT_ENTRY
    z: Mapped[float] = mapped_column(Float, default=0.0)
    slope: Mapped[float] = mapped_column(Float, default=0.0)
    close: Mapped[float] = mapped_column(Float, default=0.0)
    acted: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str] = mapped_column(String(400), default="")

    def to_dict(self) -> dict:
        return {
            "time": self.time.isoformat(),
            "instrument_key": self.instrument_key,
            "signal": self.signal,
            "z": round(self.z, 3),
            "slope": round(self.slope, 3),
            "close": round(self.close, 2),
            "acted": self.acted,
            "note": self.note,
        }
