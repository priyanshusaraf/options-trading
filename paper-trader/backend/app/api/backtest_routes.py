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

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response, StreamingResponse

from app.api.paging import MAX_PAGE
from pydantic import BaseModel

from app.backtest import sweep
from app.core.instruments import get_instrument
from app.db.models import BacktestResult, CapitalState
from app.db.session import SessionLocal
from app.api.principal import Principal, get_principal, owner_id_for
from app.api.execution_access import local_execution_cell
from app.backtest import repository


def _budget(request: Request, principal: Principal) -> float:
    """The owner's real tradeable budget for affordability flags: the live Kite
    account's free funds when known (cached by the engine), else the configured
    initial_capital. Budget-relative flags are computed at THIS layer so they track
    the account without re-running the (budget-independent) backtest."""
    try:
        runner = local_execution_cell(request, principal)
    except Exception:
        return 0.0
    with SessionLocal() as session:
        cap = session.get(CapitalState, (runner.broker_account_id, runner.book))
        return float(cap.cash) if cap is not None else 0.0


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
    # This is causal admission only. Dataset/provider, market-truth, and live
    # readiness checks remain separate Strategy Preflight responsibilities.
    admission_address: str
    scope: str = "liquid"                 # "liquid" | "full"
    intervals: list[str] | None = None    # default: 1m/5m/15m/30m/1h/day
    capital: float = 50_000.0
    instruments: list[str] | None = None  # restrict to these keys (e.g. GOLD/SILVER/COPPER)
    lookback_days: int | None = None      # preset window in days (None = entire history)
    start_date: str | None = None         # ISO custom window start (overrides lookback)
    end_date: str | None = None           # ISO custom window end
    strategies: list[str] | None = None   # registry strategy keys (None = default v3)


@router.post("/sweep")
def start(body: SweepRequest, principal: Principal = Depends(get_principal)):
    try:
        run_id = sweep.start_sweep(
            scope=body.scope, intervals=body.intervals, capital=body.capital,
            instruments=body.instruments, lookback_days=body.lookback_days,
            start_date=body.start_date, end_date=body.end_date,
            strategies=body.strategies, admission_address=body.admission_address,
            owner_id=owner_id_for(principal))
    except repository.AdmissionRequired as e:
        return {"error": e.code}
    except sweep.WorkloadAdmissionError as e:
        return {"error": "backtest workload unavailable", "reason": e.reason}
    except Exception as e:
        return {"error": str(e)}
    return {"run_id": run_id, "running": True}


@router.post("/runs/{run_id}/cancel")
def cancel(run_id: int, principal: Principal = Depends(get_principal)):
    """Request cancellation for the principal's own pending/running work only."""
    owner_id = owner_id_for(principal)
    with SessionLocal() as session:
        accepted = repository.request_cancel(session, owner_id=owner_id, run_id=run_id)
        if accepted:
            session.commit()
    # Foreign and absent ids collapse to the same response. No global queue state
    # or worker identifiers are disclosed.
    return {"accepted": accepted}


@router.get("/instruments")
def instruments(scope: str = "liquid", principal: Principal = Depends(get_principal)):
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
            "strategies": strategy_meta(owner_id=owner_id_for(principal))}


@router.get("/status")
def status(run_id: int | None = None, principal: Principal = Depends(get_principal)):
    owner_id = owner_id_for(principal)
    with SessionLocal() as s:
        run = (repository.get_run(s, owner_id=owner_id, run_id=run_id) if run_id else
               repository.latest_run(s, owner_id=owner_id))
        if not run:
            return {"run": None, "running": False}
        return {"run": run.to_dict(), "running": run.status == "running"}


@router.get("/runs")
def runs(limit: int = Query(default=100, ge=1, le=MAX_PAGE),
         principal: Principal = Depends(get_principal)):
    """Every past sweep, newest first — so no completed run is ever lost or
    silently overwritten. Each row carries a result count so the UI can show
    'NIFTY×6 · 312 cells · done · 19 Jun'."""
    owner_id = owner_id_for(principal)
    with SessionLocal() as s:
        rows = repository.list_runs_with_counts(s, owner_id=owner_id, limit=limit)
    out = []
    for r, result_count in rows:
        d = r.to_dict()
        d["result_count"] = result_count
        out.append(d)
    return {"runs": out}


