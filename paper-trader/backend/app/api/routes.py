"""
REST + WebSocket endpoints.

REST powers the (static, polled) Monitor tiles, the Options-Calc table, and the
analytics Dashboard. The main WebSocket (/ws) pushes engine state + logs live.
A per-instrument WebSocket (/ws/instrument/{key}) is opened only when a tile is
expanded — it streams that one instrument's underlying and option premium ticks.
"""
from __future__ import annotations

import asyncio
import datetime as dt

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.core.config import get_settings
from app.core.instruments import all_instruments, get_instrument
from app.db.models import DailyAccountSnapshot, Position, Trade
from app.db.session import SessionLocal
from app.engine import analytics
from app.options.pricing import bs_price, implied_vol
from app.strategy.registry import get_strategy
from app.strategy.signals import to_payload
from app.ws.manager import manager

router = APIRouter()
settings = get_settings()


def _runner(req_or_ws):
    return req_or_ws.app.state.runner


def _df(candles):
    import pandas as pd
    return pd.DataFrame([{"date": c.ts, "open": c.open, "high": c.high,
                          "low": c.low, "close": c.close} for c in candles])


# ── status / auth ─────────────────────────────────────────────────────────
@router.get("/api/status")
def status(request: Request):
    r = _runner(request)
    p = r.provider
    with SessionLocal() as s:
        cap = analytics.capital_dict(s)
    return {
        "provider": p.name,
        "authenticated": p.is_authenticated(),
        "login_url": p.login_url(),
        "running": r.running,
        "armed": r.armed,
        "tick": r.tick_count,
        "time": p.now().isoformat(),
        "interval": settings.interval,
        "capital": cap,
    }


@router.get("/api/calendar")
def calendar(request: Request, days: int = 120):
    """Per-day P&L for the Calendar view: the BOT's booked live P&L (from the trade
    ledger) and YOUR discretionary P&L (day-over-day account-equity change minus the
    bot's that day, from the daily snapshots). Values are None where there's no
    activity / no snapshot yet (rendered neutral grey). Builds forward from go-live."""
    import datetime as _dt
    from collections import defaultdict
    r = _runner(request)
    today = r.provider.now().date()

    bot_by_day: dict[str, float] = defaultdict(float)
    bot_n_by_day: dict[str, int] = defaultdict(int)
    with SessionLocal() as s:
        trades = list(s.scalars(select(Trade).where(Trade.mode == "live")))
        snaps = {row.day: row.account_net for row in s.scalars(select(DailyAccountSnapshot))}
    for t in trades:
        if not t.exit_time:
            continue
        d = t.exit_time.date().isoformat()
        bot_by_day[d] += t.net_pnl
        bot_n_by_day[d] += 1

    # Anchor the calendar to the FIRST month we have any data for (go-live), not a
    # rolling lookback — so it starts at the go-live month and grows forward instead
    # of showing empty pre-go-live months. Before any data, show the current month.
    data_days = sorted(set(list(snaps.keys()) + list(bot_by_day.keys())))
    anchor = data_days[0] if data_days else today.isoformat()
    ay, am, _ = anchor.split("-")
    start = _dt.date(int(ay), int(am), 1)
    cap = today - _dt.timedelta(days=max(31, min(days, 1460)))   # safety bound on very old data
    if start < cap:
        start = _dt.date(cap.year, cap.month, 1)

    # prior-snapshot net for each snapshot day, to diff day-over-day account change
    snap_days = sorted(snaps)
    prev_net: dict[str, float | None] = {}
    last = None
    for d in snap_days:
        prev_net[d] = snaps[last] if last is not None else None
        last = d

    out = []
    cur = start
    while cur <= today:
        ds = cur.isoformat()
        bot = round(bot_by_day[ds], 2) if ds in bot_by_day else None
        my = None
        if ds in snaps and prev_net.get(ds) is not None:
            my = round((snaps[ds] - prev_net[ds]) - bot_by_day.get(ds, 0.0), 2)
        out.append({"day": ds, "bot_pnl": bot, "my_pnl": my,
                    "bot_trades": bot_n_by_day.get(ds, 0)})
        cur += _dt.timedelta(days=1)
    return {"from": start.isoformat(), "to": today.isoformat(), "days": out}


