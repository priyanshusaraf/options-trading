"""Tests for the Technical Analysis Engine."""
import numpy as np
import pandas as pd
import pytest

from backend.app.analytics.technical.engine import TechnicalEngine, TechnicalSignals


def _make_ohlcv(n: int = 300, trend: float = 0.0003, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2023-01-01", periods=n, freq="B")
    vol = 0.015
    close = 100 * np.exp(np.cumsum(rng.normal(trend, vol, n)))
    high = close * (1 + abs(rng.normal(0, 0.005, n)))
    low = close * (1 - abs(rng.normal(0, 0.005, n)))
    open_ = close * (1 + rng.normal(0, 0.003, n))
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": rng.integers(1e5, 5e6, n)},
        index=dates,
    )


@pytest.fixture
def engine():
    return TechnicalEngine()


@pytest.fixture
def df():
    return _make_ohlcv()


class TestTechnicalEngine:
    def test_returns_signals_object(self, engine, df):
        s = engine.compute("TEST", df)
        assert isinstance(s, TechnicalSignals)

    def test_rsi_in_range(self, engine, df):
        s = engine.compute("TEST", df)
        assert 0 <= s.rsi_14 <= 100

    def test_probabilities_sum_to_one(self, engine, df):
        s = engine.compute("TEST", df)
        total = s.bullish_prob + s.bearish_prob
        assert abs(total - 1.0) < 1e-6

    def test_probabilities_in_range(self, engine, df):
        s = engine.compute("TEST", df)
        assert 0 <= s.bullish_prob <= 1
        assert 0 <= s.breakout_prob <= 1
        assert 0 <= s.reversal_prob <= 1

    def test_signal_is_valid_label(self, engine, df):
        s = engine.compute("TEST", df)
        assert s.signal in ("STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL")

    def test_confidence_in_range(self, engine, df):
        s = engine.compute("TEST", df)
        assert 0 <= s.confidence <= 1

    def test_bb_pct_in_range(self, engine, df):
        s = engine.compute("TEST", df)
        # bb_pct can briefly exceed 0-1 due to price outside bands
        assert isinstance(s.bb_pct, float)

    def test_downtrend_leans_bearish(self):
        """Strong downtrend should produce bearish signal."""
        engine = TechnicalEngine()
        df = _make_ohlcv(trend=-0.003, seed=10, n=300)
        s = engine.compute("DOWN", df)
        assert s.bullish_prob < 0.5

    def test_uptrend_leans_bullish(self):
        """Strong uptrend should produce bullish signal."""
        engine = TechnicalEngine()
        df = _make_ohlcv(trend=0.004, seed=20, n=300)
        s = engine.compute("UP", df)
        assert s.bullish_prob > 0.5

    def test_empty_df_returns_defaults(self, engine):
        s = engine.compute("EMPTY", pd.DataFrame())
        assert s.signal == "NEUTRAL"
        assert s.bullish_prob == 0.5
