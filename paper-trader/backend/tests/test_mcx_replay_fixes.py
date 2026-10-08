"""Live-engine bugs found by the MCX paper replay (scripts/replay_mcx.py):

1. MCX closes at 23:55 IST while New York is on standard time (Nov→Mar), not
   23:30 — the engine stopped scanning at 23:30, so winter signals/exits on the
   last two 15m bars (e.g. spike_fade's exit bar) were never seen.
2. The live candle frame dropped `volume`, so VWAP strategies ran on equal weights
   live while every backtest used real volume.
3. The entry signal re-read on later loops inside its own candle counted as a
   "reinforcement" of the position it had just opened (stop locked above entry).
"""
import datetime as dt

from app.core import market_hours as mh
from app.core.instruments import get_instrument
from app.core.market_hours import ist_epoch
from app.db.session import init_db
from app.engine.runner import EngineRunner, _to_df
from app.providers.base import Candle


def at(day: str, h: int, m: int) -> dt.datetime:
    return dt.datetime.fromisoformat(day).replace(hour=h, minute=m, tzinfo=mh.IST)


def test_mcx_winter_session_runs_to_2355():
    winter = "2026-01-15"                          # Thursday, NY on standard time
    assert mh.is_open("MCX", at(winter, 23, 45))
    assert mh.is_open("MCX", at(winter, 23, 55))
    assert not mh.is_open("MCX", at(winter, 23, 56))
    assert mh.minutes_to_close("MCX", at(winter, 23, 40)) == 15.0
    # the summer schedule is unchanged
    assert not mh.is_open("MCX", at("2026-06-19", 23, 45))
    assert mh.minutes_to_close("MCX", at("2026-06-19", 23, 20)) == 10.0
    # equity sessions never move
    assert not mh.is_open("NSE", at(winter, 15, 45))


def test_mcx_close_follows_the_us_dst_switch():
    assert mh.is_open("MCX", at("2026-03-06", 23, 45))        # Fri before the 8 Mar switch
    assert not mh.is_open("MCX", at("2026-03-09", 23, 45))    # Mon after it
    assert not mh.is_open("MCX", at("2026-10-30", 23, 45))    # still DST (ends 1 Nov)
    assert mh.is_open("MCX", at("2026-11-02", 23, 45))        # Mon after it ends


def test_mcx_session_matches_strategy_session_clock():
    """market_hours and strategy.ta.mcx_close_minute must agree on every day."""
    import pandas as pd

    from app.strategy.ta import mcx_close_minute
    days = pd.date_range("2024-01-01", "2027-12-31", freq="D")
    cm = mcx_close_minute(pd.DataFrame({"date": days}))
    for d, c in zip(days, cm):
        close = mh.session_window("MCX", d.date())[1]
        assert close.hour * 60 + close.minute == c, d


def test_live_candle_frame_carries_volume():
    t = dt.datetime(2026, 6, 1, 9, 0)
    df = _to_df([Candle(t, 1, 2, 0.5, 1.5, 1234.0), Candle(t, 1, 2, 0.5, 1.5)])
    assert list(df["volume"]) == [1234.0, 0.0]


def _held_long():
    init_db(reset=True)
    r = EngineRunner()
    r.armed = True
    nifty = get_instrument("NIFTY")
    chain = r.provider.get_option_chain(nifty)
    q = min((x for x in chain.quotes if x.option_type == "CE"),
            key=lambda x: abs(x.strike - chain.spot))
    pos = r.broker.open_position(nifty, "LONG", q, "t", r.provider.now(), chain.spot)
    r.broker.mark(pos, premium=q.ltp * 1.25, spot=chain.spot, now=r.provider.now())
    r.broker.commit()
    return r, chain, q, pos


def test_entry_candle_does_not_reinforce_its_own_position():
    r, chain, q, pos = _held_long()
    base_stop = pos.stop_price
    # the candle that produced the entry completed BEFORE the fill
    entry_bar = ist_epoch(pos.entry_time) - 30 * 60
    r.state["NIFTY"] = {"signal": "LONG_ENTRY", "z": 1.5, "slope": 1.0,
                        "close": chain.spot, "time": entry_bar}
    r.process_entries()
    p = r.broker.position_for("NIFTY")
    assert p.reinforcement_count == 0 and p.stop_price == base_stop


def test_later_candle_still_reinforces():
    r, chain, q, pos = _held_long()
    base_stop = pos.stop_price
    # a fresh crossover on a candle that completed after the fill
    r.state["NIFTY"] = {"signal": "LONG_ENTRY", "z": 1.5, "slope": 1.0,
                        "close": chain.spot, "time": ist_epoch(pos.entry_time)}
    r.process_entries()
    p = r.broker.position_for("NIFTY")
    assert p.reinforcement_count == 1 and p.stop_price > base_stop