@router.get("/api/login")
def login(request: Request):
    url = _runner(request).provider.login_url()
    return RedirectResponse(url) if url else {"error": "provider has no login flow (mock)"}


@router.get("/api/session")
def session(request: Request):
    """Kite OAuth redirects here with ?request_token=… after login."""
    rt = request.query_params.get("request_token")
    if not rt:
        return {"error": "missing request_token"}
    try:
        _runner(request).provider.complete_session(rt)
    except Exception as e:
        return {"error": f"login failed: {e}"}
    # Kite redirects here (the backend) with the request_token; now that the token is
    # captured, bounce the browser to the FRONTEND so the user lands back on the UI
    # (not the bare backend origin). Configurable via PT_FRONTEND_URL.
    return RedirectResponse(settings.frontend_url or "/")


# ── instruments ─────────────────────────────────────────────────────────────
@router.get("/api/instruments")
def instruments(request: Request):
    r = _runner(request)
    out = []
    for inst in all_instruments():
        st = r.state.get(inst.key, {})
        out.append({
            "key": inst.key, "name": inst.name, "segment": inst.segment,
            "priority": inst.priority, "lot_size": inst.lot_size,
            "enabled": inst.key in r.enabled,
            "signal": st.get("signal", "NONE"), "trend": st.get("trend"),
            "z": st.get("z"), "close": st.get("close"),
            "position": st.get("position"),
        })
    return {"instruments": out}


class Toggle(BaseModel):
    enabled: bool


@router.post("/api/instruments/{key}/toggle")
def toggle(key: str, body: Toggle, request: Request):
    if key not in {i.key for i in all_instruments()}:
        return {"error": "unknown instrument"}
    _runner(request).set_enabled(key, body.enabled)
    return {"key": key, "enabled": body.enabled}


# ── portfolio universe (customizable homepage) ───────────────────────────────
class AddInstrument(BaseModel):
    key: str
    on_home: bool = True
    interval: str | None = None   # carry a backtest winner's timeframe into live


@router.post("/api/portfolio/add")
def portfolio_add(body: AddInstrument, request: Request):
    from app.core import universe_resolver
    r = _runner(request)
    res = universe_resolver.add_instrument(body.key, r.provider, on_home=body.on_home,
                                           interval=body.interval)
    if "error" not in res:
        r.enabled.add(body.key)   # the live engine picks it up next tick
        if res.get("interval"):
            r.intervals[body.key] = res["interval"]
    return res


@router.post("/api/portfolio/remove")
def portfolio_remove(body: AddInstrument, request: Request):
    from app.core import universe_resolver
    r = _runner(request)
    res = universe_resolver.remove_instrument(body.key)
    r.enabled.discard(body.key)
    return res


@router.get("/api/portfolio/home")
def portfolio_home(request: Request):
    """Instruments pinned to the customizable homepage, with live state."""
    from app.core.instruments import home_instruments
    r = _runner(request)
    out = []
    for inst in home_instruments():
        st = r.state.get(inst.key, {})
        out.append({
            "key": inst.key, "name": inst.name, "segment": inst.segment,
            "has_options": inst.has_options, "enabled": inst.key in r.enabled,
            "signal": st.get("signal", "NONE"), "trend": st.get("trend"),
            "z": st.get("z"), "close": st.get("close"), "position": st.get("position"),
        })
    return {"instruments": out}


# ── charts ──────────────────────────────────────────────────────────────────
@router.get("/api/candles/{key}")
def candles(key: str, request: Request, interval: str | None = None):
    r = _runner(request)
    inst = get_instrument(key)
    iv = interval or r._interval_for(key)   # detail chart defaults to the live interval
    try:
        cs = r.provider.get_candles(inst, iv, settings.history_days)
    except Exception:
        cs = []  # provider not ready (e.g. Kite not authenticated) — degrade gracefully
    if not cs:
        return {"candles": [], "ema": [], "zscore": [], "markers": [], "latest": None,
                "name": inst.name}
    sig = get_strategy(None).signals(_df(cs), ema_length=settings.ema_length,
                                     z_length=settings.z_length, entry_z=settings.entry_z,
                                     slope_lookback=settings.slope_lookback)
    payload = to_payload(sig, entry_z=settings.entry_z)
    payload["name"] = inst.name
    return payload


