"""The admitted backtest engine keeps completed-bar decisions off the signal bar."""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from app.backtest import engine
from app.core.instruments import get_instrument
from app.core.market_hours import ist_epoch


def _signal_frame() -> pd.DataFrame:
    return pd.DataFrame({
        "date": [dt.datetime(2025, 1, 2, 9, 15), dt.datetime(2025, 1, 2, 9, 20)],
        "open": [100.0, 101.0], "high": [101.0, 102.0],
        "low": [99.0, 100.0], "close": [100.5, 101.5],
        "longEntry": [True, False], "shortEntry": [False, False],
        "longExit": [False, False], "shortExit": [False, False],
    })


def _assert_next_bar_entry() -> None:
    frame = _signal_frame()
    trades = engine.run_trades(
        frame, get_instrument("NIFTY"), "NFO", 50_000.0, rm=None,
        event_risk=False, slippage_pct=0.0,
    )
    assert trades[0].entry_time == ist_epoch(frame.loc[1, "date"])


def test_signal_on_t_cannot_fill_on_t():
    """Hypothesis: a completed-bar entry decision fills at that bar's close/open."""
    _assert_next_bar_entry()


def test_same_bar_mutant_is_killed(monkeypatch):
    """Changing the production fill index to the signal index breaks the real guard."""
    monkeypatch.setattr(engine.replay_decisions, "next_fill_index", lambda signal_index: signal_index)
    with pytest.raises(IndexError):
        _assert_next_bar_entry()
