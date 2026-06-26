"""Direction-aware equity exit geometry — the bit that differs from the options
long-premium model. A SHORT's stop is ABOVE entry and target BELOW, and its MTM
profits when price falls. Pinned because getting a short's sign wrong is a
real-money bug."""
import pytest

from app.engine.equity_entry import equity_exit, equity_stop_target, equity_unrealized


def test_long_stop_below_target_above():
    stop, target = equity_stop_target("LONG", 100.0, 0.01, 0.02)
    assert stop == pytest.approx(99.0)
    assert target == pytest.approx(102.0)


def test_short_stop_above_target_below():
    stop, target = equity_stop_target("SHORT", 100.0, 0.01, 0.02)
    assert stop == pytest.approx(101.0)
    assert target == pytest.approx(98.0)


def test_long_exits():
    stop, target = 99.0, 102.0
    assert equity_exit("LONG", 98.9, stop, target, False, False) == (True, "STOP_LOSS")
    assert equity_exit("LONG", 102.1, stop, target, False, False) == (True, "TARGET")
    assert equity_exit("LONG", 100.0, stop, target, True, False) == (True, "STRATEGY_EXIT")
    assert equity_exit("LONG", 100.0, stop, target, False, False) == (False, "")


def test_short_exits():
    stop, target = 101.0, 98.0
    assert equity_exit("SHORT", 101.1, stop, target, False, False) == (True, "STOP_LOSS")
    assert equity_exit("SHORT", 97.9, stop, target, False, False) == (True, "TARGET")
    assert equity_exit("SHORT", 100.0, stop, target, False, True) == (True, "STRATEGY_EXIT")
    assert equity_exit("SHORT", 100.0, stop, target, False, False) == (False, "")


def test_stop_beats_target_when_both_would_trigger():
    # a gap that is past BOTH levels resolves to the protective stop first
    assert equity_exit("LONG", 90.0, 99.0, 102.0, False, False)[1] == "STOP_LOSS"


def test_unrealized_sign():
    assert equity_unrealized("LONG", 100.0, 105.0, 10) == pytest.approx(50.0)
    assert equity_unrealized("LONG", 100.0, 95.0, 10) == pytest.approx(-50.0)
    assert equity_unrealized("SHORT", 100.0, 95.0, 10) == pytest.approx(50.0)   # short profits down
    assert equity_unrealized("SHORT", 100.0, 105.0, 10) == pytest.approx(-50.0)
