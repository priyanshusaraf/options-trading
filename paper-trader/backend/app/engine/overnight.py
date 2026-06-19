"""
Overnight-holding rules for bought options.

For an option BUYER the overnight enemies are theta (guaranteed decay) and the
expiry cliff, not gap risk (max loss is capped at the premium). So eligibility is
gated on position size (as a fraction of capital), reinforcement confirmation,
time-to-expiry, and a hard max holding period. Pure + testable; the engine calls
`overnight_decision` at session close.
"""
from __future__ import annotations


def position_capital_pct(entry_cost: float, total_capital: float) -> float:
    return entry_cost / total_capital if total_capital > 0 else 1.0


def overnight_decision(entry_cost: float, total_capital: float, reinforcement_count: int,
                       days_to_expiry: int | None, holding_days: int | None,
                       into_weekend: bool, params: dict) -> tuple[bool, str]:
    """Return (keep_overnight, reason), evaluated at session close.

    Order of checks (most protective first):
      1. feature off                      -> square off
      2. expiry within N days             -> square off (theta cliff)
      3. held >= max_holding_days         -> square off (dead-money cap)
      4. weekend carry blocked            -> square off
      5. size > overnight_max_pct         -> square off (too big to ever carry)
      6. size <= overnight_auto_pct       -> hold (auto)
      7. mid band, reinforced enough      -> hold; else square off
    """
    if not params.get("overnight_enabled", True):
        return False, "overnight holding disabled"
    if days_to_expiry is not None and days_to_expiry < params["overnight_min_days_to_expiry"]:
        return False, f"expiry too close ({days_to_expiry}d < {params['overnight_min_days_to_expiry']}d)"
    if holding_days is not None and holding_days >= params["max_holding_days"]:
        return False, f"max holding period reached ({holding_days}d)"
    if into_weekend and params.get("block_overnight_into_weekend", False):
        return False, "weekend carry blocked"
    pct = position_capital_pct(entry_cost, total_capital)
    if pct > params["overnight_max_pct"]:
        return False, f"position too large ({pct:.0%} > {params['overnight_max_pct']:.0%} cap)"
    if pct <= params["overnight_auto_pct"]:
        return True, f"auto-hold ({pct:.0%} ≤ {params['overnight_auto_pct']:.0%})"
    if reinforcement_count >= params["overnight_min_reinforcements"]:
        return True, f"held — reinforced ×{reinforcement_count} ({pct:.0%} of capital)"
    return False, f"needs ≥{params['overnight_min_reinforcements']} reinforcement ({pct:.0%} of capital)"
