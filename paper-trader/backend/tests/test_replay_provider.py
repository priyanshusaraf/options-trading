"""Replay mode — re-run a recorded day, and never see a bar that had not printed.

When the engine does something surprising on a live day, the only honest way to
understand it is to feed it that day again, identically. A mock market cannot
reproduce a real Monday.

Everything here exists to defend ONE property: **no look-ahead**. A replay that
leaked future bars would make the engine appear to make decisions it could never
have made live — and it would look like a perfectly successful replay while
doing it, which is what makes it worth this many tests.
"""
from __future__ import annotations

import datetime as dt
import json

import pytest

from app.providers.replay import ReplayProvider, load_session


class _Inst:
    key = "NIFTY"
    spot_exchange = "NSE"


def _write(tmp_path, rows=6, key="NIFTY", start_hour=10):
    base = dt.datetime(2026, 8, 3, start_hour, 0)
    data = {key: [{"ts": (base + dt.timedelta(minutes=15 * i)).isoformat(),
                   "open": 100 + i, "high": 101 + i, "low": 99 + i,
                   "close": 100.5 + i, "volume": 1000 + i} for i in range(rows)]}
    p = tmp_path / "session.json"
    p.write_text(json.dumps(data))
    return str(p)


# ── no look-ahead ───────────────────────────────────────────────────────────

def test_history_never_includes_a_future_bar(tmp_path):
    """The whole safety argument. At every cursor position the engine must see
    exactly the bars that had printed by then."""
    p = ReplayProvider(_write(tmp_path, rows=6))
    for expected in range(1, 7):
        assert len(p.get_candles(_Inst(), "15minute", 30)) == expected, \
            f"cursor {expected - 1} exposed the wrong number of bars"
        if not p.advance():
            break


def test_the_last_visible_bar_is_the_current_one(tmp_path):
    p = ReplayProvider(_write(tmp_path, rows=5))
    p.advance(); p.advance()
    bars = p.get_candles(_Inst(), "15minute", 30)
    assert bars[-1].ts == p.now()


def test_the_ltp_is_the_current_bar_close_not_the_final_one(tmp_path):
    """Returning the recording's last close would be look-ahead wearing a
    convenience method's clothes."""
    p = ReplayProvider(_write(tmp_path, rows=6))
    first = p.get_ltp(_Inst())
    p.advance()
    assert p.get_ltp(_Inst()) != first


# ── the clock ───────────────────────────────────────────────────────────────

def test_now_is_the_recorded_time_not_wall_clock(tmp_path):
    """Replaying a Monday against a Saturday's clock would put every bar outside
    market hours and change the engine's behaviour completely."""
    p = ReplayProvider(_write(tmp_path))
    assert p.now() == dt.datetime(2026, 8, 3, 10, 0)
    assert p.now().year == 2026


def test_advancing_moves_the_clock_forward_by_a_bar(tmp_path):
    p = ReplayProvider(_write(tmp_path))
    before = p.now()
    p.advance()
    assert p.now() > before


def test_advance_returns_false_at_the_end(tmp_path):
    p = ReplayProvider(_write(tmp_path, rows=3))
    assert p.advance() is True
    assert p.advance() is True
    assert p.advance() is False, "ran past the end of the recording"


def test_the_clock_does_not_run_off_the_end(tmp_path):
    p = ReplayProvider(_write(tmp_path, rows=3))
    while p.advance():
        pass
    assert p.now() is not None


# ── it cannot trade ─────────────────────────────────────────────────────────

def test_replay_can_never_authenticate(tmp_path):
    """make_broker() refuses a real LiveBroker without an authenticated kite
    provider, so this single False is what stops a replay placing an order."""
    assert ReplayProvider(_write(tmp_path)).is_authenticated() is False


def test_replay_cannot_price_a_future(tmp_path):
    """A recording carries the underlying series; no futures feed was captured.
    Inventing a basis would be fabricated data in a tool whose entire purpose is
    fidelity to what actually happened."""
    assert ReplayProvider(_write(tmp_path)).get_futures_ltp(_Inst(), dt.date(2026, 8, 27)) is None


# ── loading ─────────────────────────────────────────────────────────────────

def test_out_of_order_rows_are_sorted(tmp_path):
    """A recording assembled from several exports can arrive interleaved, and an
    out-of-order series would invert the meaning of 'up to the cursor'."""
    base = dt.datetime(2026, 8, 3, 10, 0)
    rows = [{"ts": (base + dt.timedelta(minutes=15 * i)).isoformat(),
             "open": 1, "high": 2, "low": 0.5, "close": 1.5} for i in (3, 0, 2, 1)]
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"NIFTY": rows}))
    loaded = load_session(str(p))["NIFTY"]
    assert [c.ts for c in loaded] == sorted(c.ts for c in loaded)


def test_multiple_instruments_share_one_timeline(tmp_path):
    """Instruments with different gaps must stay aligned to one clock rather than
    each advancing at its own rate."""
    base = dt.datetime(2026, 8, 3, 10, 0)
    data = {
        "NIFTY": [{"ts": (base + dt.timedelta(minutes=15 * i)).isoformat(),
                   "open": 1, "high": 2, "low": 0.5, "close": 1.5} for i in range(4)],
        "BANKNIFTY": [{"ts": (base + dt.timedelta(minutes=15 * i)).isoformat(),
                       "open": 1, "high": 2, "low": 0.5, "close": 1.5} for i in (0, 2)],
    }
    f = tmp_path / "s.json"
    f.write_text(json.dumps(data))
    p = ReplayProvider(str(f))
    assert p.progress == (1, 4)


def test_an_empty_recording_does_not_crash(tmp_path):
    f = tmp_path / "empty.json"
    f.write_text(json.dumps({}))
    p = ReplayProvider(str(f))
    assert p.get_candles(_Inst(), "15minute", 30) == []
    assert p.advance() is False


# ── determinism ─────────────────────────────────────────────────────────────

def test_two_replays_of_the_same_file_are_identical(tmp_path):
    """The point of a replay: run it as many times as you need and get the same
    answer, or it cannot be used to isolate a bug."""
    path = _write(tmp_path, rows=5)

    def walk():
        p = ReplayProvider(path)
        seen = []
        while True:
            seen.append((p.now(), p.get_ltp(_Inst())))
            if not p.advance():
                return seen

    assert walk() == walk()
