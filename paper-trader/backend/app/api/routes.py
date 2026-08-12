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

from fastapi import APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse

from app.api.paging import MAX_PAGE
from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.instruments import all_instruments, get_instrument
from app.db.models import DailyAccountSnapshot, Position, Trade
from app.db.session import SessionLocal
from app.engine import analytics
from app.options.pricing import bs_price, implied_vol
from app.providers.base import ProviderReadError
from app.core.execution_binding import AuthorityNotGranted
from app.strategy.registry import get_strategy
from app.strategy.signals import to_payload
from app.api.principal import Principal, get_principal, owner_id_for
from app.ws.manager import manager

router = APIRouter()
settings = get_settings()


def _runner(req_or_ws):
    return req_or_ws.app.state.runner


def _period_since(period: str | None, now):
    """Map a period token to a naive-IST cutoff (exit_time >= cutoff). None = all-time.
    `now` comes from provider.now(); strip tz so it compares to naive exit_time."""
    if not period or period == "all":
        return None
    if getattr(now, "tzinfo", None) is not None:
        now = now.replace(tzinfo=None)
    if period == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "7d":
        return now - dt.timedelta(days=7)
    if period == "30d":
        return now - dt.timedelta(days=30)
    return None


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
        # `r.book`, not the configured mode: `make_broker` returns a PaperBroker whenever
        # the live gates or the Kite provider are absent, so the setting and the broker
        # that was actually built can disagree. The cockpit must report the book the
        # engine is writing.
        cap = analytics.capital_dict(
            s, book=r.book, owner_id=r.owner_id,
            broker_account_id=r.broker_account_id)
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
        # research-plane freeze flag — the cockpit hides the Portfolio tab when off
        "research_enabled": settings.research_enabled,
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
        trades = list(s.scalars(select(Trade).where(
            Trade.owner_id == r.owner_id,
            Trade.broker_account_id == r.broker_account_id,
            Trade.mode == "live")))
        snaps = {row.day: row.account_net for row in s.scalars(
            select(DailyAccountSnapshot).where(
                DailyAccountSnapshot.broker_account_id == r.broker_account_id))}
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
    strategy_key: str | None = None  # carry the winner's best strategy
    product: str | None = None       # options | equity_intraday


@router.post("/api/portfolio/add")
def portfolio_add(body: AddInstrument, request: Request):
    from app.core import universe_resolver
    r = _runner(request)
    res = universe_resolver.add_instrument(body.key, r.provider, on_home=body.on_home,
                                           interval=body.interval,
                                           strategy_key=body.strategy_key, product=body.product,
                                           owner_id=r.owner_id)
    if "error" not in res:
        r.apply_universe_entry(body.key, res)   # config-then-enable (H11); live next tick
    return res


@router.post("/api/portfolio/remove")
def portfolio_remove(body: AddInstrument, request: Request):
    from app.core import universe_resolver
    r = _runner(request)
    res = universe_resolver.remove_instrument(
        body.key, owner_id=r.owner_id,
        broker_account_id=r.broker_account_id)
    r.remove_universe_entry(body.key)   # disable-first (H11)
    return res


class BulkItem(BaseModel):
    key: str
    interval: str | None = None
    strategy_key: str | None = None
    product: str | None = None
    on_home: bool = True


class BulkAdd(BaseModel):
    items: list[BulkItem]


@router.post("/api/portfolio/add-bulk")
def portfolio_add_bulk(body: BulkAdd, request: Request):
    """Add several instruments at once (backtest winners). Each carries its best
    interval / strategy / product; every successfully added item is enabled for
    live trading. Over-budget names are excluded client-side before posting."""
    from app.core import universe_resolver
    r = _runner(request)
    added, skipped = [], []
    for it in body.items:
        try:
            res = universe_resolver.add_instrument(
                it.key, r.provider, on_home=it.on_home, interval=it.interval,
                strategy_key=it.strategy_key, product=it.product, owner_id=r.owner_id)
        except Exception as e:
            skipped.append({"key": it.key, "reason": str(e)})
            continue
        if "error" in res:
            skipped.append({"key": it.key, "reason": res["error"]})
            continue
        r.apply_universe_entry(it.key, res)   # config-then-enable (H11)
        added.append(res)
    return {"added": added, "skipped": skipped}


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
    except ProviderReadError:
        # A DATA failure degrades to an empty panel: the operator is looking at a chart, and a
        # 500 is not an improvement on "no bars yet". Narrowed from bare `Exception` once the
        # provider gained a failure channel — a `TypeError` in the signal path used to render
        # here as a blank chart with a 200, indistinguishable from an unauthenticated
        # connection, so the defect never surfaced.
        cs = []
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
        # Book-scoped like every other position read (ADR 0012 §6.3): with two books the
        # same instrument can be open in both, and an unscoped read would show whichever
        # row SQLite returned first.
        pos = s.scalar(select(Position).where(Position.instrument_key == key,
                                              Position.owner_id == r.owner_id,
                                              Position.broker_account_id == r.broker_account_id,
                                              Position.mode == r.book))
        if not pos:
            return {"candles": [], "tradingsymbol": None}
        tsym, strike, expiry, otype = pos.tradingsymbol, pos.strike, pos.expiry, pos.option_type
        entry_premium, stop_price, target_price = pos.entry_premium, pos.stop_price, pos.target_price
    inst = get_instrument(key)
    try:
        cs = r.provider.get_candles(inst, r._interval_for(key), settings.history_days)
    except ProviderReadError:
        # Same narrowing as the sibling route above, and for the same reason.
        cs = []
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
        return analytics.account_pnl(s, r.provider, book=r.book,
                                     owner_id=r.owner_id,
                                     broker_account_id=r.broker_account_id)


