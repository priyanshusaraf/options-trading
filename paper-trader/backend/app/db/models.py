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

from app.core.version import get_build_sha
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    DDL,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    event,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# Segments whose positions are MARGINED rather than fully paid for: only the
# margin left cash, so the position contributes margin + unrealized P&L to equity
# — never its full notional, which would double-count the leverage. They can also
# be genuinely SHORT, unlike the long-premium options path.
#
# A named set rather than a repeated string literal because the two methods below
# must never disagree about which segments are leveraged: one saying "futures are
# margined" while the other says "futures are fully paid" would inflate portfolio
# equity by the notional on every futures tick.
MARGIN_SEGMENTS = frozenset({"equity_intraday", "index_futures"})

# FUNDED segments: the broker lends part of the position and charges interest for
# every day it is held. Their P&L is TIME-DEPENDENT — it worsens while you do
# nothing — which no other segment here is. `mtf` is the only member today.
#
# Separate from MARGIN_SEGMENTS on purpose: both are leveraged, but "only the
# margin left cash" and "interest accrues daily" are different facts, and a
# single set conflating them would silently give futures a carry cost or MTF an
# intraday square-off.
FUNDED_SEGMENTS = frozenset({"mtf"})


class Base(DeclarativeBase):
    pass


# The deployment every pre-existing row belongs to. Before Phase B the system had
# exactly one implicit book — one capital balance, one arm switch, one strategy
# assignment per instrument — and this id names it retroactively. Rows created
# before deployments existed are not "unattributed"; they were all executed by this
# one. Keep it as a constant rather than a literal 1: the number appears in a
# server_default, a seed, a backfill and every lookup default, and those four must
# never drift apart.
LEGACY_DEPLOYMENT_ID = 1


class Deployment(Base):
    """A strategy, running, with its own parameters, universe, capital and switches.

    THE primary execution object. Before this existed, "what is running" was spread
    across `instrument_state.strategy_key`, `watchlists.strategy_key`, the global
    `Settings`/`runtime_config` merge, and a single in-memory `armed` flag on the
    runner — six places, none of them addressable, and no way for two strategies to
    run different risk parameters or hold the same underlying.

    Everything about this table is designed so that today's behaviour is EXACTLY
    deployment 1 and nothing else changes:

    - `universe_mode='legacy'` means "whatever the per-instrument config and active
      watchlists say", i.e. the existing resolution path, untouched.
    - `allocation=None` means "the whole account", which is what a single book has.
    - `strategy_key=None` means "resolve per instrument, as before" rather than
      pinning one strategy across the book.
    - `armed` starts False, matching the disarm-on-every-start invariant.

    A second deployment therefore cannot appear by accident: it has to be created,
    and until one is, every query that filters by deployment sees the same rows it
    saw before.
    """
    __tablename__ = "deployments"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)

    # ── what runs ────────────────────────────────────────────────────────────
    # NULL = per-instrument resolution (the legacy path). A real deployment pins one.
    strategy_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Filled by Phase D (immutable strategy identity). NULL until then, and NULL on
    # the legacy deployment forever — it does not pin a strategy, so it cannot pin a
    # version either.
    strategy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # ── where it runs ────────────────────────────────────────────────────────
    # The broker account this book belongs to. One account today; the column exists
    # so that adding a second is a row, not a schema change.
    account_id: Mapped[str] = mapped_column(String(64), default="default",
                                            server_default="default")
    # legacy | watchlist | explicit — how this deployment's instruments are decided.
    universe_mode: Mapped[str] = mapped_column(String(16), default="legacy",
                                               server_default="legacy")
    watchlist_id: Mapped[int | None] = mapped_column(
        ForeignKey("watchlists.id"), nullable=True)

    # ── how it is parameterised (Phase C reads this) ─────────────────────────
    # JSON object of deployment-scoped overrides over platform defaults. Empty
    # object = "inherit everything", which is what the legacy deployment does.
    params_json: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")

    # ── capital ──────────────────────────────────────────────────────────────
    # NULL = the entire account (today's single-book behaviour). A number caps what
    # this deployment may deploy, so two books can share one account.
    allocation: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── runtime state + lifecycle ────────────────────────────────────────────
    # draft | active | paused | archived. Only `active` is ever scanned.
    status: Mapped[str] = mapped_column(String(12), default="active",
                                        server_default="active")
    # Per-deployment arm, alongside (never instead of) the global master switch.
    # False on creation and reset on every process start — same invariant the global
    # flag has, for the same reason.
    armed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    # Set when this deployment's own daily-loss halt trips; cleared next session.
    halted_on: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "strategy_key": self.strategy_key,
                "strategy_version": self.strategy_version, "account_id": self.account_id,
                "universe_mode": self.universe_mode, "watchlist_id": self.watchlist_id,
                "allocation": self.allocation, "status": self.status,
                "armed": self.armed,
                "halted_on": self.halted_on.isoformat() if self.halted_on else None,
                "notes": self.notes}


class CapitalState(Base):
    """One ledger per execution book. `cash` and `realized_pnl` are aggregates mutated
    in place, so a paper fill debiting the live book's cash could not be prevented by
    filtering a query — this table needed a row per book, not a predicate.

    `book` is NULL on exactly one row: the single pre-L1.3B ledger, whose owning book is
    decided once from the `mode` already stamped on the money rows it produced
    (`core/execution_book.capital_for_book`). NULL therefore means "written before
    2026-08-07 and not yet attributed", never "shared"."""

    __tablename__ = "capital_state"
    __table_args__ = (
        # Two rows for one book would silently split a ledger in half. Partial so the
        # unclaimed legacy row is exempt rather than blocking the constraint entirely.
        Index("uq_capital_state_book", "book", unique=True,
              sqlite_where=text("book IS NOT NULL")),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    book: Mapped[str | None] = mapped_column(String(8), nullable=True)
    initial_capital: Mapped[float] = mapped_column(Float)
    cash: Mapped[float] = mapped_column(Float)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    account_baseline: Mapped[float | None] = mapped_column(Float, nullable=True)  # live account equity when bot-vs-you tracking started
    anchored_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)  # last re-anchor to real broker equity (NULL = never)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)


