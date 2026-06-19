"""
Backtest sweep + portfolio API.

  POST /api/backtest/sweep              start a sweep (background); returns run id
  GET  /api/backtest/status             latest run progress (for the progress bar)
  GET  /api/backtest/results            filterable result list (win%/PF/DD/return)
  GET  /api/backtest/result/{key}/{iv}  drill-down: equity curve + trade list
"""
from __future__ import annotations

import json

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.backtest import sweep
from app.db.models import BacktestResult, BacktestRun
from app.db.session import SessionLocal

router = APIRouter(prefix="/api/backtest")


class SweepRequest(BaseModel):
    scope: str = "liquid"                 # "liquid" | "full"
    intervals: list[str] | None = None    # default: 1m/5m/15m/30m/1h/day
    capital: float = 50_000.0


@router.post("/sweep")
def start(body: SweepRequest):
    if sweep.is_running():
        return {"error": "a sweep is already running"}
    try:
        run_id = sweep.start_sweep(scope=body.scope, intervals=body.intervals,
                                   capital=body.capital)
    except Exception as e:
        return {"error": str(e)}
    return {"run_id": run_id, "running": True}


@router.get("/status")
def status(run_id: int | None = None):
    with SessionLocal() as s:
        run = (s.get(BacktestRun, run_id) if run_id else
               s.scalars(select(BacktestRun).order_by(BacktestRun.id.desc())).first())
        if not run:
            return {"run": None, "running": sweep.is_running()}
        return {"run": run.to_dict(), "running": sweep.is_running()}


@router.get("/results")
def results(run_id: int | None = None, interval: str | None = None,
            min_win_rate: float = 0.0, min_profit_factor: float = 0.0,
            max_drawdown: float = 100.0, min_return: float = -1e9,
            min_trades: int = 1, sort: str = "return_pct", limit: int = 500):
    with SessionLocal() as s:
        if run_id is None:
            run = s.scalars(select(BacktestRun).order_by(BacktestRun.id.desc())).first()
            run_id = run.id if run else -1
        q = select(BacktestResult).where(BacktestResult.run_id == run_id)
        rows = list(s.scalars(q))

    out = []
    for r in rows:
        if r.error or r.trades < min_trades:
            continue
        if interval and r.interval != interval:
            continue
        pf = r.profit_factor if r.profit_factor is not None else 1e9
        if (r.win_rate < min_win_rate or pf < min_profit_factor
                or r.max_drawdown_pct > max_drawdown or r.return_pct < min_return):
            continue
        out.append(r.summary())

    reverse = sort not in ("max_drawdown_pct", "charges")
    out.sort(key=lambda d: (d.get(sort) if d.get(sort) is not None else -1e18), reverse=reverse)
    return {"run_id": run_id, "count": len(out), "results": out[:limit]}


@router.get("/result/{key}/{interval}")
def result_detail(key: str, interval: str, run_id: int | None = None):
    with SessionLocal() as s:
        if run_id is None:
            run = s.scalars(select(BacktestRun).order_by(BacktestRun.id.desc())).first()
            run_id = run.id if run else -1
        r = s.scalar(select(BacktestResult).where(
            BacktestResult.run_id == run_id,
            BacktestResult.instrument_key == key,
            BacktestResult.interval == interval))
        if not r:
            return {"error": "no such result"}
        d = r.summary()
        d["equity_curve"] = json.loads(r.curve_json or "[]")
        d["trades"] = json.loads(r.trades_json or "[]")
        return d
