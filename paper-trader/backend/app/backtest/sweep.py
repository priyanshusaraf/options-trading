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
from dataclasses import dataclass
from functools import cached_property

from app.backtest.engine import (backtest_charge_segment, compute_signals,
                                 prepare_signal_frame, simulate)
from app.backtest.metrics import BTMetrics
from app.backtest import dataset_store
from app.backtest.identity import (INSTRUMENT_IDENTITY_FIELDS,
                                   PROVIDER_IDENTITY_FIELDS,
                                   execution_result_address,
                                   ordered_dataset_address, source_identity)
from app.backtest.premium import NO_OPTIONS_PREMIUM_ERROR, simulate_premium
from app.core.config import get_settings
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

def _requested_window(interval: str, win) -> dict:
    """The request half of a dataset address: what we ASKED the provider for.

    Kept in one place because it is now computed twice — once when fetching, and
    once when checking that a pinned dataset was fetched for this same request.
    """
    start, end = win.get("start"), win.get("end")
    return {
        "lookback_days": win.get("lookback_days"),
        "start": start,
        "end": end,
        "fetch_days": _fetch_days(interval, win.get("lookback_days"), start, end),
    }


# ── pinned runs ──────────────────────────────────────────────────────────────
# A pinned run evaluates against dataset addresses the CALLER named. It makes
# zero provider reads, and that claim is truthful only because the caller chose
# the exact bytes. Nothing below is ever reached from an ordinary sweep: a
# refresh must still pay one read per dataset (design: "Truthful warm modes"),
# because no provider API exposes a revision token that could prove historical
# bytes unchanged. Pinning is opt-in at the call site and nowhere else.

def pin_key(instrument_key: str, interval: str) -> str:
    """The address-map key for one (instrument, interval) cell."""
    return f"{instrument_key}|{interval}"


def _is_address(value: str) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value.lower()))


def normalize_pinned_datasets(pinned_datasets) -> dict[str, str]:
    """Validate a caller's pin map, or raise. Malformed input must not reach a
    run row: a half-valid pin map would silently fail closed cell by cell and
    look like missing data rather than a caller mistake."""
    normalized: dict[str, str] = {}
    for key, address in dict(pinned_datasets).items():
        if not isinstance(key, str) or "|" not in key:
            raise RuntimeError(
                f"pinned dataset key must be 'INSTRUMENT|interval', got {key!r}")
        if not _is_address(address):
            raise RuntimeError(
                f"not a dataset address for {key}: {address!r}")
        normalized[key] = address.lower()
    return normalized


def resolve_pinned_datasets(provider, instruments, intervals, *,
                            lookback_days: int | None = None,
                            start_date: str | None = None,
                            end_date: str | None = None,
                            store=None) -> dict[str, str]:
    """Look up the stored dataset address for each requested cell.

    This is the *source-run* half of the pinned API: it turns "the datasets a
    previous sweep of this window fetched" into explicit addresses the caller
    then passes to `start_sweep(pinned_datasets=...)`. It is deliberately a
    separate call — `start_sweep` never invokes it — so that pinning cannot
    happen by omission. Cells with nothing stored are simply absent from the
    result and will fail closed if pinned anyway.
    """
    store = store or dataset_store.get_store()
    win = {"lookback_days": lookback_days, "start": start_date, "end": end_date}
    resolved: dict[str, str] = {}
    for inst in instruments:
        for interval in intervals:
            entry = store.lookup(
                provider=provider, instrument=inst, interval=interval,
                requested_window=_requested_window(interval, win))
            if entry is not None:
                resolved[pin_key(inst.key, interval)] = entry.address
    return resolved


_state_lock = threading.Lock()
_running = False
_worker: "threading.Thread | None" = None


