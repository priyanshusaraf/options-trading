"""Trailing-stop ratchet — aggressive schedule: a gentle first step, then trail
exactly one step (10%) behind the high-water profit, with NO upper ceiling.

  lock = first_step_lock_pct                  at step 1   (+10% profit)
  lock = (steps - 1) * step_lock_pct          at step >=2 (+20%, +30%, ...)

so on a 400-entry option the locked stop is +2.5% / +10% / +20% / ... and keeps
climbing forever (used when a winner is let run past its take-profit)."""
from app.engine.exit_monitor import trailing_stop

# entry 400, +10% trigger step, 2.5% gentle first step, then 10% per step, no cap.
P = dict(trigger_pct=0.10, first_step_lock_pct=0.025, step_lock_pct=0.10)
ENTRY = 400.0
INITIAL_STOP = ENTRY * 0.70  # the app's default -30% stop = 280


def test_no_ratchet_below_first_threshold():
    assert trailing_stop(ENTRY, 420.0, INITIAL_STOP, **P) == INITIAL_STOP  # only +5%


def test_gentle_first_step():
    # +10% high-water -> a soft 2.5% lock (410), not a full 10% step yet
    assert trailing_stop(ENTRY, 440.0, INITIAL_STOP, **P) == 410.0


def test_trails_one_step_behind_after_the_first():
    assert trailing_stop(ENTRY, 480.0, INITIAL_STOP, **P) == 440.0  # +20% -> lock 10%
    assert trailing_stop(ENTRY, 520.0, INITIAL_STOP, **P) == 480.0  # +30% -> lock 20%
    assert trailing_stop(ENTRY, 560.0, INITIAL_STOP, **P) == 520.0  # +40% -> lock 30%
    assert trailing_stop(ENTRY, 640.0, INITIAL_STOP, **P) == 600.0  # +60% -> lock 50%


def test_no_upper_ceiling():
    # beyond the +60% target the ratchet KEEPS climbing (let-it-run rides)
    assert trailing_stop(ENTRY, 800.0, INITIAL_STOP, **P) == 760.0   # +100% -> lock 90%
    assert trailing_stop(ENTRY, 1200.0, INITIAL_STOP, **P) == 1160.0  # +200% -> lock 190%


def test_never_loosens():
    # a stop already above the computed ratchet is preserved
    assert trailing_stop(ENTRY, 440.0, 450.0, **P) == 450.0
