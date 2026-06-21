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

from sqlalchemy import Boolean, Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CapitalState(Base):
    __tablename__ = "capital_state"
    id: Mapped[int] = mapped_column(primary_key=True)
    initial_capital: Mapped[float] = mapped_column(Float)
    cash: Mapped[float] = mapped_column(Float)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    account_baseline: Mapped[float | None] = mapped_column(Float, nullable=True)  # live account equity when bot-vs-you tracking started
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)


class InstrumentState(Base):
    __tablename__ = "instrument_state"
    instrument_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    live_interval: Mapped[str] = mapped_column(String(12), default="15minute")
    entries_blocked: Mapped[bool] = mapped_column(Boolean, default=False)


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
    last_mark_time: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    # highest premium seen since entry — drives the trailing-stop ratchet
    high_water_premium: Mapped[float] = mapped_column(Float, default=0.0)
    # reinforcement + overnight management
    reinforcement_count: Mapped[int] = mapped_column(Integer, default=0)
    last_reinforce_time: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    held_overnight: Mapped[bool] = mapped_column(Boolean, default=False)
    overnight_pnl: Mapped[float] = mapped_column(Float, default=0.0)   # Σ premium delta across session gaps
    session_close_premium: Mapped[float] = mapped_column(Float, default=0.0)  # mark at last session close
    last_squareoff_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)  # date the daily hold/square-off decision was last made (re-arm each session)
    manual_target: Mapped[bool] = mapped_column(Boolean, default=False)  # owner set the target by hand — reinforcement won't auto-extend it
    no_take_profit: Mapped[bool] = mapped_column(Boolean, default=False)  # owner "let it run": suppress the TP cap (trailing stop still protects)
    gtt_trigger_id: Mapped[str | None] = mapped_column(String(32), nullable=True)  # Zerodha GTT safety-net stop id (live execution)
    mode: Mapped[str] = mapped_column(String(8), default="paper")  # "paper" | "live" — which broker opened it; never mixed in the UI

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
            "last_mark_time": self.last_mark_time.isoformat() if self.last_mark_time else None,
            "high_water_premium": round(self.high_water_premium or self.entry_premium, 2),
            "reinforcement_count": self.reinforcement_count,
            "held_overnight": self.held_overnight,
            "manual_target": self.manual_target,
            "no_take_profit": self.no_take_profit,
            "unrealized_pnl": round(unrealized, 2),
            "mode": self.mode,
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
    # intraday vs overnight attribution
    held_overnight: Mapped[bool] = mapped_column(Boolean, default=False)
    overnight_pnl: Mapped[float] = mapped_column(Float, default=0.0)   # part of net from session gaps
    intraday_pnl: Mapped[float] = mapped_column(Float, default=0.0)    # net - overnight
    reinforcements: Mapped[int] = mapped_column(Integer, default=0)
    mode: Mapped[str] = mapped_column(String(8), default="paper")  # "paper" | "live" — broker that executed it

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
            "entry_spot": round(self.entry_spot, 2) if self.entry_spot else None,
            "exit_spot": round(self.exit_spot, 2) if self.exit_spot else None,
            "spot_move_pct": (round((self.exit_spot - self.entry_spot) / self.entry_spot * 100, 2)
                              if self.entry_spot and self.exit_spot else None),
            "premium_move_pct": (round((self.exit_premium - self.entry_premium) / self.entry_premium * 100, 2)
                                 if self.entry_premium else None),
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat(),
            "exit_reason": self.exit_reason,
            "gross_pnl": round(self.gross_pnl, 2),
            "charges_total": round(self.charges_total, 2),
            "net_pnl": round(self.net_pnl, 2),
            "return_pct": round(self.return_pct, 2),
            "holding_minutes": round(self.holding_minutes, 1),
            "win": self.win,
            "held_overnight": self.held_overnight,
            "overnight_pnl": round(self.overnight_pnl, 2),
            "intraday_pnl": round(self.intraday_pnl, 2),
            "reinforcements": self.reinforcements,
            "mode": self.mode,
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


