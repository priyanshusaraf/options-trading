"""
Backtest sweep + portfolio API.

  POST /api/backtest/sweep              start a sweep (background); returns run id
  GET  /api/backtest/status             latest run progress (for the progress bar)
  GET  /api/backtest/runs               all past runs (browse history; nothing wasted)
  GET  /api/backtest/results            filterable result list (win%/PF/DD/return)
  GET  /api/backtest/result/{key}/{iv}  drill-down: equity curve + trade list
  GET  /api/backtest/export             download a run's results as CSV
"""
from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, select

from app.backtest import sweep
from app.core.config import get_settings
from app.core.instruments import get_instrument
from app.db.models import BacktestResult, BacktestRun
from app.db.session import SessionLocal


def _budget(request: Request) -> float:
    """The owner's real tradeable budget for affordability flags: the live Kite
    account's free funds when known (cached by the engine), else the configured
    initial_capital. Budget-relative flags are computed at THIS layer so they track
    the account without re-running the (budget-independent) backtest."""
    runner = getattr(request.app.state, "runner", None)
    funds = getattr(runner, "_account_funds", None) if runner else None
    if funds and funds.get("available"):
        return float(funds["available"])
    return float(get_settings().initial_capital or 50_000.0)


def _with_affordability(d: dict, budget: float) -> dict:
    """Attach budget-relative affordability to a result row. We trade OPTIONS (1
    lot of an ATM option) which are far cheaper than the futures notional, so a name
    can be unaffordable as futures yet tradable as options. option_cost==0 means we
    couldn't estimate it (treat as unknown, not affordable)."""
    notional = d.get("notional") or 0.0
    opt = d.get("option_cost") or 0.0
    d["budget"] = round(budget, 0)
    d["affordable_futures"] = bool(notional and notional <= budget)
    d["affordable_options"] = bool(opt and opt <= budget)
    return d

router = APIRouter(prefix="/api/backtest")


class SweepRequest(BaseModel):
    scope: str = "liquid"                 # "liquid" | "full"
    intervals: list[str] | None = None    # default: 1m/5m/15m/30m/1h/day
    capital: float = 50_000.0
    instruments: list[str] | None = None  # restrict to these keys (e.g. GOLD/SILVER/COPPER)
    lookback_days: int | None = None      # preset window in days (None = entire history)
    start_date: str | None = None         # ISO custom window start (overrides lookback)
    end_date: str | None = None           # ISO custom window end
    strategies: list[str] | None = None   # registry strategy keys (None = default v3)


@router.post("/sweep")
def start(body: SweepRequest):
    if sweep.is_running():
        return {"error": "a sweep is already running"}
    try:
        run_id = sweep.start_sweep(
            scope=body.scope, intervals=body.intervals, capital=body.capital,
            instruments=body.instruments, lookback_days=body.lookback_days,
            start_date=body.start_date, end_date=body.end_date,
            strategies=body.strategies)
    except Exception as e:
        return {"error": str(e)}
    return {"run_id": run_id, "running": True}


@router.get("/instruments")
def instruments(scope: str = "liquid"):
    """The resolvable backtest universe (for the instrument picker), plus the
    preset lookback windows and per-interval max history the UI discloses."""
    from app.backtest.universe import full_universe, liquid_universe
    from app.providers.factory import get_provider
    from app.strategy.registry import strategy_meta
    prov = get_provider()
    specs = full_universe(prov) if scope == "full" else liquid_universe(prov)
    out = sorted(({"key": i.key, "name": i.name, "segment": i.segment,
                   "has_options": getattr(i, "has_options", True)} for i in specs),
                 key=lambda d: (d["segment"], d["key"]))
    return {"instruments": out, "presets": list(sweep.PRESET_DAYS.keys()),
            "preset_days": sweep.PRESET_DAYS, "max_days": sweep.MAX_DAYS,
            "strategies": strategy_meta()}


@router.get("/status")
def status(run_id: int | None = None):
    with SessionLocal() as s:
        run = (s.get(BacktestRun, run_id) if run_id else
               s.scalars(select(BacktestRun).order_by(BacktestRun.id.desc())).first())
        if not run:
            return {"run": None, "running": sweep.is_running()}
        return {"run": run.to_dict(), "running": sweep.is_running()}


@router.get("/runs")
def runs(limit: int = 100):
    """Every past sweep, newest first — so no completed run is ever lost or
    silently overwritten. Each row carries a result count so the UI can show
    'NIFTY×6 · 312 cells · done · 19 Jun'."""
    with SessionLocal() as s:
        rows = list(s.scalars(select(BacktestRun).order_by(BacktestRun.id.desc()).limit(limit)))
        counts = dict(s.execute(
            select(BacktestResult.run_id, func.count())
            .where(BacktestResult.error == "")
            .group_by(BacktestResult.run_id)).all())
    out = []
    for r in rows:
        d = r.to_dict()
        d["result_count"] = int(counts.get(r.id, 0))
        out.append(d)
    return {"runs": out}


