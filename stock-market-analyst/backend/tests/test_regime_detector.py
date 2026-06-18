"""Tests for the Regime Detector."""
import numpy as np
import pandas as pd
import pytest

from backend.app.intelligence.regime.detector import RegimeDetector, Regime


def _make_df(n=400, trend=0.0003, vol=0.015, seed=42):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2022-01-01", periods=n, freq="B")
    close = 100 * np.exp(np.cumsum(rng.normal(trend, vol, n)))
    return pd.DataFrame({"close": close}, index=dates)


@pytest.fixture
def detector():
    return RegimeDetector()


class TestRegimeDetector:
    def test_bull_trend_detection(self, detector):
        df = _make_df(trend=0.001, vol=0.008, n=400)
        r = detector.detect(df)
        assert r.regime == Regime.BULL_TREND

    def test_bear_trend_detection(self, detector):
        df = _make_df(trend=-0.002, vol=0.012, n=400)
        r = detector.detect(df)
        assert r.regime in (Regime.BEAR_TREND, Regime.HIGH_VOL)

    def test_high_vol_detection(self, detector):
        df = _make_df(trend=-0.001, vol=0.04, n=300)
        r = detector.detect(df)
        assert r.vol_regime in ("high", "extreme")

    def test_confidence_in_range(self, detector):
        df = _make_df()
        r = detector.detect(df)
        assert 0 <= r.confidence <= 1

    def test_insufficient_data_returns_unknown(self, detector):
        df = _make_df(n=30)
        r = detector.detect(df)
        assert r.regime == Regime.UNKNOWN

    def test_realized_vol_positive(self, detector):
        df = _make_df()
        r = detector.detect(df)
        assert r.realized_vol_30d > 0
        assert r.realized_vol_90d > 0

    def test_multipliers_exist(self, detector):
        df = _make_df()
        r = detector.detect(df)
        assert r.momentum_weight_adj > 0
        assert r.vol_risk_discount > 0