@router.get("/api/dashboard")
def dashboard(request: Request, segment: str | None = None, strategy: str | None = None,
              period: str | None = None):
    """Portfolio dashboard. Optional ?segment=, ?strategy=, and ?period=all|today|7d|30d
    slice the summary / curves / trades. The headline `equity_curve` is the global
    mark-to-market series when unfiltered; for a slice it's the realized-P&L curve."""
    seg = segment or None
    strat = strategy or None
    r = _runner(request)
    since = _period_since(period, r.provider.now()) if (period and period != "all") else None
    with SessionLocal() as s:
        # The equity curve stays unfiltered on purpose: points written before 2026-08-07
        # carry no book, so scoping it would drop the entire pre-slice history from the
        # cockpit (ADR 0012 §6.3). Everything derived from live rows is book-scoped.
        scope = {"owner_id": r.owner_id,
                 "broker_account_id": r.broker_account_id}
        equity = (analytics.equity_curve(s, since=since, **scope) if not (seg or strat)
                  else analytics.realized_curve(s, seg, strat, since, **scope))
        return {
            "capital": analytics.capital_dict(
                s, book=r.book, **scope),
            "summary": analytics.summary(s, seg, strat, since, **scope),
            "equity_curve": equity,
            "instrument_curves": analytics.per_instrument_curves(
                s, seg, strat, since, **scope),
            "segment_curves": analytics.segment_curves(s, since, **scope),
            "strategy_curves": analytics.strategy_curves(s, seg, since, **scope),
            "recent_trades": analytics.recent_trades(
                s, 50, segment=seg, strategy=strat, since=since, **scope),
            "open_positions": [p.to_dict() for p in analytics.open_positions(
                s, r.book, **scope)],
            "segment": seg, "strategy": strat, "period": period or "all",
        }


@router.get("/api/instrument/{key}")
def instrument_detail(key: str, request: Request, segment: str | None = None,
                      strategy: str | None = None, period: str | None = None):
    """Full per-instrument stat block + that instrument's trades, honoring
    ?segment=, ?strategy=, ?period=."""
    try:
        inst = get_instrument(key)
    except KeyError:
        inst = None
    r = _runner(request)
    since = _period_since(period, r.provider.now()) if (period and period != "all") else None
    scope = {"owner_id": r.owner_id,
             "broker_account_id": r.broker_account_id}
    with SessionLocal() as s:
        stats = analytics.instrument_stats(
            s, key, segment or None, strategy or None, since, **scope)
        trades = analytics.instrument_trades(
            s, key, segment or None, strategy or None, since, **scope)
    return {"key": key, "name": inst.name if inst else key,
            "segment": inst.segment if inst else None,
            "stats": stats, "trades": trades, "period": period or "all"}


@router.get("/api/trades")
def trades(request: Request, limit: int = Query(default=100, ge=1, le=MAX_PAGE),
           mode: str | None = None):
    # mode="paper"|"live" filters the log to one ledger; omitted returns both
    # (each row still carries its own `mode` so the UI can split them).
    r = _runner(request)
    with SessionLocal() as s:
        return {"trades": analytics.recent_trades(
            s, limit, mode, owner_id=r.owner_id,
            broker_account_id=r.broker_account_id)}


