"""
Dashboard analytics, computed from the persisted ledger (Trade + EquitySnapshot).

  - portfolio equity curve (mark-to-market each tick, includes unrealized)
  - per-instrument equity curves (cumulative realized net P&L by exit time)
  - win rate / expectancy / charges, overall and per instrument
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.execution_book import capital_for_book, configured_execution_mode
from app.db.models import (LEGACY_BROKER_ACCOUNT_ID, CapitalState, EquitySnapshot, Position,
                           SignalEvent, Trade)
from app.strategy.registry import DEFAULT_STRATEGY_KEY
from app.providers import capabilities as caps


def _seg(t: Trade) -> str:
    return t.segment or "options"


def _strat(t: Trade) -> str:
    # a null strategy_key means the engine default (v3) produced the trade
    return t.strategy_key or DEFAULT_STRATEGY_KEY


def _apply(trades: list[Trade], segment: str | None, strategy: str | None,
           since: "dt.datetime | None" = None) -> list[Trade]:
    if since is not None:
        cut = since.replace(tzinfo=None) if since.tzinfo else since
        trades = [t for t in trades if t.exit_time >= cut]
    if segment:
        trades = [t for t in trades if _seg(t) == segment]
    if strategy:
        trades = [t for t in trades if _strat(t) == strategy]
    return trades


def _stat_block(trades: list[Trade]) -> dict:
    """Full per-group performance block (used for per-instrument + instrument detail)."""
    n = len(trades)
    wins = [t for t in trades if t.win]
    nw = len(wins)
    nl = n - nw
    net = sum(t.net_pnl for t in trades)
    return {
        "trades": n,
        "wins": nw,
        "win_rate": round(100 * nw / n, 1) if n else 0.0,
        "net": round(net, 2),
        "gross": round(sum(t.gross_pnl for t in trades), 2),
        "charges": round(sum(t.charges_total for t in trades), 2),
        "avg_pnl": round(net / n, 2) if n else 0.0,
        "avg_win": round(sum(t.net_pnl for t in wins) / nw, 2) if nw else 0.0,
        "avg_loss": round(sum(t.net_pnl for t in trades if not t.win) / nl, 2) if nl else 0.0,
        "expectancy": round(net / n, 2) if n else 0.0,
        "avg_holding_minutes": round(sum(t.holding_minutes for t in trades) / n, 1) if n else 0.0,
        "best": round(max((t.net_pnl for t in trades), default=0.0), 2),
        "worst": round(min((t.net_pnl for t in trades), default=0.0), 2),
    }


def _cumulative_curve(trades: list[Trade]) -> list[dict]:
    """Cumulative realized net P&L by exit time (real rupees) — the realized-P&L
    curve used for per-segment / per-strategy views (EquitySnapshot is global-only)."""
    cum = 0.0
    out = []
    for t in sorted(trades, key=lambda x: x.exit_time):
        cum += t.net_pnl
        out.append({"time": int(t.exit_time.timestamp()), "value": round(cum, 2)})
    return out


def bot_vs_you(account_equity_now: float | None, account_baseline: float | None,
               bot_realized: float, bot_unrealized: float) -> dict:
    """Split the live account's change since baseline into the bot's tracked P&L
    and the 'unrecorded' remainder — assumed to be the owner's own trades (plus any
    deposits/withdrawals). Lets the dashboard show how the bot is doing vs the owner
    on the same account. Unavailable until a live account baseline exists."""
    if account_equity_now is None or account_baseline is None:
        return {"available": False}
    account_change = account_equity_now - account_baseline
    bot_pnl = bot_realized + bot_unrealized
    return {
        "available": True,
        "account_equity": round(account_equity_now, 2),
        "account_change": round(account_change, 2),
        "bot_pnl": round(bot_pnl, 2),
        "your_pnl_unrecorded": round(account_change - bot_pnl, 2),
    }


def account_pnl(s: Session, provider, book: str | None = None, *, owner_id: str,
                broker_account_id: str) -> dict:
    """Bot-vs-you split from a caller-owned session + the live provider. Records the
    account baseline once, on the first successful live equity read."""
    book = book or configured_execution_mode()
    cap = capital_for_book(s, book, broker_account_id=broker_account_id)
    eq = (provider.account_equity()
          if caps.provider_supports(provider, caps.ACCOUNT_EQUITY) else None)
    if eq is not None and not cap.account_baseline:
        cap.account_baseline = eq
        s.commit()
    opens = open_positions(
        s, book, owner_id=owner_id, broker_account_id=broker_account_id)
    # E8: defer to the direction-aware Position.unrealized_pnl() — the inlined
    # (last - entry) * qty formula inverted the sign of an open equity SHORT, showing a
    # winning short as a loss and mis-attributing the gap to the owner's own trades.
    bot_unrealized = sum(p.unrealized_pnl() for p in opens)
    return bot_vs_you(eq, cap.account_baseline, cap.realized_pnl, bot_unrealized)


def capital_dict(s: Session, book: str | None = None, *, owner_id: str,
                 broker_account_id: str) -> dict:
    """Capital snapshot from a caller-owned session (thread-safe for API use).

    `book` names the execution book. It is optional only so that a caller with no
    broker to hand keeps working; when omitted the process's own book is used, which
    is what every production caller means. It is never "both": cash and realised P&L
    from two ledgers cannot be summed into one meaningful figure."""
    book = book or configured_execution_mode()
    cap = capital_for_book(s, book, broker_account_id=broker_account_id)
    opens = open_positions(
        s, book, owner_id=owner_id, broker_account_id=broker_account_id)
    # segment-aware: leveraged MIS contributes margin + unrealized P&L, not full
    # notional (raw last × qty), which double-counts leverage and inflates equity.
    mtm = sum(p.mtm_value() for p in opens)
    return {
        "initial": cap.initial_capital, "cash": round(cap.cash, 2),
        "invested": round(sum(p.entry_cost for p in opens), 2),
        "equity": round(cap.cash + mtm, 2),
        "realized_pnl": round(cap.realized_pnl, 2),
        "open_count": len(opens),
    }


def open_positions(s: Session, book: str | None = None, *, owner_id: str,
                   broker_account_id: str) -> list[Position]:
    """One book's open positions. Isolated, not cross-book: an open position is a claim
    on one ledger's cash, and mixing the two makes every figure derived from it wrong."""
    book = book or configured_execution_mode()
    return list(s.scalars(select(Position).where(
        Position.mode == book,
        Position.owner_id == owner_id,
        Position.broker_account_id == broker_account_id,
    )))