class UniverseInstrument(Base):
    """The dynamic, DB-backed tradable universe. Seeded from the curated list and
    extended at runtime when the owner adds instruments from the homepage /
    backtest winners. `has_options` decides whether the live engine options-trades
    it or just tracks + backtests it."""
    __tablename__ = "universe_instruments"
    key: Mapped[str] = mapped_column(String(48), primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    segment: Mapped[str] = mapped_column(String(12))       # NFO/BFO/MCX/NCDEX/NSE/BSE
    spot_exchange: Mapped[str] = mapped_column(String(12))
    spot_symbol: Mapped[str] = mapped_column(String(64))
    option_name: Mapped[str] = mapped_column(String(64), default="")
    lot_size: Mapped[int] = mapped_column(Integer, default=1)
    strike_step: Mapped[float] = mapped_column(Float, default=1.0)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    has_options: Mapped[bool] = mapped_column(Boolean, default=True)
    source: Mapped[str] = mapped_column(String(8), default="seed")   # seed | user
    on_home: Mapped[bool] = mapped_column(Boolean, default=False)    # shown on homepage
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # mock seeds (only used by the synthetic market in tests/dryrun)
    mock_spot: Mapped[float] = mapped_column(Float, default=1000.0)
    mock_vol: Mapped[float] = mapped_column(Float, default=0.2)


class BacktestRun(Base):
    __tablename__ = "backtest_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)
    status: Mapped[str] = mapped_column(String(16), default="running")  # running|done|error
    scope: Mapped[str] = mapped_column(String(16), default="liquid")    # liquid|full
    intervals: Mapped[str] = mapped_column(String(128), default="")     # csv
    capital: Mapped[float] = mapped_column(Float, default=50_000.0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    done: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str] = mapped_column(String(400), default="")
    window: Mapped[str] = mapped_column(String(64), default="")          # lookback label: "1y" | "max" | "2024-01-01→2024-06-01"
    instruments: Mapped[str] = mapped_column(String(400), default="")    # csv of selected keys (empty = whole scope)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "created_at": self.created_at.isoformat(),
            "status": self.status, "scope": self.scope,
            "intervals": [i for i in self.intervals.split(",") if i],
            "capital": self.capital, "total": self.total, "done": self.done,
            "progress": round(100 * self.done / self.total, 1) if self.total else 0.0,
            "note": self.note,
            "window": self.window or "max",
            "instruments": [i for i in self.instruments.split(",") if i],
        }


