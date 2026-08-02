"""Session-aware blocks: opening-range breakout and time-of-day window.

These were the last two entries in Workstream A Phase 2's vocabulary, and they were
deliberately left behind when the rest landed. Every other block in the library is
pure bar math — it can read a frame of anonymous OHLC rows and be correct. These two
cannot: they need to know where a trading *session* begins and what time of day a bar
sits at. That is a different shape of change, and it comes with two hazards the
bar-math blocks never had.

**Hazard one: look-ahead.** An opening range is the only construct in the library
that summarises a group of bars and then asks other bars about it. Computed carelessly
— group the session, take the high, broadcast to every row — bar 2 of the session
would "break out" of a range that includes bar 8. The leak would be invisible: the
backtest would simply look good. So the range is built from the first `bars` bars and
the breakout is masked off until the bar AFTER that window closes, and the test below
proves a bar inside the range window can never fire.

**Hazard two: the host clock.** The 2026-08-01 timezone audit found a stop that would
silently stop firing on a rebuilt UTC droplet, because one code path fell back to
naive host-local time. A time-of-day block is exactly the shape of code that invites
that mistake. These read the wall clock recorded ON THE BAR and never call a
clock function, so the whole family is host-independent by construction — asserted
here by running the same frame under three different `TZ` values.

Both fail CLOSED: a frame with no usable `date` column reads False everywhere rather
than unconditionally True. A filter that cannot evaluate must narrow a strategy to
nothing, never silently remove the condition it was added to impose — the same rule
`regime_is` follows.
"""
from __future__ import annotations

import datetime as dt
import os
import time

import pandas as pd
import pytest

from research.strategy.builder import blocks
from research.strategy.builder.grammar import parse_ref


def _session(day: int, closes, highs=None, lows=None, start=(9, 15), step=15):
    """One trading session's bars, 15m apart from 09:15 IST by default."""
    n = len(closes)
    base = dt.datetime(2026, 1, day, *start)
    highs = highs if highs is not None else [c + 0.5 for c in closes]
    lows = lows if lows is not None else [c - 0.5 for c in closes]
    return [{"date": base + dt.timedelta(minutes=step * i),
             "open": closes[i], "high": highs[i], "low": lows[i],
             "close": closes[i], "volume": 1000.0} for i in range(n)]


def _frame(*sessions):
    return pd.DataFrame([r for s in sessions for r in s]).reset_index(drop=True)


# ── time-of-day window ───────────────────────────────────────────────────────

def test_the_window_selects_only_bars_inside_it():
    # 09:15, 09:30, 09:45, 10:00, 10:15  →  minutes 555, 570, 585, 600, 615
    df = _frame(_session(5, [100.0] * 5))
    s = blocks.time_of_day(df, 570, 600)          # [09:30, 10:00)
    assert list(s) == [False, True, True, False, False]


def test_the_window_is_half_open_so_adjacent_windows_do_not_overlap():
    """Two windows meeting at the same minute must partition the bars, not
    double-count the boundary bar — otherwise `all(w1, w2)` is satisfiable and a
    composition can ask for a bar to be in two disjoint windows at once."""
    df = _frame(_session(5, [100.0] * 5))
    early = blocks.time_of_day(df, 555, 585)
    late = blocks.time_of_day(df, 585, 615)
    assert not (early & late).any()


def test_the_window_applies_to_every_session_not_just_the_first():
    df = _frame(_session(5, [100.0] * 4), _session(6, [100.0] * 4))
    s = blocks.time_of_day(df, 555, 570)          # the 09:15 bar of each day
    assert list(s) == [True, False, False, False, True, False, False, False]


def test_an_inverted_window_selects_nothing():
    """end <= start is not a wrap around midnight — Indian sessions never do that.
    It is a nonsensical window, and a nonsensical filter must exclude everything
    rather than accidentally including everything."""
    df = _frame(_session(5, [100.0] * 5))
    assert not blocks.time_of_day(df, 600, 570).any()
    assert not blocks.time_of_day(df, 600, 600).any()


def test_the_window_reads_the_bars_clock_not_the_hosts():
    """The 2026-08-01 audit's lesson, applied before it can bite. The same frame
    must select the same bars under any `TZ` the droplet happens to be rebuilt with."""
    df = _frame(_session(5, [100.0] * 5))
    seen = []
    original = os.environ.get("TZ")
    try:
        for tz in ("UTC", "Asia/Kolkata", "America/New_York"):
            os.environ["TZ"] = tz
            time.tzset()
            seen.append(list(blocks.time_of_day(df, 570, 600)))
    finally:
        if original is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original
        time.tzset()
    assert seen[0] == seen[1] == seen[2] == [False, True, True, False, False]


# ── opening-range breakout ───────────────────────────────────────────────────

def test_a_break_above_the_opening_range_fires():
    # first 2 bars set the range (high 100.5 / 101.5); bar 3 closes above it
    df = _frame(_session(5, [100.0, 101.0, 100.5, 103.0]))
    s = blocks.opening_range_break_up(df, 2, 0.1)
    assert list(s) == [False, False, False, True]


def test_a_break_below_the_opening_range_fires():
    df = _frame(_session(5, [100.0, 99.0, 99.5, 96.0]))
    s = blocks.opening_range_break_down(df, 2, 0.1)
    assert list(s) == [False, False, False, True]


def test_a_bar_inside_the_range_window_can_never_fire():
    """The look-ahead guard, stated directly. Bar 1 of the session sits at the
    highest close of the whole day; if the range were broadcast from a groupby it
    would be compared against a maximum computed from bars 2-5, which had not
    happened yet."""
    df = _frame(_session(5, [999.0, 100.0, 100.0, 100.0, 100.0]))
    s = blocks.opening_range_break_up(df, 3, 0.1)
    assert not s.iloc[:3].any()


