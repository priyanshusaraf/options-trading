"""
Dashboard analytics, computed from the persisted ledger (Trade + EquitySnapshot).

  - portfolio equity curve (mark-to-market each tick, includes unrealized)
  - per-instrument equity curves (cumulative realized net P&L by exit time)
  - win rate / expectancy / charges, overall and per instrument
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CapitalState, EquitySnapshot, Position, Trade


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


def equity_curve(s: Session, limit: int = 2000) -> list[dict]:
    snaps = list(s.scalars(select(EquitySnapshot).order_by(EquitySnapshot.time)))
    return [sn.to_dict() for sn in snaps[-limit:]]


def per_instrument_curves(s: Session) -> dict[str, list[dict]]:
    trades = list(s.scalars(select(Trade).order_by(Trade.exit_time)))
    curves: dict[str, list[dict]] = {}
    cum: dict[str, float] = {}
    for t in trades:
        cum[t.instrument_key] = cum.get(t.instrument_key, 0.0) + t.net_pnl
        curves.setdefault(t.instrument_key, []).append(
            {"time": int(t.exit_time.timestamp()), "value": round(cum[t.instrument_key], 2)})
    return curves


def summary(s: Session) -> dict:
    trades = list(s.scalars(select(Trade).order_by(Trade.exit_time)))
    n = len(trades)
    wins = [t for t in trades if t.win]
    net = sum(t.net_pnl for t in trades)
    gross = sum(t.gross_pnl for t in trades)
    charges = sum(t.charges_total for t in trades)

    per: dict[str, dict] = {}
    for t in trades:
        d = per.setdefault(t.instrument_key,
                           {"trades": 0, "wins": 0, "net": 0.0, "gross": 0.0, "charges": 0.0})
        d["trades"] += 1
        d["wins"] += 1 if t.win else 0
        d["net"] += t.net_pnl
        d["gross"] += t.gross_pnl
        d["charges"] += t.charges_total
    for d in per.values():
        d["win_rate"] = round(100 * d["wins"] / d["trades"], 1) if d["trades"] else 0.0
        d["net"] = round(d["net"], 2)
        d["gross"] = round(d["gross"], 2)
        d["charges"] = round(d["charges"], 2)

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


def recent_trades(s: Session, limit: int = 50) -> list[dict]:
    trades = list(s.scalars(select(Trade).order_by(Trade.exit_time.desc()).limit(limit)))
    return [t.to_dict() for t in trades]