class BacktestResult(Base):
    """One (instrument × interval) backtest result. Cached so reruns are instant."""
    __tablename__ = "backtest_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, index=True)
    instrument_key: Mapped[str] = mapped_column(String(48), index=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    segment: Mapped[str] = mapped_column(String(12), default="")   # backtest charge segment
    interval: Mapped[str] = mapped_column(String(12), index=True)
    trades: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    profit_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0)
    return_pct: Mapped[float] = mapped_column(Float, default=0.0)
    net_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    gross_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    charges: Mapped[float] = mapped_column(Float, default=0.0)
    expectancy: Mapped[float] = mapped_column(Float, default=0.0)
    cagr: Mapped[float | None] = mapped_column(Float, nullable=True)
    # smoothness / quality
    calmar: Mapped[float | None] = mapped_column(Float, nullable=True)
    consistency: Mapped[float | None] = mapped_column(Float, nullable=True)  # PER-TRADE hit consistency (not annualised)
    sharpe: Mapped[float | None] = mapped_column(Float, nullable=True)       # annualised Sharpe (cross-frequency comparable)
    max_consec_losses: Mapped[int] = mapped_column(Integer, default=0)
    time_underwater_pct: Mapped[float] = mapped_column(Float, default=0.0)
    worst_trade_pnl: Mapped[float] = mapped_column(Float, default=0.0)  # single worst net P&L (tail risk)
    worst_mae_pct: Mapped[float] = mapped_column(Float, default=0.0)    # worst intra-trade adverse excursion, %
    # honest sizing / affordability
    notional: Mapped[float] = mapped_column(Float, default=0.0)   # 1-lot underlying notional = base capital (entry × lot)
    lots: Mapped[int] = mapped_column(Integer, default=0)         # 1 for F&O (cash: shares); 0 = no trades
    affordable: Mapped[bool] = mapped_column(Boolean, default=True)  # back-compat; real flags computed at payload layer
    option_cost: Mapped[float] = mapped_column(Float, default=0.0)   # est. cost to buy 1 lot of an ATM option (BS), budget-independent
    # realised vs OPEN_AT_END
    open_at_end: Mapped[bool] = mapped_column(Boolean, default=False)
    win_rate_realised: Mapped[float] = mapped_column(Float, default=0.0)
    return_pct_realised: Mapped[float] = mapped_column(Float, default=0.0)
    # benchmark
    bh_return_pct: Mapped[float | None] = mapped_column(Float, nullable=True)  # buy-and-hold over the same span, %
    # true per-(instrument,interval) coverage (honest span disclosure)
    first_ts: Mapped[int] = mapped_column(Integer, default=0)        # epoch of first candle in this cell
    last_ts: Mapped[int] = mapped_column(Integer, default=0)         # epoch of last candle in this cell
    effective_days: Mapped[int] = mapped_column(Integer, default=0)  # actual days covered (first→last)
    clamped: Mapped[bool] = mapped_column(Boolean, default=False)    # requested span exceeded Kite's ceiling
    bars: Mapped[int] = mapped_column(Integer, default=0)
    curve_json: Mapped[str] = mapped_column(Text, default="[]")     # equity curve
    bh_curve_json: Mapped[str] = mapped_column(Text, default="[]")  # buy-and-hold overlay
    trades_json: Mapped[str] = mapped_column(Text, default="[]")    # trade list (drill-down)
    error: Mapped[str] = mapped_column(String(400), default="")
    # reusable-cache metadata (content-addressed reuse across runs)
    params_hash: Mapped[str] = mapped_column(String(64), default="")
    last_candle_ts: Mapped[int] = mapped_column(Integer, default=0)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    from_cache: Mapped[bool] = mapped_column(Boolean, default=False)
    computed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    def summary(self) -> dict:
        return {
            "id": self.id, "run_id": self.run_id,
            "instrument_key": self.instrument_key, "name": self.name,
            "segment": self.segment, "interval": self.interval,
            "trades": self.trades, "wins": self.wins,
            "win_rate": round(self.win_rate, 1),
            "profit_factor": round(self.profit_factor, 3) if self.profit_factor is not None else None,
            "max_drawdown_pct": round(self.max_drawdown_pct, 1),
            "return_pct": round(self.return_pct, 1),
            "net_pnl": round(self.net_pnl, 0),
            "gross_pnl": round(self.gross_pnl, 0),
            "charges": round(self.charges, 0),
            "expectancy": round(self.expectancy, 0),
            "cagr": round(self.cagr, 1) if self.cagr is not None else None,
            "calmar": round(self.calmar, 2) if self.calmar is not None else None,
            "consistency": round(self.consistency, 2) if self.consistency is not None else None,
            "sharpe": round(self.sharpe, 2) if self.sharpe is not None else None,
            "max_consec_losses": self.max_consec_losses,
            "time_underwater_pct": round(self.time_underwater_pct, 1),
            "worst_trade_pnl": round(self.worst_trade_pnl, 0),
            "worst_mae_pct": round(self.worst_mae_pct, 1),
            "notional": round(self.notional, 0),
            "option_cost": round(self.option_cost or 0.0, 0),
            "lots": self.lots,
            "affordable": bool(self.affordable),
            "open_at_end": bool(self.open_at_end),
            "win_rate_realised": round(self.win_rate_realised, 1),
            "return_pct_realised": round(self.return_pct_realised, 1),
            "bh_return_pct": round(self.bh_return_pct, 1) if self.bh_return_pct is not None else None,
            "first_ts": self.first_ts,
            "last_ts": self.last_ts,
            "effective_days": self.effective_days,
            "clamped": bool(self.clamped),
            "bars": self.bars,
            "from_cache": self.from_cache,
            "error": self.error,
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


class RuntimeConfig(Base):
    """Runtime parameter overrides (manual-override mode). Each row overrides one
    Settings field by name; absent keys fall back to the code default. Lets the
    owner retune reinforcement / overnight / trailing knobs without code edits."""
    __tablename__ = "runtime_config"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(64))   # stringified; coerced to the field's type
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)


class OptionData(Base):
    """Persistent option-chain research dataset. Every distinct contract quote we
    fetch is appended (deduped at snapshot cadence) to build a growing local
    options history that survives restarts and is reusable for research."""
    __tablename__ = "option_data"
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_key: Mapped[str] = mapped_column(String(32), index=True)
    ts: Mapped[dt.datetime] = mapped_column(DateTime, index=True)
    expiry: Mapped[dt.date] = mapped_column(Date)
    strike: Mapped[float] = mapped_column(Float)
    option_type: Mapped[str] = mapped_column(String(4))   # CE | PE
    tradingsymbol: Mapped[str] = mapped_column(String(64))
    spot: Mapped[float] = mapped_column(Float, default=0.0)
    ltp: Mapped[float] = mapped_column(Float, default=0.0)
    bid: Mapped[float] = mapped_column(Float, default=0.0)
    ask: Mapped[float] = mapped_column(Float, default=0.0)
    oi: Mapped[int] = mapped_column(Integer, default=0)
    volume: Mapped[int] = mapped_column(Integer, default=0)
    iv: Mapped[float | None] = mapped_column(Float, nullable=True)
    delta: Mapped[float | None] = mapped_column(Float, nullable=True)
