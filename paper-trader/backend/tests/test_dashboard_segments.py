"""Phase 4 analytics: the dashboard slices by segment and by strategy. Per-segment
and per-strategy realized curves let the UI show options vs outrights, and how each
strategy performed inside each segment."""
import datetime as dt

from fastapi.testclient import TestClient

from app.db.models import Trade
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
    app.state.runner = EngineRunner()
    return TestClient(app)


def _trade(s, *, seg, strat, net, hours):
    s.add(Trade(instrument_key="X", direction="LONG",
                option_type="EQ" if seg == "equity_intraday" else "CE",
                tradingsymbol="X", exchange="NSE_INTRADAY" if seg == "equity_intraday" else "NFO",
                segment=seg, strategy_key=strat, strike=0.0, expiry=dt.date(2026, 7, 31), qty=10,
                entry_premium=100.0, entry_cost=1000.0, entry_spot=100.0,
                entry_time=dt.datetime(2026, 6, 1, 9, 0),
                exit_premium=100.0 + net / 10, exit_charges=2.0, exit_spot=100.0,
                exit_time=dt.datetime(2026, 6, 1, 9 + hours, 0), exit_reason="TARGET",
                gross_pnl=net + 2, charges_total=2.0, net_pnl=net, return_pct=0.0,
                holding_minutes=60.0, win=net > 0))


def _seed(c):
    with SessionLocal() as s:
        _trade(s, seg="options", strat="trend_impulse_v3", net=100.0, hours=1)
        _trade(s, seg="options", strat="expanding_z_v4", net=-30.0, hours=2)
        _trade(s, seg="equity_intraday", strat="expanding_z_v4", net=200.0, hours=3)
        _trade(s, seg="equity_intraday", strat="trend_impulse_v3", net=50.0, hours=4)
        s.commit()


def test_segment_curves_split_options_and_outrights():
    c = _client(); _seed(c)
    d = c.get("/api/dashboard").json()
    sc = d["segment_curves"]
    assert sc["options"][-1]["value"] == 70.0           # 100 - 30
    assert sc["equity_intraday"][-1]["value"] == 250.0  # 200 + 50


def test_strategy_curves_within_a_segment():
    c = _client(); _seed(c)
    d = c.get("/api/dashboard?segment=equity_intraday").json()
    sk = d["strategy_curves"]
    assert sk["expanding_z_v4"][-1]["value"] == 200.0
    assert sk["trend_impulse_v3"][-1]["value"] == 50.0


def test_summary_filtered_by_segment():
    c = _client(); _seed(c)
    opt = c.get("/api/dashboard?segment=options").json()["summary"]
    assert opt["trades"] == 2
    assert opt["net_pnl"] == 70.0
    eq = c.get("/api/dashboard?segment=equity_intraday").json()["summary"]
    assert eq["trades"] == 2
    assert eq["net_pnl"] == 250.0


def test_summary_filtered_by_strategy_across_segments():
    c = _client(); _seed(c)
    v4 = c.get("/api/dashboard?strategy=expanding_z_v4").json()["summary"]
    # v4 appears in both segments: options -30 + equity 200 = 170
    assert v4["trades"] == 2
    assert v4["net_pnl"] == 170.0


def test_unfiltered_dashboard_keeps_global_equity_curve():
    c = _client(); _seed(c)
    d = c.get("/api/dashboard").json()
    # unfiltered equity_curve is the MTM EquitySnapshot series (may be empty here);
    # the realized slice only appears when filtered. Shape stays back-compatible.
    assert "equity_curve" in d and "instrument_curves" in d and "recent_trades" in d