@router.get("/api/option-candles/{key}")
def option_candles(key: str, request: Request):
    """Premium path for the instrument's open contract, repriced (Black-Scholes)
    across recent underlying candles — feeds the option chart toggle."""
    r = _runner(request)
    with SessionLocal() as s:
        pos = s.scalar(select(Position).where(Position.instrument_key == key))
        if not pos:
            return {"candles": [], "tradingsymbol": None}
        tsym, strike, expiry, otype = pos.tradingsymbol, pos.strike, pos.expiry, pos.option_type
        entry_premium, stop_price, target_price = pos.entry_premium, pos.stop_price, pos.target_price
    inst = get_instrument(key)
    cs = r.provider.get_candles(inst, r._interval_for(key), settings.history_days)
    if not cs:
        return {"candles": [], "tradingsymbol": tsym}
    flag = "c" if otype == "CE" else "p"
    rfr = settings.risk_free_rate
    now = r.provider.now()
    cur_prem = r.provider.option_ltp(inst, tsym, strike, expiry, otype)
    spot_now = cs[-1].close
    T_now = max((dt.datetime.combine(expiry, dt.time(15, 30)) - now).total_seconds() / (365 * 86400), 0.5 / 365)
    iv = (implied_vol(cur_prem, spot_now, strike, T_now, rfr, flag) if cur_prem else None) or inst.mock_vol
    series = []
    for c in cs:
        T = max((dt.datetime.combine(expiry, dt.time(15, 30)) - c.ts).total_seconds() / (365 * 86400), 0.5 / 365)
        prem = bs_price(c.close, strike, T, rfr, iv, flag)
        series.append({"time": int(c.ts.timestamp()), "value": round(max(prem, 0.05), 2)})
    return {"candles": series, "tradingsymbol": tsym,
            "entry_premium": round(entry_premium, 2),
            "stop_price": round(stop_price, 2), "target_price": round(target_price, 2)}


# ── options-calc / analytics / logs ─────────────────────────────────────────
@router.get("/api/options-calc/{key}")
def options_calc(key: str, request: Request):
    return _runner(request).last_pick.get(key) or {"candidates": [], "reason": "no signal evaluated yet"}


@router.get("/api/account-pnl")
def account_pnl_route(request: Request):
    """Bot-vs-you split on the shared real account (live only)."""
    r = _runner(request)
    with SessionLocal() as s:
        return analytics.account_pnl(s, r.provider)


@router.get("/api/dashboard")
def dashboard(request: Request, segment: str | None = None, strategy: str | None = None):
    """Portfolio dashboard. Optional ?segment=options|equity_intraday and ?strategy=<key>
    slice the summary / curves / trades. The headline `equity_curve` is the global
    mark-to-market series (EquitySnapshot) when unfiltered; for a slice it's the
    realized-P&L curve from that slice's trades. `segment_curves` and `strategy_curves`
    always carry the per-segment / per-strategy overlays so the UI can compare."""
    seg = segment or None
    strat = strategy or None
    with SessionLocal() as s:
        equity = (analytics.equity_curve(s) if not (seg or strat)
                  else analytics.realized_curve(s, seg, strat))
        return {
            "capital": analytics.capital_dict(s),
            "summary": analytics.summary(s, seg, strat),
            "equity_curve": equity,
            "instrument_curves": analytics.per_instrument_curves(s, seg, strat),
            "segment_curves": analytics.segment_curves(s),
            "strategy_curves": analytics.strategy_curves(s, seg),
            "recent_trades": analytics.recent_trades(s, 50, segment=seg, strategy=strat),
            "open_positions": [p.to_dict() for p in analytics.open_positions(s)],
            "segment": seg, "strategy": strat,
        }


@router.get("/api/trades")
def trades(request: Request, limit: int = 100, mode: str | None = None):
    # mode="paper"|"live" filters the log to one ledger; omitted returns both
    # (each row still carries its own `mode` so the UI can split them).
    with SessionLocal() as s:
        return {"trades": analytics.recent_trades(s, limit, mode)}


@router.get("/api/logs")
def logs(limit: int = 300):
    from app.core.logging import log
    return {"logs": log.recent(limit)}