@router.get("/export")
def export(run_id: int | None = None, principal: Principal = Depends(get_principal)):
    """Download a run's results as CSV (so a sweep's output survives outside the
    app). Defaults to the latest run."""
    owner_id = owner_id_for(principal)
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
        run = (repository.get_run(s, owner_id=owner_id, run_id=run_id) if run_id is not None
               else repository.latest_run(s, owner_id=owner_id))
        if run is None:
            return Response(status_code=404, content="not found")
        run_id = run.id
    def stream():
        header = io.StringIO()
        csv.DictWriter(header, fieldnames=cols, extrasaction="ignore").writeheader()
        yield header.getvalue()
        for row in repository.iter_successful_results(
                owner_id=owner_id, run_id=run_id, batch_size=250):
            body = io.StringIO()
            csv.DictWriter(body, fieldnames=cols, extrasaction="ignore").writerow(row.summary())
            yield body.getvalue()
    return StreamingResponse(
        stream(), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="backtest_run_{run_id}.csv"'})


@router.get("/results")
def results(request: Request, run_id: int | None = None, interval: str | None = None,
            strategy: str | None = None,
            min_win_rate: float = 0.0, min_profit_factor: float = 0.0,
            max_drawdown: float = 100.0, min_return: float = -1e9,
            min_trades: int = 10, sort: str = "return_pct",
            limit: int = Query(default=500, ge=1, le=MAX_PAGE),
            offset: int = Query(default=0, ge=0),
            principal: Principal = Depends(get_principal)):
            # H9: default raised 1 -> 10 so a 1-lucky-trade cell is never surfaced as
            # promotable by default (grid selection bias across the sweep). Overridable.
    owner_id = owner_id_for(principal)
    budget = _budget(request, principal)
    with SessionLocal() as s:
        run = (repository.get_run(s, owner_id=owner_id, run_id=run_id) if run_id is not None
               else repository.latest_run(s, owner_id=owner_id))
        if run is None:
            # A foreign opaque id and an absent id deliberately collapse to the
            # same public payload.  Echoing either id would make the probe
            # distinguishable despite the owner-scoped lookup above.
            return {"run_id": None, "count": 0, "total": 0, "offset": offset,
                    "limit": limit, "results": [], "budget": round(budget, 0),
                    "skipped": 0, "unaffordable": 0,
                    "skipped_breakdown": {"errored": 0, "low_trades": 0, "filtered": 0}}
        run_id = run.id
        column = getattr(BacktestResult, sort, BacktestResult.return_pct)
        reverse = sort not in ("max_drawdown_pct", "charges", "max_consec_losses",
                               "time_underwater_pct", "worst_mae_pct")
        rows = repository.filtered_results(
            s, owner_id=owner_id, run_id=run_id, interval=interval, strategy_key=strategy,
            min_win_rate=min_win_rate, min_profit_factor=min_profit_factor,
            max_drawdown=max_drawdown, min_return=min_return, min_trades=min_trades,
            sort_column=column, descending=reverse, limit=limit, offset=offset)
        total, skipped_errored, skipped_low_trades, skipped_filtered = repository.filtered_counts(
            s, owner_id=owner_id, run_id=run_id, interval=interval, strategy_key=strategy,
            min_win_rate=min_win_rate, min_profit_factor=min_profit_factor,
            max_drawdown=max_drawdown, min_return=min_return, min_trades=min_trades)

    out = []
    # survivorship disclosure (DV-1): cells excluded from the visible set, by reason,
    # so the visible list is never mistaken for the whole universe.
    skipped = skipped_errored + skipped_low_trades + skipped_filtered
    unaffordable = 0             # can't afford 1 lot of the ATM OPTION at the current budget — badged, NOT hidden
    for r in rows:
        d = _with_affordability(r.summary(), budget)
        try:
            d["has_options"] = bool(get_instrument(r.instrument_key).has_options)
        except KeyError:
            d["has_options"] = True
        if not d["affordable_options"]:
            unaffordable += 1
        out.append(d)

    return {"run_id": run_id, "count": len(out), "total": total,
            "offset": offset, "limit": limit, "results": out,
            "budget": round(budget, 0), "skipped": skipped, "unaffordable": unaffordable,
            "skipped_breakdown": {
                "errored": skipped_errored, "low_trades": skipped_low_trades,
                "filtered": skipped_filtered}}


@router.get("/result/{key}/{interval}")
def result_detail(key: str, interval: str, request: Request, run_id: int | None = None,
                  strategy: str | None = None,
                  principal: Principal = Depends(get_principal)):
    owner_id = owner_id_for(principal)
    with SessionLocal() as s:
        run = (repository.get_run(s, owner_id=owner_id, run_id=run_id) if run_id is not None
               else repository.latest_run(s, owner_id=owner_id))
        run_id = run.id if run else -1
        r = repository.result_detail(s, owner_id=owner_id, run_id=run_id,
                                     instrument_key=key, interval=interval,
                                     strategy_key=strategy)
        if not r:
            return {"error": "no such result"}
        d = _with_affordability(r.summary(), _budget(request, principal))
        d["equity_curve"] = json.loads(r.curve_json or "[]")
        d["bh_curve"] = json.loads(r.bh_curve_json or "[]")
        d["trades"] = json.loads(r.trades_json or "[]")
        return d
    owner_id = owner_id_for(principal)
