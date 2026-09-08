"""
Two safety/clarity features:

1. The realized+unrealized daily-drawdown halt — a deep OPEN drawdown must halt
   new entries even before any loss is booked, and must un-trip if it recovers.
2. Paper-vs-real trade tagging — every Position and Trade is stamped with the
   broker `mode` ("paper"/"live") so the two can never be confused in the log.
"""
from __future__ import annotations

import pytest

from app.engine.risk_controls import daily_loss_halt
from tests.admitted_entry import persist_admitted_entry


def test_daily_loss_halt_both_off():
    # both caps disabled -> never halts no matter how deep the loss
    assert daily_loss_halt(-999_999, -999_999, 0, 0) == (False, "")


def test_realized_breaker_trips_on_booked_loss_only():
    h, why = daily_loss_halt(-5000, 0.0, 5000, 0)
    assert h and why == "realized"
    assert daily_loss_halt(-4999, 0.0, 5000, 0) == (False, "")
    # a big OPEN loss does NOT trip the realized-only breaker
    assert daily_loss_halt(-100, -50_000, 5000, 0) == (False, "")


def test_open_drawdown_breaker_uses_realized_plus_unrealized():
    # nothing booked yet, but open MTM is deep red -> halt
    h, why = daily_loss_halt(0.0, -4000, 0, 4000)
    assert h and why == "open_drawdown"
    # realized + unrealized combine
    h, why = daily_loss_halt(-1000, -3500, 0, 4000)   # combined -4500 <= -4000
    assert h and why == "open_drawdown"
    # recovers above the cap -> entries resume (breaker un-trips)
    assert daily_loss_halt(2000, -3000, 0, 4000) == (False, "")  # combined -1000


def test_realized_reason_wins_when_both_trip():
    h, why = daily_loss_halt(-6000, -1000, 5000, 4000)
    assert h and why == "realized"


def test_paper_broker_stamps_mode_on_position_and_trade():
    import datetime as dt
    from app.db.session import init_db
    from app.engine.broker import PaperBroker
    from app.core.instruments import get_instrument
    from app.providers.mock import MockProvider
    from app.providers.base import OptionQuote

    init_db(reset=True)
    prov = MockProvider()
    broker = PaperBroker(prov, owner_id="owner", broker_account_id="account.default")
    assert broker.MODE == "paper"
    inst = get_instrument("NIFTY")
    now = dt.datetime(2026, 6, 21, 10, 0, 0)
    q = OptionQuote(instrument_key="NIFTY", tradingsymbol="NIFTY26JUN24000CE",
                    exchange="NFO", strike=24000.0, expiry=dt.date(2026, 6, 25),
                    option_type="CE", lot_size=75, ltp=100.0, bid=99.5, ask=100.5,
                    volume=5000, oi=10000, delta=0.5, iv=0.15)
    admission = persist_admitted_entry(broker.s)
    pos = broker.open_position(inst, "LONG", q, "TEST", now, 24000.0, **admission)
    assert pos.mode == "paper"
    tr = broker.close_position(pos, 120.0, "TARGET", now, 24050.0)
    assert tr.mode == "paper"
    assert tr.to_dict()["mode"] == "paper"
    broker.close()


def test_live_broker_mode_is_live():
    # class-level contract: a LiveBroker stamps every fill as a real trade.
    from app.engine.live_broker import LiveBroker
    assert LiveBroker.MODE == "live"


def test_fixed_profit_target_uses_net_boundary_and_never_flattens():
    import datetime as dt
    from types import SimpleNamespace
    from app.engine.runner import EngineRunner
    runner = EngineRunner.__new__(EngineRunner)
    runner.params = {"max_daily_profit": 1000, "notify_enabled": False}
    runner._pl_halted_date = None
    runner._halt_notified_date = None
    runner.notifier = SimpleNamespace(daily_halt=lambda *args: pytest.fail("not a loss"))
    runner._square_off_all = lambda *args: pytest.fail("fixed target must not flatten")
    now = dt.datetime(2026, 9, 5, 12)
    runner._today_net_realized = lambda day: 999.999
    assert runner.halt_status(now)["halted"] is False
    runner._today_net_realized = lambda day: 1000
    assert runner._entries_halted(now) is True
    assert runner.halt_status(now)["reason"] == "realized_profit"
    assert runner._entries_halted(now) is True
    runner.params["max_daily_profit"] = 0
    assert runner._entries_halted(now) is False