class InstrumentState(Base):
    __tablename__ = "instrument_state"
    instrument_key: Mapped[str] = mapped_column(String(32), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    live_interval: Mapped[str] = mapped_column(String(12), default="15minute")
    entries_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    # dual-segment / multi-strategy assignment (Phase 0 foundation)
    strategy_key: Mapped[str | None] = mapped_column(String(64), nullable=True)  # None = default strategy
    priority_flag: Mapped[bool] = mapped_column(Boolean, default=False)  # "purple" intraday priority
    product: Mapped[str] = mapped_column(String(16), default="options")  # options | equity_intraday
    overtrade_flag: Mapped[bool] = mapped_column(Boolean, default=False)  # "red" overtrading flag (advisory)
    # Instrument-scoped parameter overrides — the narrowest layer of the
    # Platform -> Deployment -> Instrument chain (app/core/scoped_config.py).
    # "{}" means inherit everything, which every row is today, so this changes
    # nothing until something writes to it.
    params_json: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")


class Position(Base):
    __tablename__ = "positions"
    # Which deployment executed this. server_default="1" is load-bearing: every
    # row written before Phase B belongs to the legacy book, and any insert path
    # that has not been taught about deployments still lands there instead of
    # failing. See LEGACY_DEPLOYMENT_ID.
    deployment_id: Mapped[int] = mapped_column(
        ForeignKey("deployments.id"), default=LEGACY_DEPLOYMENT_ID,
        server_default="1", index=True)
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_key: Mapped[str] = mapped_column(String(32), index=True)
    direction: Mapped[str] = mapped_column(String(8))       # LONG | SHORT
    option_type: Mapped[str] = mapped_column(String(4))     # CE | PE
    tradingsymbol: Mapped[str] = mapped_column(String(64))
    exchange: Mapped[str] = mapped_column(String(8))        # NFO/BFO/MCX/NCDEX
    # product family + originating strategy (Phase 0 foundation)
    segment: Mapped[str] = mapped_column(String(16), default="options")  # options | equity_intraday
    strategy_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Content hash of the strategy that executed this row (Phase D). NULL is
    # meaningful and is NOT the same as 'unknown': NULL means the row predates
    # the column and is genuinely unattributable, 'unknown' means a strategy was
    # running but could not be identified. Same three-value rule as build_sha —
    # never collapse the two.
    strategy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
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
    # purple SL/TP tiering (2026-07-17): the SL/TP *percentages* this equity_intraday
    # position was opened with, frozen at entry. NULL for options positions and for
    # legacy equity rows predating this feature — both fall back to the current global
    # intraday_stop_loss_pct/intraday_target_pct knobs at ratchet time.
    entry_sl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    entry_tp_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    last_premium: Mapped[float] = mapped_column(Float, default=0.0)  # live mark
    last_spot: Mapped[float] = mapped_column(Float, default=0.0)
    last_mark_time: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    # highest premium seen since entry — drives the trailing-stop ratchet
    high_water_premium: Mapped[float] = mapped_column(Float, default=0.0)
    # peak-excursion telemetry (E0.3): best/worst unrealized P&L (₹) seen while open,
    # from unrealized_pnl() so it is already segment/direction-aware (e.g. an equity
    # SHORT profits on a spot fall). mfe >= 0, mae <= 0 by construction — both seeded
    # at the 0 excursion at entry. Pure telemetry: never read by cash/P&L/exit logic.
    mfe: Mapped[float] = mapped_column(Float, default=0.0)
    mae: Mapped[float] = mapped_column(Float, default=0.0)
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
    # H2 — live ratchet state (unify onto the backtest-validated RatchetState). NULL =>
    # not ratchet-managed (no risk_model). entry_atr frozen at fill; hw/spot_stop ratchet
    # on completed underlying candles; last_bar_ts guards against double-consuming a bar.
    entry_atr: Mapped[float | None] = mapped_column(Float, nullable=True)
    ratchet_hw: Mapped[float | None] = mapped_column(Float, nullable=True)
    spot_stop: Mapped[float | None] = mapped_column(Float, nullable=True)
    ratchet_last_bar_ts: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    mode: Mapped[str] = mapped_column(String(8), default="paper")  # "paper" | "live" — which broker opened it; never mixed in the UI

    def unrealized_pnl(self) -> float:
        """Mark-to-market P&L. Equity intraday and index futures can be real SHORTS
        (profits as price falls); the options path is always long-premium.

        FUNDED (MTF) positions subtract accrued interest. Without it a held
        position looks better every day it is held — the exact opposite of the
        truth — and the error compounds silently for as long as it stays open,
        which for MTF can be weeks. It is the one segment whose P&L moves while
        nothing happens.
        """
        last = self.last_premium or self.entry_premium
        if self.segment in MARGIN_SEGMENTS and self.direction == "SHORT":
            gross = (self.entry_premium - last) * self.qty
        else:
            gross = (last - self.entry_premium) * self.qty
        if self.segment in FUNDED_SEGMENTS:
            gross -= self.accrued_carry()
        return gross

    def accrued_carry(self) -> float:
        """Interest owed so far on a funded position; 0.0 for every other segment.

        Never raises: a carry figure that cannot be computed must not take down
        the mark loop, and 0.0 is the conservative direction here only because
        the alternative is no P&L at all — it is logged as a gap, not treated as
        free money, by the caller that reports it.
        """
        if self.segment not in FUNDED_SEGMENTS:
            return 0.0
        try:
            from app.engine.carry import accrued_to_date
            import datetime as _dt
            entry = self.entry_time.date() if self.entry_time else _dt.date.today()
            today = (self.last_mark_time or self.entry_time or _dt.datetime.now()).date()
            margin = (self.entry_cost or 0.0) - (self.entry_charges or 0.0)
            return accrued_to_date(
                position_value=self.entry_premium * self.qty,
                margin_paid=margin, entry=entry, today=today)
        except Exception:
            return 0.0

    def mtm_value(self) -> float:
        """Contribution to portfolio equity. Options: the contract's liquidation value
        (premium × qty), since the full cost left cash. Leveraged equity (MIS): only
        the MARGIN left cash, so the position returns its margin (entry_cost) plus its
        unrealized P&L — NOT the full notional (last × qty), which double-counts the
        leverage and inflates equity."""
        if self.segment in MARGIN_SEGMENTS:
            return self.entry_cost + self.unrealized_pnl()
        return (self.last_premium or self.entry_premium) * self.qty

    def to_dict(self) -> dict:
        unrealized = self.unrealized_pnl()
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
            "mfe": round(self.mfe or 0.0, 2),
            "mae": round(self.mae or 0.0, 2),
            "reinforcement_count": self.reinforcement_count,
            "held_overnight": self.held_overnight,
            "manual_target": self.manual_target,
            "no_take_profit": self.no_take_profit,
            "unrealized_pnl": round(unrealized, 2),
            "mode": self.mode,
            "segment": self.segment or "options",
            "strategy_key": self.strategy_key,
        }


