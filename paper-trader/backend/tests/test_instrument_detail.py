"""Dashboard period filter + per-instrument detail endpoint."""
import datetime as dt

from app.db.models import Trade
from app.db.session import SessionLocal, init_db
from app.engine.runner import EngineRunner
from app.main import app
from fastapi.testclient import TestClient


def _client():
    prev = getattr(app.state, "runner", None)
    if prev is not None:
        try:
            prev.broker.close()
        except Exception:
            pass
    init_db(reset=True)
    r = EngineRunner()
    app.state.runner = r
    return TestClient(app), r


def _trade(s, *, key, net, hold, exit_time):
    s.add(Trade(instrument_key=key, direction="LONG", option_type="CE",
                tradingsymbol=key, exchange="NFO", segment="options",
                strategy_key="trend_impulse_v3", strike=0.0,
                expiry=dt.date(2026, 7, 31), qty=10,
                entry_premium=100.0, entry_cost=1000.0, entry_spot=100.0,
                entry_time=exit_time - dt.timedelta(hours=1),
                exit_premium=100.0 + net / 10, exit_charges=2.0, exit_spot=100.0,
                exit_time=exit_time, exit_reason="TARGET",
                gross_pnl=net + 2, charges_total=2.0, net_pnl=net, return_pct=0.0,
                holding_minutes=hold, win=net > 0))


def test_dashboard_period_filters_to_today():
    c, r = _client()
    now = r.provider.now()
    if now.tzinfo is not None:
        now = now.replace(tzinfo=None)
    with SessionLocal() as s:
        _trade(s, key="GOLDM", net=100.0, hold=60, exit_time=now)
        _trade(s, key="GOLDM", net=50.0, hold=60, exit_time=now - dt.timedelta(days=10))
        s.commit()
    assert c.get("/api/dashboard").json()["summary"]["trades"] == 2
    today = c.get("/api/dashboard?period=today").json()["summary"]
    assert today["trades"] == 1 and today["net_pnl"] == 100.0


def test_instrument_detail_stats_and_trade_list():
    c, r = _client()
    now = r.provider.now()
    if now.tzinfo is not None:
        now = now.replace(tzinfo=None)
    with SessionLocal() as s:
        _trade(s, key="GOLDM", net=100.0, hold=60, exit_time=now)
        _trade(s, key="GOLDM", net=-40.0, hold=30, exit_time=now)
        _trade(s, key="SILVERM", net=20.0, hold=10, exit_time=now)
        s.commit()
    d = c.get("/api/instrument/GOLDM").json()
    assert d["key"] == "GOLDM"
    assert d["stats"]["trades"] == 2 and d["stats"]["net"] == 60.0
    assert d["stats"]["avg_holding_minutes"] == 45.0
    assert len(d["trades"]) == 2
    assert all(t["instrument_key"] == "GOLDM" for t in d["trades"])


def test_instrument_detail_unknown_key_does_not_500():
    c, r = _client()
    d = c.get("/api/instrument/NOPE_NOT_REAL").json()
    assert d["key"] == "NOPE_NOT_REAL"
    assert d["stats"]["trades"] == 0
    assert d["trades"] == []
