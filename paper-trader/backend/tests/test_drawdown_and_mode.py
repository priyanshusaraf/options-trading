"""
Two safety/clarity features:

1. The realized+unrealized daily-drawdown halt — a deep OPEN drawdown must halt
   new entries even before any loss is booked, and must un-trip if it recovers.
2. Paper-vs-real trade tagging — every Position and Trade is stamped with the
   broker `mode` ("paper"/"live") so the two can never be confused in the log.
"""
from __future__ import annotations

from app.engine.risk_controls import daily_loss_halt


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
    broker = PaperBroker(prov)
    assert broker.MODE == "paper"
    inst = get_instrument("NIFTY")
    now = dt.datetime(2026, 6, 21, 10, 0, 0)
    q = OptionQuote(instrument_key="NIFTY", tradingsymbol="NIFTY26JUN24000CE",
                    exchange="NFO", strike=24000.0, expiry=dt.date(2026, 6, 25),
                    option_type="CE", lot_size=75, ltp=100.0, bid=99.5, ask=100.5,
                    volume=5000, oi=10000, delta=0.5, iv=0.15)
    pos = broker.open_position(inst, "LONG", q, "TEST", now, 24000.0)
    assert pos.mode == "paper"
    tr = broker.close_position(pos, 120.0, "TARGET", now, 24050.0)
    assert tr.mode == "paper"
    assert tr.to_dict()["mode"] == "paper"
    broker.close()


def test_live_broker_mode_is_live():
    # class-level contract: a LiveBroker stamps every fill as a real trade.
    from app.engine.live_broker import LiveBroker
    assert LiveBroker.MODE == "live"
