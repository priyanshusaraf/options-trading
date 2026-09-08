"""Kite instrument dump normalization.

Kite's MCX dump reports lot_size=1 for commodity option rows even though the
premium must be costed against the contract unit configured in our universe.
It also names copper contracts as COPPER, not COPPERM.
"""
from __future__ import annotations

import datetime as dt

import pytest

from app.core.instruments import Instrument
from app.providers.kite import KiteProvider
from app.providers.base import ProviderReadError


def _provider(rows):
    p = KiteProvider.__new__(KiteProvider)
    p._fut_cache = {}
    p._tick_cache = {}
    p._instruments = lambda exchange: rows
    p.get_ltp = lambda inst: 7100.0
    p._quote = lambda keys: {
        k: {
            "last_price": 365.0,
            "volume": 1000,
            "oi": 5000,
            "depth": {
                "buy": [{"price": 364.0, "quantity": 300}],
                "sell": [{"price": 366.0, "quantity": 125}],
            },
        }
        for k in keys
    }
    return p


def test_mcx_option_chain_uses_configured_contract_units_when_kite_lot_is_one():
    expiry = dt.date.today() + dt.timedelta(days=14)
    rows = [
        {
            "instrument_token": 1,
            "tradingsymbol": "CRUDEOIL26JUL7100CE",
            "name": "CRUDEOIL",
            "instrument_type": "CE",
            "expiry": expiry,
            "strike": 7100.0,
            "lot_size": 1,
        }
    ]
    inst = Instrument(
        "CRUDEOIL", "CRUDE OIL", "MCX", "MCX", "CRUDEOIL", "CRUDEOIL",
        lot_size=100, strike_step=50, priority=4, mock_spot=6500, mock_vol=0.30,
    )

    chain = _provider(rows).get_option_chain(inst)

    assert chain is not None
    assert chain.quotes[0].lot_size == 100
    assert chain.quotes[0].bid_qty == 300
    assert chain.quotes[0].ask_qty == 125


def test_mcx_near_future_falls_back_from_mini_suffix_to_base_name():
    expiry = dt.date.today() + dt.timedelta(days=14)
    rows = [
        {
            "instrument_token": 99,
            "tradingsymbol": "COPPER26JULFUT",
            "name": "COPPER",
            "instrument_type": "FUT",
            "expiry": expiry,
            "strike": 0.0,
            "lot_size": 1,
        }
    ]
    inst = Instrument(
        "COPPERM", "COPPER MINI", "MCX", "MCX", "COPPERM", "COPPERM",
        lot_size=250, strike_step=5, priority=8, mock_spot=850, mock_vol=0.20,
    )

    fut = _provider(rows)._near_future(inst)

    assert fut is not None
    assert fut["tradingsymbol"] == "COPPER26JULFUT"


# ── 2026-07-15: per-instrument tick size, sourced from the Kite instrument dump ────
# root cause of the LT/MARUTI SL-M failures: every trigger was rounded to a hardcoded
# 0.05 grid. The real grid lives in the dump's `tick_size` column, per tradingsymbol.
def test_tick_size_reads_the_real_grid_from_the_instrument_dump():
    rows = [
        {"tradingsymbol": "LT", "tick_size": 0.10},
        {"tradingsymbol": "MARUTI", "tick_size": 1.0},
    ]
    p = _provider(rows)
    assert p.tick_size("LT", "NSE") == 0.10
    assert p.tick_size("MARUTI", "NSE") == 1.0


def test_tick_size_falls_back_to_0_05_for_an_unknown_symbol():
    p = _provider([{"tradingsymbol": "LT", "tick_size": 0.10}])
    assert p.tick_size("SOMETHING_ELSE", "NSE") == 0.05


def test_tick_size_falls_back_to_0_05_when_the_dump_is_empty():
    """Mock provider / not-yet-loaded dump -> the safe default, not a crash."""
    p = _provider([])
    assert p.tick_size("LT", "NSE") == 0.05


def test_tick_size_is_cached_per_session():
    """The dump lookup must not be re-scanned on every call — cache per
    (exchange, tradingsymbol) for the session."""
    calls = {"n": 0}
    rows = [{"tradingsymbol": "LT", "tick_size": 0.10}]
    p = _provider(rows)

    def counting(exchange):
        calls["n"] += 1
        return rows
    p._instruments = counting

    assert p.tick_size("LT", "NSE") == 0.10
    assert p.tick_size("LT", "NSE") == 0.10
    assert calls["n"] == 1


def test_tick_size_does_not_poison_the_cache_on_a_transient_dump_failure():
    """A transient dump failure (not-yet-authenticated / API blip) makes
    `_instruments` degrade to []. If the resulting 0.05 fallback were cached, the
    REAL tick would never be re-queried for the rest of the session — silently
    reproducing the exact 2026-07-15 LT/MARUTI incident (this time the dump loads
    fine on retry, but the stale cached fallback would still win). The fallback
    from an empty/failed dump must NOT be cached; once the dump loads, the real
    tick must be returned."""
    calls = {"n": 0}

    def failing_then_loaded(exchange):
        calls["n"] += 1
        if calls["n"] == 1:
            return []                              # transient failure -> degrades to []
        return [{"tradingsymbol": "LT", "tick_size": 0.10}]   # dump loads on retry

    p = _provider([])
    p._instruments = failing_then_loaded
    assert p.tick_size("LT", "NSE") == 0.05        # first call: uncached fallback
    assert p.tick_size("LT", "NSE") == 0.10        # second call: real tick, not stale 0.05
    assert calls["n"] == 2                          # NOT short-circuited by a poisoned cache


@pytest.mark.parametrize("interval,seconds", [
    ("minute", 60), ("3minute", 180), ("5minute", 300), ("10minute", 600),
    ("15minute", 900), ("30minute", 1800), ("60minute", 3600), ("day", 86400),
])
@pytest.mark.parametrize("offset,expected", [(-1, 0), (0, 1), (1, 1), (172800, 1)])
def test_kite_history_keeps_final_bar_only_after_completion(interval, seconds, offset, expected):
    from app.core.instruments import get_instrument
    start = dt.datetime(2026, 9, 4, tzinfo=dt.timezone(dt.timedelta(hours=5, minutes=30)))
    row = {"date": start, "open": 100, "high": 102, "low": 99, "close": 101, "volume": 10}
    provider = _provider([])
    provider._underlying_token = lambda _inst: 123
    provider._historical = lambda *_args: [row]
    provider.now = lambda: (start + dt.timedelta(seconds=seconds + offset)).replace(tzinfo=None)
    bars = provider.get_candles(get_instrument("NIFTY"), interval, 5)
    assert len(bars) == expected
    if bars:
        assert bars[0].ts == start.replace(tzinfo=None)
        assert (bars[0].open, bars[0].high, bars[0].low, bars[0].close, bars[0].volume) == (100, 102, 99, 101, 10)


def test_kite_completion_uses_each_timestamp_not_row_position():
    from app.providers.kite import completed_candles
    now = dt.datetime(2026, 9, 4, 10, 30)
    rows = [{"date": stamp, "open": 100, "high": 102, "low": 99, "close": 101}
            for stamp in (now, now - dt.timedelta(minutes=15), now + dt.timedelta(minutes=15))]
    assert [bar.ts for bar in completed_candles(rows, "15minute", now)] == [now - dt.timedelta(minutes=15)]
    assert completed_candles([], "15minute", now) == []
    with pytest.raises(ProviderReadError, match="unsupported"):
        completed_candles(rows, "week", now)
