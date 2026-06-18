"""
Position Sizing Engine.

Implements three complementary sizing strategies:

1. **Fractional Kelly Criterion**
   pos = (edge / odds) * kelly_fraction
   Where edge = expected return, odds = win/loss ratio from signal confidence.
   Uses half-Kelly (conservative) by default.

2. **Volatility Parity**
   Each position's size is inversely proportional to its volatility,
   so all positions contribute equal risk to the portfolio.

3. **Correlation-Adjusted (Maximum Diversification)**
   Penalizes positions that are highly correlated to existing holdings,
   preventing hidden concentration risk.

Final output: suggested weight per position (% of total portfolio),
subject to:
  - Max single position: configurable (default 10%)
  - Min position: configurable (default 0.5%)
  - Max sector concentration: configurable (default 35%)
  - Max portfolio gross leverage: 100% (no leverage by default)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from backend.app.core.logging import logger


# ── Configuration ─────────────────────────────────────────────────────────────

@dataclass
class SizingConfig:
    kelly_fraction: float = 0.5          # Half-Kelly (more conservative)
    max_position_pct: float = 10.0       # Max single position %
    min_position_pct: float = 0.5        # Minimum meaningful allocation
    max_sector_pct: float = 35.0         # Max sector concentration %
    target_portfolio_vol: float = 0.15   # Target annual portfolio vol (15%)
    correlation_penalty: float = 0.5     # 0=ignore corr, 1=full penalty
    method: str = "combined"             # "kelly" / "vol_parity" / "combined"


@dataclass
class PositionSuggestion:
    symbol: str
    raw_kelly_pct: float
    vol_parity_pct: float
    final_pct: float                     # After all constraints
    score: float
    confidence: float
    annual_vol: float
    reason: str
    capped: bool = False                 # True if hit max position limit


@dataclass
class AllocationResult:
    suggestions: list[PositionSuggestion]
    total_allocated_pct: float
    cash_pct: float
    expected_portfolio_vol: float
    diversification_ratio: float          # > 1 = well diversified
    sector_breakdown: dict[str, float]
    warnings: list[str] = field(default_factory=list)


# ── Engine ─────────────────────────────────────────────────────────────────────

class PositionSizer:
    """
    Given a list of scored opportunities, compute optimal position sizes.
    """

    def __init__(self, config: Optional[SizingConfig] = None):
        self.cfg = config or SizingConfig()

    def allocate(
        self,
        opportunities: list[dict],       # [{symbol, score, confidence, annual_vol, sector}]
        existing_weights: Optional[dict[str, float]] = None,  # symbol → current_pct
        returns_matrix: Optional[pd.DataFrame] = None,         # for correlation adjustment
    ) -> AllocationResult:
        """
        Main entry point.

        opportunities: list of dicts with keys:
          - symbol (str)
          - score (float, –1 to +1)
          - confidence (float, 0 to 1)
          - annual_vol (float, e.g. 0.25 for 25%)
          - sector (str, optional)

        returns: AllocationResult with per-position suggested weights.
        """
        # Only size positions with positive score
        candidates = [o for o in opportunities if o.get("score", 0) > 0.05]
        if not candidates:
            return AllocationResult(
                suggestions=[], total_allocated_pct=0.0, cash_pct=100.0,
                expected_portfolio_vol=0.0, diversification_ratio=1.0,
                sector_breakdown={},
            )

        suggestions = []
        warnings = []

        # ── Step 1: Raw Kelly weights ──────────────────────────────────────────
        kelly_weights = self._kelly_weights(candidates)

        # ── Step 2: Vol parity weights ─────────────────────────────────────────
        vol_parity_weights = self._vol_parity_weights(candidates)

        # ── Step 3: Combine methods ────────────────────────────────────────────
        if self.cfg.method == "kelly":
            raw_weights = kelly_weights
        elif self.cfg.method == "vol_parity":
            raw_weights = vol_parity_weights
        else:
            # Weighted blend: 40% Kelly signal, 60% vol parity
            raw_weights = {
                sym: 0.40 * kelly_weights.get(sym, 0) + 0.60 * vol_parity_weights.get(sym, 0)
                for sym in kelly_weights
            }

        # ── Step 4: Correlation penalty ───────────────────────────────────────
        if returns_matrix is not None and self.cfg.correlation_penalty > 0:
            raw_weights = self._apply_correlation_penalty(
                raw_weights, candidates, returns_matrix
            )

        # ── Step 5: Apply sector constraints ──────────────────────────────────
        raw_weights, sector_warnings = self._apply_sector_cap(raw_weights, candidates)
        warnings.extend(sector_warnings)

        # ── Step 6: Normalize and apply position limits ────────────────────────
        final_weights, cap_warnings = self._normalize_and_cap(raw_weights)
        warnings.extend(cap_warnings)

        # ── Step 7: Build output ───────────────────────────────────────────────
        for opp in candidates:
            sym = opp["symbol"]
            vol = opp.get("annual_vol", 0.20)
            final_pct = final_weights.get(sym, 0.0)
            suggestions.append(PositionSuggestion(
                symbol=sym,
                raw_kelly_pct=round(kelly_weights.get(sym, 0) * 100, 2),
                vol_parity_pct=round(vol_parity_weights.get(sym, 0) * 100, 2),
                final_pct=round(final_pct * 100, 2),
                score=opp.get("score", 0),
                confidence=opp.get("confidence", 0),
                annual_vol=vol,
                reason=self._sizing_reason(opp, final_pct),
                capped=final_pct * 100 >= self.cfg.max_position_pct - 0.01,
            ))

        suggestions.sort(key=lambda s: s.final_pct, reverse=True)

        total = sum(s.final_pct for s in suggestions)
        exp_vol = self._expected_portfolio_vol(suggestions, returns_matrix)
        dr = self._diversification_ratio(suggestions, returns_matrix)

        sector_breakdown = {}
        for s in suggestions:
            sec = next((o.get("sector", "Unknown") for o in candidates if o["symbol"] == s.symbol), "Unknown")
            sector_breakdown[sec] = sector_breakdown.get(sec, 0) + s.final_pct

        return AllocationResult(
            suggestions=suggestions,
            total_allocated_pct=round(total, 2),
            cash_pct=round(max(0.0, 100.0 - total), 2),
            expected_portfolio_vol=round(exp_vol, 4),
            diversification_ratio=round(dr, 3),
            sector_breakdown={k: round(v, 2) for k, v in sorted(sector_breakdown.items(), key=lambda x: -x[1])},
            warnings=warnings,
        )

    # ── Sizing methods ────────────────────────────────────────────────────────

    def _kelly_weights(self, candidates: list[dict]) -> dict[str, float]:
        """
        Compute Kelly fraction for each position.

        Kelly formula: f* = (p * b - q) / b
          p = probability of win = (1 + confidence) / 2  (maps 0→0.5, 1→1.0)
          b = odds = expected_gain / expected_loss ≈ (1 + score) / (1 - score) approximately
          q = 1 - p

        Apply fractional Kelly (half-Kelly by default) for robustness.
        """
        weights = {}
        for opp in candidates:
            score = float(opp.get("score", 0))
            conf = float(opp.get("confidence", 0.5))
            vol = float(opp.get("annual_vol", 0.20))

            if score <= 0:
                continue

            # Map score to win probability: score=0.1→p=0.55, score=0.8→p=0.9
            p_win = 0.5 + score * 0.5 * conf
            p_loss = 1.0 - p_win

            # Odds ratio based on volatility (expected range)
            b = (1.0 + vol) / vol if vol > 0 else 2.0

            kelly = (p_win * b - p_loss) / b
            kelly = max(0.0, kelly) * self.cfg.kelly_fraction

            weights[opp["symbol"]] = kelly

        return weights

    def _vol_parity_weights(self, candidates: list[dict]) -> dict[str, float]:
        """
        Each position gets a weight inversely proportional to its volatility.
        Target: all positions contribute equal risk.
        """
        vols = {
            opp["symbol"]: max(float(opp.get("annual_vol", 0.20)), 0.05)
            for opp in candidates
            if opp.get("score", 0) > 0
        }
        if not vols:
            return {}

        inv_vol = {sym: 1.0 / vol for sym, vol in vols.items()}
        total_inv_vol = sum(inv_vol.values())

        # Scale so total portfolio vol ≈ target
        raw = {sym: iv / total_inv_vol for sym, iv in inv_vol.items()}

        # Scale by conviction (score × confidence)
        conviction = {
            opp["symbol"]: max(0.0, opp.get("score", 0) * opp.get("confidence", 0.5))
            for opp in candidates
        }
        total_conviction = sum(conviction.values()) or 1.0

        adjusted = {}
        for sym in raw:
            vol_weight = raw[sym]
            conv_weight = conviction.get(sym, 0) / total_conviction
            # 60% vol parity, 40% conviction tilt
            adjusted[sym] = 0.60 * vol_weight + 0.40 * conv_weight

        return adjusted

    def _apply_correlation_penalty(
        self,
        weights: dict[str, float],
        candidates: list[dict],
        returns: pd.DataFrame,
    ) -> dict[str, float]:
        """
        Reduce weights of highly correlated pairs.
        For each symbol, compute average pairwise correlation with all others
        and scale weight down by (1 - penalty * avg_correlation).
        """
        syms = [c["symbol"] for c in candidates if c["symbol"] in weights]
        common = [s for s in syms if s in returns.columns]
        if len(common) < 2:
            return weights

        corr_matrix = returns[common].pct_change().dropna().corr()
        adjusted = dict(weights)

        for sym in common:
            others = [s for s in common if s != sym]
            if not others:
                continue
            avg_corr = float(corr_matrix.loc[sym, others].clip(-1, 1).mean())
            # Penalty: 0 if uncorrelated, reduces weight if highly correlated
            penalty_factor = 1.0 - self.cfg.correlation_penalty * max(0.0, avg_corr)
            adjusted[sym] = weights.get(sym, 0) * penalty_factor

        return adjusted

    def _apply_sector_cap(
        self, weights: dict[str, float], candidates: list[dict]
    ) -> tuple[dict[str, float], list[str]]:
        """Cap any single sector to max_sector_pct of portfolio."""
        sector_map = {opp["symbol"]: opp.get("sector", "Unknown") for opp in candidates}
        sector_total: dict[str, float] = {}

        for sym, w in weights.items():
            sec = sector_map.get(sym, "Unknown")
            sector_total[sec] = sector_total.get(sec, 0) + w

        warnings = []
        adjusted = dict(weights)
        max_frac = self.cfg.max_sector_pct / 100.0

        for sector, total in sector_total.items():
            if total > max_frac:
                scale = max_frac / total
                for sym, w in adjusted.items():
                    if sector_map.get(sym) == sector:
                        adjusted[sym] = w * scale
                warnings.append(
                    f"Sector '{sector}' capped at {self.cfg.max_sector_pct}% "
                    f"(was {total * 100:.1f}%)."
                )

        return adjusted, warnings

    def _normalize_and_cap(
        self, weights: dict[str, float]
    ) -> tuple[dict[str, float], list[str]]:
        """
        Normalize weights to sum ≤ 100%, apply min/max position limits.
        """
        if not weights:
            return {}, []

        warnings = []
        max_frac = self.cfg.max_position_pct / 100.0
        min_frac = self.cfg.min_position_pct / 100.0

        # Normalize to sum = 1.0 first
        total = sum(weights.values()) or 1.0
        norm = {sym: w / total for sym, w in weights.items()}

        # Apply max cap iteratively (excess redistributed to cash, not other positions)
        capped = {}
        for sym, w in norm.items():
            if w > max_frac:
                warnings.append(f"{sym} capped at {self.cfg.max_position_pct}% (raw: {w * 100:.1f}%)")
                capped[sym] = max_frac
            elif w < min_frac:
                capped[sym] = 0.0  # Too small to be meaningful — skip
            else:
                capped[sym] = w

        return capped, warnings

    # ── Risk analytics ────────────────────────────────────────────────────────

    def _expected_portfolio_vol(
        self,
        suggestions: list[PositionSuggestion],
        returns: Optional[pd.DataFrame],
    ) -> float:
        """Estimate portfolio volatility using pairwise covariance."""
        if not suggestions:
            return 0.0

        weights = np.array([s.final_pct / 100.0 for s in suggestions])
        vols = np.array([s.annual_vol for s in suggestions])

        if returns is not None:
            syms = [s.symbol for s in suggestions if s.symbol in returns.columns]
            common_weights = np.array([s.final_pct / 100.0 for s in suggestions if s.symbol in syms])
            if len(syms) >= 2:
                cov = returns[syms].pct_change().dropna().cov() * 252
                port_var = common_weights @ cov.values @ common_weights
                return float(math.sqrt(max(port_var, 0)))

        # Fallback: assume zero correlation
        port_var = float(np.sum((weights * vols) ** 2))
        return math.sqrt(port_var)

    def _diversification_ratio(
        self,
        suggestions: list[PositionSuggestion],
        returns: Optional[pd.DataFrame],
    ) -> float:
        """
        DR = weighted average of individual vols / portfolio vol.
        DR > 1 = diversification benefit, DR = 1 = no benefit.
        """
        if not suggestions:
            return 1.0
        weights = np.array([s.final_pct / 100.0 for s in suggestions])
        vols = np.array([s.annual_vol for s in suggestions])
        weighted_avg_vol = float(np.dot(weights, vols))
        port_vol = self._expected_portfolio_vol(suggestions, returns)
        if port_vol == 0:
            return 1.0
        return weighted_avg_vol / port_vol

    @staticmethod
    def _sizing_reason(opp: dict, final_frac: float) -> str:
        score = opp.get("score", 0)
        conf = opp.get("confidence", 0)
        vol = opp.get("annual_vol", 0.20)
        return (
            f"Score {score:.2f} × confidence {conf:.0%} → "
            f"{final_frac * 100:.1f}% allocation "
            f"(vol-adjusted for {vol * 100:.0f}% annual vol)"
        )
