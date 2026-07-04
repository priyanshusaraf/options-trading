"""Phase 3 REST surface: per-instrument product/purple/strategy controls (which the
watchlist drives), the registered-strategies list, and segment-aware positions +
analytics. The controls must take effect on the LIVE runner (not just the DB) so the
next tick honours them."""
import datetime as dt

from fastapi.testclient import TestClient

from app.api import routes
from app.db.models import Position, Trade
from app.db.session import SessionLocal, init_db
from app.engine.runner import EngineRunner
from app.main import app


def _client():
    prev = getattr(app.state, "runner", None)
    if prev is not None:
        try:
            prev.broker.close()   # release the prior test's long-lived broker session
        except Exception:
            pass
    init_db(reset=True)
    r = EngineRunner()
    app.state.runner = r
    return TestClient(app), r


def test_set_product_updates_runner_and_db():
    c, r = _client()
    res = c.post("/api/instruments/NIFTY/product", json={"product": "equity_intraday"}).json()
    assert res["product"] == "equity_intraday"
    assert r.products["NIFTY"] == "equity_intraday"          # live runner sees it
    # garbage coerces to options
    assert c.post("/api/instruments/NIFTY/product", json={"product": "junk"}).json()["product"] == "options"


def test_set_priority_flag_roundtrips():
    c, r = _client()
    c.post("/api/instruments/NIFTY/priority", json={"priority_flag": True})
    assert r.priority_flags.get("NIFTY") is True
    c.post("/api/instruments/NIFTY/priority", json={"priority_flag": False})
    assert "NIFTY" not in r.priority_flags


def test_set_strategy_validates_against_registry():
    c, r = _client()
    ok = c.post("/api/instruments/NIFTY/strategy", json={"strategy_key": "expanding_z_v4"}).json()
    assert ok["strategy_key"] == "expanding_z_v4"
    assert r.strategy_keys["NIFTY"] == "expanding_z_v4"
    # unknown key clears to default (None)
    cleared = c.post("/api/instruments/NIFTY/strategy", json={"strategy_key": "nope"}).json()
    assert cleared["strategy_key"] is None
    assert "NIFTY" not in r.strategy_keys


def test_signals_carry_product_priority_strategy():
    c, r = _client()
    c.post("/api/instruments/NIFTY/product", json={"product": "equity_intraday"})
    c.post("/api/instruments/NIFTY/priority", json={"priority_flag": True})
    rows = {x["key"]: x for x in c.get("/api/signals").json()["instruments"]}
    assert rows["NIFTY"]["product"] == "equity_intraday"
    assert rows["NIFTY"]["priority_flag"] is True
    assert "strategy_key" in rows["NIFTY"]


def test_strategies_endpoint_lists_registry():
    c, _ = _client()
    keys = {s["key"] for s in c.get("/api/strategies").json()["strategies"]}
    assert {"trend_impulse_v3", "expanding_z_v4"} <= keys


def _seed_positions(s):
    common = dict(direction="LONG", tradingsymbol="X", strike=0.0,
                  expiry=dt.date(2026, 7, 31), lot_size=1, qty=10,
                  entry_premium=100.0, entry_charges=1.0, entry_cost=1001.0,
                  entry_spot=100.0, entry_time=dt.datetime(2026, 6, 1, 10, 0),
                  stop_price=99.0, target_price=102.0, last_premium=100.0)
    s.add(Position(instrument_key="NIFTY", option_type="CE", exchange="NFO",
                   segment="options", **common))
    s.add(Position(instrument_key="SBIN", option_type="EQ", exchange="NSE_INTRADAY",
                   segment="equity_intraday", **common))


def test_positions_segment_filter():
    c, r = _client()
    with SessionLocal() as s:
        _seed_positions(s); s.commit()
    allp = c.get("/api/positions").json()["positions"]
    assert {p["segment"] for p in allp} == {"options", "equity_intraday"}
    eq = c.get("/api/positions?segment=equity_intraday").json()["positions"]
    assert eq and all(p["segment"] == "equity_intraday" for p in eq)


def _seed_trade(s, seg, net):
    s.add(Trade(instrument_key="X", direction="LONG", option_type="EQ" if seg == "equity_intraday" else "CE",
                tradingsymbol="X", exchange="NSE_INTRADAY" if seg == "equity_intraday" else "NFO",
                segment=seg, strike=0.0, expiry=dt.date(2026, 7, 31), qty=10,
                entry_premium=100.0, entry_cost=1000.0, entry_spot=100.0,
                entry_time=dt.datetime(2026, 6, 1, 10, 0),
                exit_premium=100.0 + net / 10, exit_charges=5.0, exit_spot=100.0,
                exit_time=dt.datetime(2026, 6, 1, 11, 0), exit_reason="TARGET",
                gross_pnl=net + 5, charges_total=5.0, net_pnl=net, return_pct=0.0,
                holding_minutes=60.0, win=net > 0))


def test_intraday_settings_overridable_and_reach_engine():
    c, _ = _client()
    from app.core import runtime_config
    # exposed in the settings schema (so the SettingsView renders the group)
    keys = {r["key"] for r in c.get("/api/settings").json()["params"]}
    assert {"intraday_enabled", "intraday_max_positions", "intraday_leverage",
            "intraday_min_margin", "intraday_max_margin"} <= keys
    # override flows into effective() — the dict the engine's self.params is built from
    c.post("/api/settings", json={"key": "intraday_enabled", "value": "true"})
    c.post("/api/settings", json={"key": "intraday_max_positions", "value": "2"})
    eff = runtime_config.effective()
    assert eff["intraday_enabled"] is True
    assert eff["intraday_max_positions"] == 2


def test_intraday_settings_bounds_reject_bad_values():
    c, _ = _client()
    bad = c.post("/api/settings", json={"key": "intraday_leverage", "value": "100"}).json()
    assert "error" in bad   # leverage capped at 20x


def test_analytics_by_segment_net_of_costs():
    c, _ = _client()
    with SessionLocal() as s:
        _seed_trade(s, "options", 200.0)
        _seed_trade(s, "equity_intraday", -50.0)
        _seed_trade(s, "equity_intraday", 80.0)
        s.commit()
    a = c.get("/api/analytics").json()
    assert a["by_segment"]["options"]["trades"] == 1
    assert a["by_segment"]["equity_intraday"]["trades"] == 2
    assert a["by_segment"]["equity_intraday"]["net_pnl"] == 30.0   # -50 + 80
    assert a["by_segment"]["equity_intraday"]["charges"] == 10.0   # both legs counted
    # segment filter narrows the headline split too
    eq = c.get("/api/analytics?segment=equity_intraday").json()
    assert eq["intraday"]["trades"] == 2   # both equity trades (not held_overnight)
