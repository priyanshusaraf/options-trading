"""Broker freshness stamps + validated manual paper open."""
from app.db.session import init_db, SessionLocal
from app.providers.mock import MockProvider
from app.engine.broker import PaperBroker
from app.core.instruments import get_instrument
from app.core.config import get_settings


def _broker():
    init_db(reset=True)
    return PaperBroker(MockProvider())


def test_mark_sets_freshness_and_high_water():
    b = _broker()
    inst = get_instrument("NIFTY")
    chain = b.provider.get_option_chain(inst)
    q = chain.quotes[0]
    pos = b.open_position(inst, "LONG", q, "test", b.provider.now(), chain.spot)
    assert pos.last_mark_time is not None
    assert pos.high_water_premium == q.ltp
    b.mark(pos, premium=q.ltp * 1.5, spot=chain.spot, now=b.provider.now())
    assert pos.high_water_premium == q.ltp * 1.5
    b.mark(pos, premium=q.ltp * 1.1, spot=chain.spot, now=b.provider.now())
    assert pos.high_water_premium == q.ltp * 1.5  # never decreases


def test_mark_with_zero_premium_advances_freshness():
    """C4: a real 0.0 mark (option decayed to zero — a buyer's max loss) must NOT
    be dropped. Dropping it leaves last_mark_time stale, the position is judged
    stale, and the protective stop is suppressed at the exact worst moment."""
    import datetime as dt
    b = _broker()
    inst = get_instrument("NIFTY")
    chain = b.provider.get_option_chain(inst)
    q = chain.quotes[0]
    t0 = b.provider.now()
    pos = b.open_position(inst, "LONG", q, "test", t0, chain.spot)
    later = t0 + dt.timedelta(seconds=5)
    b.mark(pos, premium=0.0, spot=chain.spot, now=later)
    assert pos.last_premium == 0.0
    assert pos.last_mark_time == later


def test_manual_open_respects_capital_and_one_position():
    b = _broker()
    inst = get_instrument("NIFTY")
    chain = b.provider.get_option_chain(inst)
    pos, reason = b.manual_open(inst, "LONG", chain, get_settings(), b.provider.now())
    assert pos is not None, reason
    pos2, reason2 = b.manual_open(inst, "LONG", chain, get_settings(), b.provider.now())
    assert pos2 is None and "already" in reason2.lower()


def test_manual_open_rejects_when_no_cash():
    b = _broker()
    cap = b.capital(); cap.cash = 1.0; b.commit()
    inst = get_instrument("NIFTY")
    chain = b.provider.get_option_chain(inst)
    pos, reason = b.manual_open(inst, "LONG", chain, get_settings(), b.provider.now())
    assert pos is None and "cash" in reason.lower()