def test_the_range_is_rebuilt_each_session():
    """Yesterday's range must not gate today. Day 2 opens far below day 1's high
    and breaks its OWN range — a carried-over range would swallow the signal."""
    day1 = _session(5, [500.0, 505.0, 502.0, 501.0])
    day2 = _session(6, [100.0, 101.0, 100.5, 104.0])
    s = blocks.opening_range_break_up(_frame(day1, day2), 2, 0.1)
    assert bool(s.iloc[-1]) is True


def test_the_buffer_suppresses_a_marginal_break():
    """A close a hair above the range is noise, not a breakout. The buffer is what
    makes this block different from `close > rolling max`."""
    df = _frame(_session(5, [100.0, 101.0, 100.5, 101.6]))
    # range high is 101.5; 101.6 is +0.10%, so a 1% buffer must reject it
    assert not blocks.opening_range_break_up(df, 2, 1.0).iloc[-1]
    assert bool(blocks.opening_range_break_up(df, 2, 0.05).iloc[-1]) is True


def test_a_session_shorter_than_the_range_produces_nothing():
    """A half-day or a truncated feed must not emit a breakout off a partial range."""
    df = _frame(_session(5, [100.0, 105.0]))
    assert not blocks.opening_range_break_up(df, 5, 0.1).any()


def test_the_range_uses_the_high_and_low_not_the_close():
    """An opening range is the extent price actually traded over, so a wick counts.
    Using closes would place the range too narrow and fire on ordinary noise."""
    df = _frame(_session(5, [100.0, 100.0, 100.0, 100.4],
                        highs=[100.2, 100.5, 100.2, 100.6],
                        lows=[99.8, 99.5, 99.8, 100.2]))
    # close 100.4 is above both opening CLOSES but below the opening HIGH of 100.5
    assert not blocks.opening_range_break_up(df, 2, 0.0001).iloc[-1]


# ── fail-closed contracts ────────────────────────────────────────────────────

@pytest.mark.parametrize("fn,args", [
    (blocks.time_of_day, (570, 600)),
    (blocks.opening_range_break_up, (2, 0.1)),
    (blocks.opening_range_break_down, (2, 0.1)),
])
def test_a_frame_with_no_date_column_reads_false_everywhere(fn, args):
    """Not True, and not an exception. A session block handed a frame it cannot
    place in time has to narrow the strategy to nothing."""
    df = pd.DataFrame({"open": [1.0] * 4, "high": [2.0] * 4,
                       "low": [0.5] * 4, "close": [1.5] * 4})
    s = fn(df, *args)
    assert s.dtype == bool and not s.any()
    assert list(s.index) == list(df.index)


@pytest.mark.parametrize("fn,args", [
    (blocks.time_of_day, (570, 600)),
    (blocks.opening_range_break_up, (2, 0.1)),
    (blocks.opening_range_break_down, (2, 0.1)),
])
def test_an_unparseable_date_column_reads_false_everywhere(fn, args):
    df = pd.DataFrame({"date": ["not a date"] * 4, "open": [1.0] * 4,
                       "high": [2.0] * 4, "low": [0.5] * 4, "close": [1.5] * 4})
    assert not fn(df, *args).any()


@pytest.mark.parametrize("fn,args", [
    (blocks.time_of_day, (570, 600)),
    (blocks.opening_range_break_up, (2, 0.1)),
    (blocks.opening_range_break_down, (2, 0.1)),
])
def test_an_empty_frame_is_not_an_error(fn, args):
    df = pd.DataFrame(columns=["date", "open", "high", "low", "close"])
    s = fn(df, *args)
    assert s.dtype == bool and len(s) == 0


# ── registration + grammar ───────────────────────────────────────────────────

def test_the_blocks_are_registered_and_reachable_by_the_search():
    """A block absent from BLOCKS is unreachable by the composition search — the
    exact way the RSI family was registered and never sampled."""
    for name in ("time_of_day", "opening_range_break_up", "opening_range_break_down"):
        assert name in blocks.BLOCKS
        assert name in blocks.block_names()


def test_a_minute_of_day_survives_the_grammars_bounds():
    """09:15 is minute 555, which no pre-existing kind admits: `length` caps at 400,
    `thr` at |10|, `pct` at 100, `choice` at 15. Declaring these as any of those
    would have made the market open unrepresentable — the same class of mistake as
    declaring the RSI threshold a `thr`."""
    ref = parse_ref("time_of_day(555, 930)")
    assert ref.args == (555, 930)


@pytest.mark.parametrize("bad", [
    "time_of_day(-1, 600)",      # before midnight
    "time_of_day(555, 1440)",    # past the end of the day
    "time_of_day(555.5, 600)",   # a fractional minute is not a minute
])
def test_the_grammar_rejects_an_impossible_minute(bad):
    with pytest.raises(ValueError):
        parse_ref(bad)


def test_the_sample_args_are_lawful_and_describe_a_real_session():
    """Sample args seed the search, so an unlawful one would be sampled and rejected
    every night. They must also be *sensible*: an opening range whose sample sits
    outside NSE hours would teach the search nothing."""
    for name in ("time_of_day", "opening_range_break_up", "opening_range_break_down"):
        spec = blocks.BLOCKS[name]
        ref = parse_ref(f"{name}({', '.join(repr(a) for a in spec.sample_args)})")
        assert ref.name == name
    start, end = blocks.BLOCKS["time_of_day"].sample_args
    assert 9 * 60 + 15 <= start < end <= 15 * 60 + 30      # inside NSE 09:15-15:30