@router.get("/api/logs")
def logs(limit: int = Query(default=300, ge=1, le=MAX_PAGE)):
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
    from app.core import runtime_config
    eff = runtime_config.effective(owner_id=r.owner_id)
    today_thr = int(eff.get("overtrade_today_threshold", 5))
    roll_thr = int(eff.get("overtrade_rolling_threshold", 15))
    roll_days = int(eff.get("overtrade_rolling_days", 7))
    with SessionLocal() as _s:
        sig_counts = analytics.signal_counts(
            _s, now, owner_id=r.owner_id,
            broker_account_id=r.broker_account_id, rolling_days=roll_days)
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
            "signals_today": sig_counts.get(inst.key, {}).get("today", 0),
            "signals_rolling": sig_counts.get(inst.key, {}).get("rolling", 0),
            "overtrade_flag": r.overtrade_flags.get(inst.key, False),
            "overtrade_suggested": (
                (today_thr > 0 and sig_counts.get(inst.key, {}).get("today", 0) >= today_thr)
                or (roll_thr > 0 and sig_counts.get(inst.key, {}).get("rolling", 0) >= roll_thr)),
        })
    return {"instruments": out, "health": h, "feed_auth_error": feed_auth_error,
            "any_market_open": any_market_open}


@router.get("/api/earnings")
def earnings_calendar():
    """Cached next-results date for every NSE/BSE cash-equity instrument in the
    universe — index (NFO/BFO) and commodity (MCX/NCDEX) instruments have no
    earnings concept and are excluded. Purely a read of the daily-refreshed cache
    (see app/core/earnings.py + scripts/refresh_earnings.py); never fetches NSE
    live, so this stays as cheap as /api/signals."""
    from app.core import earnings as earnings_core
    stocks = [i.key for i in all_instruments() if i.segment in ("NSE", "BSE")]
    with SessionLocal() as s:
        return {"earnings": earnings_core.earnings_map(s, stocks)}


@router.get("/api/storage")
def storage_stats(request: Request):
    """Database size, what is growing, and what retention will do about it.

    The DB reached 108 MB on a 1 GB droplet before anyone noticed, because nothing in the
    product ever reported its size — the growth was only ever visible by SSH-ing in. The
    option-chain sweep in particular is a DELIBERATE cost (Kite sells no historical chains,
    so an unsnapshotted day is gone forever); the point of this endpoint is that the owner
    can see what that decision costs and switch it off knowingly, rather than discover it
    from an OOM."""
    import os

    from app.db.models import EquitySnapshot, OptionData, OrderJournal, SignalEvent, Trade
    r = _runner(request)
    s_ = get_settings()

    path = s_.db_path
    size_mb = 0.0
    for sfx in ("", "-wal", "-shm"):
        try:
            size_mb += os.path.getsize(path + sfx) / 1e6
        except OSError:
            pass

    now = r.provider.now()
    day_ago = now - dt.timedelta(days=1)
    with SessionLocal() as s:
        tables = {
            "option_data": (s.query(func.count(OptionData.id)).scalar() or 0,
                            s.query(func.count(OptionData.id)).filter(
                                OptionData.ts >= day_ago).scalar() or 0),
            "signal_events": (s.query(func.count(SignalEvent.id)).filter(
                              SignalEvent.owner_id == r.owner_id,
                              SignalEvent.broker_account_id == r.broker_account_id).scalar() or 0,
                              s.query(func.count(SignalEvent.id)).filter(
                                  SignalEvent.time >= day_ago,
                                  SignalEvent.owner_id == r.owner_id,
                                  SignalEvent.broker_account_id == r.broker_account_id).scalar() or 0),
            "equity_snapshots": (s.query(func.count(EquitySnapshot.id)).filter(
                                 EquitySnapshot.owner_id == r.owner_id,
                                 EquitySnapshot.broker_account_id == r.broker_account_id).scalar() or 0,
                                 s.query(func.count(EquitySnapshot.id)).filter(
                                     EquitySnapshot.time >= day_ago,
                                     EquitySnapshot.owner_id == r.owner_id,
                                     EquitySnapshot.broker_account_id == r.broker_account_id).scalar() or 0),
            "trades": (s.query(func.count(Trade.id)).filter(
                Trade.owner_id == r.owner_id,
                Trade.broker_account_id == r.broker_account_id).scalar() or 0, None),
            "order_journal": (s.query(func.count(OrderJournal.id)).filter(
                OrderJournal.owner_id == r.owner_id,
                OrderJournal.broker_account_id == r.broker_account_id).scalar() or 0, None),
        }

    return {
        "db_path": path,
        "size_mb": round(size_mb, 1),
        "tables": [{"name": k, "rows": v[0], "rows_last_24h": v[1],
                    "pruned": v[1] is not None} for k, v in tables.items()],
        "retention": {
            "enabled": bool(r.params.get("retention_enabled", True)),
            "option_data_days": r.params.get("retention_option_data_days"),
            "signal_events_days": r.params.get("retention_signal_events_days"),
            "equity_full_days": r.params.get("retention_equity_full_days"),
            "equity_downsample_minutes": r.params.get("retention_equity_downsample_minutes"),
            "last_run": r._pruned_date.isoformat() if r._pruned_date else None,
        },
        "option_cache_enabled": bool(r.params.get("option_cache_enabled", True)),
    }


