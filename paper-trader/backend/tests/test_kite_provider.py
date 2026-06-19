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
