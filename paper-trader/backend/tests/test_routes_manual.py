"""REST surface for the cockpit: signals list, positions, health, interval/block,
manual open/close. Uses FastAPI TestClient with a directly-attached runner (no
background loops)."""
import asyncio

from fastapi.testclient import TestClient

from app.api import routes
from app.db.session import init_db, SessionLocal
from app.engine.runner import EngineRunner
from app.main import app


def _client():
    init_db(reset=True)
    r = EngineRunner()
    # No warmup ticks: /api/signals lists all instruments regardless of state, and
    # a clean book keeps manual-open deterministic (ticking can auto-open NIFTY).
    app.state.runner = r
    return TestClient(app), r


def test_signals_list_is_lightweight():
    c, _ = _client()
    res = c.get("/api/signals").json()
    assert "instruments" in res and isinstance(res["instruments"], list)
    assert res["instruments"]
    row = res["instruments"][0]
    for k in ("key", "signal", "interval", "has_position", "has_options", "stale", "pinned"):
        assert k in row


def test_signals_carry_pinned_flag_and_pin_unpin_roundtrips():
    """MERGE-1: the unified Watchlist filters/marks rows by `pinned` (on_home). The
    portfolio add/remove routes must flip it so the 'pinned only' view and the per-row
    star reflect the curated portfolio. NIFTY is a seed instrument (on_home in SEED)."""
    c, _ = _client()
    rows = {x["key"]: x for x in c.get("/api/signals").json()["instruments"]}
    assert isinstance(rows["NIFTY"]["pinned"], bool)

    c.post("/api/portfolio/remove", json={"key": "NIFTY", "on_home": False})
    rows = {x["key"]: x for x in c.get("/api/signals").json()["instruments"]}
    # seed instrument stays in the universe but un-pinned (and trading disabled)
    assert rows["NIFTY"]["pinned"] is False
    assert rows["NIFTY"]["enabled"] is False

    c.post("/api/portfolio/add", json={"key": "NIFTY", "on_home": True})
    rows = {x["key"]: x for x in c.get("/api/signals").json()["instruments"]}
    assert rows["NIFTY"]["pinned"] is True
    assert rows["NIFTY"]["enabled"] is True


def test_signals_staleness_is_per_instrument():
    """C3/MON-1: a failing instrument must NOT flip every other row to stale, and a
    healthy instrument must NOT mask a dead one. Freshness is per-key off
    last_scan_ok, not a shared global candle-failure counter."""
    import datetime as dt
    c, r = _client()
    now = r.provider.now()
    # seed two instruments with state so the 'no state -> stale' path is bypassed
    for key in ("NIFTY", "BANKNIFTY"):
        r.state[key] = {"instrument": key, "signal": "NONE", "time": 0,
                        "close": 100.0, "z": 0.0, "trend": "flat", "position": None}
    r.last_scan_ok["NIFTY"] = now                       # fresh
    r.last_scan_ok["BANKNIFTY"] = now - dt.timedelta(hours=1)  # long stale

    rows = {x["key"]: x for x in c.get("/api/signals").json()["instruments"]}
    assert rows["NIFTY"]["stale"] is False, "fresh instrument wrongly marked stale"
    assert rows["BANKNIFTY"]["stale"] is True, "stale instrument wrongly marked live"


def test_signals_surface_feed_auth_error_flag():
    """C3/KITE-1: a Kite session expiry classified on candle health is exposed as a
    feed-wide flag for the re-auth banner (without folding it into per-row stale)."""
    c, r = _client()
    r.health.record_fail("candle", "Incorrect api_key or access_token", r.provider.now())
    res = c.get("/api/signals").json()
    assert res["feed_auth_error"] is True
    assert res["health"]["candle"]["auth_error"] is True


def test_signals_carry_market_open_flag():
    """OPS-R2-1: the read layer must distinguish 'market closed, all fine' from
    'feed broken'. Each row carries market_open and the payload carries a feed-wide
    any_market_open so the UI can render a neutral 'market closed' instead of an
    amber 'stale' alarm overnight/weekends."""
    c, _ = _client()
    res = c.get("/api/signals").json()
    assert "any_market_open" in res
    row = res["instruments"][0]
    assert "market_open" in row
    # mock provider is always tradable -> market reads open and any_market_open True
    assert row["market_open"] is True
    assert res["any_market_open"] is True


def test_signals_market_closed_is_distinct_from_broken_feed():
    """OPS-R2-1: when the market is closed, rows can read stale (last_scan_ok can't
    advance) but market_open=False tells the UI it is benign idle, NOT a broken feed.
    A broken feed during open hours keeps market_open=True so stale stays an alarm."""
    c, r = _client()
    # simulate all markets closed (overnight/weekend) at the read layer. The mock
    # provider is a cached singleton, so restore the bound method to keep isolation.
    orig = r.provider.is_tradable_now
    r.provider.is_tradable_now = lambda inst: False
    try:
        res = c.get("/api/signals").json()
        assert res["any_market_open"] is False
        assert all(row["market_open"] is False for row in res["instruments"])
        # the per-row stale flag itself is unchanged (no state seeded -> stale True);
        # the discrimination lives in market_open, so the UI can recolor it closed.
        assert all(row["stale"] is True for row in res["instruments"])
    finally:
        r.provider.is_tradable_now = orig