# ── signal-first list / positions cockpit / health (F1, F3, F5) ──────────────
_INTERVAL_MINUTES = {"5minute": 5, "15minute": 15, "30minute": 30, "60minute": 60}
_STALE_GRACE_SECONDS = 90.0   # slack on top of the interval budget before a row reads stale


@router.get("/api/signals")
def signals(request: Request):
    """Lightweight signal-first list. Pure read of in-memory engine state +
    health — it NEVER fetches candles, so rows stay cheap.

    Freshness is PER-INSTRUMENT: each row is stale only if ITS OWN last successful
    candle scan is older than its interval budget (+grace). One failing instrument
    no longer flips every other row to stale (the old global-flag bug). The
    feed-wide health (candle failures / auth expiry) stays in the `health` block
    for a feed-wide banner, and `feed_auth_error` surfaces a Kite session expiry."""
    from app.engine.health import is_stale
    r = _runner(request)
    h = r.health.as_dict()
    candle = h.get("candle", {})
    feed_auth_error = bool(candle.get("auth_error")) or bool(h.get("quote", {}).get("auth_error"))
    now = r.provider.now()
    out = []
    any_market_open = False
    for inst in all_instruments():
        st = r.state.get(inst.key, {})
        pos = st.get("position")
        budget = _INTERVAL_MINUTES.get(r._interval_for(inst.key), 15) * 60 + _STALE_GRACE_SECONDS
        last_ok = r.last_scan_ok.get(inst.key)
        # Market-open mirrors the engine's own scan gate (runner.scan_signals skips
        # closed instruments). When closed, last_scan_ok can't advance, so a stale
        # flag is EXPECTED and benign — the UI must show "market closed", not alarm.
        market_open = r.provider.is_tradable_now(inst)
        any_market_open = any_market_open or market_open
        # No state yet OR this instrument's own last good scan is past its budget.
        stale = (not st) or is_stale(last_ok, now, budget)
        out.append({
            "key": inst.key, "name": inst.name, "segment": inst.segment,
            "enabled": inst.key in r.enabled,
            "pinned": inst.on_home,   # in the curated portfolio (Watchlist "pinned" filter)
            "interval": r._interval_for(inst.key),
            "signal": st.get("signal", "NONE"), "trend": st.get("trend"),
            "z": st.get("z"), "close": st.get("close"),
            "last_candle_time": st.get("time"),
            "has_position": pos is not None,
            "has_options": inst.has_options,
            "entries_blocked": inst.key in r.entry_blocks,
            "stale": stale,
            "market_open": market_open,
            # dual-segment / multi-strategy per-instrument config
            "product": r.products.get(inst.key, "options"),
            "priority_flag": r.priority_flags.get(inst.key, False),
            "strategy_key": r.strategy_keys.get(inst.key),
        })
    return {"instruments": out, "health": h, "feed_auth_error": feed_auth_error,
            "any_market_open": any_market_open}


@router.get("/api/positions")
async def positions(request: Request, segment: str | None = None):
    """Active-positions cockpit rows: marks, trailing stop, stale/health. Optional
    ?segment=options|equity_intraday filters to one trading window.

    Async + engine-lock: this reads the broker's long-lived Session, which the
    engine loops also use. Running on the event loop under r._lock keeps all
    Session access single-threaded (SQLAlchemy Sessions are not thread-safe)."""
    r = _runner(request)
    ticks = r.position_ticks
    out = []
    async with r._lock:
        for p in r.broker.open_positions():
            seg = p.segment or "options"
            if segment and seg != segment:
                continue
            d = p.to_dict()
            t = ticks.get(p.instrument_key, {})
            d["live_premium"] = t.get("option_premium")
            d["live_spot"] = t.get("spot")
            d["stale"] = t.get("stale", True)
            d["stale_age"] = t.get("stale_age")
            # distance to the trigger, signed so positive = still safe / has room —
            # direction-aware so an equity SHORT (stop above, target below) reads right.
            last = d["last_premium"]
            if seg == "equity_intraday" and p.direction == "SHORT":
                d["dist_to_stop"] = round(d["stop_price"] - last, 2)
                d["dist_to_target"] = round(last - d["target_price"], 2)
            else:
                d["dist_to_stop"] = round(last - d["stop_price"], 2)
                d["dist_to_target"] = round(d["target_price"] - last, 2)
            out.append(d)
        cap = r.capital_dict()
    return {"positions": out, "capital": cap}


