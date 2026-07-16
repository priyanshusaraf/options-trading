"""Kite instrument dump normalization.

Kite's MCX dump reports lot_size=1 for commodity option rows even though the
premium must be costed against the contract unit configured in our universe.
It also names copper contracts as COPPER, not COPPERM.
"""
from __future__ import annotations

import datetime as dt

from app.core.instruments import Instrument
from app.providers.kite import KiteProvider


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
                "buy": [{"price": 364.0}],
                "sell": [{"price": 366.0}],
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
