"""The one place candles become a signal frame — and the one place they are checked.

Before this module there were two byte-identical converters, `runner._to_df` and
`backtest.engine._candles_to_df`, each doing `pd.DataFrame([{...}])` and handing
the result straight to `strat.signals`. Nothing sorted the bars, nothing removed
a duplicate, and nothing rejected a bar whose close was NaN or whose high sat
below its low.

The output of this path is not a chart, it is an order:

  - a duplicated bar shifts every EMA and z-score computed after it;
  - an out-of-order bar measures the z-score against a series that never
    happened;
  - `high < low` yields a nonsense ATR, and ATR sets the ratchet stop distance
    on live positions (`entry_atr`).

None of those announce themselves. They surface as a slightly different signal,
which is indistinguishable from the strategy simply having a different opinion.

Two rules govern what this is allowed to do:

**On clean data it is a no-op.** `candles_to_df` returns a frame identical to
what the old converters produced, column for column and row for row — pinned by
test. Anything else would make this a silent re-tuning of a live strategy rather
than a safety net under it.

**Repairs are limited to the unambiguous.** Sorting, de-duplication and widening
a bar's high/low to contain its own open/close each have exactly one correct
answer, so they happen and are counted. A bar with a missing, infinite or
non-positive price has no correct answer, so it is dropped — never
forward-filled, interpolated, or guessed at. Inventing a price is how a data bug
becomes a fabricated trade.

The envelope repair was originally a drop, and the project's own test fixtures
are what changed it: `tests/test_backtest_ratchet_overlay.py` builds a bar
`(open=100.0, high=100.5, low=98.5, close=97.9)` — a close below its own low,
which cannot happen in real OHLC. Dropping it silently deleted the bar the test
existed to exercise. That made the better answer obvious: we hold direct
evidence price traded at 97.9, so the low was at most 97.9. Correct it from what
we know instead of discarding a real observation.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import pandas as pd

# The frame contract `strat.signals` consumes. Order matters: it is asserted
# against the pre-existing converters so live and backtest cannot drift.
FRAME_COLUMNS = ["date", "open", "high", "low", "close"]

_PRICE_FIELDS = ("open", "high", "low", "close")


@dataclass(frozen=True)
class CandleReport:
    """What validation actually did. Returned rather than logged so the caller
    decides how loud to be — the live scan sees the same series every few
    seconds and would otherwise flood the log bus."""
    total_in: int = 0
    kept: int = 0
    duplicates: int = 0
    dropped_corrupt: int = 0
    repaired: int = 0
    reordered: bool = False
    reasons: dict[str, int] = field(default_factory=dict)

    @property
    def clean(self) -> bool:
        return not (self.duplicates or self.dropped_corrupt or self.repaired
                    or self.reordered)

    def summary(self) -> str:
        """One line for a human, empty when there is nothing to say — so a caller
        can use it directly as "should I log this?"."""
        if self.clean:
            return ""
        bits = []
        if self.dropped_corrupt:
            detail = ", ".join(f"{k}={v}" for k, v in sorted(self.reasons.items()))
            bits.append(f"{self.dropped_corrupt} corrupt bar(s) dropped ({detail})")
        if self.repaired:
            bits.append(f"{self.repaired} bar(s) had high/low widened to contain "
                        f"their own open/close")
        if self.duplicates:
            bits.append(f"{self.duplicates} duplicate timestamp(s) collapsed")
        if self.reordered:
            bits.append("bars arrived out of chronological order")
        return f"{'; '.join(bits)} — {self.kept}/{self.total_in} bars kept"


def _price_values(c) -> tuple[dict | None, str | None]:
    """Extract the four prices as floats, or say why the bar is unusable.

    Only two conditions are genuinely unrepairable, and both mean there is no
    price here to trust: a value that is missing/NaN/infinite, and a value at or
    below zero. Everything else about a bar's shape can be corrected — see
    `_repair_envelope`.

    Deliberately permissive otherwise: `high == low` is a legitimate flat bar in
    an illiquid name, and volume is not checked at all because nothing here
    trades on it. Dropping usable OHLC over a volume quirk costs signals for no
    safety gain.
    """
    vals = {}
    for f in _PRICE_FIELDS:
        v = getattr(c, f, None)
        if v is None:
            return None, "not_finite"
        try:
            v = float(v)
        except (TypeError, ValueError):
            return None, "not_finite"
        if not math.isfinite(v):
            return None, "not_finite"
        if v <= 0:
            return None, "non_positive"   # a price of zero or less is not a price
        vals[f] = v
    return vals, None


def _repair_envelope(vals: dict) -> dict | None:
    """Widen high/low so the bar contains its own open and close, or None if it
    already does.

    This is a correction, not a guess, and the distinction is the whole reason
    it is allowed. If a bar closes at 97.9 while reporting a low of 98.5, we
    hold direct evidence that price traded at 97.9 — so the true low was at most
    97.9. Setting `low = min(low, open, close)` uses a fact we have rather than
    inventing one.

    Discarding the bar instead would throw away a real price observation, and
    leaving it alone yields a negative or nonsense range — which flows straight
    into ATR, and ATR sets the ratchet stop distance on live positions.

    Note this subsumes `high < low` entirely: afterwards
    `high >= max(open, close) >= min(open, close) >= low` holds by construction,
    so an inverted bar cannot survive without ever needing to guess whether the
    provider swapped two fields.
    """
    hi = max(vals["high"], vals["open"], vals["close"])
    lo = min(vals["low"], vals["open"], vals["close"])
    if hi == vals["high"] and lo == vals["low"]:
        return None
    return {**vals, "high": hi, "low": lo}


def validate_candles(candles) -> tuple[list, CandleReport]:
    """Return (usable candles, report). Pure: no logging, no clock, no I/O.

    De-duplication keeps the LAST copy of a timestamp. Kite revises the most
    recent bar as trades settle, so a later copy of the same bar is the more
    final one — keeping the first would pin the stale version.
    """
    candles = list(candles or [])
    total = len(candles)
    if not total:
        return [], CandleReport()

    kept, reasons, dropped, repaired = [], {}, 0, 0
    for c in candles:
        vals, reason = _price_values(c)
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
            dropped += 1
            continue
        fixed = _repair_envelope(vals)
        if fixed is None:
            kept.append(c)
        else:
            # `replace` keeps this working for any Candle-shaped record without
            # this module needing to know the type's full field list.
            kept.append(replace(c, high=fixed["high"], low=fixed["low"]))
            repaired += 1
            reasons["repaired_envelope"] = reasons.get("repaired_envelope", 0) + 1

    # Collapse duplicate timestamps, last one wins, without disturbing the
    # relative order of everything else.
    by_ts = {}
    for c in kept:
        by_ts[c.ts] = c
    duplicates = len(kept) - len(by_ts)

    ordered = sorted(by_ts.values(), key=lambda c: c.ts)
    # "Reordered" describes the INPUT, so compare against the surviving bars in
    # arrival order — otherwise removing a duplicate could read as a reorder.
    reordered = [c.ts for c in by_ts.values()] != [c.ts for c in ordered]

    return ordered, CandleReport(
        total_in=total, kept=len(ordered), duplicates=duplicates,
        dropped_corrupt=dropped, repaired=repaired, reordered=reordered,
        reasons=reasons,
    )


def candles_to_df(candles) -> pd.DataFrame:
    """Validated candles as the signal frame. THE converter — both the live
    engine and the backtester route through this, so a data fix cannot land in
    one plane and miss the other.

    Silent by design: see `validate_candles_logged` for the noisy variant used
    on the live path, where an anomaly is worth a line in the log.
    """
    clean, _ = validate_candles(candles)
    if not clean:
        return pd.DataFrame(columns=FRAME_COLUMNS)
    return pd.DataFrame([{"date": c.ts, "open": c.open, "high": c.high,
                          "low": c.low, "close": c.close} for c in clean])
