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
