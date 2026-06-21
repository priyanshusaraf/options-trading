"""
Sweep orchestrator — runs the strategy backtest across the universe × intervals.

Runs in a background thread (Kite calls are blocking + throttled). Progress is
written to the BacktestRun row so the UI can poll a progress bar. Each
(instrument, interval) result is cached in BacktestResult so reruns are instant
and the UI can filter/sort without recomputation.
"""
from __future__ import annotations

import datetime as dt
import json
import threading

from app.backtest.engine import backtest_charge_segment, simulate
from app.backtest.universe import full_universe, liquid_universe
from app.core.logging import log
from app.db.models import BacktestResult, BacktestRun
from app.db.session import SessionLocal
from app.providers.factory import get_provider

# Kite's documented max lookback per interval (days). We pull as much as allowed.
# This is the hard ceiling: a requested range is silently CLAMPED to it (and the
# UI discloses the clamp), because Kite sells no history older than this.
MAX_DAYS = {
    "minute": 60, "3minute": 90, "5minute": 100, "10minute": 100,
    "15minute": 200, "30minute": 200, "60minute": 400, "day": 2000,
}
DEFAULT_INTERVALS = ["minute", "5minute", "15minute", "30minute", "60minute", "day"]
MIN_BARS = 60

# Preset lookback windows (days) the UI offers; None = "entire available history".
PRESET_DAYS = {"1w": 7, "2w": 14, "1m": 30, "3m": 90, "6m": 180,
               "1y": 365, "3y": 1095, "7y": 2555, "10y": 3650, "max": None}
_DAYS_TO_LABEL = {v: k for k, v in PRESET_DAYS.items() if v}


def window_label(lookback_days: int | None, start_date: str | None,
                 end_date: str | None) -> str:
    """Human label for a sweep's date window (stored on the run, shown in the UI)."""
    if start_date or end_date:
        return f"{start_date or '…'}→{end_date or 'now'}"
    if lookback_days and lookback_days > 0:
        return _DAYS_TO_LABEL.get(lookback_days, f"{lookback_days}d")
    return "max"


def _fetch_days(interval: str, lookback_days: int | None, start_date: str | None) -> int:
    """How many days to pull for this interval, clamped to Kite's per-interval max."""
    cap = MAX_DAYS.get(interval, 200)
    if start_date:
        sd = dt.date.fromisoformat(start_date)
        return max(1, min(cap, (dt.date.today() - sd).days + 2))
    if lookback_days and lookback_days > 0:
        return min(cap, lookback_days)
    return cap


def _clip_to_window(candles, start_date: str | None, end_date: str | None):
    """Keep only candles whose date falls inside an explicit custom window."""
    if not (start_date or end_date):
        return candles
    sd = dt.date.fromisoformat(start_date) if start_date else dt.date.min
    ed = dt.date.fromisoformat(end_date) if end_date else dt.date.max
    return [c for c in candles if sd <= c.ts.date() <= ed]

_state_lock = threading.Lock()
_running = False
_worker: "threading.Thread | None" = None


def is_running() -> bool:
    return _running


def _join() -> None:
    """Test helper: block until the running sweep thread completes."""
    t = _worker
    if t is not None:
        t.join()


def start_sweep(scope: str = "liquid", intervals: list[str] | None = None,
                capital: float = 50_000.0, provider=None,
                instruments: list[str] | None = None,
                lookback_days: int | None = None,
                start_date: str | None = None, end_date: str | None = None) -> int:
    """Create a run row, resolve the universe, launch the background thread.
    Returns the new run id. Raises if a sweep is already in flight.

    `instruments`  — restrict the sweep to these instrument keys (e.g. just
                     GOLD/SILVER/COPPER); None/empty = the whole scope.
    `lookback_days`— preset window in days (None = max available history).
    `start_date`/`end_date` — ISO custom window (overrides lookback_days)."""
    global _running, _worker
    with _state_lock:
        if _running:
            raise RuntimeError("a sweep is already running")
        _running = True
    try:
        intervals = [i for i in (intervals or DEFAULT_INTERVALS) if i in MAX_DAYS]
        provider = provider or get_provider()
        specs = full_universe(provider) if scope == "full" else liquid_universe(provider)
        if instruments:
            want = {k.strip() for k in instruments if k.strip()}
            specs = [i for i in specs if i.key in want]
            if not specs:
                raise RuntimeError(f"none of the requested instruments exist: {sorted(want)}")
        win = {"lookback_days": lookback_days, "start": start_date, "end": end_date,
               "label": window_label(lookback_days, start_date, end_date)}
        total = len(specs) * len(intervals)
        with SessionLocal() as s:
            run = BacktestRun(status="running", scope=scope,
                              intervals=",".join(intervals), capital=capital,
                              total=total, done=0, window=win["label"],
                              instruments=",".join(i.key for i in specs) if instruments else "",
                              note=f"{len(specs)} instruments × {len(intervals)} intervals · {win['label']}")
            s.add(run)
            s.commit()
            run_id = run.id
        log.info(f"backtest sweep #{run_id} started — {total} cells, window={win['label']}")
        t = threading.Thread(target=_run,
                             args=(run_id, provider, specs, intervals, capital, win),
                             daemon=True)
        _worker = t
        t.start()
        return run_id
    except Exception:
        _running = False
        raise


