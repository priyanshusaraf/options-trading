"""Runner-side wiring of the daily ledger re-anchor (the decision itself is unit-tested
pure in `test_daily_reanchor.py`).

History: E0.2 originally re-anchored ONCE, ever, and only on a ledger that had never
traded. On the production book — trading since 2026-07-13 — that path was unreachable, so
the cockpit reported the synthetic ₹50k seed for three weeks. The rule is now "once a day,
flat book, before the day's first trade, only if actually adrift", and the gate is LIVE
EXECUTION (broker MODE), not merely a Kite data feed: a paper ledger fed by real quotes is
still a paper ledger and must keep its synthetic base.
"""
import datetime as dt

import pytest

from app.db.models import CapitalState, Position, Trade
from app.db.session import SessionLocal, init_db
from app.engine.broker import PaperBroker
from app.engine.runner import EngineRunner
from app.providers.kite import KiteProvider as _KiteForCaps


@pytest.fixture(autouse=True)
def restore_the_broker_class():
    """`_runner` promotes the broker CLASS, so put it back — a leaked `MODE` would make
    every later test in the session write the live book."""
    yield
    PaperBroker.MODE = "paper"


def _runner(live=True):
    init_db(reset=True)
    # Promoted before construction, on the class, which is where the real LiveBroker sets
    # it. Since L1.3B, construction attributes this broker's ledger to its book — so a
    # post-hoc instance flip would leave the broker live and its `capital_state` row
    # paper, which is not a state any real broker can be in.
    PaperBroker.MODE = "live" if live else "paper"
    return EngineRunner(owner_id="owner", broker_account_id="account.default")


class _KiteFunds:
    name = "kite"
    CAPABILITIES = _KiteForCaps.CAPABILITIES  # a double impersonating Kite must declare what Kite declares

    def __init__(self, net=73_250.0, available=70_000.0):
        self.net = net
        self.available = available
        self.calls = 0

    def account_funds(self):
        self.calls += 1
        return {"available": self.available, "net": self.net}

    def now(self):
        return dt.datetime.now()


def _closed_trade(exit_time):
    return Trade(
        instrument_key="NIFTY", direction="LONG", option_type="CE",
        tradingsymbol="NIFTY26JAN20000CE", exchange="NFO", segment="options",
        strike=20000.0, expiry=dt.date(2026, 1, 29), qty=50,
        entry_premium=100.0, entry_cost=5000.0, entry_spot=20000.0,
        entry_time=exit_time - dt.timedelta(hours=1),
        exit_premium=110.0, exit_charges=5.0, exit_spot=20050.0,
        exit_time=exit_time, exit_reason="TARGET",
        gross_pnl=500.0, charges_total=10.0, net_pnl=490.0,
        return_pct=9.8, holding_minutes=60.0, win=True,
        mode="live",   # the LIVE book's trade — see the note on the open position below
    )


def test_live_ledger_reanchors_to_real_equity():
    r = _runner()
    r.provider = _KiteFunds(net=73_250.0)
    r._next_funds_epoch = 0.0

    # Touch the broker's long-lived session BEFORE the re-anchor and HOLD A STRONG
    # REFERENCE to the CapitalState it returns. SQLAlchemy's identity map holds instances
    # weakly, so a write through a *different* session can look deceptively correct — the
    # moment the last strong ref drops, the next .get() silently re-fetches fresh rows and
    # masks the bug. Holding the ref proves the write reached the instance every other
    # broker call reuses.
    pre = r.broker.snapshot(dt.datetime(2026, 1, 2, 9, 0))
    assert pre.equity == 50_000.0
    cap_ref = r.broker.capital()
    assert cap_ref.initial_capital == 50_000.0

    r._maybe_refresh_funds()

    with SessionLocal() as s:            # the DB row itself was written
        cap = s.get(CapitalState, ("account.default", "live"))
        assert cap.initial_capital == 73_250.0
        assert cap.cash == 73_250.0
        assert cap.realized_pnl == 0.0
        assert cap.account_baseline == 73_250.0
        assert cap.anchored_at is not None      # the once-a-day stamp
    assert r._reanchored is True

    # Through the broker's OWN session — the regression guard described above.
    assert cap_ref.initial_capital == 73_250.0
    assert cap_ref.cash == 73_250.0
    assert r.broker.capital() is cap_ref

    # The next equity snapshot must read the real base, not the synthetic seed.
    snap = r.broker.snapshot(dt.datetime(2026, 1, 2, 10, 0))
    assert snap.equity == 73_250.0