def equity_curve(s: Session, limit: int = 2000, since: "dt.datetime | None" = None,
                 book: str | None = None, *, owner_id: str,
                 broker_account_id: str) -> list[dict]:
    # Filter + tail-limit in SQL: this feeds /api/dashboard's 5s poll, and the old
    # version materialized the whole table (~72k rows on the live VPS) per call —
    # the second allocator-churn leak of the 2026-07-23 outage (with signal_counts).
    q = select(EquitySnapshot).where(
        EquitySnapshot.owner_id == owner_id,
        EquitySnapshot.broker_account_id == broker_account_id,
    ).order_by(EquitySnapshot.time.desc(), EquitySnapshot.id.desc())
    # Book is opt-in here and only here among the isolated queries: points written before
    # 2026-08-07 carry no book (ADR 0012 §6.3), so defaulting to one would silently drop
    # the entire pre-slice curve. Callers plotting a single book pass it explicitly.
    if book is not None:
        q = q.where(EquitySnapshot.book == book)
    if since is not None:
        cut = since.replace(tzinfo=None) if since.tzinfo else since
        q = q.where(EquitySnapshot.time >= cut)
    snaps = list(s.scalars(q.limit(limit)))
    return [sn.to_dict() for sn in reversed(snaps)]


def _closed_on(s: Session, day, book: str, *, owner_id: str,
               broker_account_id: str):
    """One book's trades closed on `day`. The shared half of the two risk controls below.

    Both were `select(Trade)` with a Python-side date filter and no book predicate, so a
    paper loss could halt the live book and a paper win could mask a live loss. A risk
    control that counts the wrong book's money is not a conservative approximation — it
    is wrong in both directions."""
    return [t for t in s.scalars(select(Trade).where(
                Trade.mode == book,
                Trade.owner_id == owner_id,
                Trade.broker_account_id == broker_account_id))
            if t.exit_time and t.exit_time.date() == day]


def realized_on(s: Session, day, book: str, *, owner_id: str,
                broker_account_id: str) -> float:
    """Net realised P&L booked by `book` on `day` — the daily-loss circuit breaker."""
    return sum(t.net_pnl for t in _closed_on(
        s, day, book, owner_id=owner_id, broker_account_id=broker_account_id))


def round_trips_on(s: Session, day, book: str, *, owner_id: str,
                   broker_account_id: str) -> int:
    """Completed round trips booked by `book` on `day` — the daily round-trip cap (#10)."""
    return len(_closed_on(
        s, day, book, owner_id=owner_id, broker_account_id=broker_account_id))


