"""ReplayProvider (scripts/replay_mcx.py): the live engine replayed on recorded bars
must never see the future — candles only once COMPLETED, the tape only up to the
clock, option vol only from days already closed. Offline, synthetic frames only."""
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

from app.core.instruments import Instrument
from app.providers.replay import ReplayProvider, Roll

INST = Instrument("NGTEST", "NG TEST", "MCX", "MCX", "NGTEST", "NGTEST",
                  lot_size=250, strike_step=5, priority=1, mock_spot=300, mock_vol=0.5)


def _frame(days=30, bars_per_day=8, seed=1, start=date(2026, 6, 1)):
    """Weekday sessions of `bars_per_day` 15m bars from 09:00 IST, random walk."""
    rng = np.random.default_rng(seed)
    idx, d = [], start
    while len(idx) < days * bars_per_day:
        if d.weekday() < 5:
            t0 = datetime(d.year, d.month, d.day, 9, 0)
            idx += [t0 + timedelta(minutes=15 * k) for k in range(bars_per_day)]
        d += timedelta(days=1)
    c = 300 * np.exp(np.cumsum(rng.normal(0, 0.01, len(idx))))
    o = np.r_[300.0, c[:-1]]
    hi = np.maximum(o, c) * 1.002
    lo = np.minimum(o, c) * 0.998
    return pd.DataFrame({"open": o, "high": hi, "low": lo, "close": c, "volume": 0.0},
                        index=pd.DatetimeIndex(idx, name="date"))


def _prov(df, **kw):
    exps = [(date(2026, 6, 24), date(2026, 6, 26)), (date(2026, 7, 23), date(2026, 7, 27)),
            (date(2026, 8, 24), date(2026, 8, 26))]
    return ReplayProvider({INST.key: df}, option_expiries={INST.key: exps}, **kw)


def test_candles_are_completed_only_and_end_at_the_clock():
    df = _frame(days=5)
    p = _prov(df)
    for s in df.index[3:30]:
        s = s.to_pydatetime()
        for off in (0, 1, 7, 14):
            p.set_now(s + timedelta(minutes=off))
            cs = p.get_candles(INST, "15minute", 30)
            assert cs, "history expected"
            assert all(c.ts + timedelta(minutes=15) <= p.now() for c in cs)   # completed
            assert cs[-1].ts == s - timedelta(minutes=15) or cs[-1].ts < s     # forming bar s excluded
            assert all(c.ts < s for c in cs)
        # exactly at the bar's end it becomes a completed candle
        p.set_now(s + timedelta(minutes=15))
        assert p.get_candles(INST, "15minute", 30)[-1].ts == s


def test_resampled_candles_never_include_a_forming_bar():
    df = _frame(days=3)
    p = _prov(df)
    p.set_now(datetime(2026, 6, 2, 9, 46))          # 09:30 30m bar still forming
    cs = p.get_candles(INST, "30minute", 30)
    assert cs[-1].ts == datetime(2026, 6, 2, 9, 0)
    assert all(c.ts + timedelta(minutes=30) <= p.now() for c in cs)
    p.set_now(datetime(2026, 6, 2, 10, 0))
    last = p.get_candles(INST, "30minute", 30)[-1]
    sub = df.loc["2026-06-02 09:30":"2026-06-02 09:45"]
    assert last.ts == datetime(2026, 6, 2, 9, 30)
    assert last.open == sub.open.iloc[0] and last.close == sub.close.iloc[-1]
    assert last.high == sub.high.max() and last.low == sub.low.min()


def test_days_window_and_unknown_instrument():
    df = _frame(days=10)
    p = _prov(df)
    p.set_now(datetime(2026, 6, 12, 9, 1))
    cs = p.get_candles(INST, "15minute", 3)
    assert cs[0].ts >= datetime(2026, 6, 9, 9, 1)
    other = Instrument("NIFTY", "N", "NFO", "NSE", "N", "N", 75, 50, 1, 1, 0.1)
    assert p.get_candles(other, "day", 3) == [] and p.get_ltp(other) is None


