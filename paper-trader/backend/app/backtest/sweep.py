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
from app.backtest.metrics import BTMetrics
from app.backtest.premium import simulate_premium
from app.backtest.universe import full_universe, liquid_universe
from app.core.logging import log
from app.core.market_hours import ist_epoch
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


def _fetch_days(interval: str, lookback_days: int | None, start_date: str | None,
                end_date: str | None = None) -> int:
    """How many days to pull for this interval, clamped to Kite's per-interval max.

    For a custom [start,end] window we must fetch enough days to cover the whole
    span back from TODAY (the provider only sells trailing history): the deepest
    candle we need is `start_date`, so we ask for (today - start) days + buffer,
    still clamped to the per-interval ceiling. `_clip_to_window` then trims to the
    requested [start,end]; a window older than the ceiling clips to nothing (see
    `_window_out_of_range`)."""
    cap = MAX_DAYS.get(interval, 200)
    if start_date:
        sd = dt.date.fromisoformat(start_date)
        return max(1, min(cap, (dt.date.today() - sd).days + 2))
    if lookback_days and lookback_days > 0:
        return min(cap, lookback_days)
    return cap


def _is_clamped(interval: str, lookback_days: int | None, start_date: str | None) -> bool:
    """True when the requested span exceeds Kite's per-interval ceiling and was
    therefore silently capped (so the UI can badge the row)."""
    cap = MAX_DAYS.get(interval, 200)
    if start_date:
        sd = dt.date.fromisoformat(start_date)
        return (dt.date.today() - sd).days + 2 > cap
    if lookback_days and lookback_days > 0:
        return lookback_days > cap
    return False   # "max" history asks for the cap itself — not a user clamp


def _window_out_of_range(interval: str, start_date: str | None,
                         end_date: str | None) -> bool:
    """True when a custom window ends BEFORE the earliest candle Kite can serve
    for this interval — i.e. the whole [start,end] is older than the per-interval
    ceiling, so no candle inside it is ever fetchable (a 2018 window on any TF)."""
    if not (start_date or end_date):
        return False
    cap = MAX_DAYS.get(interval, 200)
    earliest_available = dt.date.today() - dt.timedelta(days=cap)
    ed = dt.date.fromisoformat(end_date) if end_date else dt.date.today()
    return ed < earliest_available


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
                start_date: str | None = None, end_date: str | None = None,
                strategies: list[str] | None = None) -> int:
    """Create a run row, resolve the universe, launch the background thread.
    Returns the new run id. Raises if a sweep is already in flight.

    `instruments`  — restrict the sweep to these instrument keys (e.g. just
                     GOLD/SILVER/COPPER); None/empty = the whole scope.
    `lookback_days`— preset window in days (None = max available history).
    `start_date`/`end_date` — ISO custom window (overrides lookback_days).
    `strategies`   — registry strategy keys to run EACH instrument×interval across;
                     None/empty = just the default strategy (single-strategy sweep)."""
    from app.strategy.registry import DEFAULT_STRATEGY_KEY, get_strategy
    global _running, _worker
    with _state_lock:
        if _running:
            raise RuntimeError("a sweep is already running")
        _running = True
    try:
        intervals = [i for i in (intervals or DEFAULT_INTERVALS) if i in MAX_DAYS]
        # resolve + de-dupe strategy keys (preserve request order); default = v3
        req_keys = [k for k in (strategies or [DEFAULT_STRATEGY_KEY]) if k]
        seen: set[str] = set()
        strat_objs = []
        for k in req_keys:
            strat = get_strategy(k)
            if strat.key not in seen:
                seen.add(strat.key)
                strat_objs.append(strat)
        if not strat_objs:
            strat_objs = [get_strategy(DEFAULT_STRATEGY_KEY)]
        provider = provider or get_provider()
        specs = full_universe(provider) if scope == "full" else liquid_universe(provider)
        if instruments:
            want = {k.strip() for k in instruments if k.strip()}
            specs = [i for i in specs if i.key in want]
            if not specs:
                raise RuntimeError(f"none of the requested instruments exist: {sorted(want)}")
        win = {"lookback_days": lookback_days, "start": start_date, "end": end_date,
               "label": window_label(lookback_days, start_date, end_date)}
        total = len(specs) * len(intervals) * len(strat_objs)
        strat_label = "×".join(st.key for st in strat_objs)
        with SessionLocal() as s:
            run = BacktestRun(status="running", scope=scope,
                              intervals=",".join(intervals), capital=capital,
                              total=total, done=0, window=win["label"],
                              instruments=",".join(i.key for i in specs) if instruments else "",
                              strategies=",".join(st.key for st in strat_objs),
                              note=f"{len(specs)} instruments × {len(intervals)} intervals "
                                   f"× {len(strat_objs)} strategies · {win['label']}")
            s.add(run)
            s.commit()
            run_id = run.id
        log.info(f"backtest sweep #{run_id} started — {total} cells, "
                 f"window={win['label']}, strategies={strat_label}")
        t = threading.Thread(target=_run,
                             args=(run_id, provider, specs, intervals, capital, win, strat_objs),
                             daemon=True)
        _worker = t
        t.start()
        return run_id
    except Exception:
        _running = False
        raise