@router.get("/api/provider-health")
def provider_health(request: Request):
    return _runner(request).health.as_dict()


# ── per-instrument interval + entry block (F6, F8) ───────────────────────────
class IntervalBody(BaseModel):
    interval: str


@router.post("/api/instruments/{key}/interval")
def set_interval(key: str, body: IntervalBody, request: Request):
    iv = _runner(request).set_interval(key, body.interval)
    return {"key": key, "interval": iv}


class BlockBody(BaseModel):
    blocked: bool


@router.post("/api/instruments/{key}/block-entries")
def block_entries(key: str, body: BlockBody, request: Request):
    _runner(request).set_entries_blocked(key, body.blocked)
    return {"key": key, "entries_blocked": body.blocked}


# ── dual-segment / multi-strategy per-instrument controls (Phase 3) ──────────
class ProductBody(BaseModel):
    product: str            # "options" | "equity_intraday"


@router.post("/api/instruments/{key}/product")
def set_product(key: str, body: ProductBody, request: Request):
    if key not in {i.key for i in all_instruments()}:
        return {"error": "unknown instrument"}
    p = _runner(request).set_product(key, body.product)
    return {"key": key, "product": p}


class PriorityBody(BaseModel):
    priority_flag: bool     # the watchlist "purple" intraday-priority flag


@router.post("/api/instruments/{key}/priority")
def set_priority(key: str, body: PriorityBody, request: Request):
    if key not in {i.key for i in all_instruments()}:
        return {"error": "unknown instrument"}
    _runner(request).set_priority_flag(key, body.priority_flag)
    return {"key": key, "priority_flag": body.priority_flag}


class StrategyBody(BaseModel):
    strategy_key: str | None = None   # None = default strategy


@router.post("/api/instruments/{key}/strategy")
def set_strategy(key: str, body: StrategyBody, request: Request):
    if key not in {i.key for i in all_instruments()}:
        return {"error": "unknown instrument"}
    sk = _runner(request).set_strategy(key, body.strategy_key)
    return {"key": key, "strategy_key": sk}


@router.get("/api/strategies")
def strategies():
    """The registered strategies, for per-instrument assignment dropdowns."""
    from app.strategy.registry import strategy_meta
    return {"strategies": strategy_meta()}


# ── manual paper overrides (F8) — never touch real Kite orders ───────────────
@router.post("/api/positions/{key}/close")
async def close_position(key: str, request: Request):
    # Async + engine-lock: serialize this manual close against the engine's
    # risk/signal loops so a manual close can never race an auto-exit on the
    # shared broker Session (which would double-close / corrupt the ledger).
    r = _runner(request)
    async with r._lock:
        pos = r.broker.position_for(key)
        if not pos:
            return {"error": "no open position for this instrument"}
        inst = get_instrument(key)
        premium = r.provider.option_ltp(inst, pos.tradingsymbol, pos.strike, pos.expiry, pos.option_type)
        if premium is None:
            premium = pos.last_premium or pos.entry_premium
        now = r.provider.now()
        r.broker.close_position(pos, premium, "MANUAL_CLOSE", now,
                                r.provider.get_ltp(inst) or pos.last_spot)
        from app.core.logging import log
        log.info(f"MANUAL CLOSE {pos.tradingsymbol} @ {premium:.2f}", instrument=key,
                 event="MANUAL_CLOSE", manual=True)
        if key in r.state:
            r.state[key]["position"] = None
        return {"closed": True, "key": key, "exit_premium": round(premium, 2)}


class SLTPBody(BaseModel):
    stop_price: float | None = None
    target_price: float | None = None
    stop_pct: float | None = None      # fraction below entry premium (e.g. 0.35)
    target_pct: float | None = None    # fraction above entry premium (e.g. 0.60)