class Trade(Base):
    __tablename__ = "trades"
    # Which deployment executed this. server_default="1" is load-bearing: every
    # row written before Phase B belongs to the legacy book, and any insert path
    # that has not been taught about deployments still lands there instead of
    # failing. See LEGACY_DEPLOYMENT_ID.
    deployment_id: Mapped[int] = mapped_column(
        ForeignKey("deployments.id"), default=LEGACY_DEPLOYMENT_ID,
        server_default="1", index=True)
    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_key: Mapped[str] = mapped_column(String(32), index=True)
    direction: Mapped[str] = mapped_column(String(8))
    option_type: Mapped[str] = mapped_column(String(4))
    tradingsymbol: Mapped[str] = mapped_column(String(64))
    exchange: Mapped[str] = mapped_column(String(8))
    # product family + originating strategy (Phase 0 foundation)
    segment: Mapped[str] = mapped_column(String(16), default="options")  # options | equity_intraday
    strategy_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Content hash of the strategy that executed this row (Phase D). NULL is
    # meaningful and is NOT the same as 'unknown': NULL means the row predates
    # the column and is genuinely unattributable, 'unknown' means a strategy was
    # running but could not be identified. Same three-value rule as build_sha —
    # never collapse the two.
    strategy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
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
    # E0.1: True when exit_premium is a MARK (last_premium / live LTP), not a real
    # fill — reconcile fallbacks (no matching order found, stop-status read failed,
    # stop still resting) and the manual-close paper override. False (default) means
    # a genuine fill: a normal engine exit, a real SL-M/GTT fill, or a real order.
    exit_price_estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    # peak-excursion telemetry (E0.3): the position's mfe/mae copied at close, so
    # give-back (Workstream C-P2 / E1) is measurable from the trade log. See
    # Position.mfe/mae for the definition.
    mfe: Mapped[float] = mapped_column(Float, default=0.0)
    mae: Mapped[float] = mapped_column(Float, default=0.0)
    # Build provenance: the commit this row was executed by. Defaulted at insert
    # from backend/VERSION (written by scripts/deploy.sh) so all four Trade
    # construction sites in broker.py are covered without touching any of them.
    #
    # Three distinguishable states, and the distinction is the point:
    #   <sha>     — executed by an identified build
    #   'unknown' — executed by a process that could not read its VERSION
    #   NULL      — row predates this column (booked before 2026-07-28)
    # Nullable only so the migration can leave historic rows alone; every row
    # written from here on gets a non-NULL value.
    build_sha: Mapped[str | None] = mapped_column(
        String(64), nullable=True, default=lambda: get_build_sha()
    )

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
            "segment": self.segment or "options",
            "strategy_key": self.strategy_key,
            "exit_price_estimated": bool(self.exit_price_estimated),
            "mfe": round(self.mfe or 0.0, 2),
            "mae": round(self.mae or 0.0, 2),
        }


class EquitySnapshot(Base):
    __tablename__ = "equity_snapshots"
    # Which deployment executed this. server_default="1" is load-bearing: every
    # row written before Phase B belongs to the legacy book, and any insert path
    # that has not been taught about deployments still lands there instead of
    # failing. See LEGACY_DEPLOYMENT_ID.
    deployment_id: Mapped[int] = mapped_column(
        ForeignKey("deployments.id"), default=LEGACY_DEPLOYMENT_ID,
        server_default="1", index=True)
    id: Mapped[int] = mapped_column(primary_key=True)
    time: Mapped[dt.datetime] = mapped_column(DateTime, index=True)
    equity: Mapped[float] = mapped_column(Float)
    cash: Mapped[float] = mapped_column(Float)
    invested: Mapped[float] = mapped_column(Float)
    realized_pnl: Mapped[float] = mapped_column(Float)
    open_count: Mapped[int] = mapped_column(Integer)
    # Which execution book this point belongs to (L1.3B). NULL = written before the
    # books were separated; those points belong to whichever book the ledger they were
    # derived from is later attributed to, which is why they are not back-stamped.
    book: Mapped[str | None] = mapped_column(String(8), nullable=True, index=True)
    # optional segment/strategy partition (null = global portfolio snapshot)
    segment: Mapped[str | None] = mapped_column(String(16), nullable=True)
    strategy_key: Mapped[str | None] = mapped_column(String(64), nullable=True)

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


