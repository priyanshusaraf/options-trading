"""What a caller ASKED for cannot depend on when they asked.

The owner's requirement is that an unchanged request reproduces an unchanged result, because
the product's claims rest on it. One thing broke that, and it was not floating point.

`_requested_window` is the request half of a dataset address, and it carried `fetch_days`.
For a custom `[start, end]` window `_fetch_days` computes `(today - start).days + 2` — the
provider only sells trailing history, so *how far back to reach* depends on the current date.
Identical caller parameters therefore produced a **different address tomorrow**:

* an unpinned rerun silently recomputed and could report different numbers, which reads as
  strategy drift rather than as a moving window;
* a pin resolved yesterday no longer matched today's request, so it failed closed and a
  "pinned rerun" became a run of all-error cells.

`fetch_days` is a fact about *how we fetched*, not about *what was requested*. What actually
came back is already recorded, exactly and separately, in the effective window (`first_ts`,
`last_ts`, `bars`, `clamped`) — which is where a genuinely larger trailing window correctly
shows up as a new dataset. Identity keeps the caller's request; the fetch mechanic stays out
of it.

Note what is deliberately NOT claimed here: a `"max"` or trailing-lookback window legitimately
grows as the market produces bars, and that must keep minting a new address. This file pins
request identity, not data identity.
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.backtest import sweep


class _FrozenDate(dt.date):
    """A `datetime.date` whose `today()` is pinned. Subclassing keeps every other
    behaviour (fromisoformat, arithmetic, comparison) exactly as the real class."""

    _pinned = dt.date(2026, 8, 10)

    @classmethod
    def today(cls) -> dt.date:
        return cls._pinned


@pytest.fixture
def at_date(monkeypatch):
    def _set(iso: str):
        class _D(_FrozenDate):
            _pinned = dt.date.fromisoformat(iso)

        class _Shim:
            date = _D
            datetime = dt.datetime
            timedelta = dt.timedelta

        monkeypatch.setattr(sweep, "dt", _Shim)
    return _set


# The start date must sit INSIDE the interval ceiling for this to bite. A window older
# than `MAX_DAYS` clamps `fetch_days` to the cap and is accidentally stable — the first
# draft of this file used 2026-01-05, which clamps at 200 and passed for a reason that had
# nothing to do with the defect. 2026-07-15 is 26 days before the pinned today, well under
# the 200-day 15-minute ceiling, so the span genuinely moves one day per day.
CUSTOM = {"lookback_days": None, "start": "2026-07-15", "end": "2026-07-30"}


def test_a_custom_window_request_identity_does_not_move_with_the_calendar(at_date):
    at_date("2026-08-10")
    today = sweep._requested_window("15minute", CUSTOM)
    at_date("2026-08-11")
    tomorrow = sweep._requested_window("15minute", CUSTOM)
    at_date("2026-08-24")
    much_later = sweep._requested_window("15minute", CUSTOM)

    assert today == tomorrow == much_later, (
        "the same custom-window request resolved to different identities on different days; "
        "a pinned rerun fails closed and an unpinned rerun looks like strategy drift")


def test_request_identity_carries_what_the_caller_actually_asked_for(at_date):
    at_date("2026-08-10")
    win = sweep._requested_window("15minute", CUSTOM)
    assert win["start"] == "2026-07-15"
    assert win["end"] == "2026-07-30"
    assert win["lookback_days"] is None


@pytest.mark.parametrize("win", [
    {"lookback_days": 365, "start": None, "end": None},
    {"lookback_days": None, "start": None, "end": None},          # "max"
])
def test_lookback_and_max_windows_were_already_dateless_and_stay_so(at_date, win):
    """These never depended on today. Pinned so the fix cannot regress them either."""
    at_date("2026-08-10")
    a = sweep._requested_window("15minute", win)
    at_date("2027-02-01")
    b = sweep._requested_window("15minute", win)
    assert a == b


def test_the_fetch_span_still_reaches_back_far_enough(at_date):
    """The mechanic must keep working — identity dropping it must not change fetching.

    A window starting 100 days ago still has to ask the provider for ~100 days of trailing
    history, clamped to the interval ceiling. If this regresses, custom windows quietly return
    nothing and every cell reports 'insufficient history'.
    """
    at_date("2026-08-10")
    span = sweep._fetch_days("15minute", None, "2026-05-02", "2026-06-01")
    assert span >= 100, f"fetch span {span} is too short to reach a 100-day-old start"
    assert span <= sweep.MAX_DAYS["15minute"]

    # and it MUST still move with the calendar — that is its job
    at_date("2026-08-24")
    later = sweep._fetch_days("15minute", None, "2026-05-02", "2026-06-01")
    assert later > span, "the fetch span must grow as the start date recedes into the past"