@router.post("/api/positions/{key}/sltp")
async def set_position_sltp(key: str, body: SLTPBody, request: Request):
    """Owner override of the stop/target on one open position. Absolute prices or
    percentages of entry. Setting a target by hand pins it (reinforcement won't
    auto-extend it); the trailing stop still ratchets up from a manual stop."""
    r = _runner(request)
    async with r._lock:
        pos = r.broker.position_for(key)
        if not pos:
            return {"error": "no open position for this instrument"}
        new_stop = body.stop_price
        if new_stop is None and body.stop_pct is not None:
            new_stop = pos.entry_premium * (1 - body.stop_pct)
        new_target = body.target_price
        if new_target is None and body.target_pct is not None:
            new_target = pos.entry_premium * (1 + body.target_pct)
        stop = new_stop if new_stop is not None else pos.stop_price
        target = new_target if new_target is not None else pos.target_price
        if stop <= 0 or target <= 0:
            return {"error": "stop and target must be positive"}
        if stop >= target:
            return {"error": "stop must be below target"}
        pos.stop_price = stop
        pos.target_price = target
        if new_target is not None:
            pos.manual_target = True
        r.broker.commit()
        # push the owner's new stop to the exchange GTT backstop (no-op on paper;
        # LiveBroker modifies the live GTT) so a bot-down exit protects at this stop,
        # not the stale one it replaced.
        r.broker.update_stop_protection(pos, pos.last_premium)
        from app.core.logging import log
        log.info(f"MANUAL SL/TP {pos.tradingsymbol} -> SL {stop:.2f} / TP {target:.2f}",
                 instrument=key, event="MANUAL_SLTP", manual=True)
        return {"ok": True, "key": key,
                "stop_price": round(stop, 2), "target_price": round(target, 2)}


class NoTPBody(BaseModel):
    enabled: bool


@router.post("/api/positions/{key}/no-take-profit")
async def set_no_take_profit(key: str, body: NoTPBody, request: Request):
    """Owner's per-position "let it run": remove (or restore) the take-profit cap
    on one open position — for an overnight winner that can run on news. The
    trailing stop, the strategy exit, and the theta/expiry/max-hold square-offs
    all still apply, so the position is never left unprotected. Enabling is
    refused while the global trailing stop is OFF (that would leave no profit
    floor at all)."""
    from app.core.runtime_config import effective
    r = _runner(request)
    async with r._lock:
        pos = r.broker.position_for(key)
        if not pos:
            return {"error": "no open position for this instrument"}
        if body.enabled and not effective(r.settings).get("trail_enabled", True):
            return {"error": "enable the trailing stop first — 'let it run' needs a "
                             "protective floor (otherwise there's no stop on the upside giveback)"}
        pos.no_take_profit = bool(body.enabled)
        r.broker.commit()
        from app.core.logging import log
        log.info(f"{'NO-TAKE-PROFIT (let it run)' if body.enabled else 'TAKE-PROFIT RESTORED'} "
                 f"{pos.tradingsymbol}", instrument=key, event="NO_TP", manual=True)
        return {"ok": True, "key": key, "no_take_profit": pos.no_take_profit}


# ── execution control: arm-to-trade + kill switch ───────────────────────────
class ArmBody(BaseModel):
    armed: bool


@router.get("/api/execution/state")
def execution_state(request: Request):
    r = _runner(request)
    return {"armed": r.armed, "provider": r.provider.name, "running": r.running}


@router.post("/api/execution/arm")
def execution_arm(body: ArmBody, request: Request):
    # arm/disarm only flips a flag + sends a notification — no broker-session access,
    # so a plain (threadpool) handler is safe here.
    return {"armed": _runner(request).arm(body.armed)}


@router.post("/api/execution/kill")
async def execution_kill(request: Request):
    # squares off open positions -> mutates the broker session, so run on the event
    # loop under the engine lock (same guarantee as the manual close route).
    r = _runner(request)
    async with r._lock:
        closed = r.kill()
    return {"killed": True, "armed": r.armed, "squared_off": closed}


class ManualOpenBody(BaseModel):
    key: str
    direction: str   # "LONG" | "SHORT"


@router.post("/api/positions/manual-open")
async def manual_open(body: ManualOpenBody, request: Request):
    # Async + engine-lock: same single-threaded-Session guarantee as the close
    # path, so a manual entry can't race the engine's entry/exit on broker.s.
    r = _runner(request)
    if body.direction not in ("LONG", "SHORT"):
        return {"error": "direction must be LONG or SHORT"}
    inst = get_instrument(body.key)
    if not inst.has_options:
        return {"error": "instrument has no listed options (tracking only)"}
    async with r._lock:
        chain = r.provider.get_option_chain(inst)
        pos, reason = r.broker.manual_open(inst, body.direction, chain, settings, r.provider.now())
        if pos is None:
            return {"error": reason}
        if body.key in r.state:
            r.state[body.key]["position"] = pos.to_dict()
        return {"opened": True, "key": body.key, "tradingsymbol": pos.tradingsymbol}


