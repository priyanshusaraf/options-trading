"""equity_curve: SQL-side filter/limit (2026-07-23 leak fix) keeps old semantics —
ascending time order, `since` cut, and tail-`limit` (newest kept when over limit)."""
import datetime as dt

from app.db.models import EquitySnapshot
from app.db.session import SessionLocal, init_db
from app.engine import analytics
from tests.legacy_money_scope import LegacyMoneyScope

analytics = LegacyMoneyScope(analytics, "equity_curve")


def _snap(t, eq):
    return EquitySnapshot(time=t, equity=eq, cash=eq, invested=0.0,
                          realized_pnl=0.0, open_count=0)


def test_equity_curve_orders_ascending_and_honors_since():
    init_db(reset=True)
    base = dt.datetime(2026, 6, 26, 9, 0)
    with SessionLocal() as s:
        for i in range(10):
            s.add(_snap(base + dt.timedelta(minutes=i), 100.0 + i))
        s.commit()
        full = analytics.equity_curve(s)
        sliced = analytics.equity_curve(s, since=base + dt.timedelta(minutes=7))
    assert len(full) == 10
    times = [p["time"] for p in full]
    assert times == sorted(times)
    assert [p["equity"] for p in sliced] == [107.0, 108.0, 109.0]


def test_equity_curve_limit_keeps_newest():
    init_db(reset=True)
    base = dt.datetime(2026, 6, 26, 9, 0)
    with SessionLocal() as s:
        for i in range(30):
            s.add(_snap(base + dt.timedelta(minutes=i), 100.0 + i))
        s.commit()
        curve = analytics.equity_curve(s, limit=5)
    assert [p["equity"] for p in curve] == [125.0, 126.0, 127.0, 128.0, 129.0]
