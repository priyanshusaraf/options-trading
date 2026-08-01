"""Duplicate-order prevention — the invariant, not the implementation.

Two guards exist: `key in held` stops a second position on an instrument, and
`signal_already_evaluated` stops the same completed bar being acted on twice.
Both read correctly. Neither had a test asserting the property they exist to
provide, which is a different thing from being correct — a later refactor can
preserve the code shape and lose the guarantee.

The invariant: **however many times the entry path runs on the same signal, at
most one position exists per instrument.** The risk lane calls into this every
tick; a duplicate is not a cosmetic bug, it is double the intended size with
half the intended stop coverage.
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.db.session import init_db
from app.engine.runner import EngineRunner

NOW = dt.datetime(2026, 8, 3, 11, 0)


@pytest.fixture
def runner():
    init_db(reset=True)
    r = EngineRunner()
    r.armed = True
    cap = r.broker.capital()
    cap.initial_capital = 500_000.0
    cap.cash = 500_000.0
    r.broker.s.commit()
    yield r
    try:
        r.broker.s.close()
    except Exception:
        pass


def _real_state(r):
    """Populate state through the REAL scan, not a hand-built dict.

    An earlier cut synthesised `{"signal": "LONG_ENTRY", ...}` and hit
    KeyError: 'z' — process_entries reads more of the signal frame than a
    plausible-looking stub provides. Driving the actual scan means the test
    exercises the guards against the state shape they really see, which is the
    only version worth asserting on.
    """
    r.scan_signals()


def test_running_entries_repeatedly_opens_at_most_one_position(runner):
    """The core invariant. process_entries is reached every signal tick."""
    _real_state(runner)
    for _ in range(5):
        runner.process_entries()
    keys = [p.instrument_key for p in runner.broker.open_positions()]
    assert len(keys) == len(set(keys)), f"duplicate positions: {keys}"
    assert keys.count("NIFTY") <= 1


def test_a_held_instrument_is_not_re_entered(runner):
    _real_state(runner)
    runner.process_entries()
    before = len(runner.broker.open_positions())
    runner.process_entries()
    assert len(runner.broker.open_positions()) == before


def test_the_same_bar_is_not_acted_on_twice(runner):
    """The fresh-signal guard: a completed bar produces at most one entry
    decision, even if the loop sees it repeatedly."""
    from app.engine.runner import signal_already_evaluated
    bar = 1_754_200_000
    assert signal_already_evaluated(bar, None) is False
    assert signal_already_evaluated(bar, bar) is True
    assert signal_already_evaluated(bar + 900, bar) is False


def test_disarmed_opens_nothing_however_many_times_it_runs(runner):
    runner.armed = False
    _real_state(runner)
    for _ in range(3):
        runner.process_entries()
    assert runner.broker.open_positions() == []


def test_the_ledger_survives_repeated_entry_attempts(runner):
    """A duplicate that was booked and then rejected would leave cash short."""
    _real_state(runner)
    for _ in range(5):
        runner.process_entries()
    cap = runner.broker.capital()
    open_cost = sum(p.entry_cost for p in runner.broker.open_positions())
    drift = cap.cash - (cap.initial_capital + cap.realized_pnl - open_cost)
    assert drift == pytest.approx(0.0, abs=1e-6)