def test_session_redirects_to_frontend_after_login(monkeypatch):
    """After Kite OAuth captures the token at the BACKEND, the browser must be bounced
    to the FRONTEND (PT_FRONTEND_URL), not left on the bare backend origin."""
    from app.core.config import get_settings
    c, r = _client()
    monkeypatch.setattr(r.provider, "complete_session", lambda rt: None, raising=False)
    res = c.get("/api/session?request_token=abc", follow_redirects=False)
    assert res.status_code in (302, 307)
    assert res.headers["location"] == get_settings().frontend_url


def _seed_trade(s, *, exit_dt, net, mode):
    import datetime as dt
    from app.db.models import Trade
    s.add(Trade(
        instrument_key="NIFTY", direction="LONG", option_type="CE",
        tradingsymbol="NIFTY24CE", exchange="NFO", strike=24000.0,
        expiry=dt.date(2026, 7, 31), qty=75,
        entry_premium=100.0, entry_cost=7500.0, entry_spot=24000.0,
        entry_time=exit_dt - dt.timedelta(hours=2),
        exit_premium=100.0 + net / 75, exit_charges=0.0, exit_spot=24010.0,
        exit_time=exit_dt, exit_reason="STRATEGY_EXIT",
        gross_pnl=net, charges_total=0.0, net_pnl=net, return_pct=0.0,
        holding_minutes=120.0, win=net > 0, mode=mode))


def test_calendar_combines_bot_ledger_and_account_snapshots():
    """Calendar: bot side = LIVE trade ledger by exit day (paper trades excluded);
    your side = day-over-day account-net change minus the bot's that day."""
    import datetime as dt
    from app.db.models import DailyAccountSnapshot
    c, r = _client()
    today = r.provider.now().date()
    yday = today - dt.timedelta(days=1)
    with SessionLocal() as s:
        s.add(DailyAccountSnapshot(day=yday.isoformat(), account_net=100_000.0, account_available=100_000.0))
        s.add(DailyAccountSnapshot(day=today.isoformat(), account_net=112_400.0, account_available=112_400.0))
        _seed_trade(s, exit_dt=dt.datetime.combine(today, dt.time(10, 0)), net=3_100.0, mode="live")
        _seed_trade(s, exit_dt=dt.datetime.combine(today, dt.time(11, 0)), net=9_999.0, mode="paper")  # ignored
        s.commit()
    rec = {x["day"]: x for x in c.get("/api/calendar").json()["days"]}
    assert rec[today.isoformat()]["bot_pnl"] == 3_100.0          # live only, paper excluded
    assert rec[today.isoformat()]["bot_trades"] == 1
    # my P&L = account change (12,400) − bot booked (3,100) = 9,300
    assert rec[today.isoformat()]["my_pnl"] == 9_300.0
    # a day with no snapshot/trades is neutral (None), not 0
    assert rec[yday.isoformat()]["my_pnl"] is None               # no prior snapshot to diff
    assert rec[yday.isoformat()]["bot_pnl"] is None


def test_set_interval_route():
    c, r = _client()
    res = c.post("/api/instruments/NIFTY/interval", json={"interval": "60minute"}).json()
    assert res["interval"] == "60minute"
    assert r._interval_for("NIFTY") == "60minute"


def test_block_entries_route():
    c, r = _client()
    c.post("/api/instruments/NIFTY/block-entries", json={"blocked": True})
    assert "NIFTY" in r.entry_blocks


def test_manual_open_then_close_and_positions():
    c, r = _client()
    op = c.post("/api/positions/manual-open", json={"key": "NIFTY", "direction": "LONG"}).json()
    assert op.get("opened") is True, op
    pos = c.get("/api/positions").json()
    assert any(p["instrument_key"] == "NIFTY" for p in pos["positions"])
    cl = c.post("/api/positions/NIFTY/close").json()
    assert cl.get("closed") is True, cl
    assert r.broker.position_for("NIFTY") is None


def test_manual_mutation_routes_run_on_event_loop():
    """C3: manual open/close/positions must NOT run in a threadpool worker thread
    sharing the engine's long-lived SQLAlchemy Session (not thread-safe). Making
    them `async def` pins them to the event loop, serialized with the engine via
    the runner lock — so all broker-session access is single-threaded."""
    assert asyncio.iscoroutinefunction(routes.close_position)
    assert asyncio.iscoroutinefunction(routes.manual_open)
    assert asyncio.iscoroutinefunction(routes.positions)


def test_double_close_is_idempotent_on_ledger():
    """C3 consequence: a second close of an already-closed position must be a
    no-op and must NOT double-count realized P&L."""
    c, r = _client()
    c.post("/api/positions/manual-open", json={"key": "NIFTY", "direction": "LONG"})
    first = c.post("/api/positions/NIFTY/close").json()
    assert first.get("closed") is True
    realized_after = r.broker.capital().realized_pnl
    second = c.post("/api/positions/NIFTY/close").json()
    assert "error" in second  # nothing left to close
    assert r.broker.capital().realized_pnl == realized_after


def test_provider_health_route():
    c, _ = _client()
    h = c.get("/api/provider-health").json()
    assert "quote" in h and "candle" in h


def test_promote_carries_supported_interval():
    c, r = _client()
    res = c.post("/api/portfolio/add", json={"key": "NIFTY", "interval": "30minute"}).json()
    assert "error" not in res, res
    assert res.get("interval") == "30minute"
    assert r._interval_for("NIFTY") == "30minute"


def test_promote_unsupported_interval_falls_back_with_warning():
    c, _ = _client()
    res = c.post("/api/portfolio/add", json={"key": "NIFTY", "interval": "minute"}).json()
    assert res.get("interval") == "15minute"     # clamped to default
    assert res.get("interval_warning")
