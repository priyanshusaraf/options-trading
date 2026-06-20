"""
Pure, additive trader risk-control guards for the entry path.

These ONLY ever prevent or limit *new* entries — they never change strategy
direction, sizing of an accepted trade, or order mechanics — so they are safe to
layer on and trivially unit-testable. The engine consults them in
`process_entries`; open-position management is untouched.
"""
from __future__ import annotations

import datetime as dt


def slots_available(open_count: int, max_open_positions: int) -> int | None:
    """How many *new* positions may still be opened. None = unlimited (cap off).

    `max_open_positions <= 0` disables the cap (back-compat default)."""
    if not max_open_positions or max_open_positions <= 0:
        return None
    return max(0, max_open_positions - open_count)


def in_reentry_cooldown(last_stop_time: dt.datetime | None, now: dt.datetime,
                        cooldown_minutes: float) -> bool:
    """True if `now` is still within the post-stop-out cooldown for an instrument.

    Prevents the classic chop trap: stop out at −X%, the next candle re-crosses,
    re-enter, stop out again. `cooldown_minutes <= 0` disables it."""
    if not cooldown_minutes or cooldown_minutes <= 0 or last_stop_time is None:
        return False
    return (now - last_stop_time).total_seconds() < cooldown_minutes * 60.0


def over_per_trade_cap(cost: float, cap: float) -> bool:
    """True if a single trade's all-in cost exceeds the per-trade capital cap.

    `cap <= 0` disables it. Guards against one fat contract (e.g. a pricey index
    option) consuming a disproportionate slice of capital on a single signal."""
    return bool(cap and cap > 0 and cost > cap)
