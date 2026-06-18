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
from app.db.models import Position
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


# ── charts ──────────────────────────────────────────────────────────────────
@router.get("/api/candles/{key}")
def candles(key: str, request: Request):
    r = _runner(request)
    inst = get_instrument(key)
    cs = r.provider.get_candles(inst, settings.interval, settings.history_days)
    if not cs:
        return {"candles": [], "ema": [], "zscore": [], "markers": [], "latest": None}
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
    cs = r.provider.get_candles(inst, settings.interval, settings.history_days)
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