def _run(run_id, provider, specs, intervals, capital, win=None) -> None:
    global _running
    win = win or {"lookback_days": None, "start": None, "end": None, "label": "max"}
    try:
        for inst in specs:
            for interval in intervals:
                _one(run_id, provider, inst, interval, capital, win)
                _bump(run_id)
        _finish(run_id, "done")
        log.info(f"backtest sweep #{run_id} complete")
    except Exception as e:  # never let the thread die silently
        _finish(run_id, "error", str(e))
        log.error(f"backtest sweep #{run_id} failed: {e}")
    finally:
        _running = False


def _one(run_id, provider, inst, interval, capital, win) -> None:
    from app.backtest import cache
    days = _fetch_days(interval, win.get("lookback_days"), win.get("start"))
    try:
        candles = provider.get_candles(inst, interval, days)
    except Exception as e:
        return _store(run_id, inst, interval, None, [], 0, error=f"candles: {e}")
    candles = _clip_to_window(candles, win.get("start"), win.get("end"))
    if len(candles) < MIN_BARS:
        return _store(run_id, inst, interval, None, [], len(candles),
                      error="insufficient history")
    last_ts = int(candles[-1].ts.timestamp())
    phash = cache.params_signature(capital, window=win.get("label", ""))
    with SessionLocal() as s:
        hit = cache.find_reusable(s, inst.key, interval, phash, last_ts)
        if hit is not None:
            _copy_from_cache(s, run_id, hit)   # nothing changed -> reuse computed metrics
            return
    trades, m = simulate(candles, inst, interval, capital=capital)
    _store(run_id, inst, interval, m, trades, len(candles),
           params_hash=phash, last_candle_ts=last_ts)


def _copy_from_cache(session, run_id, src) -> None:
    import datetime as dt
    session.add(BacktestResult(
        run_id=run_id, instrument_key=src.instrument_key, name=src.name,
        segment=src.segment, interval=src.interval, trades=src.trades, wins=src.wins,
        win_rate=src.win_rate, profit_factor=src.profit_factor,
        max_drawdown_pct=src.max_drawdown_pct, return_pct=src.return_pct,
        net_pnl=src.net_pnl, gross_pnl=src.gross_pnl, charges=src.charges,
        expectancy=src.expectancy, cagr=src.cagr,
        calmar=src.calmar, consistency=src.consistency,
        max_consec_losses=src.max_consec_losses, time_underwater_pct=src.time_underwater_pct,
        bars=src.bars, curve_json=src.curve_json, trades_json=src.trades_json,
        params_hash=src.params_hash, last_candle_ts=src.last_candle_ts,
        schema_version=src.schema_version, from_cache=True, computed_at=dt.datetime.now()))
    session.commit()


def _store(run_id, inst, interval, m, trades, bars, error="",
           params_hash="", last_candle_ts=0) -> None:
    import datetime as dt
    from app.backtest import cache
    seg = backtest_charge_segment(inst)
    common = dict(run_id=run_id, instrument_key=inst.key, name=inst.name,
                  segment=seg, interval=interval, bars=bars,
                  params_hash=params_hash, last_candle_ts=last_candle_ts,
                  schema_version=cache.SCHEMA_VERSION, from_cache=False,
                  computed_at=dt.datetime.now())
    with SessionLocal() as s:
        if m is None:
            s.add(BacktestResult(error=error, **common))
        else:
            s.add(BacktestResult(
                trades=m.trades, wins=m.wins, win_rate=m.win_rate,
                profit_factor=m.profit_factor, max_drawdown_pct=m.max_drawdown_pct,
                return_pct=m.return_pct, net_pnl=m.net_pnl, gross_pnl=m.gross_pnl,
                charges=m.charges, expectancy=m.expectancy, cagr=m.cagr,
                calmar=m.calmar, consistency=m.consistency,
                max_consec_losses=m.max_consec_losses, time_underwater_pct=m.time_underwater_pct,
                curve_json=json.dumps(m.equity_curve),
                trades_json=json.dumps([t.to_dict() for t in trades]), **common))
        s.commit()


def _bump(run_id) -> None:
    with SessionLocal() as s:
        run = s.get(BacktestRun, run_id)
        if run:
            run.done += 1
            s.commit()


def _finish(run_id, status, note="") -> None:
    with SessionLocal() as s:
        run = s.get(BacktestRun, run_id)
        if run:
            run.status = status
            if note:
                run.note = note[:400]
            s.commit()
