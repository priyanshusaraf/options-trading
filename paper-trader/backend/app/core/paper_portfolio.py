"""Read realized paper results from the owner's ledger, without execution authority."""
from __future__ import annotations

import datetime as dt
from decimal import Decimal
import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import GraphArtifact, Project, Trade


def _graph_key(key: str | None, names: dict[str, str]) -> str | None:
    if key in names:
        return key
    match = re.fullmatch(r"(.+)\.[a-f0-9]{12}", key or "")
    return match[1] if match and match[1] in names else None


def _display_name(key: str | None, names: dict[str, str]) -> str:
    if key is None:
        return "Unattributed strategy"
    graph = _graph_key(key, names)
    if graph is not None:
        return names[graph]
    return {"trend_impulse_v3": "Trend Impulse V3",
            "expanding_z_v4": "Expanding Z Impulse V4"}.get(key, "Saved strategy")


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01")))


def read_paper_portfolio(session: Session, *, owner_id: str) -> dict:
    """All closed paper trades, grouped by ledger day and exact strategy revision.

    Ledger timestamps are local exchange wall time. Date-only points preserve that
    meaning without reinterpreting them in the API server's timezone. Capital,
    open marks and independent backtests do not enter this realized-P&L series.
    SQL aggregates before materialization; no trade-history truncation is applied.
    """
    day = func.date(Trade.exit_time)
    rows = session.execute(select(
        day.label("day"), Trade.strategy_key, Trade.strategy_version,
        func.sum(Trade.net_pnl).label("net"), func.count().label("count"),
    ).where(Trade.owner_id == owner_id, Trade.mode == "paper").group_by(
        day, Trade.strategy_key, Trade.strategy_version,
    ).order_by(day, Trade.strategy_key, Trade.strategy_version)).all()
    graphs = session.execute(select(
        GraphArtifact.identifier, GraphArtifact.display_name,
        GraphArtifact.current_version, Project.status,
    ).join(Project, (Project.owner_id == GraphArtifact.owner_id)
           & (Project.project_id == GraphArtifact.project_id)).where(
        GraphArtifact.owner_id == owner_id).order_by(GraphArtifact.identifier)).all()
    names = {f"ir.{graph.identifier}": graph.display_name for graph in graphs}
    result = _portfolio_result(rows, names)
    traded = {_graph_key(row.strategy_key, names) for row in rows}
    result["untraded_strategies"] = [
        {"strategy_key": f"ir.{graph.identifier}",
         "strategy_version": str(graph.current_version) if graph.current_version is not None else None,
         "display_name": graph.display_name}
        for graph in graphs
        if graph.status == "active" and f"ir.{graph.identifier}" not in traded
    ]
    return result


def _portfolio_result(rows, names: dict[str, str]) -> dict:
    daily: dict[str, Decimal] = {}
    strategies: dict[tuple, dict] = {}
    for row in rows:
        value = Decimal(str(row.net))
        date = str(row.day)
        daily[date] = daily.get(date, Decimal(0)) + value
        identity = (row.strategy_key, row.strategy_version)
        item = strategies.setdefault(identity, {
            "strategy_key": row.strategy_key, "strategy_version": row.strategy_version,
            "display_name": _display_name(row.strategy_key, names),
            "realized_pnl": Decimal(0), "closed_trades": 0,
        })
        item["realized_pnl"] += value
        item["closed_trades"] += row.count
    points = _points(daily)
    items = [{**item, "realized_pnl": _money(item["realized_pnl"])}
             for item in strategies.values()]
    return {
        "schema": "paper-portfolio/1", "currency": "INR",
        "as_of": dt.datetime.now(dt.timezone.utc).isoformat(),
        "points": points, "strategies": items,
        "realized_pnl": points[-1]["realized_pnl"] if points else 0.0,
        "closed_trades": sum(item["closed_trades"] for item in items),
    }


def _points(daily: dict[str, Decimal]) -> list[dict]:
    cumulative = Decimal(0)
    points = []
    for date, net in sorted(daily.items()):
        cumulative += net
        points.append({"timestamp": date, "realized_pnl": _money(cumulative)})
    return points