@router.get("/api/event-risk")
def event_risk_today(request: Request, day: str | None = None):
    """Every scheduled-event blackout in force for the universe on `day` (default
    today), plus the health of the earnings calendar behind it.

    This exists so a sit-out is never mysterious. Before it, the only way to learn the
    bot had declined a signal was to read the journal — the cockpit showed an idle bot
    with no explanation, which is indistinguishable from a broken one. Read-only and
    cheap: pure rule evaluation plus one cached-calendar query."""
    from app.core import earnings as earnings_core
    from app.engine.event_risk import DEFAULT_RULES, blackouts_for_day, normalize_key
    r = _runner(request)
    try:
        target = dt.date.fromisoformat(day) if day else r.provider.now().date()
    except ValueError:
        raise HTTPException(400, f"bad day '{day}' — expected YYYY-MM-DD")

    enabled = bool(r.params.get("event_risk_enabled", True))
    stocks = [i.key for i in all_instruments() if i.segment in ("NSE", "BSE")]
    with SessionLocal() as s:
        emap = earnings_core.earnings_map(s, [normalize_key(k) for k in stocks], target)

    out = []
    for inst in all_instruments():
        product = r.products.get(inst.key, "options")
        edate = emap.get(normalize_key(inst.key), {}).get("date")
        bl = blackouts_for_day(
            inst.key, product, target,
            earnings_date=dt.date.fromisoformat(edate) if edate else None,
            enabled=enabled)
        if bl:
            out.append({"key": inst.key, "name": inst.name, "product": product,
                        "blackouts": [b.as_dict() for b in bl]})
    return {
        "day": target.isoformat(),
        "enabled": enabled,
        # A per-day opt-in lifts the weekday sit-outs; surfaced so the UI can explain
        # why a "blocked" instrument is trading anyway.
        "override_today": r._event_override_today(r.provider.now()),
        "instruments": out,
        "earnings_calendar": {"known": len(emap), "of_stocks": len(stocks)},
        "rules": [{"kind": r_.kind, "label": r_.label, "keys": list(r_.keys),
                   "products": list(r_.products)} for r_ in DEFAULT_RULES],
    }


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
    try:
        p = _runner(request).set_product(key, body.product)
    except ValueError as e:           # #5: not MIS-eligible -> refuse the intraday assignment
        return {"error": str(e)}
    return {"key": key, "product": p}


class PriorityBody(BaseModel):
    priority_flag: bool     # the watchlist "purple" intraday-priority flag


@router.post("/api/instruments/{key}/priority")
def set_priority(key: str, body: PriorityBody, request: Request):
    if key not in {i.key for i in all_instruments()}:
        return {"error": "unknown instrument"}
    _runner(request).set_priority_flag(key, body.priority_flag)
    return {"key": key, "priority_flag": body.priority_flag}


class OvertradeBody(BaseModel):
    flag: bool


@router.post("/api/instruments/{key}/overtrade")
def set_overtrade(key: str, body: OvertradeBody, request: Request):
    if key not in {i.key for i in all_instruments()}:
        return {"error": "unknown instrument"}
    _runner(request).set_overtrade_flag(key, body.flag)
    return {"key": key, "overtrade_flag": body.flag}


class StrategyBody(BaseModel):
    strategy_key: str | None = None   # None = default strategy


@router.post("/api/instruments/{key}/strategy")
def set_strategy(key: str, body: StrategyBody, request: Request):
    if key not in {i.key for i in all_instruments()}:
        return {"error": "unknown instrument"}
    try:
        sk = _runner(request).set_strategy(key, body.strategy_key)
    except AuthorityNotGranted as e:
        # The gate's verdict is consumed here, not re-derived: no namespace test lives in
        # this route. 409 rather than 500 — the assignment is well-formed and the platform
        # is healthy; the source is one that may not execute, and that is a state of the
        # world the operator needs the reason for.
        raise HTTPException(status_code=409, detail=str(e)) from e
    return {"key": key, "strategy_key": sk}


