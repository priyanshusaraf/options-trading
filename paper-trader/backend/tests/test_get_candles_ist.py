"""get_candles must anchor its historical-data window on IST wall-clock
(self.now()), not naive server-local time (dt.datetime.now()).

On a UTC-hosted deployment, dt.datetime.now() lands ~5.5h behind IST, so the
'to' bound of the Kite historical_data window would silently exclude the most
recent candles (or worse, straddle the session boundary incorrectly). The
provider already exposes self.now() -> IST wall-clock, naive (see
KiteProvider.now()) for exactly this reason, but get_candles never adopted it.
"""
from __future__ import annotations

import datetime as dt

from app.core.instruments import Instrument
from app.providers.kite import KiteProvider

_SENTINEL_NOW = dt.datetime(2026, 7, 9, 14, 30, 0)  # fixed IST wall-clock, naive


def _provider():
    p = KiteProvider.__new__(KiteProvider)
    p._underlying_token = lambda inst: 12345
    p.now = lambda: _SENTINEL_NOW
    return p


def test_get_candles_uses_self_now_not_wall_clock():
    captured = {}

    def _fake_historical(token, frm, to, interval):
        captured["token"] = token
        captured["frm"] = frm
        captured["to"] = to
        captured["interval"] = interval
        return []

    p = _provider()
    p._historical = _fake_historical

    inst = Instrument(
        "NIFTY", "NIFTY 50", "NSE", "NSE", "NIFTY 50", "NIFTY",
        lot_size=50, strike_step=50, priority=1, mock_spot=22000, mock_vol=0.15,
    )

    p.get_candles(inst, "15minute", 5)

    assert captured["to"] == _SENTINEL_NOW
    assert captured["frm"] == _SENTINEL_NOW - dt.timedelta(days=5)