@dataclass(frozen=True)
class _FrozenCandle:
    ts: dt.datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class _PreparedDataset:
    candles: tuple[_FrozenCandle, ...] = ()
    bars: int = 0
    first_ts: int = 0
    last_ts: int = 0
    effective_days: int = 0
    clamped: bool = False
    dataset_address: str = ""
    error: str = ""

    @cached_property
    def frame(self):
        # Lazily prepared: a refresh-warm cache hit validates candle bytes but
        # performs no DataFrame conversion or signal work.
        return prepare_signal_frame(self.candles)


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
                strategies: list[str] | None = None,
                pinned_datasets=None) -> int:
    """Create a run row, resolve the universe, launch the background thread.
    Returns the new run id. Raises if a sweep is already in flight.

    `instruments`  — restrict the sweep to these instrument keys (e.g. just
                     GOLD/SILVER/COPPER); None/empty = the whole scope.
    `lookback_days`— preset window in days (None = max available history).
    `start_date`/`end_date` — ISO custom window (overrides lookback_days).
    `strategies`   — registry strategy keys to run EACH instrument×interval across;
                     None/empty = just the default strategy (single-strategy sweep).
    `pinned_datasets` — OPT-IN pinned run: `{"NIFTY|15minute": <dataset address>}`,
                     normally built by `resolve_pinned_datasets`. Every cell is
                     served from the local dataset store and the run makes ZERO
                     provider reads; a cell whose pin is missing, corrupt, or
                     describes another series fails closed with an explanatory
                     error rather than falling back to a fetch. Omit it and the
                     sweep behaves exactly as before, provider reads included."""
    from app.strategy.registry import DEFAULT_STRATEGY_KEY, get_strategy
    global _running, _worker
    pinned = normalize_pinned_datasets(pinned_datasets) if pinned_datasets else None
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
                                   f"× {len(strat_objs)} strategies · {win['label']}"
                                   + (" · pinned" if pinned else ""))
            s.add(run)
            s.commit()
            run_id = run.id
        log.info(f"backtest sweep #{run_id} started — {total} cells, "
                 f"window={win['label']}, strategies={strat_label}"
                 + (f", PINNED to {len(pinned)} stored datasets" if pinned else ""))
        t = threading.Thread(target=_run,
                             args=(run_id, provider, specs, intervals, capital, win,
                                   strat_objs, pinned),
                             daemon=True)
        _worker = t
        t.start()
        return run_id
    except Exception:
        _running = False
        raise


def _run(run_id, provider, specs, intervals, capital, win=None, strategies=None,
         pinned=None) -> None:
    global _running
    win = win or {"lookback_days": None, "start": None, "end": None, "label": "max"}
    if not strategies:
        from app.strategy.registry import get_strategy
        strategies = [get_strategy(None)]
    try:
        for inst in specs:
            for interval in intervals:
                prepared = _prepare_dataset(provider, inst, interval, win,
                                            pinned=pinned)
                for strat in strategies:
                    _one(run_id, provider, inst, interval, capital, win, strat,
                         prepared=prepared)
                    _bump(run_id)
        _finish(run_id, "done")
        log.info(f"backtest sweep #{run_id} complete")
    except Exception as e:  # never let the thread die silently
        _finish(run_id, "error", str(e))
        log.error(f"backtest sweep #{run_id} failed: {e}")
    finally:
        _running = False


def _prepare_dataset(provider, inst, interval, win, *,
                     pinned=None) -> _PreparedDataset:
    start, end = win.get("start"), win.get("end")
    clamped = _is_clamped(interval, win.get("lookback_days"), start)
    if pinned is not None:
        # Explicitly pinned: the store is the only source, and a pin that cannot
        # be honoured is an error, never a fetch. Falling back here would turn a
        # pinned run into a refresh wearing a pin's name.
        return _pinned_dataset(provider, inst, interval, win, pinned,
                               clamped=clamped)
    # A custom window entirely older than Kite's per-interval ceiling can never be
    # fetched — surface a DISTINCT, explanatory status rather than the generic,
    # silently-dropped 'insufficient history' (DV-3).
    if _window_out_of_range(interval, start, end):
        cap = MAX_DAYS.get(interval, 200)
        return _PreparedDataset(
            clamped=clamped,
            error=f"window older than Kite max for this interval "
                  f"(≈{cap}d on {interval})")
    requested_window = _requested_window(interval, win)
    days = requested_window["fetch_days"]
    try:
        candles = provider.get_candles(inst, interval, days, end=end) \
            if _supports_end(provider) else provider.get_candles(inst, interval, days)
    except Exception as e:
        # Preserve the existing provider-failure artifact: clamp metadata was not
        # asserted when no dataset was obtained.
        return _PreparedDataset(error=f"candles: {e}")
    candles = tuple(
        _FrozenCandle(c.ts, float(c.open), float(c.high), float(c.low),
                      float(c.close), float(c.volume))
        for c in _clip_to_window(candles, start, end)
    )
    if len(candles) < MIN_BARS:
        # distinguish "the window is reachable but thin" from "older than ceiling"
        if (start or end):
            return _PreparedDataset(
                candles=candles, bars=len(candles), clamped=clamped,
                error="window older than Kite max for this interval"
                if len(candles) == 0 else "insufficient history in window")
        return _PreparedDataset(
            candles=candles, bars=len(candles), clamped=clamped,
            error="insufficient history")
    first_ts = ist_epoch(candles[0].ts)
    last_ts = ist_epoch(candles[-1].ts)   # IST-correct cache discriminator (DV-5)
    effective_days = max(0, round((last_ts - first_ts) / 86400))
    effective_window = {
        "first_ts": first_ts,
        "last_ts": last_ts,
        "bars": len(candles),
        "clamped": clamped,
    }
    try:
        dataset_address = ordered_dataset_address(
            candles,
            provider=provider,
            instrument=inst,
            interval=interval,
            requested_window=requested_window,
            effective_window=effective_window,
        )
    except Exception as exc:
        # A dataset can still be simulated when it cannot be addressed. It is
        # deliberately non-reusable for this run.
        log.warn(f"backtest cache disabled for {inst.key}/{interval}: {exc}")
        dataset_address = ""
    if dataset_address:
        # Keep the bytes we just paid a throttled provider read for. This is a
        # WRITE only: the sweep never reads the store back, so a refresh still
        # costs its reads. Serving from the store is an explicit pinned run.
        # Storage failure is not a sweep failure, exactly as above.
        try:
            dataset_store.get_store().put(
                candles, provider=provider, instrument=inst, interval=interval,
                requested_window=requested_window,
                effective_window=effective_window, address=dataset_address)
        except Exception as exc:
            log.warn(f"backtest dataset not stored for "
                     f"{inst.key}/{interval}: {exc}")
    return _PreparedDataset(
        candles=candles, bars=len(candles), first_ts=first_ts, last_ts=last_ts,
        effective_days=effective_days, clamped=clamped,
        dataset_address=dataset_address)


