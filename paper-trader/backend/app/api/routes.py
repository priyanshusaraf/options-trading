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
from app.db.models import Position, Trade
from app.db.session import SessionLocal
from app.engine import analytics
from app.options.pricing import bs_price, implied_vol
from app.strategy.signals import compute_signals, to_payload
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
        "tick": r.tick_count,
        "time": p.now().isoformat(),
        "interval": settings.interval,
        "capital": cap,
    }


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
    return RedirectResponse("/")


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
    sig = compute_signals(_df(cs), ema_length=settings.ema_length,
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


@router.get("/api/dashboard")
def dashboard(request: Request):
    with SessionLocal() as s:
        return {
            "capital": analytics.capital_dict(s),
            "summary": analytics.summary(s),
            "equity_curve": analytics.equity_curve(s),
            "instrument_curves": analytics.per_instrument_curves(s),
            "recent_trades": analytics.recent_trades(s, 50),
            "open_positions": [p.to_dict() for p in analytics.open_positions(s)],
        }


@router.get("/api/trades")
def trades(request: Request, limit: int = 100):
    with SessionLocal() as s:
        return {"trades": analytics.recent_trades(s, limit)}


@router.get("/api/logs")
def logs(limit: int = 300):
    from app.core.logging import log
    return {"logs": log.recent(limit)}


# ── signal-first list / positions cockpit / health (F1, F3, F5) ──────────────
@router.get("/api/signals")
def signals(request: Request):
    """Lightweight signal-first list. Pure read of in-memory engine state +
    health — it NEVER fetches candles, so rows stay cheap."""
    r = _runner(request)
    h = r.health.as_dict()
    candle_fails = h.get("candle", {}).get("consecutive_failures", 0)
    out = []
    for inst in all_instruments():
        st = r.state.get(inst.key, {})
        pos = st.get("position")
        out.append({
            "key": inst.key, "name": inst.name, "segment": inst.segment,
            "enabled": inst.key in r.enabled,
            "interval": r._interval_for(inst.key),
            "signal": st.get("signal", "NONE"), "trend": st.get("trend"),
            "z": st.get("z"), "close": st.get("close"),
            "last_candle_time": st.get("time"),
            "has_position": pos is not None,
            "has_options": inst.has_options,
            "entries_blocked": inst.key in r.entry_blocks,
            "stale": (not st) or candle_fails > 0,
        })
    return {"instruments": out, "health": h}


@router.get("/api/positions")
def positions(request: Request):
    """Active-positions cockpit rows: marks, trailing stop, stale/health."""
    r = _runner(request)
    ticks = r.position_ticks
    out = []
    for p in r.broker.open_positions():
        d = p.to_dict()
        t = ticks.get(p.instrument_key, {})
        d["live_premium"] = t.get("option_premium")
        d["live_spot"] = t.get("spot")
        d["stale"] = t.get("stale", True)
        d["stale_age"] = t.get("stale_age")
        d["dist_to_stop"] = round(d["last_premium"] - d["stop_price"], 2)
        d["dist_to_target"] = round(d["target_price"] - d["last_premium"], 2)
        out.append(d)
    return {"positions": out, "capital": r.capital_dict()}


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


# ── manual paper overrides (F8) — never touch real Kite orders ───────────────
@router.post("/api/positions/{key}/close")
def close_position(key: str, request: Request):
    r = _runner(request)
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


class ManualOpenBody(BaseModel):
    key: str
    direction: str   # "LONG" | "SHORT"


@router.post("/api/positions/manual-open")
def manual_open(body: ManualOpenBody, request: Request):
    r = _runner(request)
    if body.direction not in ("LONG", "SHORT"):
        return {"error": "direction must be LONG or SHORT"}
    inst = get_instrument(body.key)
    if not inst.has_options:
        return {"error": "instrument has no listed options (tracking only)"}
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
def analytics_split(request: Request):
    from app.options.cache import stats as option_stats
    with SessionLocal() as s:
        trades = list(s.scalars(select(Trade)))

    def agg(ts):
        n = len(ts)
        wins = sum(1 for t in ts if t.win)
        return {"trades": n, "wins": wins,
                "win_rate": round(100 * wins / n, 1) if n else 0.0,
                "net_pnl": round(sum(t.net_pnl for t in ts), 2)}

    overnight = [t for t in trades if t.held_overnight]
    intraday = [t for t in trades if not t.held_overnight]
    return {
        "intraday": agg(intraday),
        "overnight": agg(overnight),
        "overnight_gap_pnl": round(sum(t.overnight_pnl for t in trades), 2),
        "reinforced_trades": sum(1 for t in trades if t.reinforcements > 0),
        "option_dataset": option_stats(),
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