@router.get("/api/strategies")
def strategies(principal: Principal = Depends(get_principal)):
    """The registered strategies, for per-instrument assignment dropdowns."""
    from app.strategy.registry import strategy_meta
    return {"strategies": strategy_meta(owner_id=owner_id_for(principal))}


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
        # this books at the live/paper LTP mark, not a real fill (in live mode
        # LiveBroker's own close_position ignores this flag — it always books its
        # own real order fill instead — so it only takes effect for PaperBroker).
        trade = r.broker.close_position(pos, premium, "MANUAL_CLOSE", now,
                                        r.provider.get_ltp(inst) or pos.last_spot,
                                        exit_price_estimated=True)
        from app.core.logging import log
        # E4: LiveBroker returns None when the close did NOT go through (ownership
        # guard, SL-M-cancel abort, account re-check). Reporting that as success gave
        # the owner a lying cockpit — position still live at the exchange, display
        # state wiped, re-entry blocked for no reason. Surface it instead.
        if trade is None:
            log.error(f"MANUAL CLOSE FAILED {pos.tradingsymbol} — still open",
                      instrument=key, event="MANUAL_CLOSE_FAILED", manual=True)
            return {"error": "close failed — the position is still open",
                    "closed": False, "key": key}
        log.info(f"MANUAL CLOSE {pos.tradingsymbol} @ {premium:.2f}", instrument=key,
                 event="MANUAL_CLOSE", manual=True)
        # #2: a manual close blocks same-day re-entry for this symbol — the bot must not
        # re-open what you deliberately exited. Clear it from the window to re-allow.
        r.set_entries_blocked(key, True)
        if key in r.state:
            r.state[key]["position"] = None
        return {"closed": True, "key": key, "exit_premium": round(premium, 2),
                "entries_blocked": True}


class SLTPBody(BaseModel):
    stop_price: float | None = None
    target_price: float | None = None
    stop_pct: float | None = None      # fraction below entry premium (e.g. 0.35)
    target_pct: float | None = None    # fraction above entry premium (e.g. 0.60)


@router.post("/api/positions/{key}/sltp")
async def set_position_sltp(key: str, body: SLTPBody, request: Request):
    """Owner override of the stop/target on one open position. Absolute prices or
    percentages of entry. Direction-aware: a SHORT-equity position keeps its stop
    ABOVE entry and target BELOW (a long option/equity keeps stop below / target
    above). Setting a target by hand pins it (reinforcement won't auto-extend it);
    the trailing stop still ratchets up from a manual stop."""
    from app.engine.equity_entry import resolve_sltp
    r = _runner(request)
    async with r._lock:
        pos = r.broker.position_for(key)
        if not pos:
            return {"error": "no open position for this instrument"}
        is_short = pos.segment == "equity_intraday" and pos.direction == "SHORT"
        stop, target, err = resolve_sltp(
            is_short=is_short, entry=pos.entry_premium,
            cur_stop=pos.stop_price, cur_target=pos.target_price,
            stop_price=body.stop_price, stop_pct=body.stop_pct,
            target_price=body.target_price, target_pct=body.target_pct)
        if err:
            return {"error": err}
        pos.stop_price = stop
        pos.target_price = target
        if body.target_price is not None or body.target_pct is not None:
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
        if body.enabled and not effective(r.settings, owner_id=r.owner_id).get("trail_enabled", True):
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
    if not r.armed:
        return {"error": "engine is disarmed — ARM before opening a position"}
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
def get_settings_route(request: Request):
    from app.core import runtime_config
    return {"params": runtime_config.schema(owner_id=_runner(request).owner_id)}


class SettingBody(BaseModel):
    key: str
    value: str | float | int | bool


@router.post("/api/settings")
def set_setting(body: SettingBody, request: Request):
    from app.core import runtime_config
    runner = _runner(request)
    res = runtime_config.set_override(body.key, body.value, owner_id=runner.owner_id)
    runner.refresh_params()
    return res


class SettingKey(BaseModel):
    key: str


@router.post("/api/settings/reset")
def reset_setting(body: SettingKey, request: Request):
    from app.core import runtime_config
    runner = _runner(request)
    runtime_config.clear_override(body.key, owner_id=runner.owner_id)
    runner.refresh_params()
    return {"key": body.key, "reset": True}