def test_ltp_walks_only_the_current_bar_path():
    df = _frame(days=2)
    p = _prov(df)
    s = df.index[5].to_pydatetime()
    row = df.loc[s]
    p.set_now(s + timedelta(minutes=1))
    assert p.get_ltp(INST) == row.open
    p.set_now(s + timedelta(minutes=14))
    assert p.get_ltp(INST) == row.close
    for m in range(15):
        p.set_now(s + timedelta(minutes=m))
        assert p.get_ltp(INST) in (row.open, row.high, row.low, row.close)
    # after the session's last bar: the last completed close, not tomorrow's open
    last = df.loc["2026-06-01"].iloc[-1]
    p.set_now(datetime(2026, 6, 1, 22, 0))
    assert p.get_ltp(INST) == last.close
    # all-zero volume is replaced by a constant weight (VWAPs stay finite)
    assert {c.volume for c in p.get_candles(INST, "15minute", 5)} == {1.0}


def test_future_bars_never_change_what_the_clock_sees():
    """Two markets identical up to T, wildly different after: every provider output
    at clocks <= T must be identical (candles, tape, option chain, option LTP)."""
    a = _frame(days=30, seed=3)
    b = a.copy()
    cut = a.index[int(len(a) * 0.8)]
    after = b.index > cut
    b.loc[after, ["open", "high", "low", "close"]] *= 1.5          # a huge future move
    pa, pb = _prov(a), _prov(b)
    probe = [t.to_pydatetime() + timedelta(minutes=m)
             for t in a.index[a.index <= cut][-40:] for m in (1, 14)]
    probe = [t for t in probe if t <= cut.to_pydatetime() + timedelta(minutes=14)]
    for t in probe:
        pa.set_now(t)
        pb.set_now(t)
        assert pa.get_candles(INST, "15minute", 60) == pb.get_candles(INST, "15minute", 60)
        assert pa.get_ltp(INST) == pb.get_ltp(INST)
        ca, cb = pa.get_option_chain(INST), pb.get_option_chain(INST)
        assert (ca is None) == (cb is None)
        if ca is not None:
            assert [q.ltp for q in ca.quotes] == [q.ltp for q in cb.quotes]
            q = ca.quotes[0]
            assert pa.option_ltp(INST, q.tradingsymbol, q.strike, q.expiry, q.option_type) == \
                pb.option_ltp(INST, q.tradingsymbol, q.strike, q.expiry, q.option_type)


def test_chain_honours_min_dte_spread_and_lot():
    df = _frame(days=30)
    p = _prov(df, spread_pct=0.02)
    p.set_now(datetime(2026, 7, 9, 10, 1))
    ch = p.get_option_chain(INST)
    assert ch is not None and ch.expiry == date(2026, 7, 23)
    assert p.get_option_chain(INST, min_dte=30).expiry == date(2026, 8, 24)
    q = next(q for q in ch.quotes if q.option_type == "CE")
    assert q.lot_size == 250 and q.oi >= 500
    assert abs(q.spread_pct - 0.02) < 0.01
    assert all(abs(x.strike - round(ch.spot / 5) * 5) <= 50 for x in ch.quotes)


def test_held_option_is_priced_off_its_own_month_across_a_roll():
    """The stitched series jumps by the contract spread at a roll; the option on the
    NEXT month must not: before the roll its underlying = front + the gap ahead."""
    df = _frame(days=40)
    roll_at = datetime(2026, 6, 26, 9, 0)
    gap = 12.0
    df.loc[df.index >= roll_at, ["open", "high", "low", "close"]] += gap
    p = _prov(df, rolls={INST.key: [Roll(at=roll_at, old_expiry=date(2026, 6, 26), gap_pts=gap)]})
    last_before = df.index[df.index < roll_at][-1].to_pydatetime()
    p.set_now(last_before + timedelta(minutes=14))
    july_before = p.underlying_for(INST.key, date(2026, 7, 23))
    june_before = p.underlying_for(INST.key, date(2026, 6, 24))
    assert july_before == p.get_ltp(INST) + gap      # next month = front + spread
    assert june_before == p.get_ltp(INST)            # front month = the tape itself
    p.set_now(roll_at + timedelta(minutes=1))
    july_after = p.underlying_for(INST.key, date(2026, 7, 23))
    assert july_after == p.get_ltp(INST)             # now the front month: no adjustment
    # the July option sees only the real move across the switch, not the roll gap
    real_move = df.loc[roll_at, "open"] - gap - df.loc[last_before, "close"]
    assert abs((july_after - july_before) - real_move) < 1e-9
