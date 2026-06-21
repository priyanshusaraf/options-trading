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


def daily_loss_halt(realized_today: float, unrealized_open: float,
                    max_daily_loss: float, max_open_drawdown: float) -> tuple[bool, str]:
    """Decide whether to HALT new entries for the day. Two independent circuit
    breakers — either one trips the halt; both are off by default (cap <= 0):

      • max_daily_loss    — today's REALIZED net loss (closed trades only). The
        original breaker; blind to a position bleeding while still open.
      • max_open_drawdown — today's REALIZED + UNREALIZED (open mark-to-market)
        loss, so a deep *open* drawdown halts new entries even before anything is
        booked. This is the realized+unrealized halt the owner asked for.

    Returns (halted, reason) with reason in {"", "realized", "open_drawdown"};
    the realized breaker wins the reason when both would trip. Open positions are
    ALWAYS still managed (SL/TP/trailing) — this only blocks opening new ones, and
    the open-drawdown breaker un-trips if the open MTM recovers."""
    if max_daily_loss and max_daily_loss > 0 and realized_today <= -max_daily_loss:
        return True, "realized"
    if (max_open_drawdown and max_open_drawdown > 0
            and (realized_today + unrealized_open) <= -max_open_drawdown):
        return True, "open_drawdown"
    return False, ""
