"""
When to close an open option position. Owner's rule: exit on a premium stop-loss
OR target OR the strategy's own exit flag — whichever comes first. Premium guards
are evaluated before the strategy flag so a protective stop/target wins any tie.
"""
from __future__ import annotations


def evaluate_exit(direction: str, stop_price: float, target_price: float,
                  current_premium: float, long_exit: bool, short_exit: bool
                  ) -> tuple[bool, str | None]:
    # protective premium guards first
    if current_premium <= stop_price:
        return True, "STOP_LOSS"
    if current_premium >= target_price:
        return True, "TARGET"
    # then the strategy's own exit on the underlying
    if direction == "LONG" and long_exit:
        return True, "STRATEGY_EXIT"
    if direction == "SHORT" and short_exit:
        return True, "STRATEGY_EXIT"
    return False, None


def trailing_stop(entry: float, high_water: float, current_stop: float,
                  *, trigger_pct: float, lock_pct: float, target_pct: float) -> float:
    """Ratchet the premium stop UP as profit thresholds are crossed; never down.

    Each time the high-water premium clears another `trigger_pct` of profit (as a
    fraction of entry), the stop is raised by `lock_pct` of entry, until the
    `target_pct` final target. Returns the new stop (>= current_stop).

    Owner's example — entry 400, trigger 10%, lock 2.5%, target 60%:
        high-water 440 (+10%) -> 1 step -> stop 410
        high-water 480 (+20%) -> 2 steps -> stop 420
        ...
        high-water 640 (+60%) -> 6 steps -> stop 460  (capped at target)
    """
    if entry <= 0 or high_water <= entry or trigger_pct <= 0:
        return current_stop
    profit_frac = min((high_water - entry) / entry, target_pct)
    steps = int(profit_frac / trigger_pct + 1e-9)
    if steps <= 0:
        return current_stop
    ratchet = entry * (1 + steps * lock_pct)
    return max(current_stop, round(ratchet, 2))