class Watchlist(Base):
    """A named list bound to exactly ONE strategy. Instruments assigned to an *active*
    watchlist are run by the engine on that watchlist's strategy (overriding the
    per-instrument default). New tables (this + the membership below) are created
    additively by `create_all`, so an existing live DB gains them with no ALTER on the
    instrument ledger — behaviour-preserving until a watchlist is actually populated."""
    __tablename__ = "watchlists"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    strategy_key: Mapped[str] = mapped_column(String(64), default="trend_impulse_v3")
    status: Mapped[str] = mapped_column(String(12), default="active")  # active|paused|archived
    interval: Mapped[str | None] = mapped_column(String(12), nullable=True)  # optional default TF
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "strategy_key": self.strategy_key,
                "status": self.status, "interval": self.interval, "notes": self.notes}


class WatchlistMembership(Base):
    """An instrument's membership in a watchlist. `instrument_key` is the primary key,
    so an instrument belongs to AT MOST ONE watchlist — the structural guarantee the
    dispute/incumbency rules rely on."""
    __tablename__ = "watchlist_membership"
    instrument_key: Mapped[str] = mapped_column(String(48), primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(ForeignKey("watchlists.id"), index=True)
    added_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)


class StrategyLifecycle(Base):
    """The archive: one row per strategy the platform has ever considered, and its
    current lifecycle state. Keeping retired strategies (rather than deleting them)
    is deliberate — a shelved idea can be revived and re-tested when regimes change, or
    tried on a different universe. `last_dsr` carries the last validated performance so
    the archive is a browsable record of what worked, where, and how well."""
    __tablename__ = "strategy_lifecycle"
    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(12), default="candidate")
    # candidate | running | probation | on_hold | retired
    source: Mapped[str] = mapped_column(String(12), default="builtin")  # builtin | generated
    deployed_watchlist_id: Mapped[int | None] = mapped_column(
        ForeignKey("watchlists.id"), nullable=True)
    last_dsr: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)

    def to_dict(self) -> dict:
        return {"strategy_key": self.strategy_key, "status": self.status,
                "source": self.source, "deployed_watchlist_id": self.deployed_watchlist_id,
                "last_dsr": self.last_dsr, "note": self.note}


class GeneratedStrategyRow(Base):
    """A bot-generated strategy that has been APPROVED and deployed, stored as its
    composition JSON (+ the emitted source, for the owner's audit). At engine startup
    `app.core.generated_strategies.register_all` reconstructs each row through the
    sandboxed builder and registers it, so a `gen_*` strategy_key on a watchlist resolves
    to the real generated strategy instead of falling back to the default. Written only
    by the human Approve→Deploy bridge — never by the research process."""
    __tablename__ = "generated_strategies"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    # Content hash of the composition (Phase D). `key` is still the PK, so a
    # redeploy of an edited strategy still overwrites in place — recording the
    # version at least makes that overwrite DETECTABLE. Making identity
    # (key, version) is tracked as remaining work.
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    composition_json: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)


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
    strategies: Mapped[str] = mapped_column(String(400), default="")     # csv of strategy keys this run swept

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
            "strategies": [s for s in self.strategies.split(",") if s] or ["trend_impulse_v3"],
        }


class BacktestResult(Base):
    """One (instrument × interval) backtest result. Cached so reruns are instant."""
    __tablename__ = "backtest_results"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, index=True)
    instrument_key: Mapped[str] = mapped_column(String(48), index=True)
    name: Mapped[str] = mapped_column(String(64), default="")
    segment: Mapped[str] = mapped_column(String(12), default="")   # backtest charge segment
    strategy_key: Mapped[str] = mapped_column(String(64), default="trend_impulse_v3", index=True)
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
    # synthetic-premium backtest (audit C6) — a Black-Scholes-on-realised-vol
    # premium path computed alongside the spot cell above. A premium-side bug
    # never kills the spot result: it lands in premium_error instead.
    premium_trades: Mapped[int] = mapped_column(Integer, default=0)
    premium_win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    premium_net_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    premium_return_pct: Mapped[float] = mapped_column(Float, default=0.0)
    premium_profit_factor: Mapped[float | None] = mapped_column(Float, nullable=True)
    premium_max_drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0)
    premium_expectancy: Mapped[float] = mapped_column(Float, default=0.0)
    premium_charges: Mapped[float] = mapped_column(Float, default=0.0)
    premium_trades_json: Mapped[str] = mapped_column(Text, default="[]")
    premium_error: Mapped[str] = mapped_column(String(200), default="")
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
            "segment": self.segment, "strategy_key": self.strategy_key or "trend_impulse_v3",
            "interval": self.interval,
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
            # synthetic-premium backtest (audit C6)
            "premium_trades": self.premium_trades,
            "premium_win_rate": round(self.premium_win_rate, 1),
            "premium_net_pnl": round(self.premium_net_pnl, 0),
            "premium_return_pct": round(self.premium_return_pct, 1),
            "premium_profit_factor": (round(self.premium_profit_factor, 3)
                                      if self.premium_profit_factor is not None else None),
            "premium_max_drawdown_pct": round(self.premium_max_drawdown_pct, 1),
            "premium_expectancy": round(self.premium_expectancy, 0),
            "premium_charges": round(self.premium_charges, 0),
            "premium_error": self.premium_error,
        }


class SignalEvent(Base):
    __tablename__ = "signal_events"
    # Which deployment executed this. server_default="1" is load-bearing: every
    # row written before Phase B belongs to the legacy book, and any insert path
    # that has not been taught about deployments still lands there instead of
    # failing. See LEGACY_DEPLOYMENT_ID.
    deployment_id: Mapped[int] = mapped_column(
        ForeignKey("deployments.id"), default=LEGACY_DEPLOYMENT_ID,
        server_default="1", index=True)
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


