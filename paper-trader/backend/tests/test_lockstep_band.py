"""Lockstep band for intraday equity: once in profit, slide BOTH the stop and the
target together by one step per `trigger_pct`-of-margin of profit, ratchet-only, with
a break-even floor so a position that's gone green can't be stopped out red.

Worked numbers: ₹10k margin at 5x -> ₹50k notional, long @ ₹100, 500 shares.
Step = 2% of margin = ₹200 = +₹0.40/share. Initial band SL 99 / TP 102."""
from app.engine.equity_entry import lockstep_band

P = dict(trigger_pct=0.02, sl_pct=0.01, tp_pct=0.02)
ENTRY, QTY, MARGIN = 100.0, 500, 10000.0
BE = 100.0   # break-even price (charges ignored for the worked example)


def test_no_move_when_flat_or_red():
    assert lockstep_band("LONG", ENTRY, QTY, MARGIN, 99.0, 102.0, 100.0, breakeven_price=BE, **P) == (99.0, 102.0)
    assert lockstep_band("LONG", ENTRY, QTY, MARGIN, 99.0, 102.0, 99.5, breakeven_price=BE, **P) == (99.0, 102.0)


def test_first_step_locks_break_even_and_slides_target():
    # +1 step (+₹200 @ 100.40): stop floored to break-even 100, target -> 102.40
    assert lockstep_band("LONG", ENTRY, QTY, MARGIN, 99.0, 102.0, 100.40, breakeven_price=BE, **P) == (100.0, 102.40)


def test_slides_both_together_after_several_steps():
    # +5 steps (+₹1000 @ 102.00): stop -> 101, target -> 104 (band width preserved)
    assert lockstep_band("LONG", ENTRY, QTY, MARGIN, 99.0, 102.0, 102.0, breakeven_price=BE, **P) == (101.0, 104.0)


def test_never_loosens():
    # an already-tighter stop / further target survive a smaller computed step
    assert lockstep_band("LONG", ENTRY, QTY, MARGIN, 101.5, 104.5, 100.40, breakeven_price=BE, **P) == (101.5, 104.5)


def test_short_mirror():
    # SHORT @ 100, +1 step (+₹200 @ 99.60): stop floored to break-even 100, target -> 97.60
    assert lockstep_band("SHORT", ENTRY, QTY, MARGIN, 101.0, 98.0, 99.60, breakeven_price=100.0, **P) == (100.0, 97.60)


# ── #6 profit-lock: once the gain is "good enough", lock a positive buffer ──
LOCK = dict(trigger_pct=0.02, sl_pct=0.01, tp_pct=0.02,
            profit_lock_threshold=200.0, profit_lock_frac=0.5)


def test_profit_lock_floors_positive_buffer_long():
    # +1 step (+₹200 @ 100.40): WITHOUT the lock the stop floors at break-even 100.0;
    # WITH profit-lock (≥₹200, 50% of the +₹0.40 move) it floors at 100.20 — locking
    # +₹100 net (500 sh × ₹0.20) instead of handing the gain back at break-even.
    stop, _ = lockstep_band("LONG", ENTRY, QTY, MARGIN, 99.0, 102.0, 100.40,
                            breakeven_price=BE, **LOCK)
    assert stop == 100.20


def test_profit_lock_dormant_below_threshold():
    # @100.20 the gain is +₹100 < ₹200 threshold -> no lock, no ratchet (stop unchanged)
    stop, _ = lockstep_band("LONG", ENTRY, QTY, MARGIN, 99.0, 102.0, 100.20,
                            breakeven_price=BE, **LOCK)
    assert stop == 99.0


def test_profit_lock_short_side():
    # SHORT @ 100, +₹200 @ 99.60: the lock floors the stop DOWN to 99.80 (mirror of long)
    stop, _ = lockstep_band("SHORT", ENTRY, QTY, MARGIN, 101.0, 98.0, 99.60,
                            breakeven_price=100.0, **LOCK)
    assert stop == 99.80