# ── L1 Stage 1: the Component IR shadow lane (read-only) ─────────────────────
@router.get("/api/ir-shadow")
def ir_shadow_observability(request: Request, limit: int = Query(default=50, ge=1, le=MAX_PAGE)):
    """What the shadow lane has seen. Observability only — there is deliberately **no**
    write route here: the lane's on/off flag is the `ir_shadow_enabled` runtime_config key
    and moves through `/api/settings`, so this cannot become a second way to steer it.

    `coverage` matters as much as `metrics`. Production's default strategy has no IR
    mirror, so "no disagreements" is usually a statement about how little is shadowed
    rather than about how well the two lanes agree.
    """
    from app.engine import ir_shadow, ir_shadow_store

    runner = _runner(request)
    assignments = dict(getattr(runner, "strategy_keys", {}) or {})
    shadowed = sorted(k for k, s in assignments.items() if ir_shadow.pairing_for(s))
    unmirrored = sorted(k for k, s in assignments.items() if not ir_shadow.pairing_for(s))
    return {
        "enabled": bool(runner.params.get("ir_shadow_enabled", False)),
        "metrics": runner.shadow_metrics.snapshot(),
        "coverage": {
            "shadowed": shadowed,
            "unmirrored": unmirrored,
            "pairings": sorted(ir_shadow.PAIRING_BUILDERS),
            # A pairing refused by the admission contract, or demoted after the feed
            # contradicted it. Reported beside `shadowed` on purpose: an instrument can be
            # mirrored AND not observed, and those two facts read identically without this.
            "rejected": dict(getattr(runner.shadow_metrics, "rejections", {})),
        },
        "reasons": list(ir_shadow.DISAGREEMENT_REASONS),
        "recorded_by_reason": ir_shadow_store.counts_by_reason(
            owner_id=runner.owner_id, broker_account_id=runner.broker_account_id),
        "divergences": ir_shadow_store.recent(
            owner_id=runner.owner_id, broker_account_id=runner.broker_account_id,
            limit=limit),
    }


# ── intraday vs overnight analytics + option dataset ─────────────────────────
@router.get("/api/analytics")
def analytics_split(request: Request, segment: str | None = None):
    """Trade analytics. Optional ?segment=options|equity_intraday narrows the
    headline split AND the per-segment block to one window. All figures are net of
    the full charge stack (Trade.net_pnl is gross − charges)."""
    from app.options.cache import stats as option_stats
    runner = _runner(request)
    with SessionLocal() as s:
        all_trades = list(s.scalars(select(Trade).where(
            Trade.owner_id == runner.owner_id,
            Trade.broker_account_id == runner.broker_account_id)))

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
    from app.api.principal import authenticate_websocket
    principal = await authenticate_websocket(ws)
    if principal is None:
        return
    ws.state.principal = principal
    await manager.connect(ws, accepted=True)
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


def _instrument_payload(provider, key: str, book: str, *, owner_id: str,
                        broker_account_id: str) -> dict:
    """H1: the blocking per-tick fetch for /ws/instrument — synchronous Kite calls
    (get_live_price, option_ltp) plus a DB read. Kept as a plain function so the WS
    handler can run it OFF the event loop via asyncio.to_thread; called directly on the
    loop it froze WS heartbeats, the risk scheduler, and the cockpit once per second per
    open tile."""
    inst = get_instrument(key)
    spot = provider.get_live_price(inst)
    with SessionLocal() as s:
        # Book-scoped (ADR 0012 §6.3). `book` is passed from the runner rather than read
        # from configuration, because `make_broker` can build a paper broker under a live
        # setting — the tile must show the book the engine actually writes.
        pos = s.scalar(select(Position).where(Position.instrument_key == key,
                                              Position.owner_id == owner_id,
                                              Position.broker_account_id == broker_account_id,
                                              Position.mode == book))
        contract = (pos.tradingsymbol, pos.strike, pos.expiry, pos.option_type) if pos else None
    opt = provider.option_ltp(inst, *contract) if contract else None
    return {
        "instrument": key,
        "time": provider.now().isoformat(),
        "spot": spot,
        "option_premium": round(opt, 2) if opt else None,
        "tradingsymbol": contract[0] if contract else None,
    }


@router.websocket("/ws/instrument/{key}")
async def ws_instrument(ws: WebSocket, key: str):
    from app.api.principal import authenticate_websocket
    principal = await authenticate_websocket(ws)
    if principal is None:
        return
    ws.state.principal = principal
    r = _runner(ws)
    try:
        while True:
            payload = await asyncio.to_thread(
                _instrument_payload, r.provider, key, r.book,
                owner_id=r.owner_id, broker_account_id=r.broker_account_id)
            await ws.send_json(payload)
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        return
    except Exception:
        return


class ShadowDeploymentIn(BaseModel):
    project_id: str
    graph_identifier: str
    graph_version: int
    instrument_key: str
    interval: str
    deployment_id: int | None = None
    note: str = ""


class ShadowTransitionIn(BaseModel):
    revision: int


