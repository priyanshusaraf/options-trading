"""
Tests for the Position Sizing Engine.
Pure math, no network / DB access.
"""
import pytest
import numpy as np
import pandas as pd

from backend.app.decision.position_sizer import PositionSizer, SizingConfig


def make_opportunities(n=5, base_score=0.4, base_vol=0.25, base_conf=0.7):
    return [
        {
            "symbol": f"STOCK{i}",
            "score": base_score + i * 0.05,
            "confidence": base_conf,
            "annual_vol": base_vol,
            "sector": f"Sector{i % 3}",
        }
        for i in range(n)
    ]


def make_returns(symbols: list[str], periods=252) -> pd.DataFrame:
    np.random.seed(42)
    data = np.random.normal(0.0, 0.01, (periods, len(symbols)))
    return pd.DataFrame(data, columns=symbols)


@pytest.fixture
def sizer():
    return PositionSizer()


class TestKellyWeights:
    def test_positive_scores_get_positive_weights(self, sizer):
        opps = make_opportunities(3)
        weights = sizer._kelly_weights(opps)
        for sym, w in weights.items():
            assert w >= 0, f"{sym} has negative Kelly weight: {w}"

    def test_zero_score_excluded(self, sizer):
        opps = [{"symbol": "A", "score": 0.0, "confidence": 0.7, "annual_vol": 0.25, "sector": "X"}]
        weights = sizer._kelly_weights(opps)
        assert "A" not in weights or weights.get("A", 0) == 0

    def test_higher_score_gets_higher_weight(self, sizer):
        opps = [
            {"symbol": "LOW", "score": 0.2, "confidence": 0.6, "annual_vol": 0.25, "sector": "X"},
            {"symbol": "HIGH", "score": 0.8, "confidence": 0.6, "annual_vol": 0.25, "sector": "X"},
        ]
        weights = sizer._kelly_weights(opps)
        assert weights.get("HIGH", 0) >= weights.get("LOW", 0)


class TestVolParityWeights:
    def test_low_vol_gets_more_weight(self, sizer):
        opps = [
            {"symbol": "LOWVOL", "score": 0.5, "confidence": 0.7, "annual_vol": 0.10, "sector": "X"},
            {"symbol": "HIGHVOL", "score": 0.5, "confidence": 0.7, "annual_vol": 0.50, "sector": "X"},
        ]
        weights = sizer._vol_parity_weights(opps)
        assert weights.get("LOWVOL", 0) > weights.get("HIGHVOL", 0)

    def test_weights_sum_to_one(self, sizer):
        opps = make_opportunities(4)
        weights = sizer._vol_parity_weights(opps)
        total = sum(weights.values())
        assert abs(total - 1.0) < 0.01, f"Weights don't sum to 1: {total}"


class TestNormalizeAndCap:
    def test_max_position_cap(self, sizer):
        raw = {"A": 0.3, "B": 0.3, "C": 0.3, "D": 0.1}
        cfg = SizingConfig(max_position_pct=10.0)
        capped_sizer = PositionSizer(cfg)
        capped, _ = capped_sizer._normalize_and_cap(raw)
        for sym, w in capped.items():
            assert w <= 0.101, f"{sym} exceeds max: {w * 100:.1f}%"

    def test_min_position_exclusion(self, sizer):
        raw = {"BIG": 0.8, "TINY": 0.001}
        cfg = SizingConfig(min_position_pct=0.5)
        capped_sizer = PositionSizer(cfg)
        final, _ = capped_sizer._normalize_and_cap(raw)
        assert final.get("TINY", 0) == 0.0, "Tiny position should be excluded"

    def test_empty_weights(self, sizer):
        final, warnings = sizer._normalize_and_cap({})
        assert final == {}


class TestSectorCap:
    def test_sector_cap_applied(self, sizer):
        cfg = SizingConfig(max_sector_pct=30.0)
        s = PositionSizer(cfg)
        opps = [
            {"symbol": f"TECH{i}", "score": 0.5, "confidence": 0.7, "annual_vol": 0.3, "sector": "Tech"}
            for i in range(5)
        ]
        weights = {f"TECH{i}": 0.2 for i in range(5)}  # 100% in Tech
        adjusted, warnings = s._apply_sector_cap(weights, opps)
        tech_total = sum(adjusted.values())
        assert tech_total <= 0.31, f"Sector cap violated: {tech_total * 100:.1f}%"
        assert len(warnings) > 0


class TestAllocateIntegration:
    def test_produces_output(self, sizer):
        opps = make_opportunities(5)
        result = sizer.allocate(opps)
        assert result is not None
        assert len(result.suggestions) == 5
        assert result.total_allocated_pct > 0
        assert result.cash_pct >= 0

    def test_no_negative_positions(self, sizer):
        opps = make_opportunities(5)
        result = sizer.allocate(opps)
        for s in result.suggestions:
            assert s.final_pct >= 0

    def test_total_leq_100(self, sizer):
        opps = make_opportunities(10)
        result = sizer.allocate(opps)
        assert result.total_allocated_pct <= 100.01

    def test_empty_opportunities(self, sizer):
        result = sizer.allocate([])
        assert result.total_allocated_pct == 0
        assert result.cash_pct == 100.0

    def test_with_correlation(self, sizer):
        opps = make_opportunities(4)
        syms = [o["symbol"] for o in opps]
        returns = make_returns(syms)
        result = sizer.allocate(opps, returns_matrix=returns)
        assert result is not None

    def test_diversification_ratio_gte_1(self, sizer):
        opps = make_opportunities(5)
        result = sizer.allocate(opps)
        assert result.diversification_ratio >= 1.0

    def test_kelly_method(self):
        s = PositionSizer(SizingConfig(method="kelly"))
        opps = make_opportunities(3)
        result = s.allocate(opps)
        assert len(result.suggestions) == 3

    def test_vol_parity_method(self):
        s = PositionSizer(SizingConfig(method="vol_parity"))
        opps = make_opportunities(3)
        result = s.allocate(opps)
        assert len(result.suggestions) == 3

    def test_sector_breakdown_present(self, sizer):
        opps = make_opportunities(6)
        result = sizer.allocate(opps)
        assert isinstance(result.sector_breakdown, dict)
        assert len(result.sector_breakdown) > 0

    def test_negative_scores_excluded(self, sizer):
        opps = [
            {"symbol": "POS", "score": 0.5, "confidence": 0.7, "annual_vol": 0.25, "sector": "X"},
            {"symbol": "NEG", "score": -0.4, "confidence": 0.7, "annual_vol": 0.25, "sector": "X"},
            {"symbol": "ZERO", "score": 0.02, "confidence": 0.7, "annual_vol": 0.25, "sector": "X"},
        ]
        result = sizer.allocate(opps)
        syms_allocated = [s.symbol for s in result.suggestions]
        assert "NEG" not in syms_allocated