class Project(Base):
    """An organisational editor container; never an execution root."""
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived')", name="ck_projects_status"),
    )

    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="",
                                              server_default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active",
                                        server_default="active")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.now)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.now)


class GraphArtifact(Base):
    """One stable graph lineage with an optimistic-concurrency working draft."""
    __tablename__ = "graph_artifacts"
    __table_args__ = (
        CheckConstraint("draft_revision >= 0", name="ck_graph_artifacts_draft_revision"),
        CheckConstraint(
            "published_revision IS NULL OR "
            "(published_revision >= 0 AND published_revision <= draft_revision)",
            name="ck_graph_artifacts_published_revision",
        ),
        CheckConstraint(
            "(current_version IS NULL) = (published_revision IS NULL)",
            name="ck_graph_artifacts_publication_state",
        ),
    )

    identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.project_id", ondelete="RESTRICT"), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    draft_json: Mapped[str] = mapped_column(Text, nullable=False)
    draft_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0")
    published_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.now)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.now)


class GraphVersion(Base):
    """An append-only executable IR artefact."""
    __tablename__ = "graph_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["graph_identifier"], ["graph_artifacts.identifier"], ondelete="RESTRICT"
        ),
        CheckConstraint("version >= 1", name="ck_graph_versions_version"),
        CheckConstraint(
            "json_valid(artifact_json)", name="ck_graph_versions_valid_json"
        ),
        CheckConstraint(
            "json_extract(artifact_json, '$.identifier') IS graph_identifier",
            name="ck_graph_versions_identifier_matches_json",
        ),
        CheckConstraint(
            "json_extract(artifact_json, '$.version') IS version",
            name="ck_graph_versions_version_matches_json",
        ),
        Index("ix_graph_versions_content_address", "content_address"),
    )

    graph_identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    artifact_json: Mapped[str] = mapped_column(Text, nullable=False)
    content_address: Mapped[str] = mapped_column(String(71), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.now)


@event.listens_for(GraphVersion, "before_insert")
def _graph_version_identity_matches_json(_mapper, _connection, target) -> None:
    """Refuse ORM persistence when executable bytes and identity diverge."""
    import json

    from app.ir.hashing import canonical_json, content_address

    document = json.loads(target.artifact_json)
    if canonical_json(document) != target.artifact_json:
        raise ValueError("graph version artifact_json must be canonical JSON")
    if content_address(document) != target.content_address:
        raise ValueError("graph version content address does not match artifact_json")


event.listen(
    GraphVersion.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER graph_versions_refuse_update "
        "BEFORE UPDATE ON graph_versions BEGIN "
        "SELECT RAISE(ABORT, 'graph versions are immutable'); END"
    ).execute_if(dialect="sqlite"),
)
event.listen(
    GraphVersion.__table__,
    "after_create",
    DDL(
        "CREATE TRIGGER graph_versions_refuse_delete "
        "BEFORE DELETE ON graph_versions BEGIN "
        "SELECT RAISE(ABORT, 'graph versions are immutable'); END"
    ).execute_if(dialect="sqlite"),
)


class IrGraphLayout(Base):
    """Revision head for sparse editor coordinates on one graph version.

    This is presentation state. It points at an immutable graph identity but is
    never an input to graph or component hashing. A parent row exists even when
    its position set is empty so optimistic concurrency still has a revision.
    """
    __tablename__ = "ir_graph_layouts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["graph_identifier", "graph_version"],
            ["graph_versions.graph_identifier", "graph_versions.version"],
            ondelete="RESTRICT",
            name="fk_ir_graph_layouts_graph_version",
        ),
    )

    graph_identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    graph_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=dt.datetime.now)


class IrGraphLayoutPosition(Base):
    """One authored node whose derived placement the editor has overridden."""
    __tablename__ = "ir_graph_layout_positions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["graph_identifier", "graph_version"],
            ["ir_graph_layouts.graph_identifier", "ir_graph_layouts.graph_version"],
            ondelete="CASCADE",
        ),
    )

    graph_identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    graph_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    instance_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)


class IrGraphLayoutGroup(Base):
    """One visual group in the revisioned presentation document."""
    __tablename__ = "ir_graph_layout_groups"
    __table_args__ = (
        ForeignKeyConstraint(
            ["graph_identifier", "graph_version"],
            ["ir_graph_layouts.graph_identifier", "ir_graph_layouts.graph_version"],
            ondelete="CASCADE",
            name="fk_ir_graph_layout_groups_layout",
        ),
        CheckConstraint("length(identifier) > 0", name="ck_ir_groups_identifier"),
        CheckConstraint("length(display_name) > 0", name="ck_ir_groups_display_name"),
        CheckConstraint("width > 0", name="ck_ir_groups_width"),
        CheckConstraint("height > 0", name="ck_ir_groups_height"),
    )

    graph_identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    graph_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    width: Mapped[float] = mapped_column(Float, nullable=False)
    height: Mapped[float] = mapped_column(Float, nullable=False)
    collapsed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("0")
    )


class IrGraphLayoutGroupMember(Base):
    """One authored instance included in a visual group."""
    __tablename__ = "ir_graph_layout_group_members"
    __table_args__ = (
        ForeignKeyConstraint(
            ["graph_identifier", "graph_version", "group_identifier"],
            [
                "ir_graph_layout_groups.graph_identifier",
                "ir_graph_layout_groups.graph_version",
                "ir_graph_layout_groups.identifier",
            ],
            ondelete="CASCADE",
            name="fk_ir_graph_layout_group_members_group",
        ),
    )

    graph_identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    graph_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    instance_id: Mapped[str] = mapped_column(String(128), primary_key=True)