@router.get("/api/ir-shadow/deployments")
def list_shadow_deployments(request: Request, include_retired: bool = False):
    """Managed, non-authoritative shadow deployments (L1.3A).

    Typed contract only — there is deliberately no frontend here. Every row states its
    project, exact graph version and content address, verified evidence lineage, instrument,
    interval, admission verdict and lifecycle state, so the answer to "what is being
    observed, on whose approval" needs no prose reconstruction.
    """
    from app.core import shadow_deployments

    runner = _runner(request)
    with SessionLocal() as s:
        return {"deployments": shadow_deployments.listing(
            s, owner_id=runner.owner_id,
            broker_account_id=runner.broker_account_id,
            include_retired=include_retired)}


@router.post("/api/ir-shadow/deployments")
def stage_shadow_deployment(body: ShadowDeploymentIn, request: Request):
    """Stage a shadow deployment. Staging never starts evaluation — activation does, and it
    is a separate call because it is the one that verifies evidence and admission."""
    from app.core import shadow_deployments

    runner = _runner(request)
    with SessionLocal() as s:
        try:
            row = shadow_deployments.stage(
                s, project_id=body.project_id, graph_identifier=body.graph_identifier,
                graph_version=body.graph_version,
                deployment_id=(body.deployment_id
                               if body.deployment_id is not None
                               else _runner(request).deployment_id),
                instrument_key=body.instrument_key, interval=body.interval,
                owner_id=runner.owner_id,
                broker_account_id=runner.broker_account_id,
                note=body.note)
            s.commit()
        except shadow_deployments.ShadowDeploymentError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        return row.to_dict()


@router.post("/api/ir-shadow/deployments/{row_id}/{action}")
def transition_shadow_deployment(row_id: int, action: str, body: ShadowTransitionIn,
                                 request: Request):
    """Move a shadow deployment through its lifecycle, revision-guarded.

    The verbs are exactly the four the service exposes. There is no verb here that could
    grant authority, and no field on the request that could name a mode — ADR 0012 §3.2 is
    the owner's decision and is not reachable from an HTTP call.
    """
    from app.core import shadow_deployments

    moves = {"activate": shadow_deployments.activate,
             "pause": shadow_deployments.pause,
             "resume": shadow_deployments.resume,
             "retire": shadow_deployments.retire}
    if action not in moves:
        raise HTTPException(status_code=404,
                            detail=f"unknown transition {action!r}; "
                                   f"expected one of {sorted(moves)}")
    runner = _runner(request)
    with SessionLocal() as s:
        try:
            row = moves[action](
                s, row_id, revision=body.revision, owner_id=runner.owner_id,
                broker_account_id=runner.broker_account_id)
            s.commit()
        except shadow_deployments.RevisionConflict as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        except shadow_deployments.ShadowDeploymentError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        result = row.to_dict()
    # The engine holds its bindings in memory, so a transition that did not reach it would
    # be a decision the operator can see and the loop cannot.
    runner.refresh_shadow_deployments()
    return result


class PaperDeploymentIn(BaseModel):
    """What a client may say when staging paper authority.

    Note what is absent and cannot be added by a caller: `execution_mode`, `authority`,
    `runtime_source`, `strategy_key` and `graph_content_address`. The mode and authority are
    the owner's reviewed grant, not a request field; the strategy key and the address are
    *derived* from the artefact the request names, so a client cannot assert an identity the
    bytes do not have.
    """

    project_id: str
    graph_identifier: str
    graph_version: int
    instrument_key: str
    interval: str
    deployment_id: int | None = None
    note: str = ""


class PaperTransitionIn(BaseModel):
    revision: int


class PaperRetireIn(BaseModel):
    """Retirement names where authority goes back to, explicitly.

    `restore_strategy_key` has no default. Omitting it is a 422, and that is the point:
    "roll back" without a named target is a request for the server to guess which strategy
    should trade an instrument, and silent substitution is the failure this project has
    closed twice. `null` is a valid, different answer — "there was no previous authority".
    """

    revision: int
    restore_strategy_key: str | None


@router.get("/api/ir-paper/deployments")
def list_paper_deployments(request: Request, include_retired: bool = False):
    """Paper-authoritative IR deployments (L1.3C).

    Typed contract only — no frontend here. Every row states its project, exact graph
    version and content address, verified evidence lineage, instrument, interval, admission
    verdict, rollback target and lifecycle state, so "what is trading paper, on whose
    approval, at which version" needs no prose reconstruction.
    """
    from app.core import paper_authority

    runner = _runner(request)
    with SessionLocal() as s:
        return {"deployments": paper_authority.listing(
            s, owner_id=runner.owner_id,
            broker_account_id=runner.broker_account_id,
            include_retired=include_retired)}