# ── runtime settings (manual-override mode) ──────────────────────────────────
@router.get("/api/settings")
def get_settings_route():
    from app.core import runtime_config
    return {"params": runtime_config.schema()}


class SettingBody(BaseModel):
    key: str
    value: str | float | int | bool


@router.post("/api/settings")
def set_setting(body: SettingBody, request: Request):
    from app.core import runtime_config
    res = runtime_config.set_override(body.key, body.value)
    _runner(request).refresh_params()
    return res


class SettingKey(BaseModel):
    key: str


@router.post("/api/settings/reset")
def reset_setting(body: SettingKey, request: Request):
    from app.core import runtime_config
    runtime_config.clear_override(body.key)
    _runner(request).refresh_params()
    return {"key": body.key, "reset": True}


# ── intraday vs overnight analytics + option dataset ─────────────────────────
@router.get("/api/analytics")
def analytics_split(request: Request, segment: str | None = None):
    """Trade analytics. Optional ?segment=options|equity_intraday narrows the
    headline split AND the per-segment block to one window. All figures are net of
    the full charge stack (Trade.net_pnl is gross − charges)."""
    from app.options.cache import stats as option_stats
    with SessionLocal() as s:
        all_trades = list(s.scalars(select(Trade)))

    def seg_of(t):
        return t.segment or "options"

    def agg(ts):
        n = len(ts)
        wins = sum(1 for t in ts if t.win)
        return {"trades": n, "wins": wins,
                "win_rate": round(100 * wins / n, 1) if n else 0.0,
                "net_pnl": round(sum(t.net_pnl for t in ts), 2),
                "charges": round(sum(t.charges_total for t in ts), 2)}

    # per-segment summary (net of costs) across BOTH windows — never filtered, so
    # the dashboard can always show options vs equity side by side
    by_segment = {seg: agg([t for t in all_trades if seg_of(t) == seg])
                  for seg in ("options", "equity_intraday")}

    trades = [t for t in all_trades if seg_of(t) == segment] if segment else all_trades
    overnight = [t for t in trades if t.held_overnight]
    intraday = [t for t in trades if not t.held_overnight]
    return {
        "intraday": agg(intraday),
        "overnight": agg(overnight),
        "overnight_gap_pnl": round(sum(t.overnight_pnl for t in trades), 2),
        "reinforced_trades": sum(1 for t in trades if t.reinforcements > 0),
        "option_dataset": option_stats(),
        "by_segment": by_segment,
    }


# ── websockets ──────────────────────────────────────────────────────────────
@router.websocket("/ws")
async def ws_main(ws: WebSocket):
    await manager.connect(ws)
    try:
        # prime the new client with the current state + recent logs
        r = _runner(ws)
        from app.core.logging import log
        await ws.send_json({"type": "state", "data": r.snapshot_state()})
        await ws.send_json({"type": "logs", "data": log.recent(120)})
        while True:
            await ws.receive_text()  # keepalive; we only push
    except WebSocketDisconnect:
        manager.disconnect(ws)
    except Exception:
        manager.disconnect(ws)


@router.websocket("/ws/instrument/{key}")
async def ws_instrument(ws: WebSocket, key: str):
    await ws.accept()
    r = _runner(ws)
    inst = get_instrument(key)
    try:
        while True:
            spot = r.provider.get_live_price(inst)
            with SessionLocal() as s:
                pos = s.scalar(select(Position).where(Position.instrument_key == key))
                contract = (pos.tradingsymbol, pos.strike, pos.expiry, pos.option_type) if pos else None
            opt = r.provider.option_ltp(inst, *contract) if contract else None
            await ws.send_json({
                "instrument": key,
                "time": r.provider.now().isoformat(),
                "spot": spot,
                "option_premium": round(opt, 2) if opt else None,
                "tradingsymbol": contract[0] if contract else None,
            })
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return
    except Exception:
        return