def _run(run_id, provider, specs, intervals, capital, win=None, strategies=None) -> None:
    global _running
    win = win or {"lookback_days": None, "start": None, "end": None, "label": "max"}
    if not strategies:
        from app.strategy.registry import get_strategy
        strategies = [get_strategy(None)]
    try:
        for inst in specs:
            for interval in intervals:
                for strat in strategies:
                    _one(run_id, provider, inst, interval, capital, win, strat)
                    _bump(run_id)
        _finish(run_id, "done")
        log.info(f"backtest sweep #{run_id} complete")
    except Exception as e:  # never let the thread die silently
        _finish(run_id, "error", str(e))
        log.error(f"backtest sweep #{run_id} failed: {e}")
    finally:
        _running = False


def _one(run_id, provider, inst, interval, capital, win, strat=None) -> None:
    if strat is None:
        from app.strategy.registry import get_strategy
        strat = get_strategy(None)
    from app.backtest import cache
    start, end = win.get("start"), win.get("end")
    clamped = _is_clamped(interval, win.get("lookback_days"), start)
    # A custom window entirely older than Kite's per-interval ceiling can never be
    # fetched — surface a DISTINCT, explanatory status rather than the generic,
    # silently-dropped 'insufficient history' (DV-3).
    if _window_out_of_range(interval, start, end):
        cap = MAX_DAYS.get(interval, 200)
        return _store(run_id, inst, interval, None, [], 0, clamped=clamped,
                      strategy_key=strat.key,
                      error=f"window older than Kite max for this interval "
                            f"(≈{cap}d on {interval})")
    days = _fetch_days(interval, win.get("lookback_days"), start, end)
    try:
        candles = provider.get_candles(inst, interval, days, end=end) \
            if _supports_end(provider) else provider.get_candles(inst, interval, days)
    except Exception as e:
        return _store(run_id, inst, interval, None, [], 0, strategy_key=strat.key,
                      error=f"candles: {e}")
    candles = _clip_to_window(candles, start, end)
    if len(candles) < MIN_BARS:
        # distinguish "the window is reachable but thin" from "older than ceiling"
        if (start or end):
            return _store(run_id, inst, interval, None, [], len(candles), clamped=clamped,
                          strategy_key=strat.key,
                          error="window older than Kite max for this interval"
                          if len(candles) == 0 else "insufficient history in window")
        return _store(run_id, inst, interval, None, [], len(candles), clamped=clamped,
                      strategy_key=strat.key, error="insufficient history")
    first_ts = ist_epoch(candles[0].ts)
    last_ts = ist_epoch(candles[-1].ts)   # IST-correct cache discriminator (DV-5)
    effective_days = max(0, round((last_ts - first_ts) / 86400))
    phash = cache.params_signature(capital, window=win.get("label", ""), strategy=strat)
    with SessionLocal() as s:
        hit = cache.find_reusable(s, inst.key, interval, phash, last_ts)
        if hit is not None:
            _copy_from_cache(s, run_id, hit)   # nothing changed -> reuse computed metrics
            return
    trades, m = simulate(candles, inst, interval, capital=capital,
                         strategy=strat, params=dict(strat.default_params))
    # synthetic-premium backtest (audit C6) — runs alongside the spot cell above.
    # A premium-side bug must NEVER kill the spot result: any exception here is
    # caught and surfaced as premium_error instead of aborting the sweep.
    if not getattr(inst, "has_options", True):
        p_trades, p_metrics, premium_error = [], BTMetrics(), \
            "instrument has no listed options (has_options=False)"
    else:
        try:
            p_trades, p_metrics = simulate_premium(
                candles, inst, interval, strategy=strat,
                params=dict(strat.default_params), capital=capital)
            premium_error = ""
        except Exception as e:
            p_trades, p_metrics, premium_error = [], BTMetrics(), str(e)
    _store(run_id, inst, interval, m, trades, len(candles), strategy_key=strat.key,
           params_hash=phash, last_candle_ts=last_ts,
           first_ts=first_ts, last_ts_span=last_ts, effective_days=effective_days,
           clamped=clamped, premium_trades=p_trades, premium_metrics=p_metrics,
           premium_error=premium_error)


def _supports_end(provider) -> bool:
    """True if this provider's get_candles accepts an `end` kwarg (backtest-only
    date-range anchoring). The live engine never passes `end`, so its frozen call
    path is untouched."""
    import inspect
    try:
        return "end" in inspect.signature(provider.get_candles).parameters
    except (TypeError, ValueError):
        return False


