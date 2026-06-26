"""Exit logic (owner-specified): close on a premium stop (-35%) OR target (+60%)
OR the strategy's own exit flag — whichever fires first. The premium guards are
checked before the strategy flag so a protective stop/target always wins a tie."""
from app.engine.exit_monitor import evaluate_exit

# A long position entered at premium 100 -> stop 65, target 160.
STOP, TARGET = 65.0, 160.0


def test_holds_when_nothing_triggers():
    should, reason = evaluate_exit("LONG", STOP, TARGET, current_premium=110.0,
                                   long_exit=False, short_exit=False)
    assert should is False
    assert reason is None


def test_stop_loss_triggers():
    should, reason = evaluate_exit("LONG", STOP, TARGET, current_premium=64.0,
                                   long_exit=False, short_exit=False)
    assert should is True
    assert reason == "STOP_LOSS"


def test_target_triggers():
    should, reason = evaluate_exit("LONG", STOP, TARGET, current_premium=161.0,
                                   long_exit=False, short_exit=False)
    assert should is True
    assert reason == "TARGET"


def test_strategy_long_exit_triggers():
    should, reason = evaluate_exit("LONG", STOP, TARGET, current_premium=110.0,
                                   long_exit=True, short_exit=False)
    assert should is True
    assert reason == "STRATEGY_EXIT"


def test_short_position_uses_short_exit_flag():
    # a short position should not be closed by the long-exit flag
    should, _ = evaluate_exit("SHORT", STOP, TARGET, current_premium=110.0,
                              long_exit=True, short_exit=False)
    assert should is False
    should, reason = evaluate_exit("SHORT", STOP, TARGET, current_premium=110.0,
                                   long_exit=False, short_exit=True)
    assert should is True
    assert reason == "STRATEGY_EXIT"


def test_stop_does_not_fire_on_a_nonpositive_premium():
    # L13: a 0.0 / negative premium is a missing or bad tick, not a tradeable price —
    # it must NOT trigger a real market STOP_LOSS exit (an option can't trade at <= 0).
    for bad in (0.0, -1.0):
        should, reason = evaluate_exit("LONG", STOP, TARGET, current_premium=bad,
                                       long_exit=False, short_exit=False)
        assert should is False and reason is None


def test_a_genuine_floor_premium_still_trips_the_stop():
    # A real near-zero premium (option at its floor) is a small POSITIVE tick and must
    # still trip the stop — the guard only filters the non-positive bad-tick case.
    should, reason = evaluate_exit("LONG", STOP, TARGET, current_premium=0.05,
                                   long_exit=False, short_exit=False)
    assert should is True and reason == "STOP_LOSS"


def test_stop_beats_strategy_flag_on_a_tie():
    # both a stop and a strategy exit are true -> protective stop reason wins
    should, reason = evaluate_exit("LONG", STOP, TARGET, current_premium=60.0,
                                   long_exit=True, short_exit=False)
    assert should is True
    assert reason == "STOP_LOSS"
