"""Strategies may declare a trade-management risk model for the backtester's
ratchet overlay. v4 declares its Pine defaults; the default strategy and the
base class declare nothing (flags-only exits)."""
from app.strategy.registry import get_strategy
from app.strategy.registry.base import Strategy


def test_base_class_declares_no_risk_model():
    assert Strategy.risk_model is None


def test_default_strategy_declares_no_risk_model():
    assert get_strategy(None).risk_model is None


def test_v4_declares_pine_default_risk_model():
    assert get_strategy("expanding_z_v4").risk_model == {
        "atr_length": 14, "initial_risk_atr": 1.25,
        "trail_start_r": 1.75, "trail_atr": 3.0,
        "use_mfe_capture_floor": True,
        "capture_start_r": 1.25, "capture_pct": 0.35,
    }
