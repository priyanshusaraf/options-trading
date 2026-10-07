"""vwap_band_reversion: canonical contract, no look-ahead (prefix == full for the
same rows), determinism, and that the layers actually produce trades on a
mean-reverting synthetic market."""
import numpy as np
import pandas as pd
import pytest

from app.strategy.registry import get_strategy
from app.strategy.registry.base import CANONICAL_COLUMNS
from app.strategy.registry.vwap_band_reversion import STRATEGY, VwapBandReversion

FLAGS = CANONICAL_COLUMNS + ("longAdd", "shortAdd")


def _mcx_like(days: int = 30, seed: int = 7, with_volume: bool = True) -> pd.DataFrame:
    """15m bars 09:00-23:15 IST on weekdays; an OU (mean-reverting) price with
    occasional impulsive excursions so band fades fire."""
    rng = np.random.default_rng(seed)
    stamps = []
    for d in pd.bdate_range("2024-03-04", periods=days):
        stamps += list(pd.date_range(d + pd.Timedelta(hours=9), d + pd.Timedelta(hours=23, minutes=15),
                                     freq="15min"))
    n = len(stamps)
    x = np.zeros(n)
    for i in range(1, n):
        shock = rng.normal(0, 0.6)
        if rng.random() < 0.01:                      # impulsive push
            shock += rng.choice([-1, 1]) * 6.0
        x[i] = x[i - 1] * 0.985 + shock
    close = 300.0 + x
    open_ = np.r_[close[0], close[:-1]] + rng.normal(0, 0.1, n)
    high = np.maximum(open_, close) + np.abs(rng.normal(0, 0.3, n))
    low = np.minimum(open_, close) - np.abs(rng.normal(0, 0.3, n))
    df = pd.DataFrame({"date": stamps, "open": open_, "high": high, "low": low, "close": close})
    if with_volume:
        df["volume"] = rng.uniform(50, 150, n)
    return df


SESSION = dict(anchor="session", band_k=2.0, min_push_er=0.0, add_k=0.0)
SHORT_ROLLING = dict(anchor_days=3.0, band_k=2.0, min_push_er=0.3, add_k=3.0, max_hold=40,
                     max_drift=1.0, stop_k=6.0)


def test_registered_with_metadata():
    s = get_strategy("vwap_band_reversion")
    assert s is STRATEGY and isinstance(s, VwapBandReversion)
    assert s.display_name == "VWAP Band Reversion (chop)"
    assert s.session_flat is False and s.pyramiding == {"max_adds": 1}
    assert s.warmup_columns == ("atr",)


@pytest.mark.parametrize("params", [{}, SESSION, SHORT_ROLLING])
def test_canonical_columns_are_boolean(params):
    out = STRATEGY.signals(_mcx_like(), **params)
    for col in FLAGS:
        assert col in out.columns, col
        assert out[col].dtype == bool, col
    for col in ("vwap", "vwapSd", "z", "upperBand", "lowerBand", "atr"):
        assert col in out.columns


def test_layers_fire_on_mean_reverting_market():
    df = _mcx_like(days=40)
    for params in (SESSION, SHORT_ROLLING):
        out = STRATEGY.signals(df, **params)
        assert out["longEntry"].sum() > 0 and out["shortEntry"].sum() > 0, params
        # never long and short on the same bar
        assert not (out["longEntry"] & out["shortEntry"]).any()


@pytest.mark.parametrize("params", [{}, SESSION, SHORT_ROLLING])
def test_no_lookahead_prefix_equals_full(params):
    df = _mcx_like(days=30)
    full = STRATEGY.signals(df, **params)
    for cut in (300, 777, 1200, len(df) - 1):
        part = STRATEGY.signals(df.iloc[:cut].copy(), **params)
        for col in FLAGS:
            assert (part[col].to_numpy() == full[col].iloc[:cut].to_numpy()).all(), (cut, col)
        pd.testing.assert_series_equal(part["z"], full["z"].iloc[:cut], check_names=False)


def test_deterministic():
    df = _mcx_like()
    a = STRATEGY.signals(df, **SHORT_ROLLING)
    b = STRATEGY.signals(df.copy(), **SHORT_ROLLING)
    pd.testing.assert_frame_equal(a, b)


def test_works_without_volume_column():
    out = STRATEGY.signals(_mcx_like(with_volume=False), **SHORT_ROLLING)
    for col in CANONICAL_COLUMNS:
        assert out[col].dtype == bool


def test_entries_only_beyond_band_and_exit_at_anchor():
    out = STRATEGY.signals(_mcx_like(days=40), **SESSION)
    assert (out.loc[out["longEntry"], "z"] <= -2.0).all()
    assert (out.loc[out["shortEntry"], "z"] >= 2.0).all()
    # target exit = back to the VWAP
    assert (out.loc[out["longExit"], "z"].dropna() >= 0).all()
    assert (out.loc[out["shortExit"], "z"].dropna() <= 0).all()
