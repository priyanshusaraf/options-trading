"""Market-data validation at the single Data seam.

Candles reached the strategy completely unchecked. Two byte-identical copies of
the same converter — `runner._to_df` and `backtest.engine._candles_to_df` — each
did `pd.DataFrame([...])` and handed the result straight to `strat.signals`.
Nothing sorted them, nothing de-duplicated them, and nothing rejected a bar with
a NaN close or a high below its low.

That matters because the output is not a chart, it is an order. A duplicated bar
shifts every EMA and z-score after it; an out-of-order bar silently inverts the
series the z-score is measured against; `high < low` produces a nonsense ATR,
and ATR sets the ratchet stop distance on live positions (`entry_atr`). None of
these announce themselves — they come out as a slightly different signal.

The design rule these tests pin: **on clean data the validator is a no-op.** The
live engine and every historical backtest have to keep producing exactly what
they produce today, or this change is a silent re-tuning of a live strategy
rather than a safety net. Repairs are limited to the unambiguous — sort,
de-duplicate, and widen a bar's high/low to contain its own open/close. A bar
with no usable price (missing/NaN/infinite, or at or below zero) has no correct
answer available, so it is DROPPED and COUNTED, never guessed at or
forward-filled.

The envelope repair earns its place from this repo's own fixtures:
`test_backtest_ratchet_overlay.py` builds `(o=100.0, h=100.5, lo=98.5, c=97.9)`,
a close below its own low. Dropping it deleted the very bar that test exists to
exercise; correcting the low to 97.9 — a price we have direct evidence traded —
keeps the observation and makes those tests pass unchanged.
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal
import math

import numpy as np
import pandas as pd
import pytest

from app.market_data.candles import candles_to_df, frame_from, validate_candles
from app.market_data.numeric import NumericIngressError
from app.providers.base import Candle


def _c(minute: int, o=100.0, h=101.0, lo=99.0, close=100.5, vol=10.0) -> Candle:
    return Candle(ts=dt.datetime(2026, 8, 1, 9, minute), open=o, high=h,
                  low=lo, close=close, volume=vol)


def _series(n: int = 5) -> list[Candle]:
    """A rising, internally COHERENT series — the whole bar moves together.

    The first cut of this helper held high=101 fixed while close climbed past it,
    producing bars whose close sat above their own high. The validator dropped
    them, correctly, and the tests failed. Left as a note because it is the exact
    class of bug this module exists to catch, and it was easier to write by
    accident than to spot by reading.
    """
    return [_c(15 + i, o=100.0 + i, h=101.0 + i, lo=99.0 + i, close=100.5 + i)
            for i in range(n)]


# ── the rule that keeps this change safe: clean data is untouched ───────────

def test_clean_candles_pass_through_unchanged():
    candles = _series(10)
    out, report = validate_candles(candles)
    assert out == candles
    assert report.clean is True
    assert report.kept == 10


def test_the_dataframe_matches_the_old_converter_exactly_on_clean_data():
    """The regression that matters most: if a PRICE column differs at all from what
    `pd.DataFrame([{...}])` produced, every live signal and every stored backtest
    result silently moves.

    `volume` was added to the frame on 2026-08-02 and is deliberately excluded from
    this comparison — see `tests/test_frame_carries_volume.py`. It is a new column,
    not a changed one: no indicator in either plane reads it, and the block that
    does had been reading False on every real frame for want of it. The invariant
    this test exists to defend is that the price columns do not move, so it now
    says exactly that instead of freezing the column list by accident.
    """
    candles = _series(8)
    old = pd.DataFrame([{"date": c.ts, "open": c.open, "high": c.high,
                         "low": c.low, "close": c.close} for c in candles])
    new = candles_to_df(candles)
    pd.testing.assert_frame_equal(new[["date", "open", "high", "low", "close"]], old)


def test_a_flat_bar_is_valid():
    """high == low == open == close is a real bar (no trades moved the price).
    Rejecting it would drop legitimate illiquid data."""
    out, report = validate_candles([_c(15, o=50.0, h=50.0, lo=50.0, close=50.0)])
    assert report.clean is True and len(out) == 1


def test_an_empty_series_is_not_an_error():
    out, report = validate_candles([])
    assert out == [] and report.total_in == 0
    assert candles_to_df([]).empty


# ── duplicates ──────────────────────────────────────────────────────────────

def test_a_duplicated_timestamp_is_collapsed():
    """A repeated bar shifts every EMA and z-score computed after it."""
    a, b = _c(15, close=100.0), _c(15, close=101.0)
    out, report = validate_candles([a, b, _c(16)])
    assert len(out) == 2
    assert report.duplicates == 1


def test_the_last_copy_of_a_duplicate_wins():
    """A re-fetched bar is the more final one — Kite revises the most recent
    bar as trades settle, so the later copy is the better copy."""
    out, _ = validate_candles([_c(15, close=100.0), _c(15, close=101.0)])
    assert out[0].close == 101.0


# ── ordering ────────────────────────────────────────────────────────────────

def test_out_of_order_candles_are_sorted():
    out, report = validate_candles([_c(17), _c(15), _c(16)])
    assert [c.ts.minute for c in out] == [15, 16, 17]
    assert report.reordered is True


def test_already_sorted_candles_do_not_report_a_reorder():
    _, report = validate_candles(_series(4))
    assert report.reordered is False


# ── corrupt bars are dropped, not repaired ──────────────────────────────────

@pytest.mark.parametrize("bad,reason", [
    (_c(23, close=0.0), "non_positive"),
    (_c(24, close=-5.0), "non_positive"),
    (_c(25, close=float("nan")), "not_finite"),
    (_c(26, h=float("inf")), "not_finite"),
])
def test_an_unrepairable_bar_is_dropped_and_counted(bad, reason):
    """Only two conditions are genuinely unrepairable — no price, or a price at
    or below zero. There is no fact left to correct from, so the bar goes."""
    good = _series(3)
    out, report = validate_candles(good + [bad])
    assert len(out) == 3, f"the {reason} bar survived validation"
    assert report.dropped_corrupt == 1
    assert report.reasons.get(reason) == 1, f"expected reason {reason}, got {report.reasons}"


# ── an inconsistent envelope is CORRECTED, not discarded ────────────────────

@pytest.mark.parametrize("bar,exp_high,exp_low", [
    # close below its own low — the real fixture shape from the ratchet tests
    (_c(20, o=100.0, h=100.5, lo=98.5, close=97.9), 100.5, 97.9),
    # close above its own high
    (_c(21, o=100.0, h=100.5, lo=99.0, close=101.2), 101.2, 99.0),
    # inverted high/low, which the envelope repair subsumes
    (_c(22, o=100.0, h=98.0, lo=101.0, close=100.0), 100.0, 100.0),
])
def test_an_inconsistent_envelope_is_widened_to_contain_the_body(bar, exp_high, exp_low):
    """We hold direct evidence price traded at open and close, so a high/low that
    excludes them is wrong about the envelope, not about the trade. Correcting it
    from what we know beats deleting a real observation — and beats leaving a
    negative range to flow into ATR, which sets live ratchet stop distances."""
    out, report = validate_candles([bar])
    assert len(out) == 1, "a repairable bar must not be dropped"
    assert out[0].high == exp_high
    assert out[0].low == exp_low
    assert report.repaired == 1
    assert report.dropped_corrupt == 0
    assert report.reasons.get("repaired_envelope") == 1


def test_a_repaired_bar_always_contains_its_own_body():
    """The post-condition the repair guarantees, stated directly."""
    out, _ = validate_candles([_c(20, o=100.0, h=98.0, lo=101.0, close=97.0)])
    c = out[0]
    assert c.low <= min(c.open, c.close) <= max(c.open, c.close) <= c.high


def test_repair_preserves_the_untouched_fields():
    out, _ = validate_candles([_c(20, o=100.0, h=100.5, lo=98.5, close=97.9, vol=42.0)])
    assert out[0].open == 100.0 and out[0].close == 97.9 and out[0].volume == 42.0


def test_a_none_price_is_dropped_not_crashed():
    """Providers hand back None for a missing field more often than NaN."""
    out, report = validate_candles([_c(15), Candle(ts=dt.datetime(2026, 8, 1, 9, 16),
                                                   open=100.0, high=101.0, low=99.0,
                                                   close=None, volume=1.0)])
    assert len(out) == 1
    assert report.dropped_corrupt == 1


def test_corruption_does_not_take_the_good_bars_with_it():
    """Fail on the bar, not on the series — dropping a whole fetch because one
    bar is bad would stop the engine trading on a single glitch."""
    out, _ = validate_candles([_c(15), _c(16, close=float("nan")), _c(17)])
    assert [c.ts.minute for c in out] == [15, 17]


def test_negative_volume_does_not_drop_a_bar():
    """Volume is not a price and nothing trades on it here. Dropping a bar over
    it would discard usable OHLC."""
    out, report = validate_candles([_c(15, vol=-1.0)])
    assert len(out) == 1 and report.clean is True


# ── the report has to be legible, or nobody will act on it ──────────────────

def test_a_dirty_report_says_what_it_did():
    _, report = validate_candles([_c(17), _c(17), _c(15, close=float("nan"))])
    assert report.clean is False
    text = report.summary()
    assert "duplicate" in text.lower()
    assert "1" in text


def test_a_clean_report_summarises_as_clean():
    _, report = validate_candles(_series(3))
    assert report.clean is True
    assert report.summary() == ""


def test_counts_reconcile():
    """kept + dropped + duplicates must account for everything that came in, or
    the report is not evidence of anything."""
    candles = [_c(15), _c(15), _c(16), _c(17, close=float("nan"))]
    out, report = validate_candles(candles)
    assert report.total_in == 4
    assert report.kept == len(out)
    assert report.kept + report.dropped_corrupt + report.duplicates == report.total_in


# ── the wired seam ──────────────────────────────────────────────────────────

def test_candles_to_df_drops_corrupt_rows():
    df = candles_to_df([_c(15), _c(16, close=float("nan")), _c(17)])
    assert len(df) == 2
    assert list(df.columns) == ["date", "open", "high", "low", "close", "volume"]


def test_candles_to_df_sorts_so_indicators_see_time_order():
    df = candles_to_df([_c(17), _c(15), _c(16)])
    assert list(df["date"]) == sorted(df["date"])


def test_both_historic_converters_now_share_one_implementation():
    """`runner._to_df` and `backtest.engine._candles_to_df` were byte-identical
    copies. Two copies of the data seam means a validation fix can land in one
    plane and not the other, which is exactly how live and backtest drift apart."""
    from app.backtest.engine import _candles_to_df
    from app.engine.runner import _to_df
    candles = _series(4)
    pd.testing.assert_frame_equal(_to_df(candles), _candles_to_df(candles))
    pd.testing.assert_frame_equal(_to_df(candles), candles_to_df(candles))

    # Agreeing on CLEAN data proves nothing — two independent copies would also
    # agree. Feed both a corrupt bar: only a converter that actually routes
    # through the shared validator drops it.
    dirty = [_c(15), _c(16, close=float("nan")), _c(17)]
    assert len(_to_df(dirty)) == 2, "the live converter is not validating"
    assert len(_candles_to_df(dirty)) == 2, "the backtest converter is not validating"


_BOOLEAN_SCALARS = (True, False, np.bool_(True), np.bool_(False))


@pytest.mark.parametrize("field", ("open", "high", "low", "close", "volume"))
@pytest.mark.parametrize("value", _BOOLEAN_SCALARS)
def test_validation_and_signal_frame_refuse_boolean_ohlcv(field, value):
    candle = _c(15)
    setattr(candle, field, value)

    clean, report = validate_candles([candle])
    assert clean == []
    assert report.dropped_corrupt == 1
    assert candles_to_df([candle]).empty
    with pytest.raises(NumericIngressError):
        frame_from([candle])


@pytest.mark.parametrize("value", (Decimal("100.25"), "100.25",
                                    np.int64(100), np.float64(100.25)))
def test_float_coercible_non_boolean_prices_keep_plain_float_frame_behavior(value):
    candle = _c(15, o=value, h=Decimal("101.5"), lo="99.5",
                close=np.float64(100.75), vol=np.int64(7))
    frame = candles_to_df([candle])
    assert frame.to_dict("records") == [{
        "date": candle.ts, "open": float(value), "high": 101.5,
        "low": 99.5, "close": 100.75, "volume": 7.0,
    }]
    assert all(type(frame.iloc[0][name]) in (float, np.float64)
               for name in ("open", "high", "low", "close", "volume"))