@router.get("/export")
def export(run_id: int | None = None):
    """Download a run's results as CSV (so a sweep's output survives outside the
    app). Defaults to the latest run."""
    cols = ["instrument_key", "name", "segment", "strategy_key", "interval", "trades", "wins",
            "win_rate", "win_rate_realised", "open_at_end", "profit_factor",
            "max_drawdown_pct", "worst_mae_pct", "return_pct", "return_pct_realised",
            "bh_return_pct", "net_pnl", "worst_trade_pnl", "gross_pnl", "charges",
            "expectancy", "cagr", "calmar", "consistency", "sharpe",
            "max_consec_losses", "time_underwater_pct",
            "notional", "option_cost", "lots", "affordable",
            "first_ts", "last_ts", "effective_days", "clamped",
            "bars", "from_cache"]
    with SessionLocal() as s:
        if run_id is None:
            run = s.scalars(select(BacktestRun).order_by(BacktestRun.id.desc())).first()
            run_id = run.id if run else -1
        rows = list(s.scalars(select(BacktestResult)
                              .where(BacktestResult.run_id == run_id,
                                     BacktestResult.error == "")))
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r.summary())
    return Response(
        content=buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="backtest_run_{run_id}.csv"'})


@router.get("/results")
def results(request: Request, run_id: int | None = None, interval: str | None = None,
            strategy: str | None = None,
            min_win_rate: float = 0.0, min_profit_factor: float = 0.0,
            max_drawdown: float = 100.0, min_return: float = -1e9,
            min_trades: int = 1, sort: str = "return_pct", limit: int = 500):
    budget = _budget(request)
    with SessionLocal() as s:
        if run_id is None:
            run = s.scalars(select(BacktestRun).order_by(BacktestRun.id.desc())).first()
            run_id = run.id if run else -1
        q = select(BacktestResult).where(BacktestResult.run_id == run_id)
        if strategy:
            q = q.where(BacktestResult.strategy_key == strategy)
        rows = list(s.scalars(q))

    out = []
    # survivorship disclosure (DV-1): cells excluded from the visible set, by reason,
    # so the visible list is never mistaken for the whole universe.
    skipped = 0
    skipped_errored = 0          # candle/window/out-of-range errors (silently dropped before)
    skipped_low_trades = 0       # too few trades to be meaningful
    skipped_filtered = 0         # failed the user's win%/PF/DD/return filters
    unaffordable = 0             # can't afford 1 lot of the ATM OPTION at the current budget — badged, NOT hidden
    for r in rows:
        if interval and r.interval != interval:
            continue
        if r.error:
            skipped += 1
            skipped_errored += 1
            continue
        if r.trades < min_trades:
            skipped += 1
            skipped_low_trades += 1
            continue
        pf = r.profit_factor if r.profit_factor is not None else 1e9
        if (r.win_rate < min_win_rate or pf < min_profit_factor
                or r.max_drawdown_pct > max_drawdown or r.return_pct < min_return):
            skipped += 1
            skipped_filtered += 1
            continue
        d = _with_affordability(r.summary(), budget)
        try:
            d["has_options"] = bool(get_instrument(r.instrument_key).has_options)
        except KeyError:
            d["has_options"] = True
        if not d["affordable_options"]:
            unaffordable += 1
        out.append(d)

    # lower-is-better metrics sort ascending; everything else descending
    reverse = sort not in ("max_drawdown_pct", "charges", "max_consec_losses",
                           "time_underwater_pct", "worst_mae_pct")
    out.sort(key=lambda d: (d.get(sort) if d.get(sort) is not None else -1e18), reverse=reverse)
    return {"run_id": run_id, "count": len(out), "results": out[:limit],
            "budget": round(budget, 0), "skipped": skipped, "unaffordable": unaffordable,
            "skipped_breakdown": {
                "errored": skipped_errored, "low_trades": skipped_low_trades,
                "filtered": skipped_filtered}}


@router.get("/result/{key}/{interval}")
def result_detail(key: str, interval: str, request: Request, run_id: int | None = None,
                  strategy: str | None = None):
    with SessionLocal() as s:
        if run_id is None:
            run = s.scalars(select(BacktestRun).order_by(BacktestRun.id.desc())).first()
            run_id = run.id if run else -1
        q = select(BacktestResult).where(
            BacktestResult.run_id == run_id,
            BacktestResult.instrument_key == key,
            BacktestResult.interval == interval)
        if strategy:   # disambiguate when a run swept several strategies
            q = q.where(BacktestResult.strategy_key == strategy)
        r = s.scalar(q)
        if not r:
            return {"error": "no such result"}
        d = _with_affordability(r.summary(), _budget(request))
        d["equity_curve"] = json.loads(r.curve_json or "[]")
        d["bh_curve"] = json.loads(r.bh_curve_json or "[]")
        d["trades"] = json.loads(r.trades_json or "[]")
        return d
