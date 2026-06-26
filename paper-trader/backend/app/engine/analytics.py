"""
Dashboard analytics, computed from the persisted ledger (Trade + EquitySnapshot).

  - portfolio equity curve (mark-to-market each tick, includes unrealized)
  - per-instrument equity curves (cumulative realized net P&L by exit time)
  - win rate / expectancy / charges, overall and per instrument
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CapitalState, EquitySnapshot, Position, SignalEvent, Trade
from app.strategy.registry import DEFAULT_STRATEGY_KEY


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


def account_pnl(s: Session, provider) -> dict:
    """Bot-vs-you split from a caller-owned session + the live provider. Records the
    account baseline once, on the first successful live equity read."""
    cap = s.get(CapitalState, 1)
    eq = provider.account_equity() if getattr(provider, "name", "") == "kite" else None
    if eq is not None and not cap.account_baseline:
        cap.account_baseline = eq
        s.commit()
    opens = list(s.scalars(select(Position)))
    bot_unrealized = sum(((p.last_premium or p.entry_premium) - p.entry_premium) * p.qty
                         for p in opens)
    return bot_vs_you(eq, cap.account_baseline, cap.realized_pnl, bot_unrealized)


def capital_dict(s: Session) -> dict:
    """Capital snapshot from a caller-owned session (thread-safe for API use)."""
    cap = s.get(CapitalState, 1)
    opens = list(s.scalars(select(Position)))
    mtm = sum((p.last_premium or p.entry_premium) * p.qty for p in opens)
    return {
        "initial": cap.initial_capital, "cash": round(cap.cash, 2),
        "invested": round(sum(p.entry_cost for p in opens), 2),
        "equity": round(cap.cash + mtm, 2),
        "realized_pnl": round(cap.realized_pnl, 2),
        "open_count": len(opens),
    }


def open_positions(s: Session) -> list[Position]:
    return list(s.scalars(select(Position)))


def equity_curve(s: Session, limit: int = 2000, since: "dt.datetime | None" = None) -> list[dict]:
    snaps = list(s.scalars(select(EquitySnapshot).order_by(EquitySnapshot.time)))
    if since is not None:
        cut = since.replace(tzinfo=None) if since.tzinfo else since
        snaps = [sn for sn in snaps if sn.time >= cut]
    return [sn.to_dict() for sn in snaps[-limit:]]


def per_instrument_curves(s: Session, segment: str | None = None,
                          strategy: str | None = None,
                          since: "dt.datetime | None" = None) -> dict[str, list[dict]]:
    trades = _apply(list(s.scalars(select(Trade).order_by(Trade.exit_time))), segment, strategy, since)
    curves: dict[str, list[dict]] = {}
    cum: dict[str, float] = {}
    for t in trades:
        cum[t.instrument_key] = cum.get(t.instrument_key, 0.0) + t.net_pnl
        curves.setdefault(t.instrument_key, []).append(
            {"time": int(t.exit_time.timestamp()), "value": round(cum[t.instrument_key], 2)})
    return curves


def realized_curve(s: Session, segment: str | None = None,
                   strategy: str | None = None,
                   since: "dt.datetime | None" = None) -> list[dict]:
    """Cumulative realized net-P&L curve for a (segment, strategy) slice."""
    return _cumulative_curve(_apply(list(s.scalars(select(Trade))), segment, strategy, since))


def segment_curves(s: Session, since: "dt.datetime | None" = None) -> dict[str, list[dict]]:
    """One realized curve per segment (options vs equity_intraday) — the portfolio
    overlay so options and outrights are visible side by side."""
    trades = list(s.scalars(select(Trade)))
    if since is not None:
        cut = since.replace(tzinfo=None) if since.tzinfo else since
        trades = [t for t in trades if t.exit_time >= cut]
    return {seg: _cumulative_curve([t for t in trades if _seg(t) == seg])
            for seg in ("options", "equity_intraday")}


def strategy_curves(s: Session, segment: str | None = None,
                    since: "dt.datetime | None" = None) -> dict[str, list[dict]]:
    """One realized curve per strategy (optionally within a segment) — so you can see
    how each strategy performed inside options and inside outrights."""
    trades = list(s.scalars(select(Trade)))
    if since is not None:
        cut = since.replace(tzinfo=None) if since.tzinfo else since
        trades = [t for t in trades if t.exit_time >= cut]
    if segment:
        trades = [t for t in trades if _seg(t) == segment]
    keys = sorted({_strat(t) for t in trades})
    return {k: _cumulative_curve([t for t in trades if _strat(t) == k]) for k in keys}


def summary(s: Session, segment: str | None = None, strategy: str | None = None,
            since: "dt.datetime | None" = None) -> dict:
    trades = _apply(list(s.scalars(select(Trade).order_by(Trade.exit_time))), segment, strategy, since)
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


def recent_trades(s: Session, limit: int = 50, mode: str | None = None,
                  segment: str | None = None, strategy: str | None = None,
                  since: "dt.datetime | None" = None) -> list[dict]:
    q = select(Trade).order_by(Trade.exit_time.desc())
    if mode in ("paper", "live"):
        q = q.where(Trade.mode == mode)   # keep paper and real trades cleanly separated
    # segment/strategy filtered in Python so legacy NULLs normalise to options/v3
    trades = _apply(list(s.scalars(q)), segment, strategy, since)
    return [t.to_dict() for t in trades[:limit]]


def instrument_stats(s: Session, key: str, segment: str | None = None,
                     strategy: str | None = None, since: "dt.datetime | None" = None) -> dict:
    """Full stat block for one instrument (segment/strategy/period aware)."""
    trades = _apply(list(s.scalars(select(Trade).where(Trade.instrument_key == key))),
                    segment, strategy, since)
    return _stat_block(trades)


def instrument_trades(s: Session, key: str, segment: str | None = None,
                      strategy: str | None = None, since: "dt.datetime | None" = None,
                      limit: int = 500) -> list[dict]:
    """That instrument's trades, newest first (segment/strategy/period aware)."""
    q = select(Trade).where(Trade.instrument_key == key).order_by(Trade.exit_time.desc())
    trades = _apply(list(s.scalars(q)), segment, strategy, since)
    return [t.to_dict() for t in trades[:limit]]


def signal_counts(s: Session, now: dt.datetime, rolling_days: int = 7) -> dict[str, dict]:
    """Per-instrument entry-signal tallies: `today` (since IST start-of-day) and
    `rolling` (last `rolling_days`). `now` must be naive IST wall-clock so it
    compares correctly against SignalEvent.time. Only instruments that fired in
    the rolling window appear; callers default the rest to zero."""
    if now.tzinfo is not None:
        now = now.replace(tzinfo=None)
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_roll = now - dt.timedelta(days=rolling_days)
    out: dict[str, dict] = {}
    for ev in s.scalars(select(SignalEvent).where(SignalEvent.time >= start_roll)):
        d = out.setdefault(ev.instrument_key, {"today": 0, "rolling": 0})
        d["rolling"] += 1
        if ev.time >= start_today:
            d["today"] += 1
    return out
