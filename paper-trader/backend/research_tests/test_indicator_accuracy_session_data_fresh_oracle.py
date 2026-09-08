"""Fresh, product-independent session-data oracle.

The fixture, expected arrays, and Decimal recurrences in this module do not import
Strategy OS product code or any earlier session-data oracle.  Event timestamps are
completed-bar close times.  The fixture contains an overnight session, a holiday
gap, a shortened session, and a reversal session.
"""
from __future__ import annotations

from decimal import Decimal, localcontext


BARS = (
    ("2026-01-02T22:30:00Z", "OVERNIGHT", "2026-01-02T22:00:00Z", "2026-01-02T23:30:00Z", "40", "44", "39", "43", "0"),
    ("2026-01-02T23:00:00Z", "OVERNIGHT", "2026-01-02T22:00:00Z", "2026-01-02T23:30:00Z", "43", "47", "42", "46", "12"),
    ("2026-01-02T23:30:00Z", "OVERNIGHT", "2026-01-02T22:00:00Z", "2026-01-02T23:30:00Z", "46", "48", "41", "42", "18"),
    ("2026-01-06T13:30:00Z", "SHORT", "2026-01-06T13:00:00Z", "2026-01-06T14:00:00Z", "70", "75", "68", "74", "10"),
    ("2026-01-06T14:00:00Z", "SHORT", "2026-01-06T13:00:00Z", "2026-01-06T14:00:00Z", "74", "78", "72", "73", "20"),
    ("2026-01-07T09:30:00Z", "REVERSAL", "2026-01-07T09:00:00Z", "2026-01-07T10:30:00Z", "55", "57", "50", "51", "5"),
    ("2026-01-07T10:00:00Z", "REVERSAL", "2026-01-07T09:00:00Z", "2026-01-07T10:30:00Z", "51", "60", "49", "59", "15"),
    ("2026-01-07T10:30:00Z", "REVERSAL", "2026-01-07T09:00:00Z", "2026-01-07T10:30:00Z", "59", "61", "52", "54", "10"),
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
    "OPEN": {"value": ("40", "43", "46", "70", "74", "55", "51", "59")},
    "HIGH": {"value": ("44", "47", "48", "75", "78", "57", "60", "61")},
    "LOW": {"value": ("39", "42", "41", "68", "72", "50", "49", "52")},
    "CLOSE": {"value": ("43", "46", "42", "74", "73", "51", "59", "54")},
    "OHLCV": {
        "open": ("40", "43", "46", "70", "74", "55", "51", "59"),
        "high": ("44", "47", "48", "75", "78", "57", "60", "61"),
        "low": ("39", "42", "41", "68", "72", "50", "49", "52"),
        "close": ("43", "46", "42", "74", "73", "51", "59", "54"),
        "volume": ("0", "12", "18", "10", "20", "5", "15", "10"),
    },
    "BARS_SINCE_SESSION_OPEN": {"value": ("0", "1", "2", "0", "1", "0", "1", "2")},
    "SESSION_OPEN": {"value": ("40", "40", "40", "70", "70", "55", "55", "55")},
    "SESSION_HIGH": {"value": ("44", "47", "48", "75", "78", "57", "60", "61")},
    "SESSION_LOW": {"value": ("39", "39", "39", "68", "68", "50", "49", "49")},
    "SESSION_OPEN_HIGH_LOW": {
        "open": ("40", "40", "40", "70", "70", "55", "55", "55"),
        "high": ("44", "47", "48", "75", "78", "57", "60", "61"),
        "low": ("39", "39", "39", "68", "68", "50", "49", "49"),
    },
    "DISTANCE_FROM_SESSION_HIGH_LOW": {
        "from_high": ("1", "1", "6", "1", "5", "6", "1", "7"),
        "from_low": ("4", "7", "3", "6", "5", "1", "10", "5"),
    },
    "TIME_TO_SESSION_CLOSE": {"value": ("60", "30", "0", "30", "0", "60", "30", "0")},
    "VWAP": {"value": (
        None, "45", "44.2", "72.333333333333333333333333333333333333333333333333",
        "73.666666666666666666666666666666666666666666666667",
        "52.666666666666666666666666666666666666666666666668",
        "55.166666666666666666666666666666666666666666666665",
        "55.333333333333333333333333333333333333333333333333",
    )},
    "OPENING_RANGE": {
        "high": (None, "47", "47", None, "78", None, "60", "60"),
        "low": (None, "39", "39", None, "68", None, "49", "49"),
        "middle": (None, "43", "43", None, "73", None, "54.5", "54.5"),
    },
    "PREVIOUS_SESSION_OHLC": {
        "open": (None, None, None, "40", "40", "70", "70", "70"),
        "high": (None, None, None, "48", "48", "78", "78", "78"),
        "low": (None, None, None, "39", "39", "68", "68", "68"),
        "close": (None, None, None, "42", "42", "73", "73", "73"),
    },
    "ANCHORED_VWAP": {"value": (
        None, "45", "44.2", "51.233333333333333333333333333333333333333333333332",
        "58.933333333333333333333333333333333333333333333333",
        "58.451282051282051282051282051282051282051282051282",
        "57.991666666666666666666666666666666666666666666666",
        "57.733333333333333333333333333333333333333333333333",
    )},
}


def columns():
    names = ("event_time", "session_id", "session_open_at", "session_close_at", "open", "high", "low", "close", "volume")
    return {name: tuple(row[index] for row in BARS) for index, name in enumerate(names)}


def previous_field(field):
    first = {"open": "40", "high": "48", "low": "39", "close": "42", "volume": "30"}
    second = {"open": "70", "high": "78", "low": "68", "close": "73", "volume": "30"}
    return (None, None, None, first[field], first[field], second[field], second[field], second[field])


def independent_weighted_values(*, reset_sessions, anchor_position=0):
    result, active = [], None
    numerator = denominator = Decimal(0)
    with localcontext() as context:
        context.prec = 60
        for position, row in enumerate(BARS):
            if position < anchor_position:
                result.append(None)
                continue
            if reset_sessions and row[1] != active:
                active, numerator, denominator = row[1], Decimal(0), Decimal(0)
            high, low, close, volume = map(Decimal, row[5:9])
            numerator += ((high + low + close) / Decimal(3)) * volume
            denominator += volume
            result.append(None if denominator == 0 else numerator / denominator)
    return tuple(result)


def test_fresh_decimal_recurrences_match_locked_constants():
    for name, actual in (
        ("VWAP", independent_weighted_values(reset_sessions=True)),
        ("ANCHORED_VWAP", independent_weighted_values(reset_sessions=False, anchor_position=1)),
    ):
        for calculated, text in zip(actual, EXPECTED[name]["value"]):
            assert calculated is None if text is None else abs(calculated - Decimal(text)) <= Decimal("1e-47")


def test_fresh_oracle_closes_all_decisions_outputs_and_masks():
    candidates = set(EXPECTED) | {"PREVIOUS_SESSION_FIELDS"}
    assert len(candidates) == 17 and len(REFUSALS) == 14
    assert candidates.isdisjoint(REFUSALS) and len(candidates | set(REFUSALS)) == 31
    assert all(len(values) == len(BARS) for outputs in EXPECTED.values() for values in outputs.values())
    assert all(len(previous_field(field)) == len(BARS) for field in ("open", "high", "low", "close", "volume"))