def per_instrument_curves(s: Session, segment: str | None = None,
                          strategy: str | None = None,
                          since: "dt.datetime | None" = None, *, owner_id: str,
                          broker_account_id: str) -> dict[str, list[dict]]:
    trades = _apply(list(s.scalars(select(Trade).where(
        Trade.owner_id == owner_id,
        Trade.broker_account_id == broker_account_id,
    ).order_by(Trade.exit_time))), segment, strategy, since)
    curves: dict[str, list[dict]] = {}
    cum: dict[str, float] = {}
    for t in trades:
        cum[t.instrument_key] = cum.get(t.instrument_key, 0.0) + t.net_pnl
        curves.setdefault(t.instrument_key, []).append(
            {"time": int(t.exit_time.timestamp()), "value": round(cum[t.instrument_key], 2)})
    return curves


def realized_curve(s: Session, segment: str | None = None,
                   strategy: str | None = None,
                   since: "dt.datetime | None" = None, *, owner_id: str,
                   broker_account_id: str) -> list[dict]:
    """Cumulative realized net-P&L curve for a (segment, strategy) slice."""
    return _cumulative_curve(_apply(list(s.scalars(select(Trade).where(
        Trade.owner_id == owner_id,
        Trade.broker_account_id == broker_account_id,
    ))), segment, strategy, since))


def segment_curves(s: Session, since: "dt.datetime | None" = None, *, owner_id: str,
                   broker_account_id: str) -> dict[str, list[dict]]:
    """One realized curve per segment (options vs equity_intraday) — the portfolio
    overlay so options and outrights are visible side by side."""
    trades = list(s.scalars(select(Trade).where(
        Trade.owner_id == owner_id,
        Trade.broker_account_id == broker_account_id,
    )))
    if since is not None:
        cut = since.replace(tzinfo=None) if since.tzinfo else since
        trades = [t for t in trades if t.exit_time >= cut]
    return {seg: _cumulative_curve([t for t in trades if _seg(t) == seg])
            for seg in ("options", "equity_intraday")}


def strategy_curves(s: Session, segment: str | None = None,
                    since: "dt.datetime | None" = None, *, owner_id: str,
                    broker_account_id: str) -> dict[str, list[dict]]:
    """One realized curve per strategy (optionally within a segment) — so you can see
    how each strategy performed inside options and inside outrights."""
    trades = list(s.scalars(select(Trade).where(
        Trade.owner_id == owner_id,
        Trade.broker_account_id == broker_account_id,
    )))
    if since is not None:
        cut = since.replace(tzinfo=None) if since.tzinfo else since
        trades = [t for t in trades if t.exit_time >= cut]
    if segment:
        trades = [t for t in trades if _seg(t) == segment]
    keys = sorted({_strat(t) for t in trades})
    return {k: _cumulative_curve([t for t in trades if _strat(t) == k]) for k in keys}


def summary(s: Session, segment: str | None = None, strategy: str | None = None,
            since: "dt.datetime | None" = None, *, owner_id: str,
            broker_account_id: str) -> dict:
    trades = _apply(list(s.scalars(select(Trade).where(
        Trade.owner_id == owner_id,
        Trade.broker_account_id == broker_account_id,
    ).order_by(Trade.exit_time))), segment, strategy, since)
    n = len(trades)
    wins = [t for t in trades if t.win]
    net = sum(t.net_pnl for t in trades)
    gross = sum(t.gross_pnl for t in trades)
    charges = sum(t.charges_total for t in trades)

    groups: dict[str, list[Trade]] = {}
    for t in trades:
        groups.setdefault(t.instrument_key, []).append(t)
    per = {k: _stat_block(v) for k, v in groups.items()}
    ranked = sorted(per.items(), key=lambda x: x[1]["net"], reverse=True)
    return {
        "trades": n,
        "wins": len(wins),
        "losses": n - len(wins),
        "win_rate": round(100 * len(wins) / n, 1) if n else 0.0,
        "expectancy": round(net / n, 2) if n else 0.0,
        "avg_win": round(sum(t.net_pnl for t in wins) / len(wins), 2) if wins else 0.0,
        "avg_loss": round(sum(t.net_pnl for t in trades if not t.win) / (n - len(wins)), 2) if (n - len(wins)) else 0.0,
        "gross_pnl": round(gross, 2),
        "charges": round(charges, 2),
        "net_pnl": round(net, 2),
        "per_instrument": per,
        "best": ranked[0][0] if ranked else None,
        "worst": ranked[-1][0] if ranked else None,
    }


