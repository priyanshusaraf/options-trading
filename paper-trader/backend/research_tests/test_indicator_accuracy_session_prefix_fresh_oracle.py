"""Independent golden oracle for the corrected session-prefix assurance.

This module imports no Strategy OS product code and no earlier oracle. Event times
are completed-bar close times. The locked fixture crosses midnight, skips a market
holiday/weekend interval, includes a shortened session, and ends with a reversal.
"""
from __future__ import annotations

from fractions import Fraction


BARS = (
    ("2026-02-14T00:00:00Z", "NIGHT", "2026-02-13T23:30:00Z", "2026-02-14T01:00:00Z", "101", "106", "99", "104", "0"),
    ("2026-02-14T00:30:00Z", "NIGHT", "2026-02-13T23:30:00Z", "2026-02-14T01:00:00Z", "104", "108", "103", "107", "12"),
    ("2026-02-14T01:00:00Z", "NIGHT", "2026-02-13T23:30:00Z", "2026-02-14T01:00:00Z", "107", "109", "100", "102", "18"),
    ("2026-02-17T09:30:00Z", "SHORT", "2026-02-17T09:00:00Z", "2026-02-17T10:00:00Z", "80", "84", "77", "82", "10"),
    ("2026-02-17T10:00:00Z", "SHORT", "2026-02-17T09:00:00Z", "2026-02-17T10:00:00Z", "82", "85", "79", "80", "20"),
    ("2026-02-18T09:30:00Z", "REVERSAL", "2026-02-18T09:00:00Z", "2026-02-18T10:30:00Z", "120", "123", "116", "118", "5"),
    ("2026-02-18T10:00:00Z", "REVERSAL", "2026-02-18T09:00:00Z", "2026-02-18T10:30:00Z", "118", "126", "115", "125", "15"),
    ("2026-02-18T10:30:00Z", "REVERSAL", "2026-02-18T09:00:00Z", "2026-02-18T10:30:00Z", "125", "127", "119", "121", "10"),
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
    "OPEN": {"value": ("101", "104", "107", "80", "82", "120", "118", "125")},
    "HIGH": {"value": ("106", "108", "109", "84", "85", "123", "126", "127")},
    "LOW": {"value": ("99", "103", "100", "77", "79", "116", "115", "119")},
    "CLOSE": {"value": ("104", "107", "102", "82", "80", "118", "125", "121")},
    "OHLCV": {
        "open": ("101", "104", "107", "80", "82", "120", "118", "125"),
        "high": ("106", "108", "109", "84", "85", "123", "126", "127"),
        "low": ("99", "103", "100", "77", "79", "116", "115", "119"),
        "close": ("104", "107", "102", "82", "80", "118", "125", "121"),
        "volume": ("0", "12", "18", "10", "20", "5", "15", "10"),
    },
    "BARS_SINCE_SESSION_OPEN": {"value": ("0", "1", "2", "0", "1", "0", "1", "2")},
    "SESSION_OPEN": {"value": ("101", "101", "101", "80", "80", "120", "120", "120")},
    "SESSION_HIGH": {"value": ("106", "108", "109", "84", "85", "123", "126", "127")},
    "SESSION_LOW": {"value": ("99", "99", "99", "77", "77", "116", "115", "115")},
    "SESSION_OPEN_HIGH_LOW": {
        "open": ("101", "101", "101", "80", "80", "120", "120", "120"),
        "high": ("106", "108", "109", "84", "85", "123", "126", "127"),
        "low": ("99", "99", "99", "77", "77", "116", "115", "115"),
    },
    "DISTANCE_FROM_SESSION_HIGH_LOW": {
        "from_high": ("2", "1", "7", "2", "5", "5", "1", "6"),
        "from_low": ("5", "8", "3", "5", "3", "2", "10", "6"),
    },
    "TIME_TO_SESSION_CLOSE": {"value": ("60", "30", "0", "30", "0", "60", "30", "0")},
    "VWAP": {"value": (None, "106", "104.6", "81", "81.222222222222222222222222222222222222222222222222", "119", "121.25", "121.611111111111111111111111111111111111111111111111")},
    "OPENING_RANGE": {
        "high": (None, "108", "108", None, "85", None, "126", "126"),
        "low": (None, "99", "99", None, "77", None, "115", "115"),
        "middle": (None, "103.5", "103.5", None, "81", None, "120.5", "120.5"),
    },
    "PREVIOUS_SESSION_OHLC": {
        "open": (None, None, None, "101", "101", "80", "80", "80"),
        "high": (None, None, None, "109", "109", "85", "85", "85"),
        "low": (None, None, None, "99", "99", "77", "77", "77"),
        "close": (None, None, None, "102", "102", "80", "80", "80"),
    },
    "ANCHORED_VWAP": {"value": (None, "106", "104.6", "98.7", "92.911111111111111111111111111111111111111111111111", "94.917948717948717948717948717948717948717948717949", "99.995833333333333333333333333333333333333333333333", "102.47777777777777777777777777777777777777777777778")},
}


def columns():
    names = ("event_time", "session_id", "session_open_at", "session_close_at", "open", "high", "low", "close", "volume")
    return {name: tuple(row[position] for row in BARS) for position, name in enumerate(names)}


def previous_field(field: str):
    first = {"open": "101", "high": "109", "low": "99", "close": "102", "volume": "30"}
    second = {"open": "80", "high": "85", "low": "77", "close": "80", "volume": "30"}
    return (None, None, None, first[field], first[field], second[field], second[field], second[field])


def _weighted_fraction(*, reset_sessions: bool, anchor_position: int = 0):
    values, active = [], None
    numerator, denominator = Fraction(), 0
    for position, row in enumerate(BARS):
        if position < anchor_position:
            values.append(None)
            continue
        if reset_sessions and row[1] != active:
            active, numerator, denominator = row[1], Fraction(), 0
        high, low, close, volume = (int(row[index]) for index in (5, 6, 7, 8))
        numerator += Fraction(high + low + close, 3) * volume
        denominator += volume
        values.append(None if denominator == 0 else numerator / denominator)
    return tuple(values)


def test_locked_weighted_values_have_independent_rational_proof():
    for name, actual in (
        ("VWAP", _weighted_fraction(reset_sessions=True)),
        ("ANCHORED_VWAP", _weighted_fraction(reset_sessions=False, anchor_position=1)),
    ):
        for fraction, text in zip(actual, EXPECTED[name]["value"]):
            if text is None:
                assert fraction is None
            else:
                assert abs(float(fraction) - float(text)) <= 1e-12


def test_oracle_closes_complete_decision_output_and_mask_universe():
    candidates = set(EXPECTED) | {"PREVIOUS_SESSION_FIELDS"}
    assert len(candidates) == 17
    assert len(REFUSALS) == 14
    assert candidates.isdisjoint(REFUSALS)
    assert len(candidates | set(REFUSALS)) == 31
    assert all(len(values) == len(BARS) for outputs in EXPECTED.values() for values in outputs.values())
    assert all(len(previous_field(field)) == len(BARS) for field in ("open", "high", "low", "close", "volume"))
