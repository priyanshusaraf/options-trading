"""Period (`since`) filtering + richer per-instrument stat block."""
import datetime as dt

from app.db.models import Trade
from app.db.session import SessionLocal, init_db
from app.engine import analytics


def _trade(s, *, key="GOLDM", net, hold=60.0, exit_time):
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


def test_since_filters_and_stat_block():
    init_db(reset=True)
    now = dt.datetime(2026, 6, 26, 14, 0)
    with SessionLocal() as s:
        _trade(s, net=100.0, hold=60.0, exit_time=now)                       # today
        _trade(s, net=-40.0, hold=30.0, exit_time=now)                       # today
        _trade(s, net=50.0, hold=20.0, exit_time=now - dt.timedelta(days=10))  # old
        s.commit()
        all_summary = analytics.summary(s)
        today = analytics.summary(s, since=now.replace(hour=0, minute=0, second=0, microsecond=0))
    assert all_summary["trades"] == 3
    assert today["trades"] == 2 and today["net_pnl"] == 60.0
    block = today["per_instrument"]["GOLDM"]
    assert block["trades"] == 2
    assert block["net"] == 60.0
    assert block["avg_win"] == 100.0
    assert block["avg_loss"] == -40.0
    assert block["avg_holding_minutes"] == 45.0
    assert block["best"] == 100.0 and block["worst"] == -40.0


def test_instrument_stats_and_trades_helpers():
    init_db(reset=True)
    now = dt.datetime(2026, 6, 26, 14, 0)
    with SessionLocal() as s:
        _trade(s, key="GOLDM", net=100.0, exit_time=now)
        _trade(s, key="SILVERM", net=20.0, exit_time=now)
        s.commit()
        stats = analytics.instrument_stats(s, "GOLDM")
        trades = analytics.instrument_trades(s, "GOLDM")
    assert stats["trades"] == 1 and stats["net"] == 100.0
    assert len(trades) == 1 and trades[0]["instrument_key"] == "GOLDM"