def _narrow(q, segment: str | None, strategy: str | None,
            since: "dt.datetime | None", *, owner_id: str,
            broker_account_id: str):
    """`_apply`'s predicates, expressed in SQL rather than over a materialised list.

    The normalisation is the whole reason this filtering used to live in Python: an unset
    `segment` means options and an unset `strategy_key` means the engine default, and both
    are legacy shapes in the money record.

    `NULLIF(col, '')` inside the COALESCE is load-bearing, not decoration. `_seg`/`_strat`
    used Python's `or`, which is falsy for the **empty string** as well as for None. A
    plain `COALESCE(segment, 'options')` matches only NULL, so a row with `segment = ''`
    would have normalised to "options" under the old code and to "" under the new — a
    silent behaviour change in a money-reporting filter. `trades.segment` is NOT NULL
    today, so the empty string is in fact the *only* reachable unset shape for it.
    `test_analytics_scan_bounds.py` compares every filter combination against the old
    implementation over both shapes so the two cannot drift.
    """
    q = q.where(
        Trade.owner_id == owner_id,
        Trade.broker_account_id == broker_account_id,
    )
    if since is not None:
        q = q.where(Trade.exit_time >= (since.replace(tzinfo=None) if since.tzinfo else since))
    if segment:
        q = q.where(func.coalesce(func.nullif(Trade.segment, ""), "options") == segment)
    if strategy:
        q = q.where(
            func.coalesce(func.nullif(Trade.strategy_key, ""), DEFAULT_STRATEGY_KEY) == strategy)
    return q


def recent_trades(s: Session, limit: int = 50, mode: str | None = None,
                  segment: str | None = None, strategy: str | None = None,
                  since: "dt.datetime | None" = None, *, owner_id: str,
                  broker_account_id: str) -> list[dict]:
    # Filter AND limit in SQL. This used to select every `Trade` row, filter in Python and
    # slice — so `limit` bounded the response and not the read. That is the same shape as
    # the `equity_curve`/`signal_counts` leaks of the 2026-07-23 outage (see the note at
    # `equity_curve`); this one survived that fix and is the reporting surface behind
    # /api/trades and the dashboard's 5s poll.
    q = select(Trade).order_by(Trade.exit_time.desc())
    if mode in ("paper", "live"):
        q = q.where(Trade.mode == mode)   # keep paper and real trades cleanly separated
    trades = list(s.scalars(_narrow(
        q, segment, strategy, since, owner_id=owner_id,
        broker_account_id=broker_account_id).limit(limit)))
    return [t.to_dict() for t in trades]


def instrument_stats(s: Session, key: str, segment: str | None = None,
                     strategy: str | None = None, since: "dt.datetime | None" = None,
                     *, owner_id: str, broker_account_id: str) -> dict:
    """Full stat block for one instrument (segment/strategy/period aware).

    Deliberately unlimited: a statistic over a subset of its own population is wrong, not
    merely partial. The scan is bounded by `instrument_key` instead, which is indexed.
    """
    q = select(Trade).where(Trade.instrument_key == key)
    return _stat_block(list(s.scalars(_narrow(
        q, segment, strategy, since, owner_id=owner_id,
        broker_account_id=broker_account_id))))


def instrument_trades(s: Session, key: str, segment: str | None = None,
                      strategy: str | None = None, since: "dt.datetime | None" = None,
                      limit: int = 500, *, owner_id: str,
                      broker_account_id: str) -> list[dict]:
    """That instrument's trades, newest first (segment/strategy/period aware)."""
    q = select(Trade).where(Trade.instrument_key == key).order_by(Trade.exit_time.desc())
    trades = list(s.scalars(_narrow(
        q, segment, strategy, since, owner_id=owner_id,
        broker_account_id=broker_account_id).limit(limit)))
    return [t.to_dict() for t in trades]


def signal_counts(s: Session, now: dt.datetime, rolling_days: int = 7, *, owner_id: str,
                  broker_account_id: str) -> dict[str, dict]:
    """Per-instrument entry-signal tallies: `today` (since IST start-of-day) and
    `rolling` (last `rolling_days`). `now` must be naive IST wall-clock so it
    compares correctly against SignalEvent.time. Only instruments that fired in
    the rolling window appear; callers default the rest to zero."""
    if now.tzinfo is not None:
        now = now.replace(tzinfo=None)
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_roll = now - dt.timedelta(days=rolling_days)
    # Aggregate in SQL — this runs on every /api/signals poll (~5s), and the old
    # per-row ORM loop materialized the whole 7-day window (~70k rows) each call:
    # ~4.6s latency + allocator-retained heap that ratcheted RSS to OOM on the
    # 1GB VPS (2026-07-23 outage, second leak after the WS hub).
    from sqlalchemy import case, func
    rows = s.execute(
        select(
            SignalEvent.instrument_key,
            func.count().label("rolling"),
            func.sum(case((SignalEvent.time >= start_today, 1), else_=0)).label("today"),
        )
        .where(
            SignalEvent.time >= start_roll,
            SignalEvent.owner_id == owner_id,
            SignalEvent.broker_account_id == broker_account_id,
        )
        .group_by(SignalEvent.instrument_key)
    )
    return {key: {"today": int(today or 0), "rolling": int(rolling)}
            for key, rolling, today in rows}
