"""H1: a multi-day overnight hold must be re-evaluated every session and have
each night's gap booked once.

The old code made `held_overnight` a sticky boolean that gated the daily
square-off: once a position carried one night, the protective re-checks (expiry
cliff, max-holding cap, size cap) never ran again, and `book_overnight_gap`
zeroed the close snapshot in the SAME pass it was taken — so no gap was ever
attributed. Both are driven through `handle_overnight` (the live orchestration).
"""
import datetime as dt

import pytest

from app.core.instruments import get_instrument
from app.db.session import init_db
from app.engine.runner import EngineRunner


def _live_runner(monkeypatch, minutes_to_close: int = 5):
    """An EngineRunner whose overnight handler runs the live (non-mock) path with
    a controllable minutes-to-close so we can simulate session closes."""
    init_db(reset=True)
    r = EngineRunner()
    monkeypatch.setattr(r.provider, "name", "live", raising=False)
    from app.core import market_hours
    monkeypatch.setattr(market_hours, "minutes_to_close",
                        lambda seg, now: minutes_to_close)
    return r


def _open_small_holdable(r):
    """Open a NIFTY position and shape it so it is auto-hold eligible (small,
    far-dated)."""
    inst = get_instrument("NIFTY")
    chain = r.provider.get_option_chain(inst)
    q = chain.quotes[0]
    day0 = dt.datetime(2026, 6, 1, 10, 0)
    pos = r.broker.open_position(inst, "LONG", q, "t", day0, chain.spot)
    pos.entry_cost = 2000.0                       # ~4% of capital -> auto-hold
    pos.expiry = dt.date(2026, 7, 1)              # far from any expiry cliff
    r.broker.commit()
    return pos, q.ltp, day0


def test_close_snapshot_survives_until_next_open(monkeypatch):
    r = _live_runner(monkeypatch)
    pos, entry_prem, day0 = _open_small_holdable(r)
    # First session close: hold overnight and snapshot the close mark.
    r.handle_overnight(dt.datetime(2026, 6, 2, 15, 30))
    assert pos.held_overnight is True
    # The snapshot must NOT be zeroed in the same pass — it is needed at next open
    # to compute the gap. (Old code booked a 0 gap and reset it to 0 immediately.)
    assert pos.session_close_premium == pytest.approx(entry_prem)


def test_holding_cap_re_fires_on_later_session(monkeypatch):
    r = _live_runner(monkeypatch)
    pos, _, day0 = _open_small_holdable(r)
    # Night 1: held (holding_days = 1 < max 5).
    r.handle_overnight(dt.datetime(2026, 6, 2, 15, 30))
    assert r.broker.position_for("NIFTY") is not None
    # A later session where holding_days (6) >= max_holding_days (5): the daily
    # re-check must re-fire and square the position off. The sticky flag froze it.
    r.handle_overnight(dt.datetime(2026, 6, 7, 15, 30))
    assert r.broker.position_for("NIFTY") is None