class IrGraphLayoutOrphanArchive(Base):
    """Reversible quarantine for a pre-0006 layout with no graph version."""
    __tablename__ = "ir_graph_layout_orphan_archive"

    graph_identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    graph_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    archived_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


class IrGraphLayoutPositionOrphanArchive(Base):
    """Sparse positions quarantined with an orphan layout parent."""
    __tablename__ = "ir_graph_layout_position_orphan_archive"

    graph_identifier: Mapped[str] = mapped_column(String(128), primary_key=True)
    graph_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    instance_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)


class ProjectReviewNote(Base):
    """Mutable owner writing anchored to, but never copied into, a review event."""
    __tablename__ = "project_review_notes"
    __table_args__ = (
        CheckConstraint("length(event_id) BETWEEN 1 AND 200", name="ck_review_note_event_id"),
        CheckConstraint(
            "event_type IN ('graph_version_published', 'experiment_run', "
            "'finding_created', 'candidate_created', 'candidate_decided')",
            name="ck_review_note_event_type",
        ),
        CheckConstraint("length(body) BETWEEN 1 AND 4000", name="ck_review_note_body"),
        CheckConstraint("created_by = 'owner'", name="ck_review_note_owner"),
        CheckConstraint("revision >= 0", name="ck_review_note_revision"),
        Index("ix_project_review_notes_project_event", "project_id", "event_id"),
    )

    note_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.project_id", ondelete="RESTRICT"), nullable=False)
    event_id: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(32), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.now)


class ProjectReviewSavedView(Base):
    """A named canonical review filter document; never a persisted cursor."""
    __tablename__ = "project_review_saved_views"
    __table_args__ = (
        CheckConstraint("length(name) BETWEEN 1 AND 80", name="ck_review_view_name"),
        CheckConstraint("json_valid(filters_json)", name="ck_review_view_filters_json"),
        CheckConstraint("created_by = 'owner'", name="ck_review_view_owner"),
        CheckConstraint("revision >= 0", name="ck_review_view_revision"),
        Index("ix_project_review_saved_views_project", "project_id"),
        Index(
            "uq_project_review_saved_views_active_name",
            "project_id", "name", unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    view_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.project_id", ondelete="RESTRICT"), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    filters_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(32), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, default=dt.datetime.now)


class ProjectReviewSnapshot(Base):
    """Append-only historical observation of the closed project review projection."""
    __tablename__ = "project_review_snapshots"
    __table_args__ = (
        CheckConstraint("length(label) BETWEEN 1 AND 80", name="ck_review_snapshot_label"),
        CheckConstraint("length(capture_key) = 36", name="ck_review_snapshot_capture_key"),
        CheckConstraint("created_by = 'owner'", name="ck_review_snapshot_owner"),
        CheckConstraint("json_valid(manifest_json)", name="ck_review_snapshot_manifest_json"),
        CheckConstraint(
            "json_extract(manifest_json, '$.schema_version') = 1",
            name="ck_review_snapshot_schema_version",
        ),
        CheckConstraint(
            "json_extract(manifest_json, '$.project_id') IS project_id",
            name="ck_review_snapshot_project_matches_json",
        ),
        CheckConstraint(
            "capture_completed_at >= capture_started_at",
            name="ck_review_snapshot_capture_window",
        ),
        Index("ix_project_review_snapshots_project_completed", "project_id", "capture_completed_at"),
        Index(
            "uq_project_review_snapshots_capture_key",
            "project_id", "capture_key", unique=True,
        ),
    )

    snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.project_id", ondelete="RESTRICT"), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    capture_key: Mapped[str] = mapped_column(String(36), nullable=False)
    manifest_json: Mapped[str] = mapped_column(Text, nullable=False)
    content_address: Mapped[str] = mapped_column(String(71), nullable=False)
    created_by: Mapped[str] = mapped_column(String(32), nullable=False)
    capture_started_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    capture_completed_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)


@event.listens_for(ProjectReviewSnapshot, "before_insert")
def _review_snapshot_identity_matches_json(_mapper, _connection, target) -> None:
    import json

    from app.core.review_snapshot import validate_snapshot_manifest
    from app.ir.hashing import canonical_json

    document = json.loads(target.manifest_json)
    if canonical_json(document) != target.manifest_json:
        raise ValueError("review snapshot manifest_json must be canonical JSON")
    validated = validate_snapshot_manifest(document)
    if validated.content_address != target.content_address:
        raise ValueError("review snapshot content address does not match manifest_json")


for trigger_name, operation in (
    ("project_review_snapshots_refuse_update", "UPDATE"),
    ("project_review_snapshots_refuse_delete", "DELETE"),
):
    event.listen(
        ProjectReviewSnapshot.__table__,
        "after_create",
        DDL(
            f"CREATE TRIGGER {trigger_name} BEFORE {operation} "
            "ON project_review_snapshots BEGIN "
            "SELECT RAISE(ABORT, 'review snapshots are immutable'); END"
        ).execute_if(dialect="sqlite"),
    )


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


class DailyAccountSnapshot(Base):
    """One row per IST calendar day: the real Kite account equity at last capture.
    The Calendar view derives YOUR discretionary daily P&L from the day-over-day
    change in account_net minus the bot's booked P&L that day (the bot's side comes
    straight from the Trade ledger). Recorded forward from go-live, so history
    builds from the first live day."""
    __tablename__ = "daily_account_snapshot"
    day: Mapped[str] = mapped_column(String(10), primary_key=True)   # "YYYY-MM-DD" IST
    account_net: Mapped[float] = mapped_column(Float, default=0.0)        # total account equity (margins.net)
    account_available: Mapped[float] = mapped_column(Float, default=0.0)  # free funds (live_balance)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)

    def to_dict(self) -> dict:
        return {"day": self.day, "account_net": round(self.account_net, 2),
                "account_available": round(self.account_available, 2)}


class OrderJournal(Base):
    """Persisted record of every real order the bot places (H13). Its WORKING set is
    the durable mirror of LiveBroker._inflight ∪ _pending_entries — the in-memory
    trackers are wiped on restart, so a crash in the ~10s order-poll window would
    otherwise leave an order whose outcome is unknown and unrecoverable. A row is
    written WORKING before placement, stamped with the order id once it acks, and
    marked TERMINAL on resolution. recover_journal() replays WORKING rows on startup.
    Every site that pops _inflight/_pending_entries must mark its row terminal so the
    two stay in lockstep."""
    __tablename__ = "order_journal"
    # Which deployment executed this. server_default="1" is load-bearing: every
    # row written before Phase B belongs to the legacy book, and any insert path
    # that has not been taught about deployments still lands there instead of
    # failing. See LEGACY_DEPLOYMENT_ID.
    deployment_id: Mapped[int] = mapped_column(
        ForeignKey("deployments.id"), default=LEGACY_DEPLOYMENT_ID,
        server_default="1", index=True)
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    tradingsymbol: Mapped[str] = mapped_column(String(64))
    instrument_key: Mapped[str] = mapped_column(String(64))
    side: Mapped[str] = mapped_column(String(8))          # BUY | SELL
    kind: Mapped[str] = mapped_column(String(12))         # options | equity
    intent: Mapped[str] = mapped_column(String(8))        # ENTRY | EXIT
    qty: Mapped[int] = mapped_column(Integer, default=0)
    context_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="WORKING", index=True)   # WORKING | TERMINAL
    resolution: Mapped[str | None] = mapped_column(String(24), nullable=True)
    # FILLED | REJECTED | CANCELLED | ADOPTED | DEAD | RACED_FILL | NEVER_PLACED | UNKNOWN
    filled_qty: Mapped[int] = mapped_column(Integer, default=0)
    avg_price: Mapped[float] = mapped_column(Float, default=0.0)
    placed_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)


