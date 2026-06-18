"""
Tests for the Options Engine — Black-Scholes, IV, Greeks, PCR, Max Pain.
All tests are pure-math / offline (no network calls).
"""
import math
import pytest
import numpy as np
import pandas as pd

from backend.app.analytics.options.engine import OptionsEngine


@pytest.fixture
def engine():
    return OptionsEngine()


# ── Black-Scholes pricing ─────────────────────────────────────────────────────

class TestBlackScholes:
    def test_call_price_atm(self, engine):
        """ATM call at 30% vol, 1Y expiry should be > 0."""
        price = engine._bs_price(S=100, K=100, T=1.0, r=0.05, sigma=0.30, option_type="CE")
        assert price > 0

    def test_put_call_parity(self, engine):
        """C - P = S - K*e^(-rT) (Put-Call Parity)."""
        S, K, T, r, sigma = 100, 100, 1.0, 0.05, 0.30
        call = engine._bs_price(S, K, T, r, sigma, "CE")
        put = engine._bs_price(S, K, T, r, sigma, "PE")
        lhs = call - put
        rhs = S - K * math.exp(-r * T)
        assert abs(lhs - rhs) < 0.01, f"Put-Call parity violated: {lhs:.4f} != {rhs:.4f}"

    def test_deep_itm_call(self, engine):
        """Deep ITM call ≈ intrinsic value (S - K)."""
        price = engine._bs_price(S=200, K=100, T=0.01, r=0.05, sigma=0.20, option_type="CE")
        assert abs(price - 100) < 2.0

    def test_zero_vol_call(self, engine):
        """Zero volatility: call price = max(S - K*e^(-rT), 0)."""
        S, K, T, r = 110, 100, 1.0, 0.05
        price = engine._bs_price(S, K, T, r, sigma=1e-6, option_type="CE")
        intrinsic = S - K * math.exp(-r * T)
        assert abs(price - max(intrinsic, 0)) < 0.50

    def test_expired_option(self, engine):
        """Near-zero time to expiry → price approaches intrinsic."""
        price = engine._bs_price(S=105, K=100, T=1e-6, r=0.05, sigma=0.30, option_type="CE")
        assert abs(price - 5.0) < 1.0


# ── Implied Volatility ────────────────────────────────────────────────────────

class TestImpliedVol:
    def test_round_trip(self, engine):
        """Compute IV from a BS price; should recover original sigma."""
        S, K, T, r, sigma = 100, 100, 1.0, 0.05, 0.25
        market_price = engine._bs_price(S, K, T, r, sigma, "CE")
        recovered_iv = engine.implied_vol(market_price, S, K, T, r, "CE")
        assert recovered_iv is not None
        assert abs(recovered_iv - sigma) < 0.001, f"IV round-trip: {recovered_iv:.4f} != {sigma:.4f}"

    def test_high_vol_round_trip(self, engine):
        sigma = 0.80
        S, K, T, r = 100, 95, 0.5, 0.04
        market_price = engine._bs_price(S, K, T, r, sigma, "CE")
        recovered_iv = engine.implied_vol(market_price, S, K, T, r, "CE")
        assert recovered_iv is not None
        assert abs(recovered_iv - sigma) < 0.01

    def test_put_iv_round_trip(self, engine):
        sigma = 0.35
        S, K, T, r = 100, 105, 0.25, 0.05
        market_price = engine._bs_price(S, K, T, r, sigma, "PE")
        recovered_iv = engine.implied_vol(market_price, S, K, T, r, "PE")
        assert recovered_iv is not None
        assert abs(recovered_iv - sigma) < 0.01

    def test_negative_price_returns_none(self, engine):
        result = engine.implied_vol(-1.0, 100, 100, 1.0, 0.05, "CE")
        assert result is None

    def test_zero_time_returns_none(self, engine):
        result = engine.implied_vol(5.0, 100, 100, 0.0, 0.05, "CE")
        assert result is None


# ── Greeks ────────────────────────────────────────────────────────────────────

class TestGreeks:
    def test_call_delta_range(self, engine):
        """Call delta must be in [0, 1]."""
        greeks = engine._bs_greeks(S=100, K=100, T=1.0, r=0.05, sigma=0.25, option_type="CE")
        assert 0 <= greeks["delta"] <= 1

    def test_put_delta_range(self, engine):
        """Put delta must be in [-1, 0]."""
        greeks = engine._bs_greeks(S=100, K=100, T=1.0, r=0.05, sigma=0.25, option_type="PE")
        assert -1 <= greeks["delta"] <= 0

    def test_atm_call_delta_near_half(self, engine):
        """ATM call delta ≈ 0.5 (N(d1) for ATM options)."""
        greeks = engine._bs_greeks(S=100, K=100, T=1.0, r=0.0, sigma=0.25, option_type="CE")
        assert 0.45 <= greeks["delta"] <= 0.65

    def test_gamma_positive(self, engine):
        """Gamma must always be positive."""
        for option_type in ["CE", "PE"]:
            greeks = engine._bs_greeks(S=100, K=100, T=1.0, r=0.05, sigma=0.25, option_type=option_type)
            assert greeks["gamma"] > 0

    def test_vega_positive(self, engine):
        """Vega must always be positive."""
        for option_type in ["CE", "PE"]:
            greeks = engine._bs_greeks(S=100, K=100, T=1.0, r=0.05, sigma=0.25, option_type=option_type)
            assert greeks["vega"] > 0

    def test_call_theta_negative(self, engine):
        """Call theta (time decay) should be negative."""
        greeks = engine._bs_greeks(S=100, K=100, T=1.0, r=0.05, sigma=0.25, option_type="CE")
        assert greeks["theta"] < 0

    def test_put_call_delta_sum(self, engine):
        """Call delta + Put delta = -1 (for same strike/expiry)."""
        kwargs = dict(S=100, K=100, T=1.0, r=0.05, sigma=0.25)
        call_delta = engine._bs_greeks(**kwargs, option_type="CE")["delta"]
        put_delta = engine._bs_greeks(**kwargs, option_type="PE")["delta"]
        # d_call + |d_put| ≈ 1 (put-call symmetry)
        assert abs(call_delta + put_delta - 0) < 0.01  # C_delta - |P_delta| ≈ 0 for zero rate


# ── Max Pain ──────────────────────────────────────────────────────────────────

class TestMaxPain:
    def test_max_pain_in_strikes(self, engine):
        """Max pain should be one of the provided strikes."""
        # Simulate a simple chain
        chain_data = pd.DataFrame([
            {"strike": 90, "option_type": "CE", "open_interest": 1000},
            {"strike": 95, "option_type": "CE", "open_interest": 2000},
            {"strike": 100, "option_type": "CE", "open_interest": 5000},
            {"strike": 105, "option_type": "CE", "open_interest": 2000},
            {"strike": 90, "option_type": "PE", "open_interest": 2000},
            {"strike": 95, "option_type": "PE", "open_interest": 5000},
            {"strike": 100, "option_type": "PE", "open_interest": 3000},
            {"strike": 105, "option_type": "PE", "open_interest": 1000},
        ])
        max_pain = engine.max_pain(chain_data)
        assert max_pain in [90, 95, 100, 105]

    def test_max_pain_empty_chain(self, engine):
        """Empty chain should return None or 0."""
        result = engine.max_pain(pd.DataFrame())
        assert result is None or result == 0
