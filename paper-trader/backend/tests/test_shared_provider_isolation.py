"""The shared market provider must not carry state from one test into the next.

`get_provider()` is a process-wide singleton, and two pieces of its state are mutable in
ways that change what *other* tests observe:

  * `now` — the pinned-clock idiom (`provider.now = lambda: <fixed datetime>`), used at
    sixteen call sites across five wiring tests;
  * `_cursor` — the synthetic market's position, moved by `advance()`, which `now()` reads
    (`self._times[self._cursor]`).

Both make the clock a function of the whole run rather than of the test. That has bitten
twice. The second time (2026-08-08) `test_notifies_on_auto_open` passed under
`pytest tests` and failed under `pytest tests research_tests` on a ONE-position difference:

    cursor=1149 -> 2025-03-05 15:15  (after the 09:30 entry gate — entry taken)
    cursor=1150 -> 2025-03-06 09:15  (before it — "ENTRY WINDOW closed")

The cursor sat on a session boundary, so one extra `advance()` anywhere earlier rolled the
clock to the next morning. The failure pointed at an innocent test, and suite greenness
became a function of test order — which an exact-head CI contract cannot tolerate.

These tests are ORDER-DEPENDENT WITHIN THIS FILE and that is the point: the first mutates
the shared state, the second asserts the mutation did not survive. pytest runs tests in
definition order within a module, so the pairing holds.
"""
from __future__ import annotations

import datetime as dt

from app.providers.factory import get_provider

_OBSERVED: dict[str, object] = {}

_PINNED = dt.datetime(2025, 3, 5, 9, 20)   # in-session but before the 09:30 entry window


def test_a_test_may_advance_the_shared_market():
    """Restoration must not break the legitimate use: stepping the market and observing it
    inside the test that did the stepping."""
    p = get_provider()
    start = p._cursor
    _OBSERVED["cursor"] = start
    for _ in range(5):
        assert p.advance() is True
    assert p._cursor == start + 5, "advance() must still move the market within a test"


def test_the_advance_does_not_survive_into_the_next_test():
    p = get_provider()
    assert p._cursor == _OBSERVED["cursor"], (
        f"the shared market cursor leaked: {_OBSERVED['cursor']} -> {p._cursor}. "
        f"now() reads _times[_cursor], so this silently moves the clock for every "
        f"subsequent test and makes suite greenness order-dependent"
    )


def test_a_test_may_pin_the_clock():
    p = get_provider()
    _OBSERVED["now_was_pinned"] = "now" in p.__dict__
    p.now = lambda: _PINNED
    assert p.now() == _PINNED


def test_the_pinned_clock_does_not_survive_into_the_next_test():
    p = get_provider()
    assert "now" in p.__dict__ if _OBSERVED["now_was_pinned"] else "now" not in p.__dict__, (
        "a pinned clock leaked past the test that set it; with `now` frozen before 09:30 "
        "every later entry is refused by the entry-window gate"
    )
    assert p.now() != _PINNED, "the shared clock is still reading the pinned value"