@router.get("/api/execution/cockpit")
def execution_cockpit(request: Request):
    """The operational read model — one call that answers the cockpit's questions.

    Assembled by `app/engine/cockpit.py` from the services that already own each answer;
    this route adds no logic and makes no decision. It exists because the alternative is a
    cockpit issuing eight calls and correlating them itself, which is how a second
    operational model gets built by accident.

    Read-only and structurally so. Lifecycle control stays on the existing routes
    (`/api/ir-paper/deployments/{id}/{action}`, `/retire`, `/api/execution/arm`,
    `/api/execution/kill`), each of which calls the existing domain service — no authority
    logic is duplicated here, and no control operation was invented for a UI's convenience.

    It answers, per instrument: what exact strategy is authorised, why (the canonical
    binding's own reason and origin), which immutable graph is running and on what
    admission evidence, in which book, what it currently holds, whether the standing gates
    would let it open another entry and which ones would not, and which lifecycle actions
    the domain would accept.

    **No research database is opened.** Admission facts come from the deployment row, which
    recorded them at activation — ADR 0013's model made visible.
    """
    from app.engine import cockpit

    with SessionLocal() as s:
        return cockpit.view(_runner(request), s).to_dict()


@router.get("/api/execution/cockpit/deployments")
def execution_cockpit_deployments(request: Request, include_retired: bool = True):
    """Every paper-authority deployment record with its lifecycle state and provenance.

    Straight through to `paper_authority.listing` — the same rows
    `/api/ir-paper/deployments` serves, defaulting to including retired ones because an
    operational surface needs the history of what once traded here, not only what does now.
    """
    from app.engine import cockpit

    runner = _runner(request)
    with SessionLocal() as s:
        return {"deployments": cockpit.paper_deployments(
            s, owner_id=runner.owner_id,
            broker_account_id=runner.broker_account_id)}


@router.post("/api/ir-paper/deployments")
def stage_paper_deployment(body: PaperDeploymentIn, request: Request):
    """Stage paper authority. Staging confers none — activation does, and it is a separate
    call because it is the one that verifies evidence and admission."""
    from app.core import paper_authority

    runner = _runner(request)
    with SessionLocal() as s:
        try:
            row = paper_authority.stage(
                s, project_id=body.project_id, graph_identifier=body.graph_identifier,
                graph_version=body.graph_version,
                deployment_id=(body.deployment_id
                               if body.deployment_id is not None
                               else _runner(request).deployment_id),
                instrument_key=body.instrument_key, interval=body.interval,
                owner_id=runner.owner_id,
                broker_account_id=runner.broker_account_id,
                note=body.note)
            s.commit()
        except paper_authority.PaperAuthorityError as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        return row.to_dict()


@router.post("/api/ir-paper/deployments/{row_id}/{action}")
def transition_paper_deployment(row_id: int, action: str, body: PaperTransitionIn,
                                request: Request):
    """Move a paper deployment through its lifecycle, revision-guarded.

    Three verbs only. `retire` is deliberately not among them: it is the one transition
    that hands authority back, and it needs a named target, so it has its own route with
    its own body rather than sharing a shape that would let the target be omitted.

    No field here can name a mode. Live authority is not reachable from an HTTP call.
    """
    from app.core import paper_authority

    moves = {"activate": paper_authority.activate,
             "pause": paper_authority.pause,
             "resume": paper_authority.resume}
    if action not in moves:
        raise HTTPException(status_code=404,
                            detail=f"unknown transition {action!r}; expected one of "
                                   f"{sorted(moves)} (retirement has its own route "
                                   f"because it must name a rollback target)")
    runner = _runner(request)
    with SessionLocal() as s:
        try:
            row = moves[action](
                s, row_id, revision=body.revision, owner_id=runner.owner_id,
                broker_account_id=runner.broker_account_id)
            s.commit()
        except paper_authority.RevisionConflict as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        except paper_authority.PaperAuthorityError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        result = row.to_dict()
    runner.refresh_paper_authority()
    return result


@router.post("/api/ir-paper/deployments/{row_id}/retire")
def retire_paper_deployment(row_id: int, body: PaperRetireIn, request: Request):
    """Retire a paper deployment and hand authority to the named target.

    Terminal. The engine is refreshed before this returns, so the operator's decision and
    the running loop cannot disagree about who is authoritative.
    """
    from app.core import paper_authority

    r = _runner(request)
    with SessionLocal() as s:
        try:
            row = paper_authority.retire(
                s, row_id, revision=body.revision,
                restore_strategy_key=body.restore_strategy_key, owner_id=r.owner_id,
                broker_account_id=r.broker_account_id)
            s.commit()
        except paper_authority.RevisionConflict as e:
            raise HTTPException(status_code=409, detail=str(e)) from e
        except paper_authority.PaperAuthorityError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        result = row.to_dict()
    r.refresh_paper_authority()
    return result