def test_account_guard_aggregates_deployments_and_isolates_owner_account_book():
    import datetime as dt
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from app.db.models import Trade, Position
    from app.engine.runner import EngineRunner
    from app.engine.broker import PaperBroker
    from tests.test_book_isolation import _closed_row, _open_row
    engine = create_engine("sqlite://")
    Trade.__table__.create(engine)
    Position.__table__.create(engine)
    day = dt.datetime(2026, 1, 1, 11)
    # Isolated query fixture, not a migration/FK or broker execution fixture.
    with Session(engine) as session:
        for index, owner, account, book, net in [
            (1, "owner", "account.default", "paper", 600),
            (2, "owner", "account.default", "paper", 500),
            (3, "other", "account.default", "paper", -9000),
            (4, "owner", "other-account", "paper", -9000),
            (5, "owner", "account.default", "live", -9000),
        ]:
            _closed_row(session, mode=book, net=net, key=str(index), when=day)
            trade = session.scalar(select(Trade).where(Trade.instrument_key == str(index)))
            trade.owner_id, trade.broker_account_id, trade.deployment_id = owner, account, index
            trade.gross_pnl, trade.charges_total = net + 100, 100
            position = _open_row(session, mode=book, key=str(index))
            position.owner_id, position.broker_account_id, position.deployment_id = owner, account, index
            position.last_premium = position.entry_premium + net
            session.commit()
        runner = EngineRunner.__new__(EngineRunner)
        runner.owner_id, runner.broker_account_id, runner.book = "owner", "account.default", "paper"
        runner._session = lambda: Session(engine)
        runner.broker = PaperBroker.__new__(PaperBroker)
        runner.broker.s = session
        runner.broker.owner_id, runner.broker.broker_account_id, runner.broker.book = "owner", "account.default", "paper"
        assert runner._today_net_realized(day.date()) == 1100
        assert runner._open_unrealized() == 1100
    engine.dispose()


@pytest.mark.parametrize("realized,unrealized,round_trips,locked,expected", [
    (-5000, 0, 10, True, "realized"),
    (1000, -4000, 10, True, "open_drawdown"),
    (1000, 0, 10, True, "round_trips"),
    (1000, 0, 0, True, "realized_profit"),
    (999.999, 0, 0, True, "profit_lock"),
    (999.999, 10000, 0, False, ""),
])
def test_account_guard_reason_precedence(realized, unrealized, round_trips, locked, expected):
    from app.engine.risk_controls import account_halt_reason
    limits = dict(max_daily_loss=5000, max_open_drawdown=2500,
                  max_daily_profit=1000, max_round_trips_per_day=10)
    assert account_halt_reason(realized, unrealized, round_trips, locked, limits) == expected


@pytest.mark.parametrize("unrealized,enabled,expected", [(0, True, (-5000, 5000)),
                                                         (-3000, True, (-3000, 2500)),
                                                         (-3000, False, None)])
def test_entry_guard_notifies_once_and_preserves_open_positions(unrealized, enabled, expected):
    import datetime as dt
    from types import SimpleNamespace
    from app.engine.runner import EngineRunner
    runner = EngineRunner.__new__(EngineRunner)
    runner.params = dict(max_daily_loss=5000, max_open_drawdown=2500, notify_enabled=enabled)
    runner._pl_halted_date = None
    runner._halt_notified_date = None
    runner._today_net_realized = lambda day: -5000 if unrealized == 0 else 0
    runner._open_unrealized = lambda: unrealized
    received = []
    runner.notifier = SimpleNamespace(daily_halt=lambda *args: received.append(args))
    runner._square_off_all = lambda *args: pytest.fail("entry halt must not flatten")
    now = dt.datetime(2026, 9, 5, 12)
    assert runner._entries_halted(now) is True
    assert runner._entries_halted(now) is True
    assert received == ([] if expected is None else [expected])


@pytest.mark.parametrize("segment,direction,expected", [
    ("index_futures", "SHORT", 20), ("index_futures", "LONG", -20),
    ("equity_intraday", "SHORT", 20), ("options", "SHORT", -20),
])
def test_open_mtm_respects_short_futures_but_keeps_long_put_premium(segment, direction, expected):
    from types import SimpleNamespace
    from app.engine.runner import EngineRunner
    runner = EngineRunner.__new__(EngineRunner)
    position = SimpleNamespace(segment=segment, direction=direction, entry_premium=100,
                               last_premium=90, qty=2)
    runner.broker = SimpleNamespace(open_positions=lambda: [position])
    assert runner._open_unrealized() == expected


def test_profit_notice_does_not_suppress_later_same_day_loss_notice(caplog):
    import datetime as dt
    from types import SimpleNamespace
    from app.engine.runner import EngineRunner
    runner = EngineRunner.__new__(EngineRunner)
    runner.params = dict(max_daily_profit=1000, max_daily_loss=5000, notify_enabled=True)
    runner._pl_halted_date = None
    runner._halt_notified_date = None
    notifications = []
    runner.notifier = SimpleNamespace(daily_halt=lambda *args: notifications.append(args))
    now = dt.datetime(2026, 9, 5, 12)
    runner._today_net_realized = lambda day: 1000
    assert runner._entries_halted(now) is True
    assert runner._entries_halted(now) is True
    assert runner._halt_notified_date is None
    assert sum(record.message.startswith("DAILY PROFIT TARGET") for record in caplog.records) == 1
    runner._today_net_realized = lambda day: 0
    assert runner._entries_halted(now) is False
    runner._today_net_realized = lambda day: -5000
    assert runner._entries_halted(now) is True
    assert runner._entries_halted(now) is True
    assert notifications == [(-5000, 5000)]
    assert runner._entries_halted(now + dt.timedelta(days=1)) is True
    assert notifications == [(-5000, 5000), (-5000, 5000)]