def test_reanchors_a_ledger_that_has_traded_on_earlier_days():
    """THE production case the old guards made impossible: history exists, book is flat,
    nothing traded today, ledger ₹23k adrift."""
    r = _runner()
    with SessionLocal() as s:
        s.add(_closed_trade(dt.datetime.now() - dt.timedelta(days=6)))
        s.commit()

    r.provider = _KiteFunds(net=73_250.0)
    r._next_funds_epoch = 0.0
    r._maybe_refresh_funds()

    with SessionLocal() as s:
        assert s.get(CapitalState, ("account.default", "live")).initial_capital == 73_250.0
    assert r._reanchored is True


def test_does_not_reanchor_once_today_has_traded():
    """Moving the anchor mid-session would reset today's drawdown frame underneath the
    daily-loss halt and the profit-lock."""
    r = _runner()
    with SessionLocal() as s:
        s.add(_closed_trade(dt.datetime.now()))
        s.commit()

    r.provider = _KiteFunds(net=73_250.0)
    r._next_funds_epoch = 0.0
    r._maybe_refresh_funds()

    with SessionLocal() as s:
        assert s.get(CapitalState, ("account.default", "live")).initial_capital == 50_000.0
    assert r._reanchored is False
    assert "traded today" in r._reanchor_reason


def test_does_not_reanchor_when_position_open():
    r = _runner()
    with SessionLocal() as s:
        s.add(Position(
            instrument_key="NIFTY", direction="LONG", option_type="CE",
            tradingsymbol="NIFTY26JAN20000CE", exchange="NFO", segment="options",
            strike=20000.0, expiry=dt.date(2026, 1, 29), lot_size=50, qty=50,
            entry_premium=100.0, entry_charges=5.0, entry_cost=5005.0,
            entry_spot=20000.0, entry_time=dt.datetime(2026, 1, 1),
            stop_price=65.0, target_price=160.0,
            mode="live",   # the LIVE book's position — `mode` defaults to paper, and
                           # since L1.3B the live broker only sees its own book
        ))
        s.commit()

    r.provider = _KiteFunds(net=73_250.0)
    r._next_funds_epoch = 0.0
    r._maybe_refresh_funds()

    with SessionLocal() as s:
        assert s.get(CapitalState, ("account.default", "live")).initial_capital == 50_000.0
    assert r._reanchored is False
    assert "flat" in r._reanchor_reason


def test_paper_broker_on_a_kite_feed_never_reanchors():
    """A paper ledger fed by real quotes is still a paper ledger — anchoring it to the
    owner's real account would silently turn paper trading into real-money accounting."""
    r = _runner(live=False)
    r.provider = _KiteFunds(net=73_250.0)
    r._next_funds_epoch = 0.0
    r._maybe_refresh_funds()

    with SessionLocal() as s:
        assert s.get(CapitalState, ("account.default", "live")).initial_capital == 50_000.0
    assert r._reanchored is False


def test_mock_provider_never_reanchors():
    r = _runner()
    r._next_funds_epoch = 0.0
    r._maybe_refresh_funds()   # provider.name != "kite" -> early return, no-op

    with SessionLocal() as s:
        assert s.get(CapitalState, ("account.default", "live")).initial_capital == 50_000.0
    assert r._reanchored is False


def test_second_refresh_the_same_day_is_a_noop():
    r = _runner()
    r.provider = _KiteFunds(net=73_250.0)
    r._next_funds_epoch = 0.0
    r._maybe_refresh_funds()
    assert r._reanchored is True

    # Broker equity moves again later the same day (the owner's own discretionary
    # positions marking): the anchor must NOT chase it — once a day, then leave it alone.
    r.provider.net = 71_000.0
    r._next_funds_epoch = 0.0
    r._maybe_refresh_funds()

    with SessionLocal() as s:
        cap = s.get(CapitalState, ("account.default", "live"))
        assert cap.initial_capital == 73_250.0
        assert cap.cash == 73_250.0
    assert "already re-anchored today" in r._reanchor_reason


def test_drift_within_tolerance_leaves_the_ledger_alone():
    r = _runner()
    r.provider = _KiteFunds(net=50_100.0)     # ₹100 off the ₹50k seed, tolerance ₹250
    r._next_funds_epoch = 0.0
    r._maybe_refresh_funds()

    with SessionLocal() as s:
        assert s.get(CapitalState, ("account.default", "live")).initial_capital == 50_000.0
    assert r._reanchored is False
    assert "tolerance" in r._reanchor_reason


def test_capital_dict_exposes_the_drift_so_a_lying_ledger_is_visible():
    r = _runner()
    r.provider = _KiteFunds(net=22_757.0)
    r._account_funds = {"available": 20_000.0, "net": 22_757.0}
    d = r.capital_dict()
    assert d["equity"] == 50_000.0
    assert d["account_net"] == 22_757.0
    assert d["ledger_drift"] == 27_243.0     # what production hid for three weeks
