"""The signal frame has to carry the volume the candles already hold.

`volume_surge` was added to the research block library on 2026-08-01 as part of
Phase 2's vocabulary widening. It is pure, tested, registered, and sampled by the
composition search — and on every real frame it read **False**, unconditionally,
because `frame_from` built the frame from five keys and `volume` was not one of
them. Kite has returned a volume on every historical bar since `kite.py:360` was
written; the data existed the whole time and the converter dropped it on the floor.

That is the project's defining defect wearing yet another costume (see
`tests/test_no_unconsumed_mechanisms.py`): built, correct, wired to nothing. The
unconsumed-mechanism guard could not catch this one — `volume_surge` HAS callers,
it is referenced by the registry and reachable from the search. What it lacked was
*data*, which no reference scan can see.

The cost was not merely a missing feature. A composition containing `volume_surge`
is guaranteed to produce zero signals, so the nightly search burned trials on
candidates that were never candidates — and every one of them still counted toward
the deflation trial count, making the DSR bar harder to clear for the compositions
that were real.

Two properties are asserted here:

  1. volume reaches the frame, so the block can actually fire; and
  2. absent or zero volume still reads FALSE, never True. Missing data must fail
     to silence, never to a signal — that is the same rule the block was written
     with, and it has to survive the column existing.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from app.market_data.candles import FRAME_COLUMNS, candles_to_df, frame_from
from app.providers.base import Candle


def _c(minute: int, *, close=100.0, volume=1000.0) -> Candle:
    return Candle(ts=dt.datetime(2026, 1, 1, 9, 15) + dt.timedelta(minutes=minute),
                  open=close, high=close + 0.5, low=close - 0.5, close=close,
                  volume=volume)


def test_volume_is_part_of_the_frame_contract():
    assert "volume" in FRAME_COLUMNS


def test_a_candles_volume_survives_the_converter():
    df = candles_to_df([_c(0, volume=1234.0), _c(15, volume=5678.0)])
    assert list(df["volume"]) == [1234.0, 5678.0]


def test_the_price_columns_are_unchanged_by_the_addition():
    """Volume is ADDITIVE. If any price column moved, every live signal and every
    stored backtest result moved with it — which is the one thing this seam is
    forbidden to do."""
    candles = [_c(15 * i, close=100.0 + i) for i in range(6)]
    old = pd.DataFrame([{"date": c.ts, "open": c.open, "high": c.high,
                         "low": c.low, "close": c.close} for c in candles])
    new = candles_to_df(candles)
    pd.testing.assert_frame_equal(new[["date", "open", "high", "low", "close"]], old)


def test_a_record_with_no_volume_attribute_remains_missing_and_has_distinct_identity():
    """The replay provider's JSON and hand-written regression fixtures predate the
    column. A frame built from them must still be a frame."""
    class Bar:
        def __init__(self, ts):
            self.ts, self.open, self.high, self.low, self.close = ts, 100.0, 101.0, 99.0, 100.0

    timestamp = dt.datetime(2026, 1, 1, 9, 15)
    missing = frame_from([Bar(timestamp)])
    zero = frame_from([_c(0, volume=0.0)])
    assert missing["volume"].isna().all()
    assert list(zero["volume"]) == [0.0]

    from app.ir.experiment import data_digest
    assert data_digest({"volume": missing["volume"]}) != data_digest({"volume": zero["volume"]})


def test_an_empty_frame_still_declares_the_column():
    assert list(frame_from([]).columns) == FRAME_COLUMNS


# ── the point of the exercise ────────────────────────────────────────────────

def test_volume_surge_can_now_actually_fire():
    """Before this fix, this assertion was impossible to satisfy with any input."""
    blocks = pytest.importorskip("research.strategy.builder.blocks")
    quiet = [_c(15 * i, close=100.0, volume=1000.0) for i in range(20)]
    loud = quiet + [_c(15 * 20, close=100.0, volume=50_000.0)]
    df = candles_to_df(loud)
    s = blocks.volume_surge(df, 10, 2.0)
    assert bool(s.iloc[-1]) is True
    assert not s.iloc[:20].any()


def test_a_zero_volume_feed_still_reads_no_surge():
    """Options chains and some historical dumps report 0. A column of zeros must
    not become a signal — `0 > 0 * mult` has to stay False rather than NaN-True."""
    blocks = pytest.importorskip("research.strategy.builder.blocks")
    df = candles_to_df([_c(15 * i, volume=0.0) for i in range(20)])
    s = blocks.volume_surge(df, 10, 1.5)
    assert s.dtype == bool
    assert not s.any()
