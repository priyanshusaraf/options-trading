"""Trailing-stop ratchet — reproduces the owner's worked example exactly."""
from app.engine.exit_monitor import trailing_stop

# entry 400, +10% trigger step, lock 2.5%/step, 60% final target.
P = dict(trigger_pct=0.10, lock_pct=0.025, target_pct=0.60)
ENTRY = 400.0
INITIAL_STOP = ENTRY * 0.65  # the app's default -35% stop = 260


def test_no_ratchet_below_first_threshold():
    assert trailing_stop(ENTRY, 420.0, INITIAL_STOP, **P) == INITIAL_STOP  # only +5%


def test_example_sequence():
    assert trailing_stop(ENTRY, 440.0, INITIAL_STOP, **P) == 410.0  # +10% -> 410
    assert trailing_stop(ENTRY, 480.0, INITIAL_STOP, **P) == 420.0  # +20% -> 420
    assert trailing_stop(ENTRY, 520.0, INITIAL_STOP, **P) == 430.0  # +30% -> 430
    assert trailing_stop(ENTRY, 640.0, INITIAL_STOP, **P) == 460.0  # +60% -> 460


def test_capped_at_target():
    # beyond the +60% target the ratchet stops climbing
    assert trailing_stop(ENTRY, 800.0, INITIAL_STOP, **P) == 460.0


def test_never_loosens():
    # a stop already above the computed ratchet is preserved
    assert trailing_stop(ENTRY, 440.0, 450.0, **P) == 450.0