class EarningsEvent(Base):
    """Cached next-results date per NSE/BSE cash-equity symbol, refreshed once a
    day by scripts/refresh_earnings.py from NSE's board-meetings feed. Purely
    informational — the /api/earnings endpoint reads this cache; the engine never
    touches it."""
    __tablename__ = "earnings_events"
    symbol: Mapped[str] = mapped_column(String(48), primary_key=True)
    event_date: Mapped[dt.date] = mapped_column(Date)
    purpose: Mapped[str] = mapped_column(String(128), default="")
    fetched_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.now)
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)


class IrShadowDivergence(Base):
    """L1 Stage 1 — one recorded disagreement between the authoritative strategy and its
    Component IR mirror.

    **This table is telemetry, never a money record.** Nothing in the execution path reads
    it; it exists so a disagreement observed weeks ago can be attributed to an exact graph
    version, an exact bar and an exact input frame, which is the whole point of running a
    shadow lane before adopting one.

    Only *disagreements* land here. Agreeing bars are counted in memory
    (`app/engine/ir_shadow_metrics.py`) — persisting every agreeing bar would add tens of
    thousands of rows a week on a 1 GB box and tell you nothing you did not already know.

    `ir_json` is nullable **on purpose**: NULL means the graph produced no verdict at all
    (it refused — insufficient history, a missing input, a runtime error), which is a
    different fact from a verdict of four `false` flags. Collapsing those two is the exact
    silent-degradation shape ADR 0011 exists to prevent, so the column may not be given a
    default.
    """

    __tablename__ = "ir_shadow_divergences"
    __table_args__ = (
        # The signal lane re-scans the same completed bar every 2.5 s until the next one
        # prints, so one bar would otherwise arrive dozens of times. One (instrument, bar,
        # graph, reason) is one row; `reason` is in the key because a bar that later fails
        # a *different* way is a different fact worth keeping.
        Index("uq_ir_shadow_divergence_bar", "instrument_key", "bar_time",
              "graph_address", "reason", unique=True),
        Index("ix_ir_shadow_divergences_observed", "observed_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    observed_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False, index=True)
    bar_time: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    instrument_key: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    authoritative_strategy_key: Mapped[str] = mapped_column(String(64), nullable=False)
    shadow_strategy_key: Mapped[str] = mapped_column(String(64), nullable=False)
    #: The graph's content address — `(key, version)` is the execution artefact, and this
    #: is the version half. A disagreement that cannot name its graph is unattributable.
    graph_address: Mapped[str] = mapped_column(String(71), nullable=False)
    authoritative_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    ir_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    warmup_state: Mapped[str] = mapped_column(String(16), nullable=False, default="settled")
    declared_warmup: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Content address of the exact bars the graph was given — same data, same identity.
    frame_id: Mapped[str] = mapped_column(String(71), nullable=False, default="")
    frame_bars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    frame_first_ts: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    frame_last_ts: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    reason: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    detail: Mapped[str] = mapped_column(String(400), nullable=False, default="")
    eval_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    #: Whether the instrument's market was open when this was observed. Stage 1 closes on
    #: "zero unexplained in-hours insufficient-history events", so out-of-hours events must
    #: be distinguishable from in-hours ones rather than counted together.
    market_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class IrShadowDeployment(Base):
    """A managed, **non-authoritative** shadow deployment of one immutable graph version.

    L1.3A turns the IR shadow pairing from runtime machinery into a server-owned record.
    It lets the platform state, durably and with lineage:

        *this approved graph version is deployed to this instrument at this interval in
        shadow mode, with this evidence and this admission state*

    and it is structurally unable to state that the graph may influence an order.

    **Why the identities are separate columns.** Project, graph identifier, graph version,
    content address, evidence lineage, deployment, instrument, interval and strategy key
    are nine different facts. The recorded defect class in this codebase is one layer
    asserting another's fact, and the cheapest way to commit it is to encode several of
    them in the strategy key and parse it back out. `strategy_key` here is the *stable
    execution identity* only — it survives a graph edit, which is exactly why it cannot
    identify the version that ran.

    **Why `execution_mode` and `authority` are columns with CHECK constraints rather than
    application logic.** ADR 0012 §3.2 reserves paper authority to the owner. A column the
    database refuses to set to anything but `shadow`/`non_authoritative` cannot be widened
    by a route, a migration data-fix, a restart path or a mistaken service call — only by a
    reviewed schema change. `AUTHORITY_BY_SOURCE` is the gate; this is the lock on the same
    door, and the two fail closed independently.

    **Why evidence is recorded rather than foreign-keyed.** The approval lineage lives in
    the research plane's own database (hard invariant 5: isolated, read-only bridges only).
    A cross-database foreign key is impossible and a cross-database write would breach the
    isolation, so activation *verifies* the lineage through the read-only bridge and
    records the verified identity. The row therefore states what was checked and when, and
    re-verification on reload is what keeps that claim honest rather than historical.
    """

    __tablename__ = "ir_shadow_deployments"
    __table_args__ = (
        ForeignKeyConstraint(["project_id"], ["projects.project_id"], ondelete="RESTRICT"),
        ForeignKeyConstraint(["graph_identifier", "graph_version"],
                             ["graph_versions.graph_identifier", "graph_versions.version"],
                             ondelete="RESTRICT"),
        ForeignKeyConstraint(["deployment_id"], ["deployments.id"], ondelete="RESTRICT"),
        # One live shadow evaluator per (deployment, instrument, interval). Retired and
        # paused rows are excluded so a retirement frees the slot without deleting the
        # history that says what once ran there.
        Index("uq_ir_shadow_deployment_active", "deployment_id", "instrument_key",
              "interval", unique=True,
              sqlite_where=text("state IN ('staged','shadow_active','paused')")),
        Index("ix_ir_shadow_deployments_state", "state"),
        CheckConstraint("runtime_source = 'ir_graph'",
                        name="ck_ir_shadow_deployment_source"),
        CheckConstraint("execution_mode = 'shadow'",
                        name="ck_ir_shadow_deployment_mode"),
        CheckConstraint("authority = 'non_authoritative'",
                        name="ck_ir_shadow_deployment_authority"),
        CheckConstraint("state IN ('staged','shadow_active','paused','retired')",
                        name="ck_ir_shadow_deployment_state"),
        CheckConstraint("graph_version >= 1", name="ck_ir_shadow_deployment_version"),
        CheckConstraint("revision >= 0", name="ck_ir_shadow_deployment_revision"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    #: Which project owns the logic. Not derivable from the graph identifier.
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    #: The exact immutable artefact. `(identifier, version)` is the executable identity;
    #: an edit mints a new version and therefore cannot inherit this row.
    graph_identifier: Mapped[str] = mapped_column(String(128), nullable=False)
    graph_version: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Recorded at activation and re-verified on every reload. A content address that stops
    #: matching its version means the bytes moved under a row that claims to name them.
    graph_content_address: Mapped[str] = mapped_column(String(71), nullable=False)
    #: Verified research lineage, recorded rather than foreign-keyed (see the class
    #: docstring). NULL run id means "staged without evidence", which may not activate.
    evidence_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_candidate_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence_content_address: Mapped[str] = mapped_column(String(71), nullable=False,
                                                          default="", server_default="")
    evidence_verified_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    #: Which book this observes. It observes it; it never writes to it.
    deployment_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    instrument_key: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    interval: Mapped[str] = mapped_column(String(16), nullable=False)
    #: The stable key the adapter registers under — identity across edits, not of a build.
    strategy_key: Mapped[str] = mapped_column(String(64), nullable=False)
    runtime_source: Mapped[str] = mapped_column(String(16), nullable=False,
                                                default="ir_graph",
                                                server_default="ir_graph")
    execution_mode: Mapped[str] = mapped_column(String(16), nullable=False,
                                                default="shadow",
                                                server_default="shadow")
    authority: Mapped[str] = mapped_column(String(20), nullable=False,
                                           default="non_authoritative",
                                           server_default="non_authoritative")
    #: The warmup/history verdict from the Stage 1 admission contract, decided before
    #: activation so an impossible pairing is refused rather than discovered per-scan.
    admission_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
                                               server_default="0")
    admission_reason: Mapped[str] = mapped_column(String(400), nullable=False,
                                                  default="", server_default="")
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="staged",
                                       server_default="staged")
    #: Optimistic concurrency. Every transition names the revision it believes it is
    #: acting on, so two operators cannot silently overwrite one another's decision.
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0,
                                          server_default="0")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                    default=dt.datetime.now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False,
                                                    default=dt.datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "project_id": self.project_id,
            "graph_identifier": self.graph_identifier,
            "graph_version": self.graph_version,
            "graph_content_address": self.graph_content_address,
            "evidence_run_id": self.evidence_run_id,
            "evidence_candidate_id": self.evidence_candidate_id,
            "evidence_content_address": self.evidence_content_address,
            "evidence_verified_at": (self.evidence_verified_at.isoformat()
                                     if self.evidence_verified_at else None),
            "deployment_id": self.deployment_id,
            "instrument_key": self.instrument_key, "interval": self.interval,
            "strategy_key": self.strategy_key, "runtime_source": self.runtime_source,
            "execution_mode": self.execution_mode, "authority": self.authority,
            "admission_ok": self.admission_ok, "admission_reason": self.admission_reason,
            "state": self.state, "revision": self.revision, "note": self.note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