def _pinned_dataset(provider, inst, interval, win, pinned, *,
                    clamped: bool) -> _PreparedDataset:
    """Serve one cell from a caller-named dataset address, or refuse.

    Every refusal below is a *closed* failure: one explanatory result row for the
    cell, the rest of the run untouched, and not one provider read. There is
    deliberately no path from here back to `provider.get_candles`.
    """
    key = pin_key(getattr(inst, "key", ""), interval)
    address = (pinned.get(key) or "").strip().lower()
    if not address:
        return _PreparedDataset(
            clamped=clamped,
            error=f"pinned run: no dataset address pinned for {key}")
    try:
        stored = dataset_store.get_store().get(address)
    except Exception as exc:
        return _PreparedDataset(
            clamped=clamped,
            error=f"pinned run: dataset store unreadable for {key}: {exc}")
    if stored is None:
        # Missing, unreadable, or its bytes no longer recompute to this address.
        # The store refuses all three the same way and so do we.
        return _PreparedDataset(
            clamped=clamped,
            error=f"pinned run: dataset {address[:12]}… for {key} is missing or "
                  f"its content no longer matches its address")
    mismatch = _pin_mismatch(stored, provider=provider, inst=inst,
                             interval=interval, win=win)
    if mismatch:
        return _PreparedDataset(
            clamped=clamped,
            error=f"pinned run: dataset {address[:12]}… does not describe "
                  f"{key} — {mismatch}")

    candles = tuple(
        _FrozenCandle(c.ts, float(c.open), float(c.high), float(c.low),
                      float(c.close), float(c.volume))
        for c in stored.candles)
    if len(candles) < MIN_BARS:
        return _PreparedDataset(
            candles=candles, bars=len(candles), clamped=clamped,
            error="insufficient history")
    first_ts = ist_epoch(candles[0].ts)
    last_ts = ist_epoch(candles[-1].ts)
    effective = stored.effective_window if isinstance(
        stored.effective_window, dict) else {}
    return _PreparedDataset(
        candles=candles, bars=len(candles), first_ts=first_ts, last_ts=last_ts,
        effective_days=max(0, round((last_ts - first_ts) / 86400)),
        clamped=bool(effective.get("clamped", clamped)),
        dataset_address=stored.address)