def _copy_from_cache(session, run_id, src) -> None:
    import datetime as dt
    session.add(BacktestResult(
        run_id=run_id, instrument_key=src.instrument_key, name=src.name,
        segment=src.segment, strategy_key=src.strategy_key or "trend_impulse_v3",
        interval=src.interval, trades=src.trades, wins=src.wins,
        win_rate=src.win_rate, profit_factor=src.profit_factor,
        max_drawdown_pct=src.max_drawdown_pct, return_pct=src.return_pct,
        net_pnl=src.net_pnl, gross_pnl=src.gross_pnl, charges=src.charges,
        expectancy=src.expectancy, cagr=src.cagr,
        calmar=src.calmar, consistency=src.consistency, sharpe=src.sharpe,
        max_consec_losses=src.max_consec_losses, time_underwater_pct=src.time_underwater_pct,
        notional=src.notional, lots=src.lots, affordable=src.affordable,
        option_cost=src.option_cost,
        open_at_end=src.open_at_end, win_rate_realised=src.win_rate_realised,
        return_pct_realised=src.return_pct_realised,
        bh_return_pct=src.bh_return_pct, worst_trade_pnl=src.worst_trade_pnl,
        worst_mae_pct=src.worst_mae_pct,
        first_ts=src.first_ts, last_ts=src.last_ts,
        effective_days=src.effective_days, clamped=src.clamped,
        bars=src.bars, curve_json=src.curve_json, trades_json=src.trades_json,
        params_hash=src.params_hash, last_candle_ts=src.last_candle_ts,
        schema_version=src.schema_version, from_cache=True, computed_at=dt.datetime.now(),
        premium_trades=src.premium_trades, premium_win_rate=src.premium_win_rate,
        premium_net_pnl=src.premium_net_pnl, premium_return_pct=src.premium_return_pct,
        premium_profit_factor=src.premium_profit_factor,
        premium_max_drawdown_pct=src.premium_max_drawdown_pct,
        premium_expectancy=src.premium_expectancy, premium_charges=src.premium_charges,
        premium_trades_json=src.premium_trades_json, premium_error=src.premium_error))
    session.commit()


def _store(run_id, inst, interval, m, trades, bars, error="",
           params_hash="", last_candle_ts=0, first_ts=0, last_ts_span=0,
           effective_days=0, clamped=False, strategy_key="trend_impulse_v3",
           premium_trades=None, premium_metrics=None, premium_error="") -> None:
    import datetime as dt
    from app.backtest import cache
    seg = backtest_charge_segment(inst)
    common = dict(run_id=run_id, instrument_key=inst.key, name=inst.name,
                  segment=seg, strategy_key=strategy_key, interval=interval, bars=bars,
                  params_hash=params_hash, last_candle_ts=last_candle_ts,
                  first_ts=first_ts, last_ts=last_ts_span,
                  effective_days=effective_days, clamped=clamped,
                  schema_version=cache.SCHEMA_VERSION, from_cache=False,
                  computed_at=dt.datetime.now())
    pm = premium_metrics if premium_metrics is not None else BTMetrics()
    ptrades = premium_trades or []
    premium_common = dict(
        premium_trades=pm.trades, premium_win_rate=pm.win_rate,
        premium_net_pnl=pm.net_pnl, premium_return_pct=pm.return_pct,
        premium_profit_factor=pm.profit_factor,
        premium_max_drawdown_pct=pm.max_drawdown_pct,
        premium_expectancy=pm.expectancy, premium_charges=pm.charges,
        premium_trades_json=json.dumps([t.to_dict() for t in ptrades]),
        premium_error=premium_error)
    with SessionLocal() as s:
        if m is None:
            s.add(BacktestResult(error=error, **premium_common, **common))
        else:
            s.add(BacktestResult(
                trades=m.trades, wins=m.wins, win_rate=m.win_rate,
                profit_factor=m.profit_factor, max_drawdown_pct=m.max_drawdown_pct,
                return_pct=m.return_pct, net_pnl=m.net_pnl, gross_pnl=m.gross_pnl,
                charges=m.charges, expectancy=m.expectancy, cagr=m.cagr,
                calmar=m.calmar, consistency=m.consistency, sharpe=m.sharpe,
                max_consec_losses=m.max_consec_losses, time_underwater_pct=m.time_underwater_pct,
                notional=m.notional, lots=m.lots, affordable=m.affordable,
                option_cost=m.option_cost,
                open_at_end=m.open_at_end, win_rate_realised=m.win_rate_realised,
                return_pct_realised=m.return_pct_realised,
                bh_return_pct=m.bh_return_pct, worst_trade_pnl=m.worst_trade_pnl,
                worst_mae_pct=m.worst_mae_pct,
                curve_json=json.dumps(m.equity_curve),
                trades_json=json.dumps([t.to_dict() for t in trades]),
                bh_curve_json=json.dumps(m.bh_curve), **premium_common, **common))
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
