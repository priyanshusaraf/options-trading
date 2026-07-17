"""Journal tables — the owner's manual/physical trade log. Fully isolated from
the execution ledger (own JournalBase, own journal.db); the engine never
imports this package.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.journal.db import JournalBase


class JournalInstrument(JournalBase):
    """The journal's own instrument list — separate from the bot's universe
    because the bot trades full-size CRUDEOIL/NATURALGAS while the owner
    manually trades the MINI contracts (different lot size/multiplier)."""
    __tablename__ = "journal_instruments"
    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    exchange: Mapped[str] = mapped_column(String(8), default="MCX")
    lot_size: Mapped[int] = mapped_column(Integer)
    tick_size: Mapped[float] = mapped_column(Float, default=1.0)
    # contract value multiplier — 1.0 unless the contract's point value differs
    # from lot_size×price (verify against the exchange contract spec per symbol
    # before trusting a non-default value).
    multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class JournalView(JournalBase):
    """An append-only horizon (e.g. 'long-term', 'current-week'). Trades bind
    to whichever view is live (retired_at IS NULL) at entry time; retiring a
    view never rewrites the trades already bound to it."""
    __tablename__ = "journal_views"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    thesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime)
    retired_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class JournalTrade(JournalBase):
    """An executed manual/physical trade. `manual_net_pnl`, when set, IS the
    net P&L (charges are never separately subtracted on top of it) — set it
    when the owner enters the broker-reported net directly; leave it NULL to
    have net computed from entry/exit price + app.engine.charges."""
    __tablename__ = "journal_trades"
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_symbol: Mapped[str] = mapped_column(
        String(32), ForeignKey("journal_instruments.symbol"))
    direction: Mapped[str] = mapped_column(String(8))  # LONG | SHORT
    lots: Mapped[int] = mapped_column(Integer)
    entry_price: Mapped[float] = mapped_column(Float)
    entry_time: Mapped[dt.datetime] = mapped_column(DateTime)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_time: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    view_id: Mapped[int] = mapped_column(Integer, ForeignKey("journal_views.id"))
    setup_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    manual_net_pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)


class JournalMissed(JournalBase):
    """A setup the owner saw but did not take, with an optional hypothetical
    entry/exit so missed-opportunity P&L can be estimated (never counted as
    real P&L)."""
    __tablename__ = "journal_missed"
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_symbol: Mapped[str] = mapped_column(
        String(32), ForeignKey("journal_instruments.symbol"))
    direction: Mapped[str] = mapped_column(String(8))
    seen_at: Mapped[dt.datetime] = mapped_column(DateTime)
    setup_tag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    skip_reason: Mapped[str] = mapped_column(Text)
    hypothetical_entry: Mapped[float | None] = mapped_column(Float, nullable=True)
    hypothetical_exit: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class JournalTag(JournalBase):
    """Curated setup-tag suggestion list. Tags are still free-text on trades/
    missed rows; this table is auto-upserted on first use so the UI can offer
    a picker instead of re-typing tags from memory."""
    __tablename__ = "journal_tags"
    name: Mapped[str] = mapped_column(String(64), primary_key=True)