def _pin_mismatch(stored, *, provider, inst, interval, win) -> str:
    """Why this stored dataset is not an answer to this cell's request, or "".

    The store's own address check proves the bytes are the bytes that address
    names. It cannot prove they are the SERIES this cell asked for: a 30-minute
    GOLD dataset recomputes to its own address perfectly. Serving it to a
    15-minute NIFTY cell would be a silently wrong backtest, which is worse than
    any refusal, so the manifest is compared against the request as well.
    """
    if stored.interval != interval:
        return f"its interval is {stored.interval!r}, not {interval!r}"
    expected_instrument = source_identity(inst, fields=INSTRUMENT_IDENTITY_FIELDS)
    if stored.instrument != expected_instrument:
        return f"its instrument is {stored.instrument!r}"
    expected_provider = source_identity(provider, fields=PROVIDER_IDENTITY_FIELDS)
    if stored.provider != expected_provider:
        return f"its provider is {stored.provider!r}"
    expected_window = _requested_window(interval, win)
    if stored.requested_window != expected_window:
        return (f"it was fetched for window {stored.requested_window!r}, "
                f"not {expected_window!r}")
    return ""


def _one(run_id, provider, inst, interval, capital, win, strat=None,
         *, prepared: _PreparedDataset | None = None) -> None:
    if strat is None:
        from app.strategy.registry import get_strategy
        strat = get_strategy(None)
    from app.backtest import cache
    prepared = prepared or _prepare_dataset(provider, inst, interval, win)
    if prepared.error:
        return _store(
            run_id, inst, interval, None, [], prepared.bars,
            clamped=prepared.clamped, strategy_key=strat.key,
            error=prepared.error)

    candles = prepared.candles
    first_ts = prepared.first_ts
    last_ts = prepared.last_ts
    effective_days = prepared.effective_days
    clamped = prepared.clamped
    slippage_pct = float(get_settings().backtest_slippage_pct)
    phash = ""
    if prepared.dataset_address:
        try:
            phash = execution_result_address(
                dataset_address=prepared.dataset_address,
                instrument=inst,
                strategy=strat,
                parameters=dict(strat.default_params),
                capital=capital,
                window=win,
                slippage_pct=slippage_pct,
                implementation_maps=(),
            ) or ""
        except Exception as exc:
            # Identity failure disables reuse for this cell; it never disables the run.
            log.warn(f"backtest cache disabled for {inst.key}/{interval}: {exc}")
            phash = ""
    if phash:
        expected_premium_error = ("" if getattr(inst, "has_options", True)
                                  else NO_OPTIONS_PREMIUM_ERROR)
        with SessionLocal() as s:
            hit = cache.find_reusable(
                s, inst.key, interval, phash, last_ts,
                expected_premium_error=expected_premium_error)
            if hit is not None:
                _copy_from_cache(s, run_id, hit)
                return
    params = dict(strat.default_params)
    signals = compute_signals(candles, strat, params, frame=prepared.frame)
    trades, m = simulate(
        candles, inst, interval, capital=capital, strategy=strat, params=params,
        slippage_pct=slippage_pct, signals=signals)
    # synthetic-premium backtest (audit C6) — runs alongside the spot cell above.
    # A premium-side bug must NEVER kill the spot result: any exception here is
    # caught and surfaced as premium_error instead of aborting the sweep.
    if not getattr(inst, "has_options", True):
        p_trades, p_metrics, premium_error = [], BTMetrics(), \
            NO_OPTIONS_PREMIUM_ERROR
    else:
        try:
            p_trades, p_metrics = simulate_premium(
                candles, inst, interval, strategy=strat,
                params=params, capital=capital, signals=signals)
            premium_error = ""
        except Exception as e:
            p_trades, p_metrics, premium_error = [], BTMetrics(), str(e)
    _store(run_id, inst, interval, m, trades, prepared.bars, strategy_key=strat.key,
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
    from app.backtest.cache import cached_result_values
    session.add(BacktestResult(
        run_id=run_id, from_cache=True, **cached_result_values(src)))
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
    # Serialization of premium trades must obey the same rule as the premium
    # simulation itself: a premium-side failure NEVER kills the spot result
    # (2026-07-23: an np.bool in a trade dict aborted whole sweeps here).
    try:
        ptrades_json = json.dumps([t.to_dict() for t in ptrades])
    except Exception as e:
        pm, ptrades_json = BTMetrics(), "[]"
        premium_error = premium_error or f"premium trades not serializable: {e}"
    premium_common = dict(
        premium_trades=pm.trades, premium_win_rate=pm.win_rate,
        premium_net_pnl=pm.net_pnl, premium_return_pct=pm.return_pct,
        premium_profit_factor=pm.profit_factor,
        premium_max_drawdown_pct=pm.max_drawdown_pct,
        premium_expectancy=pm.expectancy, premium_charges=pm.charges,
        premium_trades_json=ptrades_json,
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
