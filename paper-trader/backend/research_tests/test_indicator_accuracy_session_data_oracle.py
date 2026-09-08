"""Independent Decimal/session oracle for the unpublished session-data wave.

This module intentionally imports no Strategy OS product math, session-data helper,
resolver, compiler, or implementation-owner test.  Its fixture and expected arrays
were frozen in the assurance run before the product implementation was inspected.
"""
from __future__ import annotations

from decimal import Decimal, getcontext


getcontext().prec = 60

COMPLETE_BARS = (
    ("2026-08-26T18:30:00Z", "S1", "2026-08-26T18:00:00Z", "2026-08-26T19:30:00Z", "100", "104", "99", "102", "10"),
    ("2026-08-26T19:00:00Z", "S1", "2026-08-26T18:00:00Z", "2026-08-26T19:30:00Z", "102", "106", "101", "105", "20"),
    ("2026-08-26T19:30:00Z", "S1", "2026-08-26T18:00:00Z", "2026-08-26T19:30:00Z", "105", "107", "103", "104", "30"),
    ("2026-08-28T22:30:00Z", "S2", "2026-08-28T22:00:00Z", "2026-08-28T23:30:00Z", "110", "112", "108", "111", "0"),
    ("2026-08-28T23:00:00Z", "S2", "2026-08-28T22:00:00Z", "2026-08-28T23:30:00Z", "111", "115", "110", "114", "25"),
    ("2026-08-28T23:30:00Z", "S2", "2026-08-28T22:00:00Z", "2026-08-28T23:30:00Z", "114", "116", "112", "113", "15"),
)

REFUSALS = {
    "ASK": "QUOTE_BINDING_UNAVAILABLE",
    "BID": "QUOTE_BINDING_UNAVAILABLE",
    "BOOK_DEPTH": "BOOK_BINDING_UNAVAILABLE",
    "DTE": "EXPIRY_BINDING_UNAVAILABLE",
    "EXPIRY_CALENDAR": "EXPIRY_BINDING_UNAVAILABLE",
    "INSTRUMENT_METADATA": "METADATA_BINDING_UNAVAILABLE",
    "LTP": "TRADE_BINDING_UNAVAILABLE",
    "MARKET_CLOCK": "CLOCK_BINDING_UNAVAILABLE",
    "MID": "QUOTE_BINDING_UNAVAILABLE",
    "OPEN_INTEREST": "OI_BINDING_UNAVAILABLE",
    "RESAMPLING": "RESAMPLING_BINDING_UNAVAILABLE",
    "SESSION_CALENDAR": "CALENDAR_BINDING_UNAVAILABLE",
    "SPREAD": "QUOTE_BINDING_UNAVAILABLE",
    "TIMEFRAME": "TIMEFRAME_BINDING_UNAVAILABLE",
}

EXPECTED = {
    "OPEN": {"value": ("100", "102", "105", "110", "111", "114")},
    "HIGH": {"value": ("104", "106", "107", "112", "115", "116")},
    "LOW": {"value": ("99", "101", "103", "108", "110", "112")},
    "CLOSE": {"value": ("102", "105", "104", "111", "114", "113")},
    "OHLCV": {
        "open": ("100", "102", "105", "110", "111", "114"),
        "high": ("104", "106", "107", "112", "115", "116"),
        "low": ("99", "101", "103", "108", "110", "112"),
        "close": ("102", "105", "104", "111", "114", "113"),
        "volume": ("10", "20", "30", "0", "25", "15"),
    },
    "BARS_SINCE_SESSION_OPEN": {"value": ("0", "1", "2", "0", "1", "2")},
    "SESSION_OPEN": {"value": ("100", "100", "100", "110", "110", "110")},
    "SESSION_HIGH": {"value": ("104", "106", "107", "112", "115", "116")},
    "SESSION_LOW": {"value": ("99", "99", "99", "108", "108", "108")},
    "SESSION_OPEN_HIGH_LOW": {
        "open": ("100", "100", "100", "110", "110", "110"),
        "high": ("104", "106", "107", "112", "115", "116"),
        "low": ("99", "99", "99", "108", "108", "108"),
    },
    "DISTANCE_FROM_SESSION_HIGH_LOW": {
        "from_high": ("2", "1", "3", "1", "1", "3"),
        "from_low": ("3", "6", "5", "3", "6", "5"),
    },
    "TIME_TO_SESSION_CLOSE": {"value": ("60", "30", "0", "60", "30", "0")},
    "VWAP": {"value": (
        "101.666666666666666666666666666666666666666666666666666666667",
        "103.222222222222222222222222222222222222222222222222222222222",
        "103.944444444444444444444444444444444444444444444444444444444",
        None, "113", "113.25",
    )},
    "OPENING_RANGE": {
        "high": (None, "106", "106", None, "115", "115"),
        "low": (None, "99", "99", None, "108", "108"),
        "middle": (None, "102.5", "102.5", None, "111.5", "111.5"),
    },
    "PREVIOUS_SESSION_OHLC": {
        "open": (None, None, None, "100", "100", "100"),
        "high": (None, None, None, "107", "107", "107"),
        "low": (None, None, None, "99", "99", "99"),
        "close": (None, None, None, "104", "104", "104"),
    },
    "ANCHORED_VWAP": {"value": (
        None, "104", "104.4", "104.4",
        "107.266666666666666666666666666666666666666666666666666666667",
        "108.333333333333333333333333333333333333333333333333333333333",
    )},
}


def columns():
    names = ("event_time", "session_id", "session_open_at", "session_close_at", "open", "high", "low", "close", "volume")
    return {name: tuple(row[index] for row in COMPLETE_BARS) for index, name in enumerate(names)}


def previous_field_expected(field):
    values = {"open": "100", "high": "107", "low": "99", "close": "104", "volume": "60"}
    return (None, None, None, values[field], values[field], values[field])


def session_vwap(rows):
    values = []
    session = None
    total_pv = total_volume = Decimal(0)
    for row in rows:
        if row[1] != session:
            session, total_pv, total_volume = row[1], Decimal(0), Decimal(0)
        high, low, close, volume = map(Decimal, row[5:9])
        total_pv += ((high + low + close) / Decimal(3)) * volume
        total_volume += volume
        values.append(None if total_volume == 0 else total_pv / total_volume)
    return tuple(values)


def anchored_vwap(rows, anchor_index=1):
    values = [None] * anchor_index
    total_pv = total_volume = Decimal(0)
    for row in rows[anchor_index:]:
        high, low, close, volume = map(Decimal, row[5:9])
        total_pv += ((high + low + close) / Decimal(3)) * volume
        total_volume += volume
        values.append(None if total_volume == 0 else total_pv / total_volume)
    return tuple(values)


def test_decimal_oracle_matches_frozen_expected_arrays():
    for actual, expected in zip(session_vwap(COMPLETE_BARS), EXPECTED["VWAP"]["value"]):
        assert actual is None if expected is None else abs(actual - Decimal(expected)) <= Decimal("1e-27")
    for actual, expected in zip(anchored_vwap(COMPLETE_BARS), EXPECTED["ANCHORED_VWAP"]["value"]):
        assert actual is None if expected is None else abs(actual - Decimal(expected)) <= Decimal("1e-27")


def test_oracle_universe_is_exact_and_refusals_have_no_placeholder_expectation():
    candidates = set(EXPECTED) | {"PREVIOUS_SESSION_FIELDS"}
    assert len(candidates) == 17
    assert len(REFUSALS) == 14
    assert candidates.isdisjoint(REFUSALS)
    assert len(candidates | set(REFUSALS)) == 31
